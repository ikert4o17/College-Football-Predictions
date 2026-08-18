"""
Project Gridiron
CFBD Request Dry-Run Planner

Purpose
-------
Estimate CFBD API usage BEFORE running a workflow.

The planner determines:

    - which requests are cache hits
    - which cache entries are expired
    - which requests are missing from cache
    - which requests would consume real CFBD calls
    - estimated total real calls
    - whether the estimate fits the per-run request budget
    - whether the estimate would violate the protected monthly reserve

IMPORTANT:
This script does NOT call football-data endpoints.

It may call:
    GET /info

to inspect current account usage.

Usage:
    python -m data.plan_cfbd_requests weekly
    python -m data.plan_cfbd_requests cache-build

Optional:
    python -m data.plan_cfbd_requests weekly --offline

In --offline mode, the planner skips /info and evaluates only cache
status + per-run budget.

Environment variables:

    CFBD_API_KEY
        Required unless --offline is used.

    CFBD_MAX_CALLS_THIS_RUN
        Per-run request limit.

    CFBD_MIN_REMAINING_CALLS
        Protected monthly reserve.
        Default: 100

    FORCE_CFBD_REFRESH=1
        Planner treats all cacheable requests as real calls.

This script uses the same cache-key and freshness logic as
data/cfbd_api.py and data/cfbd_cache_policy.py.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

from data.cfbd_cache_policy import (
    cache_policy,
    cache_ttl_seconds,
)


# ============================================================
# PATHS / CONSTANTS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

CACHE_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "cfbd"
)

BASE_URL = (
    "https://api.collegefootballdata.com"
)

INFO_ENDPOINT = "/info"

DEFAULT_MONTHLY_RESERVE = 100

DEFAULT_WEEKLY_BUDGET = 20

DEFAULT_CACHE_BUILD_BUDGET = 75


# ============================================================
# PLANNED REQUEST SETS
# ============================================================

# These are logical request plans.
#
# If a downloader internally makes multiple endpoint requests,
# include each expected endpoint separately here.
#
# This gives us a realistic upper-level estimate before running.

WEEKLY_REQUESTS = [
    {
        "label":
            "2026 games",

        "endpoint":
            "/games",

        "params": {
            "year":
                2026,
        },
    },

    {
        "label":
            "2026 returning production",

        "endpoint":
            "/player/returning",

        "params": {
            "year":
                2026,
        },
    },

    {
        "label":
            "2026 transfer portal",

        "endpoint":
            "/player/portal",

        "params": {
            "year":
                2026,
        },
    },

    {
        "label":
            "2026 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2026,
        },
    },
]


CACHE_BUILD_REQUESTS = [
    {
        "label":
            "FBS teams",

        "endpoint":
            "/teams/fbs",

        "params": {},
    },

    # --------------------------------------------------------
    # 2024 player data
    # --------------------------------------------------------

    {
        "label":
            "2024 player usage",

        "endpoint":
            "/player/usage",

        "params": {
            "year":
                2024,
        },
    },

    {
        "label":
            "2024 player PPA",

        "endpoint":
            "/ppa/players/season",

        "params": {
            "year":
                2024,
        },
    },

    {
        "label":
            "2024 roster",

        "endpoint":
            "/roster",

        "params": {
            "year":
                2024,
        },
    },

    # --------------------------------------------------------
    # 2025 player data
    # --------------------------------------------------------

    {
        "label":
            "2025 player usage",

        "endpoint":
            "/player/usage",

        "params": {
            "year":
                2025,
        },
    },

    {
        "label":
            "2025 player PPA",

        "endpoint":
            "/ppa/players/season",

        "params": {
            "year":
                2025,
        },
    },

    {
        "label":
            "2025 roster",

        "endpoint":
            "/roster",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # SP+
    # --------------------------------------------------------

    {
        "label":
            "2024 SP+",

        "endpoint":
            "/ratings/sp",

        "params": {
            "year":
                2024,
        },
    },

    {
        "label":
            "2025 SP+",

        "endpoint":
            "/ratings/sp",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # Coaching
    # --------------------------------------------------------

    {
        "label":
            "2024 coaches",

        "endpoint":
            "/coaches",

        "params": {
            "year":
                2024,
        },
    },

    {
        "label":
            "2024 coach seasons",

        "endpoint":
            "/coaches/seasons",

        "params": {
            "year":
                2024,
        },
    },

    {
        "label":
            "2025 coaches",

        "endpoint":
            "/coaches",

        "params": {
            "year":
                2025,
        },
    },

    {
        "label":
            "2025 coach seasons",

        "endpoint":
            "/coaches/seasons",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # Returning production
    # --------------------------------------------------------

    {
        "label":
            "2025 returning production",

        "endpoint":
            "/player/returning",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # Transfer portal
    # --------------------------------------------------------

    {
        "label":
            "2025 transfer portal",

        "endpoint":
            "/player/portal",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # Recruiting
    # --------------------------------------------------------

    {
        "label":
            "2019 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2019,
        },
    },

    {
        "label":
            "2020 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2020,
        },
    },

    {
        "label":
            "2021 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2021,
        },
    },

    {
        "label":
            "2022 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2022,
        },
    },

    {
        "label":
            "2023 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2023,
        },
    },

    {
        "label":
            "2024 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2024,
        },
    },

    {
        "label":
            "2025 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # NFL draft
    # --------------------------------------------------------

    {
        "label":
            "2025 NFL draft picks",

        "endpoint":
            "/draft/picks",

        "params": {
            "year":
                2025,
        },
    },

    # --------------------------------------------------------
    # 2026 current data
    # --------------------------------------------------------

    {
        "label":
            "2026 games",

        "endpoint":
            "/games",

        "params": {
            "year":
                2026,
        },
    },

    {
        "label":
            "2026 returning production",

        "endpoint":
            "/player/returning",

        "params": {
            "year":
                2026,
        },
    },

    {
        "label":
            "2026 transfer portal",

        "endpoint":
            "/player/portal",

        "params": {
            "year":
                2026,
        },
    },

    {
        "label":
            "2026 recruiting players",

        "endpoint":
            "/recruiting/players",

        "params": {
            "year":
                2026,
        },
    },
]


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def env_truthy(
    name,
    default=False
):
    """Read boolean-style environment variable."""

    value = os.getenv(
        name
    )

    if value is None:
        return default

    return (
        value
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }
    )


def safe_env_int(
    name,
    default
):
    """Read integer environment variable safely."""

    value = os.getenv(
        name
    )

    if value is None:
        return default

    try:

        return max(
            int(
                value
            ),
            0
        )

    except ValueError:

        return default


def force_refresh_enabled():
    """Return whether planner should ignore valid cache."""

    return env_truthy(
        "FORCE_CFBD_REFRESH",
        default=False,
    )


def monthly_reserve():
    """Return protected monthly reserve."""

    return safe_env_int(
        "CFBD_MIN_REMAINING_CALLS",
        DEFAULT_MONTHLY_RESERVE,
    )


# ============================================================
# GENERIC HELPERS
# ============================================================

def normalize_endpoint(endpoint):
    """Normalize endpoint."""

    endpoint = str(
        endpoint
    ).strip()

    if not endpoint.startswith(
        "/"
    ):

        endpoint = (
            "/"
            +
            endpoint
        )

    return endpoint


def normalize_params(params):
    """Normalize parameters."""

    if not isinstance(
        params,
        dict
    ):

        return {}

    return {
        str(key):
            value
        for key, value in params.items()
        if value is not None
    }


def cache_key(
    endpoint,
    params
):
    """Generate same cache key used by cfbd_api.py."""

    payload = {
        "endpoint":
            endpoint,

        "params":
            {
                key:
                    params[key]
                for key in sorted(
                    params
                )
            },
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":"
        ),
        default=str,
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def cache_path(
    endpoint,
    params
):
    """Return expected cache file."""

    return (
        CACHE_DIRECTORY
        /
        f"{cache_key(endpoint, params)}.json"
    )


def load_json(path):
    """Load JSON safely."""

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )

    except (
        OSError,
        json.JSONDecodeError
    ):

        return None


# ============================================================
# CACHE STATUS
# ============================================================

def inspect_cache(
    endpoint,
    params
):
    """
    Determine whether request is a valid hit, expired, or missing.
    """

    endpoint = normalize_endpoint(
        endpoint
    )

    params = normalize_params(
        params
    )

    policy = cache_policy(
        endpoint,
        params,
    )

    ttl = cache_ttl_seconds(
        endpoint,
        params,
    )

    if force_refresh_enabled():

        return {
            "status":
                "FORCED_REFRESH",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                str(
                    cache_path(
                        endpoint,
                        params
                    )
                ),

            "age_seconds":
                None,

            "would_call_api":
                True,
        }

    if ttl == 0:

        return {
            "status":
                "NO_CACHE",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                None,

            "age_seconds":
                None,

            "would_call_api":
                True,
        }

    path = cache_path(
        endpoint,
        params
    )

    if not path.exists():

        return {
            "status":
                "MISSING",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                str(
                    path
                ),

            "age_seconds":
                None,

            "would_call_api":
                True,
        }

    payload = load_json(
        path
    )

    if not isinstance(
        payload,
        dict
    ):

        return {
            "status":
                "INVALID",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                str(
                    path
                ),

            "age_seconds":
                None,

            "would_call_api":
                True,
        }

    if "data" not in payload:

        return {
            "status":
                "INVALID",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                str(
                    path
                ),

            "age_seconds":
                None,

            "would_call_api":
                True,
        }

    # Permanent cache.

    if ttl is None:

        return {
            "status":
                "HIT",

            "policy":
                policy,

            "ttl":
                None,

            "path":
                str(
                    path
                ),

            "age_seconds":
                None,

            "would_call_api":
                False,
        }

    saved_at = payload.get(
        "saved_at"
    )

    try:

        saved_at = float(
            saved_at
        )

    except (
        TypeError,
        ValueError
    ):

        return {
            "status":
                "INVALID",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                str(
                    path
                ),

            "age_seconds":
                None,

            "would_call_api":
                True,
        }

    age = max(
        time.time()
        -
        saved_at,
        0,
    )

    if age > ttl:

        return {
            "status":
                "EXPIRED",

            "policy":
                policy,

            "ttl":
                ttl,

            "path":
                str(
                    path
                ),

            "age_seconds":
                int(
                    age
                ),

            "would_call_api":
                True,
        }

    return {
        "status":
            "HIT",

        "policy":
            policy,

        "ttl":
            ttl,

        "path":
            str(
                path
            ),

        "age_seconds":
            int(
                age
            ),

        "would_call_api":
            False,
    }


# ============================================================
# ACCOUNT USAGE
# ============================================================

def fetch_usage():
    """Fetch CFBD /info usage."""

    api_key = os.getenv(
        "CFBD_API_KEY"
    )

    if not api_key:

        raise ValueError(
            "CFBD_API_KEY is required unless --offline is used."
        )

    response = requests.get(
        f"{BASE_URL}{INFO_ENDPOINT}",
        headers={
            "Authorization":
                f"Bearer {api_key}",

            "Accept":
                "application/json",
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(
        payload,
        dict
    ):

        raise ValueError(
            "Unexpected CFBD /info response."
        )

    return payload


# ============================================================
# PLAN SELECTION
# ============================================================

def get_plan(name):
    """Return planned requests and default budget."""

    if name == "weekly":

        return (
            WEEKLY_REQUESTS,
            DEFAULT_WEEKLY_BUDGET,
        )

    if name == "cache-build":

        return (
            CACHE_BUILD_REQUESTS,
            DEFAULT_CACHE_BUILD_BUDGET,
        )

    raise ValueError(
        f"Unknown plan: {name}"
    )


# ============================================================
# FORMATTERS
# ============================================================

def format_ttl(ttl):
    """Human-readable TTL."""

    if ttl is None:
        return "permanent"

    if ttl == 0:
        return "disabled"

    return (
        f"{ttl}s"
    )


# ============================================================
# PLANNER
# ============================================================

def run_plan(
    name,
    offline=False
):
    """Run dry-run plan."""

    requests_plan, default_budget = get_plan(
        name
    )

    configured_budget = safe_env_int(
        "CFBD_MAX_CALLS_THIS_RUN",
        default_budget,
    )

    rows = []

    estimated_calls = 0

    for item in requests_plan:

        endpoint = normalize_endpoint(
            item[
                "endpoint"
            ]
        )

        params = normalize_params(
            item.get(
                "params"
            )
        )

        status = inspect_cache(
            endpoint,
            params,
        )

        if status[
            "would_call_api"
        ]:

            estimated_calls += 1

        rows.append(
            {
                "label":
                    item[
                        "label"
                    ],

                "endpoint":
                    endpoint,

                "params":
                    params,

                **status,
            }
        )

    usage = None

    if not offline:

        usage = fetch_usage()

    print("=" * 80)

    print(
        "PROJECT GRIDIRON CFBD REQUEST PLAN"
    )

    print("=" * 80)

    print()

    print(
        f"Plan: "
        f"{name}"
    )

    print(
        f"Force refresh: "
        f"{force_refresh_enabled()}"
    )

    print(
        f"Per-run request budget: "
        f"{configured_budget}"
    )

    print(
        f"Estimated real CFBD calls: "
        f"{estimated_calls}"
    )

    print()

    print(
        "REQUEST PLAN"
    )

    print("-" * 80)

    for index, row in enumerate(
        rows,
        start=1
    ):

        print(
            f"{index}. "
            f"{row['label']}"
        )

        print(
            f"   endpoint: "
            f"{row['endpoint']}"
        )

        print(
            f"   params: "
            f"{row['params']}"
        )

        print(
            f"   policy: "
            f"{row['policy']}"
        )

        print(
            f"   ttl: "
            f"{format_ttl(row['ttl'])}"
        )

        print(
            f"   cache status: "
            f"{row['status']}"
        )

        print(
            f"   consumes call: "
            f"{row['would_call_api']}"
        )

        if row[
            "age_seconds"
        ] is not None:

            print(
                f"   cache age: "
                f"{row['age_seconds']}s"
            )

        print()

    print(
        "PER-RUN BUDGET CHECK"
    )

    print("-" * 80)

    if estimated_calls <= configured_budget:

        print(
            "PASS"
        )

        print(
            f"Estimated calls "
            f"{estimated_calls} <= "
            f"budget {configured_budget}"
        )

        budget_pass = True

    else:

        print(
            "BLOCKED"
        )

        print(
            f"Estimated calls "
            f"{estimated_calls} > "
            f"budget {configured_budget}"
        )

        budget_pass = False

    monthly_pass = True

    if usage is not None:

        remaining = int(
            usage.get(
                "remainingCalls",
                0
            )
        )

        reserve = monthly_reserve()

        projected_remaining = (
            remaining
            -
            estimated_calls
        )

        print()

        print(
            "MONTHLY QUOTA CHECK"
        )

        print("-" * 80)

        print(
            f"Tier: "
            f"{usage.get('tierName')}"
        )

        print(
            f"Monthly limit: "
            f"{usage.get('monthlyLimit')}"
        )

        print(
            f"Used calls: "
            f"{usage.get('usedCalls')}"
        )

        print(
            f"Remaining calls now: "
            f"{remaining}"
        )

        print(
            f"Estimated calls this run: "
            f"{estimated_calls}"
        )

        print(
            f"Projected remaining: "
            f"{projected_remaining}"
        )

        print(
            f"Protected reserve: "
            f"{reserve}"
        )

        print(
            f"Reset at: "
            f"{usage.get('resetAt')}"
        )

        if projected_remaining >= reserve:

            print()

            print(
                "PASS"
            )

            print(
                "This plan stays above the protected monthly reserve."
            )

        else:

            print()

            print(
                "BLOCKED"
            )

            print(
                "This plan would violate the protected monthly reserve."
            )

            monthly_pass = False

    print()

    print(
        "FINAL PLAN RESULT"
    )

    print("-" * 80)

    if (
        budget_pass
        and
        monthly_pass
    ):

        print(
            "SAFE TO RUN"
        )

        return 0

    print(
        "DO NOT RUN"
    )

    return 1


# ============================================================
# CLI
# ============================================================

def parse_args():
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Plan CFBD requests before running a workflow."
        )
    )

    parser.add_argument(
        "plan",
        choices=[
            "weekly",
            "cache-build",
        ],
    )

    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Skip CFBD /info and evaluate only local cache "
            "and per-run budget."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":

    args = parse_args()

    exit_code = run_plan(
        args.plan,
        offline=args.offline,
    )

    sys.exit(
        exit_code
    )
