"""
CollegeFootballData API Client

Handles communication with the CollegeFootballData API.
"""

import os
import requests


BASE_URL = "https://api.collegefootballdata.com"


class CFBDClient:
    """Client for interacting with the CFBD API."""

    def __init__(self):
        self.api_key = os.getenv("CFBD_API_KEY")

        if not self.api_key:
            raise ValueError(
                "CFBD_API_KEY environment variable is not set."
            )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

    def get(self, endpoint, params=None):
        """Send a GET request to the CFBD API."""

        url = f"{BASE_URL}{endpoint}"

        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()
