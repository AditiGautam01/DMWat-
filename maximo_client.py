"""
Maximo REST API client for work order and asset data retrieval.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class MaximoClient:
    def __init__(self):
        self.base_url = os.getenv("MAXIMO_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("MAXIMO_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": self.api_key,
            "Content-Type": "application/json",
        })

    def _get(self, resource: str, params: dict = None) -> dict:
        """Generic GET against the Maximo OSLC/JSON API."""
        if not self.base_url:
            raise ValueError("MAXIMO_BASE_URL is not configured in .env")
            
        url = f"{self.base_url}/oslc/os/{resource}"
        
        # When mocking or testing without real maximo, disable SSL verification warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        try:
            resp = self.session.get(url, params=params or {}, verify=False)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            # Provide helpful context for authentication and connectivity issues
            error_msg = f"Maximo connection failed: {str(e)}"
            if getattr(e, 'response', None) is not None:
                if e.response.status_code == 401:
                    error_msg = "Maximo authentication failed: Invalid API Key"
                elif e.response.status_code == 404:
                    error_msg = f"Maximo resource '{resource}' not found"
            raise ValueError(error_msg)

    def get_work_orders(self, limit: int = 50) -> list[dict]:
        """Fetch recent work orders."""
        data = self._get("mxwo", params={
            "oslc.pageSize": limit,
            "oslc.select": "wonum,description,status,reportdate,assetnum,location",
            "oslc.orderBy": "-reportdate",
        })
        return data.get("member", [])

    def get_assets(self, limit: int = 50) -> list[dict]:
        """Fetch assets."""
        data = self._get("mxasset", params={
            "oslc.pageSize": limit,
            "oslc.select": "assetnum,description,status,location,manufacturer",
        })
        return data.get("member", [])

    def get_service_requests(self, limit: int = 50) -> list[dict]:
        """Fetch service requests (tickets)."""
        data = self._get("mxsr", params={
            "oslc.pageSize": limit,
            "oslc.select": "ticketid,description,status,reportdate,reportedby",
            "oslc.orderBy": "-reportdate",
        })
        return data.get("member", [])

    def get_work_order(self, wonum: str) -> dict:
        """Fetch a single work order by number."""
        data = self._get("mxwo", params={
            "oslc.where": f'wonum="{wonum}"',
            "oslc.select": "*",
        })
        members = data.get("member", [])
        return members[0] if members else {}
