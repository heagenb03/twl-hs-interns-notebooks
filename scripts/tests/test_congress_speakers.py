import re
from pathlib import Path

import pytest

from congress_speakers import (
    attribute_granule,
    last_speaker,
    normalize_lnf,
    split_turns,
)

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


# --- CRITICAL 1: same-surname disambiguation --------------------------------

TWO_SCOTTS = [
    {"lnf": "Scott, Rick", "bio": "S001217", "role": "SPEAKING", "state": "FL"},
    {"lnf": "Scott, Tim", "bio": "S001184", "role": "SPEAKING", "state": "SC"},
]


def test_same_surname_senators_are_disambiguated_by_state():
    """Five same-surname pairs served concurrently in 2010-2024. Keying the
    speaking map by surname alone collapses them and credits one senator's
    words entirely to the other, with no error raised."""
    text = (
        "  Mr. SCOTT of Florida. china FL.\n"
        "  Mr. SCOTT of South Carolina. china SC china SC."
    )
    attributed = attribute_granule(text, TWO_SCOTTS, carry_in=None)
    assert set(attributed) == {"S001217", "S001184"}
    assert len(re.findall("china", attributed["S001217"], re.I)) == 1
    assert len(re.findall("china", attributed["S001184"], re.I)) == 2


def test_ambiguous_same_surname_turn_without_qualifier_raises():
    """With two speaking Scotts, a bare 'Mr. SCOTT.' is genuinely ambiguous.
    Guessing is the exact failure mode being fixed, so it must raise."""
    text = "  Mr. SCOTT. china with no qualifier."
    with pytest.raises(ValueError, match="SCOTT"):
        attribute_granule(text, TWO_SCOTTS, carry_in=None)


def test_last_speaker_disambiguates_same_surname():
    """The carry-in boundary path shares the collapse bug; a wrong carry_in
    misfiles the head of the *next* granule."""
    text = "  Mr. SCOTT of South Carolina. china.\n  Mr. SCOTT of Florida. china."
    assert last_speaker(text, TWO_SCOTTS) == "S001217"


def test_unqualified_surname_still_works_when_only_one_member_has_it():
    """Most turns carry no qualifier. Disambiguation must not require one when
    there is nothing to disambiguate."""
    text = "  Mr. SCOTT. china."
    members = [{"lnf": "Scott, Rick", "bio": "S001217", "role": "SPEAKING", "state": "FL"}]
    assert set(attribute_granule(text, members, carry_in=None)) == {"S001217"}


# --- CRITICAL 2: dropped segments must not vanish ---------------------------

def test_header_absent_from_metadata_raises_instead_of_dropping_text():
    """`continue` on an unmatched header discards the segment. The totals-based
    checks still pass, so term mentions disappear with no error at all."""
    text = (
        "  Mr. THUNE. china one.\n"
        "  Mr. GHOST. china china china.\n"
        "  Mr. THUNE. china last."
    )
    members = [{"lnf": "Thune, John", "bio": "T000250", "role": "SPEAKING"}]
    with pytest.raises(ValueError, match="GHOST"):
        attribute_granule(text, members, carry_in=None)


# --- CRITICAL 3: carry_in exemption ----------------------------------------

def test_carry_in_is_excused_only_when_it_actually_received_text():
    """Exempting carry_in unconditionally excuses a member who spoke nowhere in
    the granule, disabling the guard for whichever bio happens to be carry_in."""
    text = "  Mr. THUNE. china china."
    members = [
        {"lnf": "Thune, John", "bio": "T000250", "role": "SPEAKING"},
        {"lnf": "Durbin, Richard J.", "bio": "D000563", "role": "SPEAKING"},
    ]
    with pytest.raises(ValueError, match="D000563"):
        attribute_granule(text, members, carry_in="D000563")


# --- regex gaps -------------------------------------------------------------

def test_accented_surname_is_matched():
    """Ben Ray Lujan was a sitting senator 2021-2024. An ASCII-only class makes
    'Mr. LUJAN.' (with an accent) match nothing, folding him into the previous
    speaker."""
    text = "  Mr. LUJÁN. china."
    assert [n for n, _ in split_turns(text)] == ["LUJAN"]
    members = [{"lnf": "Luján, Ben Ray", "bio": "L000570", "role": "SPEAKING"}]
    assert set(attribute_granule(text, members, carry_in=None)) == {"L000570"}


def test_normalize_lnf_folds_accents():
    assert normalize_lnf("Luján, Ben Ray") == "LUJAN"


def test_miss_honorific_is_matched():
    """'Miss' takes no period, so requiring one made that alternative dead."""
    assert [n for n, _ in split_turns("  Miss LANDRIEU. china.")] == ["LANDRIEU"]


# --- end-to-end attribution on a real multi-speaker granule -----------------

def test_attribute_granule_on_real_multi_speaker_granule():
    """attribute_granule against real CREC text rather than a toy string.

    NOTE: this granule spans pages S3975-S3980 and has 19 turns across 10
    distinct speakers, so the full speaking roster is passed. The china
    distribution over the four members of interest matches the split_turns
    test exactly, but arrived at through the real attribution path.
    """
    text = load("CREC-2021-06-08-pt1-PgS3975-2")
    members = [
        {"lnf": "Cornyn, John", "bio": "C001056", "role": "SPEAKING", "state": "TX"},
        {"lnf": "Scott, Rick", "bio": "S001217", "role": "SPEAKING", "state": "FL"},
        {"lnf": "Durbin, Richard J.", "bio": "D000563", "role": "SPEAKING", "state": "IL"},
        {"lnf": "Wicker, Roger F.", "bio": "W000437", "role": "SPEAKING", "state": "MS"},
        {"lnf": "Cantwell, Maria", "bio": "C000127", "role": "SPEAKING", "state": "WA"},
        {"lnf": "Kennedy, John", "bio": "K000393", "role": "SPEAKING", "state": "LA"},
        {"lnf": "Murray, Patty", "bio": "M001111", "role": "SPEAKING", "state": "WA"},
        {"lnf": "Paul, Rand", "bio": "P000603", "role": "SPEAKING", "state": "KY"},
        {"lnf": "Schumer, Charles E.", "bio": "S000148", "role": "SPEAKING", "state": "NY"},
        {"lnf": "Young, Todd", "bio": "Y000064", "role": "SPEAKING", "state": "IN"},
    ]
    attributed = attribute_granule(text, members, carry_in=None)
    counts = {
        bio: len(re.findall("china", seg, re.I)) for bio, seg in attributed.items()
    }
    assert {b: c for b, c in counts.items() if c} == {
        "C001056": 1,
        "S001217": 1,
        "D000563": 9,
        "W000437": 3,
    }
    # no text lost: the attributed china total equals the granule total
    assert sum(counts.values()) == len(re.findall("china", text, re.I)) == 14
