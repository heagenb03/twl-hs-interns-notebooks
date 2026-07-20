"""Guard rails for the Week 1 notebook prose cleanup.

Captures a notebook's invariants before editing (`snapshot`) and asserts they
are unchanged afterward (`check`). The prose diff is large by design, so this
is what proves no code, anchor value, or template marker moved.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?%?")
EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # pictographs, symbols, emoticons
    "←-⇿"          # arrows (▶ is not here; see below)
    "─-➿"          # box drawing, misc symbols, dingbats (▶️ ✅ ✏️)
    "⬀-⯿"          # misc symbols and arrows
    "️"                 # variation selector-16
    "]"
)
MARKERS = (
    "▶️ JUST RUN",
    "✏️ YOUR TURN",
    "# <-- EDIT",
    "**What you should see",
    "**If you get a red error:**",
)


def read_nb(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_nb(path: str | Path, nb: dict[str, Any]) -> None:
    text = json.dumps(nb, indent=1, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)


def _src(cell: dict[str, Any]) -> str:
    return "".join(cell["source"])


def _markdown(nb: dict[str, Any]) -> str:
    return "\n".join(
        _src(c) for c in nb["cells"] if c["cell_type"] == "markdown"
    )


def _blockquotes(nb: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "markdown":
            continue
        for line in _src(cell).split("\n"):
            if line.lstrip().startswith(">"):
                out.append(f"{i}:{line}")
    return out


def _headers(nb: dict[str, Any]) -> list[str]:
    return [
        " ".join(EMOJI_RE.sub("", line).split())
        for line in _markdown(nb).split("\n")
        if line.startswith("#")
    ]


def _all_text(nb: dict[str, Any]) -> str:
    # Marker counts span both cell types: "▶️ JUST RUN" and "# <-- EDIT"
    # live in code cells too. Counting markdown alone would silently
    # report 0 for "# <-- EDIT" and never catch its removal.
    return "\n".join(_src(c) for c in nb["cells"])


def snapshot(nb: dict[str, Any]) -> dict[str, Any]:
    md = _markdown(nb)
    everything = _all_text(nb)
    return {
        "n_cells": len(nb["cells"]),
        "cell_types": [c["cell_type"] for c in nb["cells"]],
        "code": [_src(c) for c in nb["cells"] if c["cell_type"] == "code"],
        "outputs": [
            json.dumps(c.get("outputs", []), sort_keys=True)
            for c in nb["cells"]
            if c["cell_type"] == "code"
        ],
        "blockquotes": _blockquotes(nb),
        "markers": {m: everything.count(m) for m in MARKERS},
        "headers": _headers(nb),
        "numbers": sorted(NUM_RE.findall(md)),
        "markdown": {
            str(i): _src(c)
            for i, c in enumerate(nb["cells"])
            if c["cell_type"] == "markdown"
        },
    }


def _code_cell_indices(cell_types: list[str]) -> list[int]:
    return [i for i, t in enumerate(cell_types) if t == "code"]


def check(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    info: list[str] = []

    # "blockquotes" is included here (not just diffed via set() below) so that
    # a pure reorder, or deleting one of two identical lines, is still a hard
    # error even though those cases are invisible to a set-difference.
    for key in ("n_cells", "cell_types", "outputs", "blockquotes"):
        if before[key] != after[key]:
            errs.append(f"{key} changed")

    if before["code"] != after["code"]:
        if len(before["code"]) != len(after["code"]):
            errs.append(
                f"code changed: code-cell count {len(before['code'])} -> {len(after['code'])}"
            )
        else:
            idx_map = _code_cell_indices(after["cell_types"]) or _code_cell_indices(
                before["cell_types"]
            )
            diff_idx = [
                idx_map[pos] if pos < len(idx_map) else f"pos{pos}"
                for pos, (b, a) in enumerate(zip(before["code"], after["code"]))
                if b != a
            ]
            errs.append(f"code changed in cell index(es): {diff_idx}")

    if before["headers"] != after["headers"]:
        pairs = []
        for i in range(max(len(before["headers"]), len(after["headers"]))):
            b = before["headers"][i] if i < len(before["headers"]) else "<missing>"
            a = after["headers"][i] if i < len(after["headers"]) else "<missing>"
            if b != a:
                pairs.append(f"#{i} {b!r} -> {a!r}")
        errs.append("headers changed: " + "; ".join(pairs))

    if before["markers"] != after["markers"]:
        pairs = [
            f"{m!r} {before['markers'].get(m)}->{after['markers'].get(m)}"
            for m in MARKERS
            if before["markers"].get(m) != after["markers"].get(m)
        ]
        errs.append("markers changed: " + "; ".join(pairs))

    if before["blockquotes"] != after["blockquotes"]:
        b, a = set(before["blockquotes"]), set(after["blockquotes"])
        for line in sorted(b - a):
            errs.append(f"blockquote line REMOVED/ALTERED: {line}")
        for line in sorted(a - b):
            errs.append(f"blockquote line ADDED: {line}")

    # Counter (not set) so that deleting one of N duplicate numbers is
    # visible: an increase in a number's count is an invention (hard error),
    # a decrease is a legal removal (non-blocking INFO).
    before_nums = Counter(before["numbers"])
    after_nums = Counter(after["numbers"])

    invented = sorted((after_nums - before_nums).elements())
    if invented:
        errs.append(f"invented numbers: {invented}")

    removed = sorted((before_nums - after_nums).elements())
    if removed:
        info.append(f"INFO numbers removed: {removed}")

    before_md = before.get("markdown", {})
    after_md = after.get("markdown", {})
    changed_md = sorted(
        int(i)
        for i in set(before_md) | set(after_md)
        if before_md.get(i) != after_md.get(i)
    )
    if changed_md:
        info.append(f"INFO markdown cells changed: {changed_md}")

    return errs, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["snapshot", "check", "roundtrip"])
    ap.add_argument("notebook")
    ap.add_argument("baseline", nargs="?")
    args = ap.parse_args()

    if args.mode == "roundtrip":
        raw = Path(args.notebook).read_bytes()
        write_nb(args.notebook, read_nb(args.notebook))
        if Path(args.notebook).read_bytes() == raw:
            print(f"OK roundtrip byte-identical: {args.notebook}")
            return 0
        print(f"FAIL roundtrip changed bytes: {args.notebook}")
        return 1

    if args.mode == "snapshot":
        if not args.baseline:
            ap.error("snapshot requires an output path")
        Path(args.baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(args.baseline).write_text(
            json.dumps(snapshot(read_nb(args.notebook)), indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"OK snapshot written: {args.baseline}")
        return 0

    if not args.baseline:
        ap.error("check requires a baseline path")
    before = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    errs, info = check(before, snapshot(read_nb(args.notebook)))
    if errs:
        print(f"FAIL {args.notebook}")
        for e in errs:
            print(f"  - {e}")
        for i in info:
            print(f"  {i}")
        return 1
    print(f"OK {args.notebook} — all invariants hold")
    for i in info:
        print(f"  {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
