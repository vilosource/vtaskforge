import requests


class VTFAPIError(Exception):
    def __init__(self, status_code, error_data):
        self.status_code = status_code
        self.error_data = error_data
        if isinstance(error_data, dict):
            msg = error_data.get("error", {}).get("message", str(error_data))
        else:
            msg = str(error_data)
        super().__init__(msg)


class VTFClient:
    def __init__(self, api_url, token=None):
        self.api_url = api_url.rstrip("/")
        self.token = token

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Token {self.token}"
        return h

    def _request(self, method, path, data=None, params=None):
        url = f"{self.api_url}{path}"
        resp = requests.request(
            method, url, json=data, params=params, headers=self._headers()
        )
        if resp.status_code >= 400:
            try:
                error_data = resp.json()
            except Exception:
                error_data = {"error": {"message": resp.text}}
            raise VTFAPIError(resp.status_code, error_data)
        return resp.json() if resp.content else {}

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, data=None):
        return self._request("POST", path, data)

    def patch(self, path, data=None):
        return self._request("PATCH", path, data)

    def delete(self, path):
        return self._request("DELETE", path)

    def get_list(self, path, params=None):
        """GET a list endpoint, handling both paginated and flat responses."""
        data = self.get(path, params=params)
        return unwrap_list(data)

    def health(self):
        return self.get("/v1/health")


def unwrap_list(data):
    """Extract list from paginated or flat response."""
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    return []
