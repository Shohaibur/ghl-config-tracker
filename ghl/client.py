"""Read-only GoHighLevel API client.

Only GET requests exist in this file, on purpose: this tool never changes
anything in GHL. Token and location ID come from environment variables
(or a local .env file), never from the code.
"""

import os

import requests
from dotenv import load_dotenv

BASE_URL = "https://services.leadconnectorhq.com"
API_VERSION = "2021-07-28"


class GHLError(Exception):
    """Any problem talking to GHL (missing settings, bad token, network...)."""


class GHLClient:
    def __init__(self, token: str | None = None, location_id: str | None = None, timeout: int = 30):
        load_dotenv()  # reads .env into environment variables, if the file exists
        self.token = token or os.getenv("GHL_TOKEN")
        self.location_id = location_id or os.getenv("GHL_LOCATION_ID")
        if not self.token:
            raise GHLError("Missing GHL_TOKEN. Add it to your .env file.")
        if not self.location_id:
            raise GHLError("Missing GHL_LOCATION_ID. Add it to your .env file.")

        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Version": API_VERSION,
            "Accept": "application/json",
        })

    def get(self, path: str, params: dict | None = None) -> dict:
        """Send one GET request and return the JSON body."""
        try:
            r = self.session.get(BASE_URL + path, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise GHLError(f"Network error on GET {path}: {e}") from e
        if not r.ok:
            raise GHLError(f"GET {path} failed ({r.status_code}): {r.text[:300]}")
        return r.json()
