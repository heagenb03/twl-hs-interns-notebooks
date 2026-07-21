# scripts/tests/test_fetch_congress_gentzkow.py
import json
import zipfile
from pathlib import Path

import pytest

import fetch_congress_gentzkow
from fetch_congress_gentzkow import (
    decode_archive_bytes,
    SENATE_CHAMBER,
    extract_congress,
    find_congress_files,
    read_pipe_table,
)


def _pipe_table(rows: list[dict[str, str]]) -> str:
    """Render rows as a Gentzkow-style pipe-delimited table with a header."""
    if not rows:
        return ""
    header = "|".join(rows[0].keys())
    lines = [header]
    lines += ["|".join(str(row[k]) for k in rows[0]) for row in rows]
    return "\n".join(lines) + "\n"


def _make_archive(
    tmp_path: Path,
    congress: str,
    speeches: list[dict[str, str]],
    descr: list[dict[str, str]],
    speaker_map: list[dict[str, str]] | None,
    prefix: str = "",
) -> Path:
    """Build a small synthetic hein-daily-shaped zip for one Congress."""
    archive = tmp_path / "hein-daily.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(f"{prefix}speeches_{congress}.txt", _pipe_table(speeches))
        zf.writestr(f"{prefix}descr_{congress}.txt", _pipe_table(descr))
        if speaker_map is not None:
            zf.writestr(f"{prefix}{congress}_SpeakerMap.txt", _pipe_table(speaker_map))
    return archive


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --------------------------------------------------------------- find_congress_files


def test_find_congress_files_locates_all_three():
    names = [
        "hein-daily/speeches_101.txt",
        "hein-daily/descr_101.txt",
        "hein-daily/101_SpeakerMap.txt",
        "hein-daily/speeches_102.txt",  # different congress, must not match
    ]
    speeches, descr, spmap = find_congress_files(names, "101")
    assert speeches == "hein-daily/speeches_101.txt"
    assert descr == "hein-daily/descr_101.txt"
    assert spmap == "hein-daily/101_SpeakerMap.txt"


def test_find_congress_files_missing_map_returns_none_not_raise():
    names = ["speeches_101.txt", "descr_101.txt"]
    speeches, descr, spmap = find_congress_files(names, "101")
    assert speeches == "speeches_101.txt"
    assert descr == "descr_101.txt"
    assert spmap is None


def test_find_congress_files_missing_everything_returns_all_none():
    speeches, descr, spmap = find_congress_files(["some_other_file.txt"], "101")
    assert (speeches, descr, spmap) == (None, None, None)


# --------------------------------------------------------------- Senate filter (the load-bearing test)


def test_senate_filter_excludes_house_rows(tmp_path: Path):
    speeches = [
        {"speech_id": "1010001", "speech": "senate remarks"},
        {"speech_id": "1010002", "speech": "house remarks"},
    ]
    descr = [
        {"speech_id": "1010001", "chamber": "S", "date": "19890103"},
        {"speech_id": "1010002", "chamber": "H", "date": "19890103"},
    ]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)
    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)

    assert counts == {
        "total": 2,
        "written": 1,
        "skipped_no_descr": 0,
        "skipped_not_senate": 1,
    }
    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert len(out) == 1
    assert out[0]["speech_id"] == "1010001"
    assert out[0]["chamber"] == SENATE_CHAMBER
    assert all(r["chamber"] == "S" for r in out)


def test_senate_filter_is_the_only_gate_on_chamber(tmp_path: Path):
    # A chamber value that is neither S nor H (e.g. a stray Joint session
    # code) must also be excluded -- the filter is an equality check against
    # 'S', not merely "not H".
    speeches = [{"speech_id": "1", "speech": "joint session remarks"}]
    descr = [{"speech_id": "1", "chamber": "J", "date": "19890103"}]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)
    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)
    assert counts["written"] == 0
    assert counts["skipped_not_senate"] == 1


# --------------------------------------------------------------- descr join


def test_speech_missing_from_descr_is_counted_and_skipped(tmp_path: Path):
    speeches = [
        {"speech_id": "1010001", "speech": "has descr"},
        {"speech_id": "1010099", "speech": "no descr row exists for this id"},
    ]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)
    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)

    assert counts["written"] == 1
    assert counts["skipped_no_descr"] == 1
    assert counts["skipped_not_senate"] == 0
    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert [r["speech_id"] for r in out] == ["1010001"]


# --------------------------------------------------------------- speaker map join


def test_speaker_map_join_populates_speaker_fields(tmp_path: Path):
    speeches = [{"speech_id": "1010001", "speech": "remarks"}]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    speaker_map = [
        {
            "speech_id": "1010001",
            "lastname": "SMITH",
            "firstname": "JANE",
            "state": "OH",
        }
    ]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map)
    with zipfile.ZipFile(archive) as zf:
        extract_congress(zf, "101", tmp_path)

    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert out[0]["lastname"] == "SMITH"
    assert out[0]["firstname"] == "JANE"
    assert out[0]["state"] == "OH"


def test_missing_speaker_map_file_is_tolerated(tmp_path: Path, capsys: pytest.CaptureFixture):
    speeches = [{"speech_id": "1010001", "speech": "remarks"}]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)
    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)

    assert counts["written"] == 1
    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert out[0]["lastname"] == ""
    assert out[0]["firstname"] == ""
    assert out[0]["state"] == ""
    assert "no *_SpeakerMap.txt found" in capsys.readouterr().out


def test_speech_with_no_speaker_map_row_still_written(tmp_path: Path):
    # Map file exists but doesn't have an entry for this particular speech_id.
    speeches = [{"speech_id": "1010001", "speech": "remarks"}]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    speaker_map = [
        {"speech_id": "9999999", "lastname": "OTHER", "firstname": "X", "state": "CA"}
    ]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map)
    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)

    assert counts["written"] == 1
    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert out[0]["lastname"] == ""


# --------------------------------------------------------------- missing files diagnostics


def test_missing_speeches_or_descr_skips_congress_without_raising(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    archive = tmp_path / "hein-daily.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("some_unrelated_file.txt", "nothing to see here")

    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)

    assert counts == {
        "total": 0,
        "written": 0,
        "skipped_no_descr": 0,
        "skipped_not_senate": 0,
    }
    captured = capsys.readouterr().out
    assert "speeches_101.txt" in captured
    assert "descr_101.txt" in captured
    assert "some_unrelated_file.txt" in captured  # the diagnostic listing
    assert not (tmp_path / "speeches_senate_101.jsonl").exists()


# --------------------------------------------------------------- required-column validation


def test_read_pipe_table_raises_on_missing_required_column(tmp_path: Path):
    import io

    handle = io.BytesIO(b"speech_id|speech\n1|hello\n")
    with pytest.raises(ValueError, match=r"missing required column.*chamber"):
        read_pipe_table(handle, ("speech_id", "chamber", "date"), "descr_101.txt")


def test_extract_congress_raises_clear_error_when_descr_missing_chamber_column(
    tmp_path: Path,
):
    archive = tmp_path / "hein-daily.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("speeches_101.txt", "speech_id|speech\n1|hello\n")
        # descr is missing the chamber column entirely.
        zf.writestr("descr_101.txt", "speech_id|date\n1|19890103\n")

    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(ValueError, match="chamber"):
            extract_congress(zf, "101", tmp_path)


# --------------------------------------------------------------- output shape


def test_speech_text_with_leading_quote_is_not_corrupted(tmp_path: Path):
    # hein-daily is plain pipe-delimited with NO csv-style quoting, and
    # senators quote constantly. csv's default quoting treats a leading '"'
    # as the start of a quoted field -- stripping it, and on an unbalanced
    # quote, swallowing subsequent lines into one field. That silently
    # merges rows and corrupts the speech_id join, which is exactly the
    # silent-drop failure mode this task exists to prevent. This is the
    # discriminating test: it fails under default csv quoting and passes
    # under QUOTE_NONE.
    quoted_text = '"We must act," she said, "before it is too late."'
    speeches = [{"speech_id": "1010001", "speech": quoted_text}]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)
    with zipfile.ZipFile(archive) as zf:
        counts = extract_congress(zf, "101", tmp_path)

    assert counts["written"] == 1
    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert out[0]["text"] == quoted_text


def test_output_jsonl_shape_matches_downstream_contract(tmp_path: Path):
    speeches = [{"speech_id": "1010001", "speech": "remarks about tariffs"}]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    speaker_map = [
        {"speech_id": "1010001", "lastname": "SMITH", "firstname": "JANE", "state": "OH"}
    ]
    archive = _make_archive(tmp_path, "101", speeches, descr, speaker_map)
    with zipfile.ZipFile(archive) as zf:
        extract_congress(zf, "101", tmp_path)

    out = _read_jsonl(tmp_path / "speeches_senate_101.jsonl")
    assert len(out) == 1
    row = out[0]
    assert set(row.keys()) == {
        "speech_id",
        "date",
        "chamber",
        "lastname",
        "firstname",
        "state",
        "text",
    }
    assert row["speech_id"] == "1010001"
    assert row["date"] == "19890103"
    assert row["chamber"] == "S"
    assert row["text"] == "remarks about tariffs"
    assert all(isinstance(v, str) for v in row.values())


# --- archive encoding ---------------------------------------------------------


def test_latin1_accented_names_survive_decoding() -> None:
    """A latin-1 archive must not lose accented senator surnames.

    decode("utf-8", errors="replace") silently turns 'Menendez' with an accent
    into 'Men�ndez'. Menendez and Lujan both sat inside the covered window,
    and the loss is not local: congress_speakers folds accents so a rendered
    header matches its metadata name, but the mangled form folds to a different
    key and the senator silently stops matching.
    """
    for name in ("Mu\xf1oz", "Luj\xe1n", "Men\xe9ndez", "Pe\xf1a"):
        assert decode_archive_bytes(name.encode("latin-1")) == name
        assert decode_archive_bytes(name.encode("utf-8")) == name


def test_decoding_never_substitutes_the_replacement_character() -> None:
    """Whatever the real archive's encoding turns out to be, no byte sequence
    should decode to U+FFFD -- that is silent, unrecoverable information loss."""
    assert "�" not in decode_archive_bytes("Luj\xe1n".encode("latin-1"))
    assert "�" not in decode_archive_bytes("Luj\xe1n".encode("utf-8"))


# --------------------------------------------------------------- C4: atomic write + exit code
#
# fetch_congress_gentzkow's sibling, fetch_congress_govinfo, writes via a temp
# file + os.replace (so a kill mid-write cannot leave a truncated file that
# exists() reports as complete) and returns 1 on any failed day (so an
# unattended run that produces nothing does not report success). This module
# had neither: `out_path.open("w")` truncated and streamed straight to the
# final path, and main() returned 0 even when the UNVERIFIED archive layout
# assumption was wrong and zero speeches were extracted across every
# congress. Consumers glob speeches_senate_*.jsonl and treat presence as
# completeness, so either gap is invisible downstream. These tests pin the
# fix to the same pattern govinfo already uses.


class _SimulatedKill(Exception):
    """Stands in for a process kill (OOM-killer, SIGKILL, spot eviction)
    partway through writing a Congress's speeches. Raised from inside the
    write loop -- after some rows have already been serialized -- so the
    only way a test can pass is if the writer never let a caller observe a
    partial result at the path consumers actually look for.
    """


def _archive_with_three_senate_speeches(tmp_path: Path) -> Path:
    speeches = [
        {"speech_id": "1010001", "speech": "first speech, written fine"},
        {"speech_id": "1010002", "speech": "second speech, kill happens here"},
        {"speech_id": "1010003", "speech": "third speech, never reached"},
    ]
    descr = [
        {"speech_id": "1010001", "chamber": "S", "date": "19890103"},
        {"speech_id": "1010002", "chamber": "S", "date": "19890103"},
        {"speech_id": "1010003", "chamber": "S", "date": "19890103"},
    ]
    return _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)


def _extract_with_simulated_kill_on_second_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run extract_congress() on a 3-speech Congress, killing it after the
    first row is serialized but before the second is. Raises _SimulatedKill
    out of extract_congress -- callers assert on what's left on disk.
    """
    archive = _archive_with_three_senate_speeches(tmp_path)
    real_dumps = json.dumps
    calls = {"n": 0}

    def flaky_dumps(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise _SimulatedKill("process killed mid-write")
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(fetch_congress_gentzkow.json, "dumps", flaky_dumps)

    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(_SimulatedKill):
            extract_congress(zf, "101", tmp_path)


def test_interrupted_write_leaves_no_file_at_final_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A write killed mid-stream must not leave a truncated file at the
    final speeches_senate_101.jsonl path -- only a complete file, or none.
    """
    _extract_with_simulated_kill_on_second_row(tmp_path, monkeypatch)
    assert not (tmp_path / "speeches_senate_101.jsonl").exists()


def test_partial_temp_file_not_matched_by_consumer_glob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Whatever artifact the interrupted write leaves behind on disk (if
    any), it must not satisfy a downstream consumer's
    glob("speeches_senate_*.jsonl") presence check -- that check is how
    build_congress_* decide a Congress's speeches are ready to read.
    """
    _extract_with_simulated_kill_on_second_row(tmp_path, monkeypatch)
    assert list(tmp_path.glob("speeches_senate_*.jsonl")) == []


def test_main_returns_nonzero_when_zero_speeches_extracted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """If the UNVERIFIED archive layout assumption is wrong, every congress
    prints a diagnostic and every count comes back zero. main() must not
    report success in that case -- govinfo's fetcher returns 1 on any failed
    day for exactly this reason, and this fetcher must match it.
    """
    archive = tmp_path / fetch_congress_gentzkow.ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("some_unrelated_file.txt", "not a hein-daily table")

    monkeypatch.setattr(
        fetch_congress_gentzkow, "CONGRESS_RAW_GENTZKOW", tmp_path, raising=False
    )
    monkeypatch.setattr(
        "sys.argv",
        ["fetch_congress_gentzkow.py", "--first-congress", "101", "--last-congress", "102"],
    )

    rc = fetch_congress_gentzkow.main()
    assert rc != 0
    assert "ABORT" in capsys.readouterr().out


def test_main_returns_zero_on_successful_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The success path must not regress: a real extraction that writes at
    least one speech still exits 0.
    """
    speeches = [{"speech_id": "1010001", "speech": "remarks"}]
    descr = [{"speech_id": "1010001", "chamber": "S", "date": "19890103"}]
    _make_archive(tmp_path, "101", speeches, descr, speaker_map=None)

    monkeypatch.setattr(
        fetch_congress_gentzkow, "CONGRESS_RAW_GENTZKOW", tmp_path, raising=False
    )
    monkeypatch.setattr(
        "sys.argv",
        ["fetch_congress_gentzkow.py", "--first-congress", "101", "--last-congress", "101"],
    )

    rc = fetch_congress_gentzkow.main()
    assert rc == 0
    assert (tmp_path / "speeches_senate_101.jsonl").exists()


def test_a_speech_larger_than_csvs_default_field_limit_parses(tmp_path):
    """csv caps a field at 128 KB by default; real Senate speeches exceed it.

    Found by running against the actual archive for the first time: congress
    114 raised `_csv.Error: field larger than field limit (131072)` on the very
    first read, and its longest speech is 162,948 characters. Long floor
    speeches and inserted documents (bill text, letters, hearing transcripts)
    routinely run past the cap.

    This survived every earlier test because nothing before it had opened the
    11.4 GB archive -- the layout was documented, never inspected. The failure
    is loud rather than silent, but it would have arrived only after the
    multi-hour GovInfo pull.
    """
    import io

    from fetch_congress_gentzkow import REQUIRED_SPEECHES_COLUMNS, read_pipe_table

    huge = "china trade " * 20_000  # ~240 KB, well past csv's 131,072 default
    assert len(huge) > 131_072, "fixture no longer exercises the limit"

    header = "|".join(REQUIRED_SPEECHES_COLUMNS)
    idx = list(REQUIRED_SPEECHES_COLUMNS)
    row = ["x"] * len(idx)
    row[idx.index("speech")] = huge
    payload = (header + "\n" + "|".join(row) + "\n").encode("utf-8")

    rows = read_pipe_table(io.BytesIO(payload), REQUIRED_SPEECHES_COLUMNS, "test")
    assert len(rows) == 1
    assert len(rows[0]["speech"]) == len(huge)
