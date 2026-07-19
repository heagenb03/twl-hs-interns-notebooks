import re
from pathlib import Path

import pytest

from congress_speakers import attribute_granule, normalize_lnf, split_turns

FIXTURES = Path(__file__).parent / "fixtures" / "crec"


def load(gid: str) -> str:
    return re.sub(r"<[^>]+>", "", (FIXTURES / f"{gid}.htm").read_text(encoding="utf-8"))


# --- the headline case: a demonstrated misattribution between two senators ---

def test_scott_of_florida_is_not_credited_to_cornyn():
    """The naive pattern reports CORNYN:2. It is wrong.

    'Mr. SCOTT of Florida.' is a real speaker turn, but the qualifier moves the
    period, so a naive `Mr. NAME\\.` pattern never matches it and Rick Scott's
    words - including one 'china' - land on the previous speaker, John Cornyn.
    """
    text = load("CREC-2021-06-08-pt1-PgS3975-2")
    members = [
        {"lnf": "Cornyn, John", "bio": "C001056", "role": "SPEAKING"},
        {"lnf": "Scott, Rick", "bio": "S001217", "role": "SPEAKING"},
        {"lnf": "Durbin, Richard J.", "bio": "D000563", "role": "SPEAKING"},
        {"lnf": "Wicker, Roger F.", "bio": "W000437", "role": "SPEAKING"},
    ]
    turns = split_turns(text)
    names = [n for n, _ in turns]
    assert "SCOTT" in names, "the 'of Florida' qualifier defeated the pattern"
    counts = {}
    for name, seg in turns:
        c = len(re.findall("china", seg, re.I))
        if c:
            counts[name] = counts.get(name, 0) + c
    assert counts == {"CORNYN": 1, "SCOTT": 1, "DURBIN": 9, "WICKER": 3}


def test_mc_names_are_matched():
    """CREC renders McCain as 'Mr. McCAIN.' - lowercase c inside an otherwise
    caps name. A naive all-caps class misses every one of his 20 turns."""
    text = load("CREC-1999-03-17-pt1-PgS2821-2")
    names = [n for n, _ in split_turns(text)]
    assert "MCCAIN" in names
    assert names.count("MCCAIN") >= 15
    assert len(names) == 28


def test_mixed_case_name_drop_does_not_split():
    """'the Senator from Texas, Mr. Cornyn.' inside another member's speech is
    a citation, not a turn. Mixed case is what distinguishes them."""
    text = load("CREC-2021-06-08-pt1-PgS3975-2")
    assert "Mr. Cornyn." in text, "fixture no longer contains the adversarial case"
    # 19 real turns; the mixed-case mention is not one of them.
    assert len(split_turns(text)) == 19


def test_sole_speaker_granule_with_no_header():
    """A granule whose speaker's turn began in a previous granule carries no
    header at all. It must still be attributed, not dropped."""
    text = load("CREC-2023-06-14-pt1-PgS2080-3")
    assert split_turns(text) == []
    members = [{"lnf": "McConnell, Mitch", "bio": "M000355", "role": "SPEAKING"}]
    attributed = attribute_granule(text, members, carry_in=None)
    assert set(attributed) == {"M000355"}


def test_two_speaker_granule_is_unchanged_by_the_fixes():
    """Regression guard: the granule the naive pattern already handled must
    produce identical results under the corrected one."""
    text = load("CREC-2019-05-22-pt1-PgS3039-2")
    turns = split_turns(text)
    assert [n for n, _ in turns] == ["PORTMAN", "CRAMER"]
    portman = turns[0][1]
    assert len(re.findall("china", portman, re.I)) == 40


# --- carry-in ---------------------------------------------------------------

def test_pre_header_text_goes_to_the_carry_in_speaker():
    """Turns span granule boundaries; CREC does not re-head a continuation.
    Text before the first header belongs to the previous granule's last speaker."""
    text = "China is the issue.\n  Mr. THUNE. I disagree about china."
    members = [
        {"lnf": "Durbin, Richard J.", "bio": "D000563", "role": "SPEAKING"},
        {"lnf": "Thune, John", "bio": "T000250", "role": "SPEAKING"},
    ]
    attributed = attribute_granule(text, members, carry_in="D000563")
    assert "China is the issue." in attributed["D000563"]
    assert "I disagree" in attributed["T000250"]


def test_unaccounted_speaking_member_raises():
    """The guard that turns silent misattribution into a build error."""
    text = "  Mr. THUNE. Mr. President, I speak about china."
    members = [
        {"lnf": "Thune, John", "bio": "T000250", "role": "SPEAKING"},
        {"lnf": "Ghost, Nobody", "bio": "G999999", "role": "SPEAKING"},
    ]
    with pytest.raises(ValueError, match="G999999"):
        attribute_granule(text, members, carry_in=None)


def test_non_speaking_members_are_not_required_to_appear():
    """Only role=SPEAKING members must be matched. Sponsors need not speak."""
    text = "  Mr. THUNE. Mr. President, I speak about china."
    members = [
        {"lnf": "Thune, John", "bio": "T000250", "role": "SPEAKING"},
        {"lnf": "Shaheen, Jeanne", "bio": "S001181", "role": "SPONSOR"},
    ]
    attributed = attribute_granule(text, members, carry_in=None)
    assert set(attributed) == {"T000250"}


# --- name normalization -----------------------------------------------------

@pytest.mark.parametrize(
    "lnf,expected",
    [
        ("Cornyn, John", "CORNYN"),
        ("Roth Jr., William V.", "ROTH"),
        ("Van Hollen, Chris", "VAN HOLLEN"),
        ("McConnell, Mitch", "MCCONNELL"),
        ("Scott, Rick", "SCOTT"),
    ],
)
def test_normalize_lnf(lnf, expected):
    assert normalize_lnf(lnf) == expected
