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
import os
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


def decode_archive_bytes(raw: bytes) -> str:
    """Decode archive bytes without destroying characters.

    The real archive's encoding is UNVERIFIED -- it has never been opened (the
    11.4 GB download is deferred), and the documented layout says nothing about
    it. So this must be lossless under either plausible answer.

    `decode("utf-8", errors="replace")` is NOT safe here: on latin-1 input it
    silently substitutes U+FFFD for every accented character, with no error.
    That destroys real senators' names -- Menendez and Lujan both sat inside the
    covered window -- and the damage does not stay local. congress_speakers
    folds accents so a rendered header matches its metadata name, but a mangled
    surname folds to 'LUJ�N', which never equals 'LUJAN', so the senator
    silently fails to match and their mentions land nowhere.

    utf-8 strict first, latin-1 as the fallback: latin-1 maps every byte to a
    codepoint, so it never raises and never loses information. Verified
    lossless on Munoz/Lujan/Menendez/Pena encoded either way.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def read_pipe_table(
    handle: IO[bytes], required_columns: tuple[str, ...], source: str
) -> list[dict[str, str]]:
    """Parse a Gentzkow pipe-delimited table; header row gives column names.

    Raises ValueError naming `source` and the missing column(s) if the
    header lacks any column in `required_columns`.
    """
    # csv caps a single field at 128 KB by default, and a real Senate speech
    # exceeds that -- verified against the actual archive, where congress 114
    # raised `_csv.Error: field larger than field limit (131072)` on the first
    # read. Long floor speeches and inserted documents (bill text, letters,
    # hearing transcripts) routinely run past it. The failure is loud, but it
    # arrives only when the 11.4 GB archive is finally on disk, which is why it
    # survived every earlier test: nothing before this had ever opened it.
    text = decode_archive_bytes(handle.read()).splitlines()
    # QUOTE_NONE: the hein-daily format is plain pipe-delimited with no
    # csv-style quoting. Speech text is full of literal '"' characters
    # (senators quote constantly); csv's default quoting treats a leading
    # '"' as the start of a quoted field, stripping it and, on an unbalanced
    # quote, consuming following lines into one field - silently merging
    # rows and corrupting the speech_id join. QUOTE_NONE makes '|' the only
    # delimiter that matters and '"' just another character.
    _raise_csv_field_limit()
    reader = csv.DictReader(text, delimiter="|", quoting=csv.QUOTE_NONE)
    fieldnames = list(reader.fieldnames or [])
    missing = [c for c in required_columns if c not in fieldnames]
    if missing:
        raise ValueError(
            f"{source}: missing required column(s) {missing}; "
            f"columns found: {fieldnames}"
        )
    return list(reader)


def _raise_csv_field_limit() -> None:
    """Lift csv's per-field cap as far as this platform allows.

    sys.maxsize overflows the C long that csv uses on Windows, so the standard
    approach is to halve until it is accepted. Idempotent: safe to call per
    table read.
    """
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 2


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

    # Write via a temp file and atomically replace, mirroring
    # fetch_congress_govinfo.fetch_day() and for the identical reason: this
    # loop streams rows one at a time, so a kill mid-write (OOM, SIGKILL,
    # spot eviction) partway through a Congress must not leave a truncated
    # file sitting at out_path. Consumers glob speeches_senate_*.jsonl and
    # treat presence as completeness -- a truncated file at the FINAL name
    # would look done to them; a truncated file under a name that glob
    # doesn't match (".jsonl.partial", not ".jsonl") does not. os.replace is
    # only reached after the with-block below closes cleanly, so partial
    # writes never get renamed into the name consumers look for.
    tmp_path = out_path.with_suffix(".jsonl.partial")
    with tmp_path.open("w", encoding="utf-8") as out:
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
    os.replace(tmp_path, out_path)

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
    # Non-zero exit when NOTHING was extracted, mirroring
    # fetch_congress_govinfo.main()'s "1 if total_failed else 0". The
    # archive layout this module assumes (see module docstring) has never
    # been verified against an opened archive. If it's wrong, every congress
    # prints its own diagnostic above and every count comes back zero --
    # "0 of 0" -- which looks identical to a clean, empty run unless the
    # exit code says otherwise. A caller that sees exit 0 is entitled to
    # assume the run produced something.
    if totals["written"] == 0:
        print(
            "ABORT: 0 Senate speeches were written across any congress in "
            f"{args.first_congress}-{args.last_congress}. This almost certainly "
            "means the archive layout assumption in this module's docstring is "
            "wrong (it has never been verified against an opened archive) -- "
            "not that these congresses genuinely had no Senate speeches. "
            "Treating this as a failure instead of silently reporting success."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
