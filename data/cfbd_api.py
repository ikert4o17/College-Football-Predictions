"""
Project Gridiron
Shared CFBD API Client

Centralized CollegeFootballData API access.

Goals:
    - avoid unnecessary repeat API calls
    - cache successful GET responses
    - reuse historical data indefinitely
    - use a short cache for current/no-year requests
    - expose FORCE_CFBD_REFRESH override
    - detect exhausted API quota before wasting requests
    - retry temporary 429 / server failures
    - print whether data came from CACHE or CFBD

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
        Disable request caching.

    CFBD_CACHE_TTL_SECONDS=3600
        Cache lifetime for current-season / non-season requests.

Historical requests where year < current calendar year are treated
as effectively permanent unless FORCE_CFBD_REFRESH is enabled.

Cache directory:

    data/cache/cfbd/

IMPORTANT:
For GitHub Actions to reuse this cache between workflow runs,
data/cache/cfbd must eventually be committed or otherwise persisted.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests


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

DEFAULT_CURRENT_CACHE_TTL = 3600

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

def env_truthy(name, default=False):
    """Read a boolean-style environment variable."""

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


def current_cache_ttl():
    """Return cache TTL for current/no-year requests."""

    value = os.getenv(
        "CFBD_CACHE_TTL_SECONDS"
    )

    if not value:
        return DEFAULT_CURRENT_CACHE_TTL

    try:

        ttl = int(
            value
        )

    except ValueError:

        return DEFAULT_CURRENT_CACHE_TTL

    return max(
        ttl,
        0
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


# ============================================================
# CACHE
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
    """Return path for cached response."""

    key = cache_key(
        endpoint,
        params
    )

    return (
        CACHE_DIRECTORY
        /
        f"{key}.json"
    )


def request_year(params):
    """Attempt to identify season year from request."""

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


def historical_request(params):
    """
    Return whether request is for a completed calendar season.

    Historical season data is considered stable and may be cached
    indefinitely.
    """

    year = request_year(
        params
    )

    if year is None:
        return False

    current_year = datetime.now(
        timezone.utc
    ).year

    return (
        year
        <
        current_year
    )


def read_cache(
    endpoint,
    params
):
    """Read valid cached response if available."""

    if not cache_enabled():

        return None

    if force_refresh_enabled():

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

    # Historical requests do not expire.

    if historical_request(
        params
    ):

        return payload[
            "data"
        ]

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

    if (
        age
        >
        current_cache_ttl()
    ):

        return None

    return payload[
        "data"
    ]


def write_cache(
    endpoint,
    params,
    data
):
    """Persist successful CFBD response."""

    if not cache_enabled():

        return

    if endpoint == INFO_ENDPOINT:

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

        self._usage_checked = False

        self._remaining_calls = None

        self._monthly_limit = None

        self._used_calls = None

        self._reset_at = None

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

        This request bypasses normal response caching.
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

        self._usage_checked = True

        self._remaining_calls = data.get(
            "remainingCalls"
        )

        self._monthly_limit = data.get(
            "monthlyLimit"
        )

        self._used_calls = data.get(
            "usedCalls"
        )

        self._reset_at = data.get(
            "resetAt"
        )

        return data

    def ensure_quota_available(self):
        """
        Check API quota before making a real CFBD request.

        Cache hits never reach this method.
        """

        usage = self.get_usage()

        if not usage:

            return

        remaining = usage.get(
            "remainingCalls"
        )

        if remaining is None:

            return

        try:

            remaining = int(
                remaining
            )

        except (
            TypeError,
            ValueError
        ):

            return

        if remaining <= 0:

            reset_at = usage.get(
                "resetAt"
            )

            monthly_limit = usage.get(
                "monthlyLimit"
            )

            used_calls = usage.get(
                "usedCalls"
            )

            raise RuntimeError(
                "\n"
                "CFBD API MONTHLY QUOTA EXHAUSTED\n"
                "--------------------------------\n"
                f"Monthly limit: {monthly_limit}\n"
                f"Used calls: {used_calls}\n"
                f"Remaining calls: {remaining}\n"
                f"Reset at: {reset_at}\n"
                "\n"
                "No CFBD data request was attempted.\n"
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

        Backward-compatible examples:

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
        # INFO endpoint
        # ----------------------------------------------------

        if endpoint == INFO_ENDPOINT:

            usage = self.get_usage()

            if usage is None:

                raise RuntimeError(
                    "Unable to retrieve CFBD API usage."
                )

            return usage

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        if use_cache:

            cached = read_cache(
                endpoint,
                params
            )

            if cached is not None:

                print(
                    f"CACHE HIT: "
                    f"{endpoint}"
                )

                if params:

                    print(
                        f"  params={params}"
                    )

                return cached

        # ----------------------------------------------------
        # QUOTA CHECK
        # ----------------------------------------------------

        self.ensure_quota_available()

        # ----------------------------------------------------
        # REQUEST
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

            print(
                f"CFBD REQUEST: "
                f"{endpoint}"
            )

            if params:

                print(
                    f"  params={params}"
                )

            print(
                f"  attempt="
                f"{attempt}/{MAX_ATTEMPTS}"
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
                        data
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

                # Re-check actual quota before retrying.

                usage = self.get_usage()

                if (
                    isinstance(
                        usage,
                        dict
                    )
                    and
                    safe_int(
                        usage.get(
                            "remainingCalls"
                        )
                    )
                    <= 0
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
                    f"Retrying in {delay} seconds."
                )

                time.sleep(
                    delay
                )

                continue

            # ------------------------------------------------
            # SERVER ERROR
            # ------------------------------------------------

            if (
                response.status_code
                >= 500
            ):

                if attempt >= MAX_ATTEMPTS:

                    response.raise_for_status()

                delay = retry_delay(
                    attempt,
                    response,
                )

                print(
                    f"CFBD server error "
                    f"{response.status_code}. "
                    f"Retrying in {delay} seconds."
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
# SMALL SAFE INTEGER HELPER
# ============================================================

def safe_int(value):
    """Safely convert value to integer."""

    if value is None:
        return 0

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return 0


# ============================================================
# SHARED CLIENT
# ============================================================

client = CFBDClient()
