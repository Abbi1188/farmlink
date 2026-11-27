"""Small wrapper around the FarmBridge REST API. Returns (ok, data_or_error_message).

Speed notes:
- One shared HTTP session keeps connections open, so each call does not set up a new connection.
- The default address is 127.0.0.1, not "localhost". On Windows, "localhost" can try IPv6 first and
  add a delay to every call.
- api_many() runs several calls at the same time, so a page that needs 3 things waits for the
  slowest one instead of for all three one after another.
"""
import os
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import session
from requests.adapters import HTTPAdapter

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

_http = requests.Session()
_http.mount("http://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
_http.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
_pool = ThreadPoolExecutor(max_workers=8)


def _call(method: str, path: str, token, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = _http.request(method, f"{API_URL}{path}", headers=headers, timeout=10, **kwargs)
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


def fetch_media(path: str):
    """Download one uploaded picture from the API, so the browser only ever talks to this website.
    Returns (bytes, content_type), or None when the picture is not there."""
    try:
        response = _http.get(f"{API_URL}/uploads/{path}", timeout=10)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    return response.content, response.headers.get("Content-Type", "application/octet-stream")


def api(method: str, path: str, **kwargs):
    return _call(method, path, session.get("token"), **kwargs)


def api_many(*calls):
    """Run several calls at once. Each call is (method, path) or (method, path, {requests options}).
    Returns a list of (ok, data) in the same order."""
    token = session.get("token")  # read here: worker threads cannot see the Flask session
    futures = [_pool.submit(_call, c[0], c[1], token, **(c[2] if len(c) > 2 else {})) for c in calls]
    return [f.result() for f in futures]
