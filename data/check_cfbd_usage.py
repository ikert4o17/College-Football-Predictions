"""
Project Gridiron
CFBD API Usage Diagnostic

Checks the current CFBD API key/account status without running
the Project Gridiron data pipeline.

Usage:
    python -m data.check_cfbd_usage
"""

import json
import os
import sys

import requests


BASE_URL = "https://api.collegefootballdata.com"
INFO_ENDPOINT = "/info"


def get_api_key():
    """Load CFBD API key from environment."""

    api_key = os.getenv("CFBD_API_KEY")

    if not api_key:
        raise ValueError(
            "CFBD_API_KEY environment variable is not set."
        )

    return api_key


def main():
    """Check CFBD API account and usage information."""

    api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    url = f"{BASE_URL}{INFO_ENDPOINT}"

    print("=" * 76)
    print("CFBD API USAGE DIAGNOSTIC")
    print("=" * 76)
    print()
    print(f"GET {INFO_ENDPOINT}")

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as error:
        print()
        print(f"Request failed: {error}")
        sys.exit(1)

    print(f"Status code: {response.status_code}")

    # ------------------------------------------------------------
    # Useful rate-limit headers
    # ------------------------------------------------------------

    print()
    print("RATE-LIMIT HEADERS")
    print("-" * 76)

    interesting_headers = [
        "X-CallLimit-Limit",
        "X-CallLimit-Remaining",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "Retry-After",
    ]

    found_header = False

    for header in interesting_headers:
        value = response.headers.get(header)

        if value is not None:
            found_header = True
            print(f"{header}: {value}")

    if not found_header:
        print("No recognized rate-limit headers returned.")

    # ------------------------------------------------------------
    # Response body
    # ------------------------------------------------------------

    print()
    print("RESPONSE")
    print("-" * 76)

    try:
        payload = response.json()

        print(
            json.dumps(
                payload,
                indent=4,
            )
        )

    except ValueError:
        print(response.text)

    # ------------------------------------------------------------
    # Interpretation
    # ------------------------------------------------------------

    print()
    print("INTERPRETATION")
    print("-" * 76)

    if response.status_code == 200:
        print("CFBD accepted the API key.")
        print(
            "Inspect the usage information above for the "
            "remaining monthly allowance."
        )

    elif response.status_code == 401:
        print(
            "CFBD rejected the API key. Check the GitHub "
            "CFBD_API_KEY secret."
        )

    elif response.status_code == 403:
        print(
            "The API key authenticated but does not have "
            "access to this resource."
        )

    elif response.status_code == 429:
        print(
            "CFBD is rate-limiting this API key/account."
        )
        print(
            "Inspect the response body and headers above "
            "for quota or reset information."
        )

    else:
        print(
            "CFBD returned an unexpected status. Inspect "
            "the response above before changing the pipeline."
        )

    # Don't fail the GitHub Action merely because the diagnostic
    # discovered a quota problem.
    sys.exit(0)


if __name__ == "__main__":
    main()
