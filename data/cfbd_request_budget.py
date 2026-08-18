"""
Project Gridiron
CFBD Per-Run Request Budget

Purpose
-------
Protect a single GitHub Actions run from consuming too many CFBD calls.

This module tracks REAL CFBD data requests during the current process/job.

Cache hits should NOT count against this budget.

Environment variable:

    CFBD_MAX_CALLS_THIS_RUN

Default:
    20

Examples:

    CFBD_MAX_CALLS_THIS_RUN=10
    CFBD_MAX_CALLS_THIS_RUN=25

The request budget is separate from the monthly quota reserve.

We therefore have two protections:

1. Monthly reserve guard
       Example: preserve final 100 monthly calls

2. Per-run request budget
       Example: never let one workflow spend more than 20 calls

The shared CFBD client will use this module before every real
football-data request.

The /info usage endpoint is NOT counted against this budget.
"""

import os
from pathlib import Path


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_MAX_CALLS_THIS_RUN = 20

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# ============================================================
# INTERNAL STATE
# ============================================================

_requests_used = 0

_request_log = []


# ============================================================
# CONFIG
# ============================================================

def max_calls_this_run():
    """Return configured request budget."""

    value = os.getenv(
        "CFBD_MAX_CALLS_THIS_RUN"
    )

    if not value:

        return DEFAULT_MAX_CALLS_THIS_RUN

    try:

        limit = int(
            value
        )

    except ValueError:

        print(
            "WARNING:"
        )

        print(
            "CFBD_MAX_CALLS_THIS_RUN is not a valid integer."
        )

        print(
            f"Using default per-run budget: "
            f"{DEFAULT_MAX_CALLS_THIS_RUN}"
        )

        return DEFAULT_MAX_CALLS_THIS_RUN

    return max(
        limit,
        0
    )


# ============================================================
# STATE
# ============================================================

def requests_used():
    """Return number of real CFBD requests used this run."""

    return _requests_used


def requests_remaining():
    """Return remaining per-run request allowance."""

    limit = max_calls_this_run()

    return max(
        limit
        -
        requests_used(),
        0
    )


def request_log():
    """Return copy of current request log."""

    return list(
        _request_log
    )


# ============================================================
# GUARD
# ============================================================

def ensure_request_available(
    endpoint=None,
    params=None
):
    """
    Ensure another real CFBD request is allowed.

    Call this immediately before sending a football-data HTTP request.
    """

    used = requests_used()

    limit = max_calls_this_run()

    if used >= limit:

        print()

        print("=" * 76)

        print(
            "CFBD PER-RUN REQUEST BUDGET EXHAUSTED"
        )

        print("=" * 76)

        print()

        print(
            f"Configured budget: "
            f"{limit}"
        )

        print(
            f"Requests already used: "
            f"{used}"
        )

        print(
            "Requests remaining: 0"
        )

        if endpoint:

            print()

            print(
                "Blocked request:"
            )

            print(
                f"  endpoint: {endpoint}"
            )

            if params:

                print(
                    f"  params: {params}"
                )

        print()

        print(
            "The workflow is stopping before another CFBD "
            "data call is consumed."
        )

        print()

        print(
            "Increase CFBD_MAX_CALLS_THIS_RUN only when "
            "the additional API usage is intentional."
        )

        raise RuntimeError(
            "CFBD per-run request budget exhausted."
        )


# ============================================================
# REGISTER REQUEST
# ============================================================

def register_request(
    endpoint,
    params=None
):
    """
    Record one real CFBD data request.

    This should be called immediately before requests.get() is sent.

    Retries count as additional real requests because they still reach
    CFBD and may consume request quota.
    """

    global _requests_used

    ensure_request_available(
        endpoint,
        params
    )

    _requests_used += 1

    entry = {
        "number":
            _requests_used,

        "endpoint":
            endpoint,

        "params":
            params or {},
    }

    _request_log.append(
        entry
    )

    print()

    print(
        "CFBD REQUEST BUDGET"
    )

    print(
        f"  request "
        f"{_requests_used}/"
        f"{max_calls_this_run()}"
    )

    print(
        f"  endpoint: "
        f"{endpoint}"
    )

    if params:

        print(
            f"  params: "
            f"{params}"
        )


# ============================================================
# SUMMARY
# ============================================================

def print_budget_summary():
    """Print current request-budget status."""

    limit = max_calls_this_run()

    used = requests_used()

    remaining = requests_remaining()

    print("=" * 76)

    print(
        "PROJECT GRIDIRON CFBD REQUEST BUDGET"
    )

    print("=" * 76)

    print()

    print(
        f"Configured budget: "
        f"{limit}"
    )

    print(
        f"Real requests used: "
        f"{used}"
    )

    print(
        f"Requests remaining: "
        f"{remaining}"
    )

    print()

    if not _request_log:

        print(
            "No real CFBD data requests have been made "
            "in this process."
        )

        return

    print(
        "REQUEST LOG"
    )

    print("-" * 76)

    for entry in _request_log:

        print(
            f"{entry['number']}. "
            f"{entry['endpoint']}"
        )

        if entry[
            "params"
        ]:

            print(
                f"   {entry['params']}"
            )


# ============================================================
# RESET
# ============================================================

def reset_budget():
    """
    Reset in-process counters.

    Primarily useful for tests.
    """

    global _requests_used

    _requests_used = 0

    _request_log.clear()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    print_budget_summary()
