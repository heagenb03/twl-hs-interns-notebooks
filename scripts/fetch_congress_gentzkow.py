# scripts/fetch_congress_gentzkow.py
"""Extract stage for the Gentzkow-Shapiro-Taddy Congressional Record corpus.

Produces Senate-only speech records. The Senate filter is NOT optional: the
corpus covers both chambers, and splicing a both-chambers pre-2017 half onto a
Senate-only GovInfo half (see fetch_congress_govinfo.py, filtered to
granuleClass=SENATE) would put a chamber discontinuity exactly where the
notebook's headline finding lives.

The 11.4 GB archive is not downloaded automatically - it may sit behind a
registration wall. Place hein-daily.zip in data/_raw/congress_gentzkow/ first;
see https://data.stanford.edu/congress_text.

Archive layout assumption (from Gentzkow/Shapiro/Taddy documentation, NOT
verified against an inspected archive - nobody who wrote this script has
opened hein-daily.zip): each Congress ships three pipe-delimited text files
with a header row, named (allowing for a directory prefix inside the zip):

    speeches_NNN.txt       one row per speech: speech_id, speech, ...
    descr_NNN.txt          one row per speech: speech_id, chamber, date, ...
    NNN_SpeakerMap.txt     one row per speech: speech_id, lastname,
                            firstname, state, ... (may be absent for some
                            congresses; speaker fields degrade to "" rather
                            than failing the whole congress)

If this layout is wrong, extract_congress() will name exactly what it looked
for and print a truncated listing of what the archive actually contains, so
whoever runs this can diagnose in one pass instead of chasing a silent empty
output.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from pathlib import Path
from typing import IO

from twl_common import CONGRESS_RAW_GENTZKOW

ARCHIVE_NAME = "hein-daily.zip"

# The single most important constant in this file: Gentzkow ships both
# chambers, and only Senate rows may reach the output JSONL.
SENATE_CHAMBER = "S"

# Columns each table MUST carry for this script to do its job. Missing any
# of these must fail loudly (ValueError) rather than silently emit rows with
# empty fields - a silently-empty `chamber` column would make the Senate
# filter pass everything through.
REQUIRED_SPEECHES_COLUMNS: tuple[str, ...] = ("speech_id", "speech")
REQUIRED_DESCR_COLUMNS: tuple[str, ...] = ("speech_id", "chamber", "date")

# How many archive entries to show in a diagnostic listing when an expected
# file is missing. Just enough to eyeball the actual naming/prefix scheme.
LISTING_TRUNCATE = 20


def read_pipe_table(
    handle: IO[bytes], required_columns: tuple[str, ...], source: str
) -> list[dict[str, str]]:
    """Parse a Gentzkow pipe-delimited table; header row gives column names.

    Raises ValueError naming `source` and the missing column(s) if the
    header lacks any column in `required_columns`.
    """
    text = handle.read().decode("utf-8", errors="replace").splitlines()
    reader = csv.DictReader(text, delimiter="|")
    fieldnames = list(reader.fieldnames or [])
    missing = [c for c in required_columns if c not in fieldnames]
    if missing:
        raise ValueError(
            f"{source}: missing required column(s) {missing}; "
            f"columns found: {fieldnames}"
        )
    return list(reader)


def find_congress_files(
    names: list[str], congress: str
) -> tuple[str | None, str | None, str | None]:
    """Locate this Congress's three files in the archive by suffix match.

    Returns (speeches_name, descr_name, map_name); any entry may be None.
    The clean `next((... for n in names if n.endswith(...)), None)` form
    used here (and only here) replaces a convoluted tuple-unpack in an
    earlier draft that called `.replace()` on a possibly-None `find(...)`
    result and would raise AttributeError before ever reaching the
    reassignment that made that branch dead code anyway.
    """
    speeches_name = next(
        (n for n in names if n.endswith(f"speeches_{congress}.txt")), None
    )
    descr_name = next((n for n in names if n.endswith(f"descr_{congress}.txt")), None)
    map_name = next(
        (n for n in names if n.endswith(f"{congress}_SpeakerMap.txt")), None
    )
    return speeches_name, descr_name, map_name


def extract_congress(zf: zipfile.ZipFile, congress: str, out_dir: Path) -> dict[str, int]:
    """Write one JSONL of Senate speeches for a single Congress.

    Returns a counter dict: total (speeches rows seen), written (Senate rows
    emitted), skipped_no_descr (speech_id absent from descr), and
    skipped_not_senate (present in descr but chamber != 'S'). Every row is
    accounted for in exactly one bucket - dropped data is counted, never
    silently discarded.
    """
    names = zf.namelist()
    speeches_name, descr_name, map_name = find_congress_files(names, congress)

    counts = {
        "total": 0,
        "written": 0,
        "skipped_no_descr": 0,
        "skipped_not_senate": 0,
    }

    if not (speeches_name and descr_name):
        missing = [
            label
            for label, present in (
                (f"speeches_{congress}.txt", speeches_name),
                (f"descr_{congress}.txt", descr_name),
            )
            if not present
        ]
        sample = names[:LISTING_TRUNCATE]
        print(
            f"  congress {congress}: could not find {missing} in the archive "
            f"({len(names)} entries total). First {len(sample)} entries: {sample}"
        )
        return counts

    with zf.open(descr_name) as fh:
        descr_rows = read_pipe_table(fh, REQUIRED_DESCR_COLUMNS, descr_name)
    descr = {r["speech_id"]: r for r in descr_rows}

    speaker_map: dict[str, dict[str, str]] = {}
    if map_name:
        with zf.open(map_name) as fh:
            map_rows = read_pipe_table(fh, ("speech_id",), map_name)
        speaker_map = {r["speech_id"]: r for r in map_rows}
    else:
        print(
            f"  congress {congress}: no *_SpeakerMap.txt found; "
            "lastname/firstname/state will be blank for every row"
        )

    out_path = out_dir / f"speeches_senate_{congress}.jsonl"
    with zf.open(speeches_name) as fh:
        speech_rows = read_pipe_table(fh, REQUIRED_SPEECHES_COLUMNS, speeches_name)

    with out_path.open("w", encoding="utf-8") as out:
        for row in speech_rows:
            counts["total"] += 1
            sid = row["speech_id"]
            meta = descr.get(sid)
            if meta is None:
                counts["skipped_no_descr"] += 1
                continue
            if meta.get("chamber") != SENATE_CHAMBER:
                counts["skipped_not_senate"] += 1
                continue
            speaker = speaker_map.get(sid, {})
            out.write(
                json.dumps(
                    {
                        "speech_id": sid,
                        "date": meta.get("date", ""),
                        "chamber": SENATE_CHAMBER,
                        "lastname": speaker.get("lastname", ""),
                        "firstname": speaker.get("firstname", ""),
                        "state": speaker.get("state", ""),
                        "text": row.get("speech", ""),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            counts["written"] += 1

    print(
        f"  congress {congress}: {counts['written']} Senate speeches written "
        f"of {counts['total']} total "
        f"({counts['skipped_no_descr']} no descr match, "
        f"{counts['skipped_not_senate']} non-Senate)"
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-congress", type=int, default=101)  # 101st starts 1989
    parser.add_argument("--last-congress", type=int, default=114)  # 114th ends Jan 2017
    args = parser.parse_args()

    CONGRESS_RAW_GENTZKOW.mkdir(parents=True, exist_ok=True)
    archive = CONGRESS_RAW_GENTZKOW / ARCHIVE_NAME
    if not archive.exists():
        print(
            f"missing {archive}\n"
            "Download hein-daily.zip (11.4 GB) from "
            "https://data.stanford.edu/congress_text and place it there.\n"
            "Free Stanford Libraries registration may be required."
        )
        return 1

    totals = {"total": 0, "written": 0, "skipped_no_descr": 0, "skipped_not_senate": 0}
    with zipfile.ZipFile(archive) as zf:
        for congress in range(args.first_congress, args.last_congress + 1):
            counts = extract_congress(zf, f"{congress:03d}", CONGRESS_RAW_GENTZKOW)
            for key in totals:
                totals[key] += counts[key]

    print(
        f"Run complete: {totals['written']} Senate speeches written "
        f"of {totals['total']} total across congresses "
        f"{args.first_congress}-{args.last_congress} "
        f"({totals['skipped_no_descr']} no descr match, "
        f"{totals['skipped_not_senate']} non-Senate dropped)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
