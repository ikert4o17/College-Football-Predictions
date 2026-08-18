"""
Project Gridiron
Persistent CFBD Per-Run Request Budget

Purpose
-------
Protect an entire GitHub Actions workflow run from consuming too many
real CFBD API calls.

Unlike an in-memory counter, this version persists state to disk so
separate Python processes/steps share the same request count.

Environment variables:

    CFBD_MAX_CALLS_THIS_RUN
        Maximum real CFBD data requests allowed during the workflow.
        Default: 20

    CFBD_REQUEST_BUDGET_RUN_ID
        Optional run identifier.

        In GitHub Actions we should set this to:
            ${{ github.run_id }}

        This prevents one workflow run from inheriting the count from
        another workflow run.

State file:
    data/cache/cfbd/request_budget_state.json

Important:
    - Cache hits count as 0
    - /info usage checks count as 0
    - Every real HTTP request attempt counts as 1
    - Retries count too
"""

import json
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

STATE_FILE = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "cfbd"
    / "request_budget_state.json"
)


# ============================================================
# CONFIG
# ============================================================

def max_calls_this_run():
    """Return configured per-run request budget."""

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
            "WARNING: CFBD_MAX_CALLS_THIS_RUN is invalid."
        )

        print(
            f"Using default budget: "
            f"{DEFAULT_MAX_CALLS_THIS_RUN}"
        )

        return DEFAULT_MAX_CALLS_THIS_RUN

    return max(
        limit,
        0
    )


def run_id():
    """Return current workflow/run identifier."""

    value = os.getenv(
        "CFBD_REQUEST_BUDGET_RUN_ID"
    )

    if value:
        return str(
            value
        )

    # Local/manual fallback.
    return "local"


# ============================================================
# STATE
# ============================================================

def default_state():
    """Return fresh request-budget state."""

    return {
        "run_id":
            run_id(),

        "requests_used":
            0,

        "request_log":
            [],
    }


def load_state():
    """
    Load state from disk.

    If the saved state belongs to another workflow run, reset it.
    """

    if not STATE_FILE.exists():
        return default_state()

    try:
        with STATE_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            state = json.load(
                file
            )

    except (
        OSError,
        json.JSONDecodeError
    ):
        return default_state()

    if not isinstance(
        state,
        dict
    ):
        return default_state()

    if (
        str(
            state.get(
                "run_id"
            )
        )
        !=
        run_id()
    ):
        return default_state()

    if not isinstance(
        state.get(
            "request_log"
        ),
        list
    ):
        state[
            "request_log"
        ] = []

    try:
        state[
            "requests_used"
        ] = int(
            state.get(
                "requests_used",
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):
        state[
            "requests_used"
        ] = 0

    return state


def save_state(state):
    """Persist state to disk."""

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with STATE_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            indent=2,
        )


# ============================================================
# COUNTERS
# ============================================================

def requests_used():
    """Return number of real requests used in this workflow run."""

    state = load_state()

    return int(
        state.get(
            "requests_used",
            0
        )
    )


def requests_remaining():
    """Return remaining per-run allowance."""

    return max(
        max_calls_this_run()
        -
        requests_used(),
        0
    )


def request_log():
    """Return a copy of current request log."""

    state = load_state()

    return list(
        state.get(
            "request_log",
            []
        )
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

    Call immediately before sending a football-data HTTP request.
    """

    used = requests_used()

    limit = max_calls_this_run()

    if used < limit:
        return

    print()
    print("=" * 76)
    print("CFBD PER-RUN REQUEST BUDGET EXHAUSTED")
    print("=" * 76)
    print()

    print(
        f"Workflow run ID: "
        f"{run_id()}"
    )

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
        print("Blocked request:")
        print(
            f"  endpoint: "
            f"{endpoint}"
        )

        if params:
            print(
                f"  params: "
                f"{params}"
            )

    print()
    print(
        "The request was blocked before reaching CFBD."
    )

    print()
    print(
        "Increase CFBD_MAX_CALLS_THIS_RUN only when "
        "additional usage is intentional."
    )

    raise RuntimeError(
        "CFBD per-run request budget exhausted."
    )


# ============================================================
# REGISTER REAL REQUEST
# ============================================================

def register_request(
    endpoint,
    params=None
):
    """
    Register one real HTTP request attempt.

    Retries count because they still reach CFBD.
    """

    state = load_state()

    used = int(
        state.get(
            "requests_used",
            0
        )
    )

    limit = max_calls_this_run()

    if used >= limit:
        ensure_request_available(
            endpoint,
            params
        )

    used += 1

    state[
        "requests_used"
    ] = used

    log = state.setdefault(
        "request_log",
        []
    )

    log.append(
        {
            "number":
                used,

            "endpoint":
                endpoint,

            "params":
                params or {},
        }
    )

    save_state(
        state
    )

    print()
    print("CFBD REQUEST BUDGET")
    print(
        f"  run_id: "
        f"{run_id()}"
    )

    print(
        f"  request "
        f"{used}/"
        f"{limit}"
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
# INITIALIZE / RESET
# ============================================================

def initialize_budget():
    """
    Initialize the request budget for the current workflow run.

    Safe to call at workflow start.
    """

    state = load_state()

    # load_state already resets automatically when run_id changes.
    save_state(
        state
    )

    print("=" * 76)
    print("PROJECT GRIDIRON CFBD REQUEST BUDGET INITIALIZED")
    print("=" * 76)
    print()

    print(
        f"Run ID: "
        f"{run_id()}"
    )

    print(
        f"Maximum calls this run: "
        f"{max_calls_this_run()}"
    )

    print(
        f"Calls currently used: "
        f"{state['requests_used']}"
    )


def reset_budget():
    """Explicitly reset current run state."""

    state = default_state()

    save_state(
        state
    )


# ============================================================
# SUMMARY
# ============================================================

def print_budget_summary():
    """Print current persisted budget status."""

    state = load_state()

    used = int(
        state.get(
            "requests_used",
            0
        )
    )

    limit = max_calls_this_run()

    print("=" * 76)
    print("PROJECT GRIDIRON CFBD REQUEST BUDGET")
    print("=" * 76)
    print()

    print(
        f"Run ID: "
        f"{run_id()}"
    )

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
        f"{max(limit - used, 0)}"
    )

    log = state.get(
        "request_log",
        []
    )

    if not log:
        print()
        print(
            "No real CFBD data requests have been made "
            "during this workflow run."
        )

        return

    print()
    print("REQUEST LOG")
    print("-" * 76)

    for entry in log:
        print(
            f"{entry.get('number')}. "
            f"{entry.get('endpoint')}"
        )

        params = entry.get(
            "params"
        )

        if params:
            print(
                f"   {params}"
            )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    initialize_budget()

    print()

    print_budget_summary()
