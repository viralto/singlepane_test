"""
Enterpryze API client.

Built against the field-level attribute export in the attribute mapping
workbook (Authenticate, Business partner, Sales invoice objects). The
exact endpoint paths were not in that export, only the object/field
shapes, so the paths below are the standard REST convention and should
be confirmed once access is enabled (this is Q20/Q21 on the tracker:
read/write scope and whether webhooks exist, still open).

Auth: POST username/password to the login endpoint, receive a
surferAuth token plus surferOrganisationId, used for subsequent calls.
Fill in ENTERPRYZE_BASE_URL / ENTERPRYZE_USERNAME / ENTERPRYZE_PASSWORD
(env vars, or pass directly) once enabled. Nothing here runs until those
are set.
"""
import os
import requests


class EnterpryzeClient:
    def __init__(self, base_url=None, username=None, password=None):
        self.base_url = (base_url or os.environ.get("ENTERPRYZE_BASE_URL", "")).rstrip("/")
        self.username = username or os.environ.get("ENTERPRYZE_USERNAME", "")
        self.password = password or os.environ.get("ENTERPRYZE_PASSWORD", "")
        self._auth = None  # {surferAuth, surferAuthExpires, surferOrganisationId}

    @property
    def configured(self):
        return bool(self.base_url and self.username and self.password)

    def authenticate(self):
        """POST to Authenticate: login/password in, surferAuth token out."""
        r = requests.post(
            f"{self.base_url}/authenticate",
            json={"username": self.username, "password": self.password},
            timeout=20,
        )
        r.raise_for_status()
        self._auth = r.json()
        return self._auth

    def _headers(self):
        if not self._auth:
            self.authenticate()
        return {"Authorization": f"Bearer {self._auth['surferAuth']}"}

    def list_business_partners(self):
        """GET business partners. cardCode is the primary key (settable on create)."""
        r = requests.get(f"{self.base_url}/business-partners", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def get_business_partner(self, card_code):
        r = requests.get(f"{self.base_url}/business-partners/{card_code}", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def list_sales_invoices(self, card_code=None):
        """GET sales invoices, optionally filtered by bpCode/cardCode."""
        params = {"bpCode": card_code} if card_code else {}
        r = requests.get(f"{self.base_url}/sales-invoices", headers=self._headers(), params=params, timeout=20)
        r.raise_for_status()
        return r.json()
