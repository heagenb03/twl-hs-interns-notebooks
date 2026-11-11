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


def test_null_title_from_gdelt_does_not_raise_attributeerror(monkeypatch, no_sleep):
    """Minor fix: GDELT can return "title": null. `a.get("title", "").strip()`
    only substitutes the default when the key is ABSENT, not when it's
    present with value None -- so a null title raised AttributeError on
    .strip(). Must degrade to an empty string instead."""
    body = json.dumps({"articles": [
        {"title": None, "url": "http://x", "domain": "nytimes.com", "seendate": "20200115"}
    ]})
    monkeypatch.setattr(fh.requests, "get", lambda *a, **k: FakeResponse(200, body))

    result = fh.fetch_one("NYT", "2020-01-15", "2020-01-22")

    assert result == [
        {"title": "", "url": "http://x", "domain": "nytimes.com", "seendate": "20200115"}
    ]


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


def test_fetch_all_refresh_true_refetches_ok_cell(monkeypatch):
    """Finding 1: --refresh must force a real re-fetch, even for cells

    already marked "ok" with cached data. If `refresh=True` were ignored (or
    the `not refresh` check inverted), this cell would be skipped and the
    stale cached article would survive untouched.
    """
    event = "Test Event"
    outlet = "NYT"
    events = ((event, "2020-01-01", "2020-01-02"),)
    outlets = (outlet,)
    data = {event: {outlet: [{"title": "stale-old-article"}]}}
    status = {event: {outlet: "ok"}}

    calls: list[str] = []

    def fake_fetch_one(outlet_arg: str, _start: str, _end: str) -> list[dict]:
        calls.append(outlet_arg)
        return [{"title": "fresh-new-article"}]

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=True, events=events, outlets=outlets)

    assert calls == [outlet], "fetch_one must be called for an ok cell when refresh=True"
    assert new_data[event][outlet] == [{"title": "fresh-new-article"}]
    assert new_status[event][outlet] == "ok"


def test_fetch_all_writes_cache_incrementally_across_events(monkeypatch, tmp_path):
    """Finding 2: _write_cache (the real implementation, not a no-op) must be

    called after each event completes, not just once at the very end. We
    inject a failure between event 1 and event 2 (via time.sleep, which is
    called unconditionally after each cell and is not swallowed by the
    per-cell try/except) and assert that event 1's results are already
    durable on disk before the run is interrupted.
    """
    event1, event2 = "Event One", "Event Two"
    outlet = "NYT"
    events = (
        (event1, "2020-01-01", "2020-01-02"),
        (event2, "2020-02-01", "2020-02-02"),
    )
    outlets = (outlet,)
    data: dict = {}
    status: dict = {}

    raw_path = tmp_path / "headlines_gdelt.json"
    status_path = tmp_path / "headlines_gdelt_status.json"
    monkeypatch.setattr(fh, "RAW_PATH", raw_path)
    monkeypatch.setattr(fh, "STATUS_PATH", status_path)

    def fake_fetch_one(_outlet: str, start: str, _end: str) -> list[dict]:
        return [{"title": f"article-for-{start}"}]

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if len(sleep_calls) == 2:
            raise RuntimeError("simulated interruption before second event's write")

    monkeypatch.setattr(fh.time, "sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="simulated interruption"):
        fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert raw_path.exists(), "cache file should already be on disk after event 1's write"
    on_disk_data = json.loads(raw_path.read_text(encoding="utf-8"))
    on_disk_status = json.loads(status_path.read_text(encoding="utf-8"))

    assert on_disk_data[event1][outlet] == [{"title": "article-for-2020-01-01"}]
    assert on_disk_status[event1][outlet] == "ok"
    # The interruption happened before event 2's write, so it must not be on disk.
    assert event2 not in on_disk_data


def test_fetch_all_ok_status_without_data_is_refetched_not_skipped(monkeypatch):
    """Finding 3 (skip-check half): a cell marked "ok" but with no matching

    data (e.g. from a desynced dual-file write) must be re-fetched, not
    trusted and skipped forever.
    """
    event = "Test Event"
    outlet = "NYT"
    events = ((event, "2020-01-01", "2020-01-02"),)
    outlets = (outlet,)
    data = {event: {}}  # no data for outlet despite "ok" status below
    status = {event: {outlet: "ok"}}

    calls: list[str] = []

    def fake_fetch_one(outlet_arg: str, _start: str, _end: str) -> list[dict]:
        calls.append(outlet_arg)
        return [{"title": "recovered-article"}]

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)
    monkeypatch.setattr(fh, "_write_cache", lambda d, s: None)

    new_data, new_status = fh.fetch_all(data, status, refresh=False, events=events, outlets=outlets)

    assert calls == [outlet], "fetch_one must be called when status says ok but data is missing"
    assert new_data[event][outlet] == [{"title": "recovered-article"}]
    assert new_status[event][outlet] == "ok"


def test_atomic_write_text_removes_tmp_file_on_replace_failure(monkeypatch, tmp_path):
    """Fix 2: a failure inside _atomic_write_text must not leak the .tmp
    sibling, and must not swallow the original exception."""
    target = tmp_path / "out.json"
    tmp_sibling = tmp_path / "out.json.tmp"

    def boom(_src, _dst):
        raise OSError("simulated os.replace failure")

    monkeypatch.setattr(fh.os, "replace", boom)

    with pytest.raises(OSError, match="simulated os.replace failure"):
        fh._atomic_write_text(target, "content")

    assert not tmp_sibling.exists(), ".tmp file must be cleaned up after a failed write"
    assert not target.exists()


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


def test_main_banner_does_not_count_ok_status_with_missing_data_as_cached(monkeypatch, tmp_path, capsys):
    """Minor fix: n_cached_ok counted status=="ok" without the matching
    data-presence check that fetch_all's actual skip-check applies, so a
    desynced cell (status "ok" but no data) was counted as already cached --
    inflating n_cached_ok and making the 'fetching N of M' banner under-
    report how much work fetch_all will actually do (it re-fetches that
    cell, matching the skip-check)."""
    monkeypatch.setattr(sys, "argv", ["fetch_headlines.py"])
    monkeypatch.setattr(fh, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fh, "RAW_PATH", tmp_path / "headlines_gdelt.json")
    monkeypatch.setattr(fh, "STATUS_PATH", tmp_path / "headlines_gdelt_status.json")

    # Every cell marked "ok" in status, but ONE cell (first event/outlet) has
    # no matching data -- a desynced cache.
    desynced_event, _, _ = fh.EVENTS[0]
    desynced_outlet = next(iter(fh.OUTLET_DOMAINS))
    data = {
        event: {outlet: [{"title": "x"}] for outlet in fh.OUTLET_DOMAINS}
        for event, _, _ in fh.EVENTS
    }
    data[desynced_event].pop(desynced_outlet)
    status = {
        event: {outlet: "ok" for outlet in fh.OUTLET_DOMAINS}
        for event, _, _ in fh.EVENTS
    }
    fh.RAW_PATH.write_text(json.dumps(data), encoding="utf-8")
    fh.STATUS_PATH.write_text(json.dumps(status), encoding="utf-8")

    monkeypatch.setattr(fh, "fetch_all", lambda d, s, r, events=fh.EVENTS, outlets=None: (d, s))

    fh.main()

    out = capsys.readouterr().out
    assert "fetching 1 of" in out, (
        "the desynced cell (status ok, no data) must be counted as needing "
        "a fetch, matching fetch_all's actual skip condition"
    )


def test_main_refresh_preserves_cached_data_when_a_cell_fails_to_refetch(monkeypatch, tmp_path):
    """Finding 1: --refresh must not be destructive.

    main() used to reset `data = {}` on --refresh, so the first per-event
    _write_cache call (after event 1) atomically overwrote RAW_PATH with
    only event 1's data -- destroying every other event's previously-cached
    articles before they were re-fetched. A cell that then fails to
    re-fetch had no fallback left: the old, good data was already gone.

    This test seeds RAW_PATH/STATUS_PATH with real cached articles for every
    cell, runs `main()` with --refresh, and makes ONE cell's re-fetch fail.
    That cell's previously-cached articles must survive on disk.
    """
    monkeypatch.setattr(sys, "argv", ["fetch_headlines.py", "--refresh"])
    monkeypatch.setattr(fh, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fh, "RAW_PATH", tmp_path / "headlines_gdelt.json")
    monkeypatch.setattr(fh, "STATUS_PATH", tmp_path / "headlines_gdelt_status.json")
    monkeypatch.setattr(fh.time, "sleep", lambda s: None)

    failing_event, failing_start, failing_end = fh.EVENTS[1]
    failing_outlet = next(iter(fh.OUTLET_DOMAINS))

    old_articles = [{"title": "old-cached-article"}]
    pre_existing_data = {
        event: {outlet: old_articles for outlet in fh.OUTLET_DOMAINS}
        for event, _, _ in fh.EVENTS
    }
    pre_existing_status = {
        event: {outlet: "ok" for outlet in fh.OUTLET_DOMAINS}
        for event, _, _ in fh.EVENTS
    }
    fh.RAW_PATH.write_text(json.dumps(pre_existing_data), encoding="utf-8")
    fh.STATUS_PATH.write_text(json.dumps(pre_existing_status), encoding="utf-8")

    def fake_fetch_one(outlet: str, start: str, end: str) -> list[dict]:
        if outlet == failing_outlet and start == failing_start and end == failing_end:
            raise RuntimeError("simulated throttle on refetch")
        return [{"title": f"fresh-{outlet}-{start}"}]

    monkeypatch.setattr(fh, "fetch_one", fake_fetch_one)

    fh.main()

    on_disk_data = json.loads(fh.RAW_PATH.read_text(encoding="utf-8"))
    assert on_disk_data[failing_event][failing_outlet] == old_articles, (
        "the failing cell's previously-cached articles must survive --refresh, "
        "not be silently destroyed before the re-fetch attempt"
    )


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
