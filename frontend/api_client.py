"""Small wrapper around the FarmLink REST API. Returns (ok, data_or_error_message)."""
import os

import requests
from flask import session

API_URL = os.environ.get("API_URL", "http://localhost:8000")


def api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    token = session.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=10, **kwargs)
    except requests.RequestException:
        return False, "Cannot reach the server. Is the backend running?"

    try:
        data = response.json()
    except ValueError:
        data = None

    if response.ok:
        return True, data

    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, list):  # validation errors from FastAPI
        detail = "; ".join(f"{'.'.join(str(p) for p in d.get('loc', [])[1:])}: {d.get('msg', 'invalid')}" for d in detail)
    return False, detail or f"Request failed ({response.status_code})"
