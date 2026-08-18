"""
Project Gridiron
Shared CFBD API Client

Centralized CollegeFootballData API access.

Responsibilities:
    - authenticated CFBD GET requests
    - persistent response caching
    - cache freshness policy
    - monthly quota protection
    - per-run request-budget protection
    - retry handling
    - useful diagnostics

Existing usage remains supported:

    from data.cfbd_api import client

    teams = client.get("/teams/fbs")

    games = client.get(
        "/games",
        {"year": 2025}
    )

    games = client.get(
        "/games",
        params={"year": 2025}
    )

Environment options:

    FORCE_CFBD_REFRESH=1
        Ignore cache and request fresh data.

    CFBD_USE_CACHE=0
        Disable response caching.

    CFBD_MAX_CALLS_THIS_RUN=20
        Maximum real CFBD HTTP attempts allowed during the workflow run.

Cache freshness is defined in:

    data/cfbd_cache_policy.py

Examples:

    historical data
        -> permanent cache

    current-season games/stats
        -> short TTL

    current-season roster/player metrics
        -> seasonal TTL

    current-season preseason/static inputs
        -> long TTL

    /info
        -> never cached
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from data.cfbd_cache_policy import (
    cache_policy,
    cache_ttl_seconds,
)

from data.cfbd_request_budget import (
    register_request,
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

BASE_URL = (
    "https://api.collegefootballdata.com"
)

CACHE_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "cfbd"
)

INFO_ENDPOINT = "/info"

MAX_ATTEMPTS = 5

BACKOFF_SECONDS = [
    5,
    10,
    20,
    40,
    60,
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


def force_refresh_enabled():
    """Return whether cache should be bypassed."""

    return env_truthy(
        "FORCE_CFBD_REFRESH",
        default=False,
    )


def cache_enabled():
    """Return whether CFBD response caching is enabled."""

    value = os.getenv(
        "CFBD_USE_CACHE"
    )

    if value is None:
        return True

    return env_truthy(
        "CFBD_USE_CACHE",
        default=True,
    )


# ============================================================
# GENERIC HELPERS
# ============================================================

def normalize_endpoint(endpoint):
    """Ensure endpoint begins with slash."""

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
    """Normalize query parameters."""

    if params is None:
        return {}

    return {
        str(key):
            value
        for key, value in params.items()
        if value is not None
    }


def safe_json(response):
    """Safely parse response JSON."""

    try:

        return response.json()

    except ValueError:

        return None


def safe_int(
    value,
    default=0
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
# CACHE KEY / PATH
# ============================================================

def cache_key(
    endpoint,
    params
):
    """Generate deterministic cache key."""

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

    digest = hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()

    return digest


def cache_path(
    endpoint,
    params
):
    """Return path for cached request."""

    return (
        CACHE_DIRECTORY
        /
        f"{cache_key(endpoint, params)}.json"
    )


# ============================================================
# CACHE READ
# ============================================================

def read_cache(
    endpoint,
    params
):
    """
    Read cached response if valid under current cache policy.
    """

    if not cache_enabled():

        return None

    if force_refresh_enabled():

        return None

    ttl = cache_ttl_seconds(
        endpoint,
        params,
    )

    # TTL = 0 means never cache this endpoint.

    if ttl == 0:

        return None

    path = cache_path(
        endpoint,
        params
    )

    if not path.exists():

        return None

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            payload = json.load(
                file
            )

    except (
        OSError,
        json.JSONDecodeError
    ):

        return None

    if not isinstance(
        payload,
        dict
    ):

        return None

    if "data" not in payload:

        return None

    # --------------------------------------------------------
    # PERMANENT CACHE
    # --------------------------------------------------------

    if ttl is None:

        return payload[
            "data"
        ]

    # --------------------------------------------------------
    # TTL CACHE
    # --------------------------------------------------------

    saved_at = payload.get(
        "saved_at"
    )

    if saved_at is None:

        return None

    try:

        saved_at = float(
            saved_at
        )

    except (
        TypeError,
        ValueError
    ):

        return None

    age = (
        time.time()
        -
        saved_at
    )

    if age > ttl:

        print(
            f"CACHE EXPIRED: "
            f"{endpoint}"
        )

        if params:

            print(
                f"  params={params}"
            )

        print(
            f"  age_seconds="
            f"{int(age)}"
        )

        print(
            f"  ttl_seconds="
            f"{ttl}"
        )

        return None

    return payload[
        "data"
    ]


# ============================================================
# CACHE WRITE
# ============================================================

def write_cache(
    endpoint,
    params,
    data
):
    """
    Persist successful CFBD response according to policy.
    """

    if not cache_enabled():

        return

    ttl = cache_ttl_seconds(
        endpoint,
        params,
    )

    if ttl == 0:

        return

    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    path = cache_path(
        endpoint,
        params
    )

    payload = {
        "endpoint":
            endpoint,

        "params":
            params,

        "cache_policy":
            cache_policy(
                endpoint,
                params,
            ),

        "ttl_seconds":
            ttl,

        "saved_at":
            time.time(),

        "saved_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "data":
            data,
    }

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
        )


# ============================================================
# CACHE DIAGNOSTICS
# ============================================================

def print_cache_policy(
    endpoint,
    params
):
    """Print cache policy for request."""

    policy = cache_policy(
        endpoint,
        params,
    )

    ttl = cache_ttl_seconds(
        endpoint,
        params,
    )

    print(
        f"CACHE POLICY: "
        f"{policy}"
    )

    if ttl is None:

        print(
            "  ttl=permanent"
        )

    else:

        print(
            f"  ttl_seconds="
            f"{ttl}"
        )


# ============================================================
# RETRY / RATE LIMIT HELPERS
# ============================================================

def retry_after_seconds(response):
    """Parse Retry-After header."""

    value = response.headers.get(
        "Retry-After"
    )

    if not value:

        return None

    value = value.strip()

    try:

        return max(
            int(
                value
            ),
            0
        )

    except ValueError:

        pass

    try:

        retry_time = parsedate_to_datetime(
            value
        )

        if retry_time.tzinfo is None:

            retry_time = retry_time.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        return max(
            int(
                (
                    retry_time
                    -
                    now
                ).total_seconds()
            ),
            0
        )

    except (
        TypeError,
        ValueError,
        OverflowError
    ):

        return None


def retry_delay(
    attempt,
    response=None
):
    """Determine retry delay."""

    if response is not None:

        header_delay = retry_after_seconds(
            response
        )

        if header_delay is not None:

            return min(
                header_delay,
                120
            )

    index = min(
        attempt - 1,
        len(
            BACKOFF_SECONDS
        ) - 1
    )

    return BACKOFF_SECONDS[
        index
    ]


# ============================================================
# CLIENT
# ============================================================

class CFBDClient:
    """Shared Project Gridiron CFBD client."""

    def __init__(
        self,
        base_url=BASE_URL
    ):

        self.base_url = (
            base_url.rstrip(
                "/"
            )
        )

        self.session = (
            requests.Session()
        )

    # ========================================================
    # AUTH
    # ========================================================

    def api_key(self):
        """Return CFBD API key."""

        api_key = os.getenv(
            "CFBD_API_KEY"
        )

        if not api_key:

            raise ValueError(
                "CFBD_API_KEY environment variable is not set."
            )

        return api_key

    def headers(self):
        """Return authenticated headers."""

        return {
            "Authorization":
                f"Bearer {self.api_key()}",

            "Accept":
                "application/json",
        }

    # ========================================================
    # USAGE
    # ========================================================

    def get_usage(self):
        """
        Fetch current API usage information.

        /info:
            - bypasses response cache
            - bypasses per-run request budget
        """

        url = (
            self.base_url
            +
            INFO_ENDPOINT
        )

        try:

            response = self.session.get(
                url,
                headers=self.headers(),
                timeout=30,
            )

        except requests.RequestException as error:

            print(
                "WARNING: Could not check CFBD usage:"
            )

            print(
                f"  {error}"
            )

            return None

        if response.status_code != 200:

            print(
                "WARNING: CFBD usage check returned "
                f"HTTP {response.status_code}."
            )

            return None

        data = safe_json(
            response
        )

        if not isinstance(
            data,
            dict
        ):

            return None

        return data

    def ensure_quota_available(self):
        """
        Check monthly quota before a real CFBD data request.

        Cache hits never reach this method.
        """

        usage = self.get_usage()

        if not usage:

            return

        remaining = safe_int(
            usage.get(
                "remainingCalls"
            ),
            default=None,
        )

        if remaining is None:

            return

        if remaining <= 0:

            raise RuntimeError(
                "\n"
                "CFBD API MONTHLY QUOTA EXHAUSTED\n"
                "--------------------------------\n"
                f"Monthly limit: "
                f"{usage.get('monthlyLimit')}\n"
                f"Used calls: "
                f"{usage.get('usedCalls')}\n"
                f"Remaining calls: "
                f"{usage.get('remainingCalls')}\n"
                f"Reset at: "
                f"{usage.get('resetAt')}\n"
                "\n"
                "No football-data request was attempted.\n"
                "Use cached data or wait for the quota reset."
            )

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        endpoint,
        params=None,
        use_cache=True,
        **query_params
    ):
        """
        Perform authenticated CFBD GET request.

        Supported patterns:

            client.get("/teams/fbs")

            client.get(
                "/games",
                {"year": 2025}
            )

            client.get(
                "/games",
                params={"year": 2025}
            )

            client.get(
                "/games",
                year=2025
            )
        """

        endpoint = normalize_endpoint(
            endpoint
        )

        params = normalize_params(
            params
        )

        if query_params:

            params.update(
                normalize_params(
                    query_params
                )
            )

        # ----------------------------------------------------
        # INFO
        # ----------------------------------------------------

        if endpoint == INFO_ENDPOINT:

            usage = self.get_usage()

            if usage is None:

                raise RuntimeError(
                    "Unable to retrieve CFBD API usage."
                )

            return usage

        # ----------------------------------------------------
        # CACHE POLICY DIAGNOSTIC
        # ----------------------------------------------------

        print_cache_policy(
            endpoint,
            params,
        )

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        if use_cache:

            cached = read_cache(
                endpoint,
                params,
            )

            if cached is not None:

                print(
                    f"CACHE HIT: "
                    f"{endpoint}"
                )

                if params:

                    print(
                        f"  params="
                        f"{params}"
                    )

                return cached

        # ----------------------------------------------------
        # MONTHLY QUOTA CHECK
        # ----------------------------------------------------

        self.ensure_quota_available()

        # ----------------------------------------------------
        # REAL HTTP REQUEST
        # ----------------------------------------------------

        url = (
            self.base_url
            +
            endpoint
        )

        for attempt in range(
            1,
            MAX_ATTEMPTS + 1
        ):

            # Every real HTTP attempt counts against the
            # persisted per-run request budget.

            register_request(
                endpoint,
                params,
            )

            print(
                f"CFBD REQUEST: "
                f"{endpoint}"
            )

            if params:

                print(
                    f"  params="
                    f"{params}"
                )

            print(
                f"  attempt="
                f"{attempt}/"
                f"{MAX_ATTEMPTS}"
            )

            try:

                response = self.session.get(
                    url,
                    headers=self.headers(),
                    params=params,
                    timeout=60,
                )

            except requests.RequestException as error:

                if attempt >= MAX_ATTEMPTS:

                    raise RuntimeError(
                        "CFBD request failed after "
                        "repeated network errors."
                    ) from error

                delay = retry_delay(
                    attempt
                )

                print(
                    f"Network error: "
                    f"{error}"
                )

                print(
                    f"Retrying in "
                    f"{delay} seconds."
                )

                time.sleep(
                    delay
                )

                continue

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:

                data = safe_json(
                    response
                )

                if data is None:

                    raise ValueError(
                        "CFBD returned invalid JSON."
                    )

                remaining_header = (
                    response.headers.get(
                        "X-CallLimit-Remaining"
                    )
                )

                if remaining_header is not None:

                    print(
                        "CFBD remaining calls: "
                        f"{remaining_header}"
                    )

                if use_cache:

                    write_cache(
                        endpoint,
                        params,
                        data,
                    )

                return data

            # ------------------------------------------------
            # 429
            # ------------------------------------------------

            if response.status_code == 429:

                body = safe_json(
                    response
                )

                print(
                    "CFBD returned HTTP 429 "
                    "Too Many Requests."
                )

                remaining = (
                    response.headers.get(
                        "X-CallLimit-Remaining"
                    )
                )

                if remaining is not None:

                    print(
                        f"Remaining calls: "
                        f"{remaining}"
                    )

                if body is not None:

                    print(
                        json.dumps(
                            body,
                            indent=2,
                        )
                    )

                usage = self.get_usage()

                if isinstance(
                    usage,
                    dict
                ):

                    remaining_calls = safe_int(
                        usage.get(
                            "remainingCalls"
                        ),
                        default=None,
                    )

                    if (
                        remaining_calls is not None
                        and
                        remaining_calls <= 0
                    ):

                        raise RuntimeError(
                            "\n"
                            "CFBD API MONTHLY QUOTA EXHAUSTED\n"
                            "--------------------------------\n"
                            f"Monthly limit: "
                            f"{usage.get('monthlyLimit')}\n"
                            f"Used calls: "
                            f"{usage.get('usedCalls')}\n"
                            f"Remaining calls: "
                            f"{usage.get('remainingCalls')}\n"
                            f"Reset at: "
                            f"{usage.get('resetAt')}\n"
                        )

                if attempt >= MAX_ATTEMPTS:

                    response.raise_for_status()

                delay = retry_delay(
                    attempt,
                    response,
                )

                print(
                    f"Temporary rate limit. "
                    f"Retrying in "
                    f"{delay} seconds."
                )

                time.sleep(
                    delay
                )

                continue

            # ------------------------------------------------
            # SERVER ERROR
            # ------------------------------------------------

            if response.status_code >= 500:

                if attempt >= MAX_ATTEMPTS:

                    response.raise_for_status()

                delay = retry_delay(
                    attempt,
                    response,
                )

                print(
                    f"CFBD server error "
                    f"{response.status_code}. "
                    f"Retrying in "
                    f"{delay} seconds."
                )

                time.sleep(
                    delay
                )

                continue

            # ------------------------------------------------
            # OTHER ERROR
            # ------------------------------------------------

            body = safe_json(
                response
            )

            if body is not None:

                print(
                    json.dumps(
                        body,
                        indent=2,
                    )
                )

            response.raise_for_status()

        raise RuntimeError(
            "CFBD request ended unexpectedly."
        )


# ============================================================
# SHARED CLIENT
# ============================================================

client = CFBDClient()
