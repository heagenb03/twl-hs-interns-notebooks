"""Offline unit tests for the hardened fetch_headlines retry/merge logic.

No live network calls: `requests.get` and `time.sleep` are monkeypatched.
"""
from __future__ import annotations

import json
import sys

import pytest
import requests

import fetch_headlines as fh


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code: int = 200, text: str = "{}"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self):
        return json.loads(self.text)


ARTICLES_JSON = json.dumps(
    {
        "articles": [
            {
                "title": "A",
                "url": "http://x",
                "domain": "nytimes.com",
                "seendate": "20200115",
            }
        ]
    }
)


@pytest.fixture()
def no_sleep(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(fh.time, "sleep", lambda s: calls.append(s))
    return calls


def test_429_then_success_retries_and_returns_articles(monkeypatch, no_sleep):
    responses = [FakeResponse(429, "rate limited"), FakeResponse(200, ARTICLES_JSON)]
    monkeypatch.setattr(fh.requests, "get", lambda *a, **k: responses.pop(0))

    result = fh.fetch_one("NYT", "2020-01-15", "2020-01-22")

    assert result == [
        {"title": "A", "url": "http://x", "domain": "nytimes.com", "seendate": "20200115"}
    ]
    assert no_sleep == [20.0]


def test_non_json_body_is_treated_as_throttle_and_retried(monkeypatch, no_sleep):
    responses = [
        FakeResponse(200, "Request was throttled, try later"),
        FakeResponse(200, ARTICLES_JSON),
    ]
    monkeypatch.setattr(fh.requests, "get", lambda *a, **k: responses.pop(0))

    result = fh.fetch_one("NYT", "2020-01-15", "2020-01-22")

    assert len(result) == 1
    assert no_sleep == [20.0]


def test_exhausting_all_retries_raises_instead_of_returning_empty(monkeypatch, no_sleep):
    monkeypatch.setattr(fh.requests, "get", lambda *a, **k: FakeResponse(429, "rate limited"))

    with pytest.raises(Exception):
        fh.fetch_one("NYT", "2020-01-15", "2020-01-22")

    assert no_sleep == [20.0, 40.0, 80.0, 160.0]


def test_genuine_empty_success_returns_empty_list_without_raising(monkeypatch, no_sleep):
    monkeypatch.setattr(fh.requests, "get", lambda *a, **k: FakeResponse(200, '{"articles": []}'))

    result = fh.fetch_one("NYT", "2020-01-15", "2020-01-22")

    assert result == []
    assert no_sleep == []


def test_fetch_all_skips_cached_ok_cell_and_leaves_it_untouched(monkeypatch):
    event = "Test Event"
    outlet = "NYT"
    events = ((event, "2020-01-01", "2020-01-02"),)
    outlets = (outlet,)
    data = {event: {outlet: [{"title": "old-good-article"}]}}
    status = {event: {outlet: "ok"}}

    def boom(*_a, **_k):
        raise AssertionError("fetch_one must not be called for an already-ok cell")

    monkeypatch.setattr(fh, "fetch_one", boom)
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert new_data[event][outlet] == [{"title": "old-good-article"}]
    assert new_status[event][outlet] == "ok"


def test_fetch_all_error_does_not_overwrite_previous_good_data(monkeypatch):
    event = "Test Event"
    good_outlet, retry_outlet = "NYT", "WSJ"
    events = ((event, "2020-01-01", "2020-01-02"),)
    outlets = (good_outlet, retry_outlet)

    data = {event: {good_outlet: [{"title": "kept"}]}}
    status = {event: {good_outlet: "ok", retry_outlet: "error: previous failure"}}

    def fake_fetch_one(outlet: str, _start: str, _end: str) -> list[dict]:
        assert outlet == retry_outlet
        raise RuntimeError("still throttled")

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert new_data[event][good_outlet] == [{"title": "kept"}]
    assert retry_outlet not in new_data[event]
    assert new_status[event][retry_outlet] == "error: still throttled"


def test_fetch_all_records_genuine_empty_result_as_ok(monkeypatch):
    event = "Test Event"
    outlet = "NYT"
    events = ((event, "2020-01-01", "2020-01-02"),)
    outlets = (outlet,)
    data: dict = {}
    status: dict = {}

    monkeypatch.setattr(fh, "fetch_one", lambda _outlet, _start, _end: [])
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert new_data[event][outlet] == []
    assert new_status[event][outlet] == "ok"


def test_fetch_all_failed_retry_on_cell_with_existing_data_keeps_ok_status(monkeypatch):
    """Defect 2: status describes trustworthiness of cached data, not the

    outcome of the most recent attempt. A cell that already holds 250 good
    articles from an earlier successful sweep must not have its status
    downgraded to "error" just because a later resume attempt got throttled.
    """
    event = "Phase One deal"
    outlet = "Xinhua"
    events = ((event, "2020-01-15", "2020-01-22"),)
    outlets = (outlet,)

    good_articles = [{"title": f"article-{i}"} for i in range(250)]
    data = {event: {outlet: good_articles}}
    status = {event: {outlet: "error: 429 Too Many Requests for Xinhua 2020-01-15"}}

    def fake_fetch_one(*_a, **_k):
        raise RuntimeError("429 Too Many Requests")

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert new_data[event][outlet] == good_articles
    assert new_status[event][outlet] == "ok"


def test_fetch_all_failed_attempt_with_no_prior_data_records_error(monkeypatch):
    """A failed attempt on a cell with no trustworthy cached data must record

    "error: ..." and must not fabricate an empty-but-ok cell.
    """
    event = "Phase One deal"
    outlet = "Xinhua"
    events = ((event, "2020-01-15", "2020-01-22"),)
    outlets = (outlet,)

    data: dict = {}
    status: dict = {}

    def fake_fetch_one(*_a, **_k):
        raise RuntimeError("429 Too Many Requests")

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert outlet not in new_data.get(event, {})
    assert new_status[event][outlet] == "error: 429 Too Many Requests"


def test_main_returns_1_when_any_cell_ends_in_error_status(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["fetch_headlines.py"])
    monkeypatch.setattr(fh, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fh, "RAW_PATH", tmp_path / "headlines_gdelt.json")
    monkeypatch.setattr(fh, "STATUS_PATH", tmp_path / "headlines_gdelt_status.json")

    def fake_fetch_all(data, status, refresh, events=fh.EVENTS, outlets=None):
        for event, _, _ in fh.EVENTS:
            status.setdefault(event, {})
            data.setdefault(event, {})
            for outlet in fh.OUTLET_DOMAINS:
                status[event][outlet] = "ok"
                data[event][outlet] = []
        status["Spy balloon"]["WSJ"] = "error: 429 Too Many Requests"
        return data, status

    monkeypatch.setattr(fh, "fetch_all", fake_fetch_all)

    assert fh.main() == 1


def test_main_returns_0_when_every_cell_ok_including_legitimate_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["fetch_headlines.py"])
    monkeypatch.setattr(fh, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fh, "RAW_PATH", tmp_path / "headlines_gdelt.json")
    monkeypatch.setattr(fh, "STATUS_PATH", tmp_path / "headlines_gdelt_status.json")

    def fake_fetch_all(data, status, refresh, events=fh.EVENTS, outlets=None):
        for event, _, _ in fh.EVENTS:
            status.setdefault(event, {})
            data.setdefault(event, {})
            for outlet in fh.OUTLET_DOMAINS:
                status[event][outlet] = "ok"
                data[event][outlet] = []
        # "Spy balloon" / WSJ is legitimately empty, but still ok.
        status["Spy balloon"]["WSJ"] = "ok"
        data["Spy balloon"]["WSJ"] = []
        return data, status

    monkeypatch.setattr(fh, "fetch_all", fake_fetch_all)

    assert fh.main() == 0
