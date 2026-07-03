from conflict_updater.store import BaseConflict
from conflict_updater.schema import CandidateEvent
from conflict_updater import dedup


BASE = [
    BaseConflict(id="seed_gaza", title="Gaza War", involved_countries=["ISR", "PSE"], start=2023),
    BaseConflict(id="seed_ukraine", title="Russia's Invasion of Ukraine",
                 aliases=["Russo-Ukrainian War"], involved_countries=["RUS", "UKR"], start=2022),
    BaseConflict(id="seed_ww2", title="World War II", involved_countries=["DEU", "USA"],
                 start=1939, end=1945),
]


def test_matches_the_right_conflict():
    cand = CandidateEvent(date="2024-05-01", title="Israeli strike on Gaza City",
                          actors=["Israel", "Palestine"], place="Gaza")
    cands = dedup.find_candidates(BASE, cand)
    assert cands, "expected at least one candidate"
    assert cands[0][0].id == "seed_gaza"


def test_alias_helps_match():
    cand = CandidateEvent(date="2023-01-01", title="Russo-Ukrainian War offensive",
                          actors=["Russia", "Ukraine"], place="Bakhmut")
    cands = dedup.find_candidates(BASE, cand)
    assert cands[0][0].id == "seed_ukraine"


def test_unrelated_event_scores_low():
    cand = CandidateEvent(date="2024-01-01", title="Peruvian coffee export dispute",
                          actors=["Peru"], place="Lima")
    cands = dedup.find_candidates(BASE, cand)
    assert all(c.id != "seed_gaza" for c, _ in cands)


def test_date_out_of_range_penalised():
    # same event text, but an out-of-range date must score lower than an in-range one
    ww2 = BASE[2]
    cand_in = CandidateEvent(date="1943-01-01", title="World War II battle", actors=["Germany", "USA"])
    cand_out = CandidateEvent(date="2024-01-01", title="World War II battle", actors=["Germany", "USA"])
    assert dedup.score(ww2, cand_in) > dedup.score(ww2, cand_out)
