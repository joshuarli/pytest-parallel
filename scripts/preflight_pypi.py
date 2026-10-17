"""Verify PyPI is reachable and the release token authenticates before publishing.

Authenticating a token requires an attempt at the upload endpoint: PyPI answers an
invalid token with 403 and a valid one with 400, because the request body is a stub
that is never accepted. Nothing is uploaded.
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_URL = "https://upload.pypi.org/legacy/"


def fail(message: str) -> None:
    sys.stdout.flush()
    print(f"preflight: {message}", file=sys.stderr)
    raise SystemExit(1)


def project_name() -> str:
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    return data["project"]["name"]


def check_index(name: str, next_version: str | None) -> None:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            print(f"preflight: {name} is not on PyPI yet")
            return
        fail(f"{url} returned HTTP {error.code}")
    except urllib.error.URLError as error:
        fail(f"cannot reach pypi.org: {error.reason}")
    releases = payload.get("releases", {})
    if next_version is not None and next_version in releases:
        fail(f"{name} {next_version} is already on PyPI; bump past it before publishing")
    print(f"preflight: pypi.org reachable, {name} has {len(releases)} published release(s)")


def check_token(token: str, name: str) -> None:
    boundary = "----pytest-parallel-preflight"
    fields = {
        ":action": "file_upload",
        "protocol_version": "1",
        "name": name,
        "version": "0.0.0",
        "filetype": "sdist",
    }
    body = b"".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        for key, value in fields.items()
    ) + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(UPLOAD_URL, data=body, method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(request, timeout=20):
            pass
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            fail("PyPI rejected UV_PUBLISH_PASSWORD (HTTP 401/403); the token is invalid or expired")
        if error.code != 400:
            fail(f"{UPLOAD_URL} returned HTTP {error.code}")
    except urllib.error.URLError as error:
        fail(f"cannot reach upload.pypi.org: {error.reason}")
    print("preflight: PyPI accepted UV_PUBLISH_PASSWORD")


def main() -> None:
    token = os.environ.get("UV_PUBLISH_PASSWORD", "")
    if not token:
        fail("UV_PUBLISH_PASSWORD is not set")
    name = project_name()
    next_version = sys.argv[1] if len(sys.argv) > 1 else None
    check_index(name, next_version)
    check_token(token, name)
    print("preflight: ok")


if __name__ == "__main__":
    main()
