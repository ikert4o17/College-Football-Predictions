"""
Project Gridiron
CFBD Cache Freshness Policy

Purpose
-------
Define how long different CFBD requests should remain valid in cache.

The goal is simple:

    Historical data:
        Treat as permanent unless explicitly forced.

    Current-season static/preseason data:
        Refresh rarely and intentionally.

    Current-season dynamic data:
        Refresh on a controlled TTL.

    /info:
        Never cache.

Environment variables may override selected defaults.

This module contains policy only.
It does not make HTTP requests.
"""

import os
from datetime import datetime, timezone


# ============================================================
# DEFAULT TTL VALUES
# ============================================================

ONE_HOUR = 60 * 60

SIX_HOURS = 6 * ONE_HOUR

TWELVE_HOURS = 12 * ONE_HOUR

ONE_DAY = 24 * ONE_HOUR

THREE_DAYS = 3 * ONE_DAY

SEVEN_DAYS = 7 * ONE_DAY

THIRTY_DAYS = 30 * ONE_DAY


# ============================================================
# POLICY CATEGORIES
# ============================================================

POLICY_PERMANENT = "permanent"

POLICY_STATIC = "static"

POLICY_SEASONAL = "seasonal"

POLICY_DYNAMIC = "dynamic"

POLICY_NO_CACHE = "no_cache"


# ============================================================
# ENDPOINT GROUPS
# ============================================================

NO_CACHE_ENDPOINTS = {
    "/info",
}


# Current-season endpoints that can change frequently during the season.

DYNAMIC_ENDPOINT_PREFIXES = (
    "/games",
    "/plays",
    "/drive",
    "/drives",
    "/stats",
    "/game",
    "/scoreboard",
)


# Current-season endpoints that may change, but not every few hours.

SEASONAL_ENDPOINT_PREFIXES = (
    "/player/usage",
    "/ppa/players",
    "/player/season",
    "/roster",
)


# Current-season preseason/static endpoints.
#
# These should not be refreshed every weekly workflow run.

STATIC_ENDPOINT_PREFIXES = (
    "/player/returning",
    "/player/portal",
    "/recruiting",
    "/coaches",
    "/draft",
    "/talent",
    "/ratings/sp",
    "/teams/fbs",
)


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

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


# ============================================================
# TTL CONFIG
# ============================================================

def dynamic_ttl():
    """
    TTL for current-season games/scores/stats.

    Default:
        6 hours
    """

    return safe_env_int(
        "CFBD_DYNAMIC_CACHE_TTL_SECONDS",
        SIX_HOURS,
    )


def seasonal_ttl():
    """
    TTL for current-season roster/player metrics.

    Default:
        24 hours
    """

    return safe_env_int(
        "CFBD_SEASONAL_CACHE_TTL_SECONDS",
        ONE_DAY,
    )


def static_ttl():
    """
    TTL for current-season preseason/static data.

    Default:
        30 days

    In practice these endpoints should usually be refreshed intentionally
    using FORCE_CFBD_REFRESH rather than automatically every month.
    """

    return safe_env_int(
        "CFBD_STATIC_CACHE_TTL_SECONDS",
        THIRTY_DAYS,
    )


def default_ttl():
    """
    Fallback TTL for uncategorized current-season requests.

    Default:
        12 hours
    """

    return safe_env_int(
        "CFBD_DEFAULT_CACHE_TTL_SECONDS",
        TWELVE_HOURS,
    )


# ============================================================
# REQUEST HELPERS
# ============================================================

def normalize_endpoint(endpoint):
    """Normalize endpoint string."""

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


def request_year(params):
    """Extract year/season if present."""

    if not isinstance(
        params,
        dict
    ):

        return None

    for key in (
        "year",
        "season",
    ):

        value = params.get(
            key
        )

        if value is None:
            continue

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            continue

    return None


def current_year():
    """Return current UTC calendar year."""

    return datetime.now(
        timezone.utc
    ).year


def is_historical_request(params):
    """
    Return whether request targets a completed prior season.
    """

    year = request_year(
        params
    )

    if year is None:
        return False

    return (
        year
        <
        current_year()
    )


def endpoint_matches(
    endpoint,
    prefixes
):
    """Return whether endpoint matches any prefix."""

    endpoint = normalize_endpoint(
        endpoint
    )

    for prefix in prefixes:

        if endpoint.startswith(
            prefix
        ):

            return True

    return False


# ============================================================
# POLICY
# ============================================================

def cache_policy(
    endpoint,
    params=None
):
    """
    Return cache policy category for a request.
    """

    endpoint = normalize_endpoint(
        endpoint
    )

    params = (
        params
        if isinstance(
            params,
            dict
        )
        else {}
    )

    # --------------------------------------------------------
    # NEVER CACHE
    # --------------------------------------------------------

    if endpoint in NO_CACHE_ENDPOINTS:

        return POLICY_NO_CACHE

    # --------------------------------------------------------
    # HISTORICAL DATA
    # --------------------------------------------------------

    if is_historical_request(
        params
    ):

        return POLICY_PERMANENT

    # --------------------------------------------------------
    # DYNAMIC
    # --------------------------------------------------------

    if endpoint_matches(
        endpoint,
        DYNAMIC_ENDPOINT_PREFIXES
    ):

        return POLICY_DYNAMIC

    # --------------------------------------------------------
    # SEASONAL
    # --------------------------------------------------------

    if endpoint_matches(
        endpoint,
        SEASONAL_ENDPOINT_PREFIXES
    ):

        return POLICY_SEASONAL

    # --------------------------------------------------------
    # STATIC
    # --------------------------------------------------------

    if endpoint_matches(
        endpoint,
        STATIC_ENDPOINT_PREFIXES
    ):

        return POLICY_STATIC

    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return POLICY_DYNAMIC


def cache_ttl_seconds(
    endpoint,
    params=None
):
    """
    Return TTL in seconds for request.

    None means:
        permanent cache

    0 means:
        do not cache
    """

    policy = cache_policy(
        endpoint,
        params,
    )

    if policy == POLICY_NO_CACHE:

        return 0

    if policy == POLICY_PERMANENT:

        return None

    if policy == POLICY_STATIC:

        return static_ttl()

    if policy == POLICY_SEASONAL:

        return seasonal_ttl()

    if policy == POLICY_DYNAMIC:

        return dynamic_ttl()

    return default_ttl()


# ============================================================
# HUMAN-READABLE DESCRIPTION
# ============================================================

def describe_policy(
    endpoint,
    params=None
):
    """Return policy summary."""

    policy = cache_policy(
        endpoint,
        params,
    )

    ttl = cache_ttl_seconds(
        endpoint,
        params,
    )

    if ttl is None:

        ttl_text = "permanent"

    elif ttl == 0:

        ttl_text = "disabled"

    else:

        ttl_text = (
            f"{ttl} seconds"
        )

    return {
        "endpoint":
            normalize_endpoint(
                endpoint
            ),

        "params":
            params or {},

        "policy":
            policy,

        "ttl_seconds":
            ttl,

        "ttl":
            ttl_text,
    }


# ============================================================
# CLI DIAGNOSTIC
# ============================================================

def print_example(
    endpoint,
    params=None
):
    """Print one policy example."""

    result = describe_policy(
        endpoint,
        params,
    )

    print(
        f"{result['endpoint']} "
        f"{result['params']}"
    )

    print(
        f"  policy: "
        f"{result['policy']}"
    )

    print(
        f"  ttl: "
        f"{result['ttl']}"
    )

    print()


if __name__ == "__main__":

    print("=" * 76)

    print(
        "PROJECT GRIDIRON CFBD CACHE POLICY"
    )

    print("=" * 76)

    print()

    print_example(
        "/games",
        {
            "year":
                current_year()
        }
    )

    print_example(
        "/games",
        {
            "year":
                current_year()
                -
                1
        }
    )

    print_example(
        "/player/returning",
        {
            "year":
                current_year()
        }
    )

    print_example(
        "/player/usage",
        {
            "year":
                current_year()
        }
    )

    print_example(
        "/coaches",
        {
            "year":
                current_year()
                -
                1
        }
    )

    print_example(
        "/info"
    )
