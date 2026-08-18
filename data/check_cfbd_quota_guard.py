"""
Project Gridiron
CFBD Quota Guard

Purpose
-------
Protect the project's monthly CFBD allowance by stopping download
workflows before they consume the final reserve of API calls.

Usage:
    python -m data.check_cfbd_quota_guard

Environment variables:

    CFBD_API_KEY
        Required.

    CFBD_MIN_REMAINING_CALLS
        Minimum number of calls to preserve.
        Default: 100

    CFBD_ALLOW_RESERVE_USE
        Set to 1/true/yes to allow a workflow to continue even when
        remaining calls are at or below the protected reserve.

Behavior:
    - Calls CFBD /info
    - Prints account usage
    - Exits 0 when quota is safe
    - Exits 1 when reserve would be violated
    - Does not block an explicit emergency override

This file does not download football data.
"""

import json
import os
import sys

import requests


BASE_URL = "https://api.collegefootballdata.com"
INFO_ENDPOINT = "/info"

DEFAULT_MIN_REMAINING_CALLS = 100


# ============================================================
# ENVIRONMENT
# ============================================================

def get_api_key():
    """Return CFBD API key."""

    api_key = os.getenv(
        "CFBD_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "CFBD_API_KEY environment variable is not set."
        )

    return api_key


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


def minimum_remaining_calls():
    """Return protected call reserve."""

    value = os.getenv(
        "CFBD_MIN_REMAINING_CALLS"
    )

    if not value:
        return DEFAULT_MIN_REMAINING_CALLS

    try:

        reserve = int(
            value
        )

    except ValueError:

        print(
            "WARNING:"
        )

        print(
            "CFBD_MIN_REMAINING_CALLS was not a valid integer."
        )

        print(
            f"Using default reserve: "
            f"{DEFAULT_MIN_REMAINING_CALLS}"
        )

        return DEFAULT_MIN_REMAINING_CALLS

    return max(
        reserve,
        0
    )


def reserve_override_enabled():
    """Return whether protected reserve may be used."""

    return env_truthy(
        "CFBD_ALLOW_RESERVE_USE",
        default=False,
    )


# ============================================================
# API
# ============================================================

def fetch_usage():
    """Fetch current CFBD account usage."""

    headers = {
        "Authorization":
            f"Bearer {get_api_key()}",

        "Accept":
            "application/json",
    }

    url = (
        BASE_URL
        +
        INFO_ENDPOINT
    )

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as error:

        raise RuntimeError(
            "Unable to contact CFBD usage endpoint."
        ) from error

    print(
        f"GET {INFO_ENDPOINT}"
    )

    print(
        f"Status code: "
        f"{response.status_code}"
    )

    if response.status_code != 200:

        try:

            payload = response.json()

            print()

            print(
                "CFBD RESPONSE"
            )

            print("-" * 76)

            print(
                json.dumps(
                    payload,
                    indent=4,
                )
            )

        except ValueError:

            print(
                response.text[:3000]
            )

        response.raise_for_status()

    try:

        usage = response.json()

    except ValueError as error:

        raise ValueError(
            "CFBD /info returned invalid JSON."
        ) from error

    if not isinstance(
        usage,
        dict
    ):

        raise ValueError(
            "CFBD /info returned an unexpected response type."
        )

    return usage


# ============================================================
# SAFE INTEGER
# ============================================================

def safe_int(
    value,
    default=None
):
    """Safely convert value to integer."""

    if value is None:
        return default

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return default


# ============================================================
# MAIN
# ============================================================

def main():
    """Run quota guard."""

    print("=" * 76)

    print(
        "PROJECT GRIDIRON CFBD QUOTA GUARD"
    )

    print("=" * 76)

    print()

    usage = fetch_usage()

    monthly_limit = safe_int(
        usage.get(
            "monthlyLimit"
        )
    )

    used_calls = safe_int(
        usage.get(
            "usedCalls"
        )
    )

    remaining_calls = safe_int(
        usage.get(
            "remainingCalls"
        )
    )

    reset_at = usage.get(
        "resetAt"
    )

    tier_name = usage.get(
        "tierName"
    )

    reserve = minimum_remaining_calls()

    override = reserve_override_enabled()

    print()

    print(
        "ACCOUNT"
    )

    print("-" * 76)

    print(
        f"Tier: "
        f"{tier_name}"
    )

    print(
        f"Monthly limit: "
        f"{monthly_limit}"
    )

    print(
        f"Used calls: "
        f"{used_calls}"
    )

    print(
        f"Remaining calls: "
        f"{remaining_calls}"
    )

    print(
        f"Reset at: "
        f"{reset_at}"
    )

    print()

    print(
        "PROJECT GRIDIRON QUOTA POLICY"
    )

    print("-" * 76)

    print(
        f"Protected reserve: "
        f"{reserve} calls"
    )

    print(
        f"Reserve override enabled: "
        f"{override}"
    )

    if remaining_calls is None:

        print()

        print(
            "GUARD RESULT: BLOCKED"
        )

        print("-" * 76)

        print(
            "CFBD did not return a usable remaining-call count."
        )

        print(
            "The workflow will stop rather than risk consuming "
            "unknown quota."
        )

        sys.exit(
            1
        )

    # ========================================================
    # EXHAUSTED
    # ========================================================

    if remaining_calls <= 0:

        print()

        print(
            "GUARD RESULT: BLOCKED"
        )

        print("-" * 76)

        print(
            "The CFBD monthly quota is exhausted."
        )

        print(
            "No football-data downloads should be attempted."
        )

        print(
            f"Quota resets at: "
            f"{reset_at}"
        )

        sys.exit(
            1
        )

    # ========================================================
    # PROTECTED RESERVE
    # ========================================================

    if (
        remaining_calls
        <=
        reserve
    ):

        if override:

            print()

            print(
                "GUARD RESULT: OVERRIDE"
            )

            print("-" * 76)

            print(
                "Remaining calls are inside the protected reserve."
            )

            print(
                "CFBD_ALLOW_RESERVE_USE is enabled, so the "
                "workflow may continue."
            )

            sys.exit(
                0
            )

        print()

        print(
            "GUARD RESULT: BLOCKED"
        )

        print("-" * 76)

        print(
            "Remaining calls are at or below the protected reserve."
        )

        print(
            f"Remaining: "
            f"{remaining_calls}"
        )

        print(
            f"Reserve: "
            f"{reserve}"
        )

        print()

        print(
            "The workflow is being stopped to preserve API capacity "
            "for production rankings and projections."
        )

        print()

        print(
            "To intentionally use the reserve, set:"
        )

        print(
            "CFBD_ALLOW_RESERVE_USE=1"
        )

        sys.exit(
            1
        )

    # ========================================================
    # SAFE
    # ========================================================

    usable_calls = (
        remaining_calls
        -
        reserve
    )

    print()

    print(
        "GUARD RESULT: SAFE"
    )

    print("-" * 76)

    print(
        "CFBD downloads may continue."
    )

    print(
        f"Calls available above reserve: "
        f"{usable_calls}"
    )

    print(
        f"Protected calls remaining after reserve: "
        f"{reserve}"
    )

    sys.exit(
        0
    )


if __name__ == "__main__":

    main()
