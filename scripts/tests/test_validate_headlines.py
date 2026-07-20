import pandas as pd
import pytest

from validate_data import validate_headlines


@pytest.fixture
def good() -> pd.DataFrame:
    rows = []
    events = [
        "2018 tariff announcement", "Huawei CFO arrest", "Phase One deal",
        "Hong Kong security law", "TikTok ban push", "Spy balloon",
    ]
    for event in events:
        for outlet in ["NYT", "WSJ", "Fox", "Xinhua"]:
            for i in range(3):
                rows.append({"event": event, "outlet": outlet,
                             "headline": f"{outlet} on {event} number {i}"})
    return pd.DataFrame(rows, columns=["event", "outlet", "headline"])


def test_good_frame_has_no_problems(good):
    assert validate_headlines(good) == []


def test_wrong_columns_are_reported(good):
    broken = good.rename(columns={"headline": "title"})
    assert any("headline" in p for p in validate_headlines(broken))


def test_unknown_outlet_is_reported(good):
    broken = pd.concat([good, pd.DataFrame([
        {"event": "Spy balloon", "outlet": "Reuters", "headline": "x"}])])
    assert any("Reuters" in p for p in validate_headlines(broken))


def test_unknown_event_is_reported(good):
    broken = pd.concat([good, pd.DataFrame([
        {"event": "Made Up Event", "outlet": "NYT", "headline": "x"}])])
    assert any("Made Up Event" in p for p in validate_headlines(broken))


def test_phase_one_must_be_the_third_distinct_event(good):
    """Row order is load-bearing: the notebook uses unique()[2]."""
    broken = good[good.event != "Huawei CFO arrest"]
    problems = validate_headlines(broken)
    assert any("Phase One deal" in p and "third" in p.lower() for p in problems)


def test_outlet_below_stratify_floor_is_reported(good):
    broken = good[~((good.outlet == "WSJ") & (good.index > 5))]
    broken = pd.concat([good[good.outlet != "WSJ"],
                        good[good.outlet == "WSJ"].head(1)])
    problems = validate_headlines(broken)
    assert any("WSJ" in p and "2" in p for p in problems)


def test_empty_headline_is_reported(good):
    broken = good.copy()
    broken.loc[broken.index[0], "headline"] = "   "
    assert any("empty" in p.lower() for p in validate_headlines(broken))


def test_duplicate_within_outlet_is_reported(good):
    broken = pd.concat([good, good.head(1)])
    assert any("duplicate" in p.lower() for p in validate_headlines(broken))


def test_missing_outlet_tolerated_by_default(good):
    """Real data may be thin; the approved policy is take-what-exists."""
    thin = good[good.outlet != "Xinhua"]
    assert not any("Xinhua" in p and "missing" in p.lower()
                   for p in validate_headlines(thin))


def test_missing_outlet_reported_when_required(good):
    thin = good[good.outlet != "Xinhua"]
    problems = validate_headlines(thin, require_all_outlets=True)
    assert any("Xinhua" in p for p in problems)
