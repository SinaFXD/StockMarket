import pytest
import requests
from conftest import FakeResponse, FakeSession

from pipeline.http import FetchError, HttpClient, redact


def client(responses, **kw):
    slept = []
    c = HttpClient(session=FakeSession(responses), sleep=slept.append, **kw)
    return c, slept


def test_redact_hides_key_parameters_and_secret_values():
    text = "GET https://api.stlouisfed.org/fred/series?series_id=X&api_key=abc123def456&file_type=json"
    assert redact(text) == "GET https://api.stlouisfed.org/fred/series?series_id=X&api_key=***&file_type=json"
    assert redact("boom TOPSECRET999 boom", ["TOPSECRET999"]) == "boom *** boom"


def test_redact_uses_the_fred_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "envsecret123")
    assert "envsecret123" not in redact("failed for envsecret123")


def test_retries_server_errors_then_succeeds():
    c, slept = client([FakeResponse(503, {"x": 1}), FakeResponse(200, {"ok": True})])
    assert c.get_json("https://example.org") == {"ok": True}
    assert c.requests_made == 2
    assert slept  # backed off before the second attempt


def test_non_json_responses_are_retried_then_reported():
    c, _ = client([FakeResponse(200, None, text="<html>maintenance</html>")], retries=2)
    with pytest.raises(FetchError, match="not JSON"):
        c.get_json("https://example.org")
    assert c.requests_made == 3


def test_client_errors_are_not_retried_and_keep_the_source_message():
    c, _ = client([FakeResponse(400, {"error_code": 400, "error_message": "The series does not exist."})])
    with pytest.raises(FetchError, match="series does not exist"):
        c.get_json("https://example.org")
    assert c.requests_made == 1


def test_network_errors_never_leak_the_key():
    err = requests.ConnectionError("cannot reach https://api.stlouisfed.org/x?api_key=SUPERSECRETKEY1")
    c, _ = client([err], retries=1, secrets=["SUPERSECRETKEY1"])
    with pytest.raises(FetchError) as info:
        c.get_json("https://example.org")
    assert "SUPERSECRETKEY1" not in str(info.value)
    assert "network error" in str(info.value)


def test_retry_after_header_is_respected():
    c, slept = client([FakeResponse(429, {}, headers={"Retry-After": "7"}), FakeResponse(200, [1])])
    assert c.get_json("https://example.org") == [1]
    assert 7 in slept


def test_sends_the_dashboard_user_agent_not_the_requests_default():
    import requests as rq

    c = HttpClient(session=rq.Session())
    assert c.session.headers["User-Agent"].startswith("PTM-Fundamental-Dashboard")
    custom = rq.Session()
    custom.headers["User-Agent"] = "my-agent"
    assert HttpClient(session=custom).session.headers["User-Agent"] == "my-agent"
