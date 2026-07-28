"""Small client for the existing DMLF asynchronous HTTP bridge."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.core.config import get_settings


def _request(path: str, method: str = "GET", payload: dict | None = None, timeout: int = 15) -> dict:
    endpoint = get_settings().dmlf_bridge_endpoint
    if not endpoint:
        raise RuntimeError("DMLF_BRIDGE_ENDPOINT is not configured")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(urljoin(endpoint.rstrip("/") + "/", path.lstrip("/")), data=body, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - configured bridge endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DMLF bridge returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"DMLF bridge is unreachable: {error.reason}") from error


def submit(experiment: dict) -> dict:
    response = _request("/execute", method="POST", payload={"experiment": experiment})
    if not response.get("jobId"):
        raise RuntimeError("DMLF bridge did not return a jobId")
    return response


def status(job_id: str) -> dict:
    return _request(f"/jobs/{job_id}")


def cancel(job_id: str) -> dict:
    return _request(f"/jobs/{job_id}/cancel", method="POST")


def health() -> dict:
    return _request("/health", timeout=3)
