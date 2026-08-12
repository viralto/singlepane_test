"""
VTAP Cloud API client.

Built directly against the VTAP Cloud OpenAPI spec (vtap_cloud_API.txt).
Auth: header 'X-KEY' (an API key generated in VTAP Cloud management).
Fill in VTAP_BASE_URL and VTAP_API_KEY (env vars, or pass directly) once
the QA credentials are available. Nothing here runs until those are set.
"""
import os
import requests


class VTAPClient:
    def __init__(self, base_url=None, api_key=None):
        self.base_url = (base_url or os.environ.get("VTAP_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("VTAP_API_KEY", "")

    @property
    def configured(self):
        return bool(self.base_url and self.api_key)

    def _get(self, path, params=None):
        headers = {"X-KEY": self.api_key}
        r = requests.get(f"{self.base_url}{path}", headers=headers, params=params or {}, timeout=20)
        r.raise_for_status()
        return r.json()

    def list_customers(self):
        """GET /cust/list -> visible customer records."""
        return self._get("/cust/list")

    def get_customer(self, cid):
        """GET /cust/{cid} -> single customer record."""
        return self._get(f"/cust/{cid}")

    def list_readers(self, params=None):
        """GET /reader/list -> full de-referenced reader records (customer, application, config resolved)."""
        return self._get("/reader/list", params=params)

    def readers_for_fleet(self, fid):
        """GET /fleet/readers/{fid} -> readers assigned to a given Fleet."""
        return self._get(f"/fleet/readers/{fid}")

    def readers_with_no_fleet(self):
        """GET /fleet/readers/nofleet -> readers not currently assigned to any Fleet."""
        return self._get("/fleet/readers/nofleet")
