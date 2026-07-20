# scripts/tests/test_fetch_congress_gentzkow.py
import json
import zipfile
from pathlib import Path

import pytest

from fetch_congress_gentzkow import (
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
