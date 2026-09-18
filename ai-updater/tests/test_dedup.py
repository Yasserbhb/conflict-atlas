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


# ---- retrieval: the cold-start failures -----------------------------------------------------
# A conflict founded by one incident is NAMED after that incident, so nothing later matches it on
# the title alone. These are the signals that let the second event find the first.

def _c(**kw):
    from conflict_updater.store import BaseConflict
    kw.setdefault("id", "c1")
    kw.setdefault("title", "Untitled")
    return BaseConflict(**kw)


def _e(**kw):
    from conflict_updater.schema import CandidateEvent
    kw.setdefault("date", "2026-06-01")
    kw.setdefault("title", "Something happened")
    return CandidateEvent(**kw)


def test_the_articles_own_name_for_the_war_finds_the_parent():
    """The whole point. The event title shares nothing with the conflict title; the source's
    framing does, and that is what `context` carries."""
    from conflict_updater.dedup import score
    war = _c(id="seed_ww2", title="Second World War", start=1939, end=1945)
    pearl = _e(date="1941-12-07", title="Japanese aircraft strike Pearl Harbor",
               actors=["Japan", "United States"])
    bare = score(war, pearl)
    with_ctx = score(war, pearl.model_copy(update={"context": "the Second World War"}))
    # Bare, it scrapes onto the candidate list on the date bonus alone and would rank below any
    # conflict that shares a word with the headline. With the source's own framing it is the
    # obvious match.
    assert bare < 0.25
    assert with_ctx > 0.5
    assert with_ctx > bare * 2.5


def test_actors_match_the_conflicts_countries_not_just_its_title():
    """"Operation Prosperity Guardian" contains neither belligerent's name, so the old scorer gave
    it exactly 0 and it never reached the resolver at all.

    It should now clear the retrieval floor — enough to be offered as an option — without winning
    on actors alone. Sharing belligerents is consistent-with, not evidence-of: every European war
    involves Germany or France, and weighting actors highly collapses the atlas into whichever
    conflicts have the most members."""
    from conflict_updater.dedup import score, find_candidates
    op = _c(id="seed_op", title="Operation Prosperity Guardian", start=2023,
            involved_countries=["USA", "YEM"], country_names=["United States", "Yemen"])
    ev = _e(date="2024-02-01", title="Strike on radar site", actors=["United States", "Yemen"])
    assert score(op, ev) >= 0.18, "must reach the candidate list"
    assert [c.id for c, _ in find_candidates([op], ev)] == ["seed_op"]


def test_sharing_belligerents_does_not_beat_naming_the_conflict():
    # The failure this replaced: unrelated European wars scored 0.4+ on shared actors alone.
    from conflict_updater.dedup import score
    right = _c(id="seed_ww2", title="Second World War", start=1939, end=1945,
               country_names=["Germany", "Poland"])
    wrong = _c(id="seed_spain", title="Spanish Civil War", start=1936, end=1939,
               country_names=["Germany", "Spain", "Poland"])
    ev = _e(date="1939-09-01", title="Germany invades Poland", context="the Second World War",
            actors=["Germany", "Poland"])
    assert score(right, ev) > score(wrong, ev) * 1.5


def test_world_war_one_and_two_are_not_the_same_war():
    # Stripping the generic word leaves "world i" vs "world ii" — 0.93 on character similarity.
    from conflict_updater.dedup import score
    ww1 = _c(id="seed_ww1", title="World War I", start=1914, end=1918,
             country_names=["Germany", "France"])
    ev = _e(date="1940-05-10", title="Germany invades France", context="World War II",
            actors=["Germany", "France"])
    assert score(ww1, ev) < 0.3


def test_a_generic_war_word_is_not_a_match():
    # Every conflict has "War" in its title; matching on it would make everything look alike.
    from conflict_updater.dedup import score
    sudan = _c(id="seed_sudan", title="Sudan Civil War", start=2023,
               country_names=["Sudan"])
    ev = _e(date="2024-01-01", title="Civil war fighting continues", actors=["Myanmar"])
    assert score(sudan, ev) < 0.25


def test_non_latin_titles_can_match_at_all():
    # [a-z0-9]+ tokenised these to the empty set, so 9 languages of sources could never resolve.
    from conflict_updater.dedup import _tokens, score
    assert _tokens("حرب غزة"), "an Arabic title must produce tokens"
    gaza = _c(id="seed_gaza", title="حرب غزة", start=2023)
    ev = _e(date="2024-01-01", title="غارة على غزة", context="حرب غزة")
    assert score(gaza, ev) > 0.4


def test_date_distance_is_graded_not_binary():
    """One year out and three centuries out used to score identically."""
    from conflict_updater.dedup import score
    war = _c(id="seed_x", title="Algerian War", start=1954, end=1962,
             country_names=["Algeria", "France"])
    near = _e(date="1963-01-01", title="Algerian War aftermath", actors=["Algeria"])
    far = _e(date="1830-01-01", title="Algerian War aftermath", actors=["Algeria"])
    assert score(war, near) > score(war, far)


def test_an_ongoing_conflict_does_not_swallow_every_future_date():
    # end was defaulted to 2100, so any date at all fell "inside the span".
    from conflict_updater.dedup import score
    c = _c(id="seed_o", title="Some Insurgency", start=2024, end=None, country_names=["Mali"])
    assert score(c, _e(date="2075-01-01", title="Unrelated", actors=["Peru"])) < 0.2


def test_a_conflicts_own_events_pull_nearby_dates_in():
    from conflict_updater.dedup import score
    with_ev = _c(id="a", title="Some Operation", start=2020,
                 events=[{"date": "2026-06-02", "title": "x"}])
    without = _c(id="b", title="Some Operation", start=2020)
    ev = _e(date="2026-06-01", title="Another strike")
    assert score(with_ev, ev) > score(without, ev)


# ---- names harvested from prose --------------------------------------------------------------

def test_clean_name_keeps_names_and_rejects_non_names():
    from conflict_updater.dedup import clean_name
    assert clean_name("the Second World War") == "Second World War"
    assert clean_name("The Gaza war.") == "Gaza war"
    assert clean_name("the ongoing conflict") == "", "names nothing — would match everything"
    assert clean_name("") == ""
    assert clean_name("a clause explaining at length what the article happens to be about") == ""


def test_the_description_is_a_fallback_when_the_article_names_nothing():
    """`context` is empty whenever the source doesn't name the war, and that is the case that
    fragments. The event's own description usually mentions it in passing, which lifts retrieval
    from 81% to 91% of curated events reaching their real parent."""
    from conflict_updater.dedup import score
    war = _c(id="seed_ww2", title="Second World War", start=1939, end=1945,
             country_names=["Germany", "Poland"])
    bare = _e(date="1939-09-01", title="Forces cross the border", actors=["Germany"])
    with_desc = bare.model_copy(
        update={"action": "the opening campaign of the Second World War"})
    assert score(war, with_desc) > score(war, bare)


# ---- the property that actually matters -----------------------------------------------------

def test_a_conflict_can_be_rebuilt_from_its_own_events():
    """Cold start, end to end: remove a conflict from the atlas and feed its events back.

    One conflict in, ONE conflict out. More than one is fragmentation, and fragmentation is
    permanent because nothing merges conflicts afterwards. Attaching to some unrelated existing
    conflict is worse still.

    Run against the real seed.json rather than a fixture, because the failure mode is entirely
    about competition with the other 239 conflicts — a synthetic atlas of three would prove
    nothing. Before this change WWII came back as 4 fragments plus 6 events lost into the Spanish
    Civil War and the Holocaust.
    """
    import json
    from pathlib import Path
    from conflict_updater.dedup import clean_name, find_candidates, _year
    from conflict_updater.schema import CandidateEvent
    from conflict_updater.store import BaseConflict, base_from_seed

    seed_path = Path(__file__).resolve().parents[2] / "src" / "data" / "seed.json"
    if not seed_path.exists():                       # running outside the repo
        import pytest
        pytest.skip("seed.json not available")
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    country = {c["id"]: c.get("name", c["id"]) for c in seed["countries"]}

    target = max((c for c in seed["conflicts"]), key=lambda c: len(c.get("events", [])))
    others = {"countries": seed["countries"],
              "conflicts": [c for c in seed["conflicts"] if c["id"] != target["id"]]}
    base = base_from_seed(others)
    existing_ids = {c.id for c in base}

    founded: list[BaseConflict] = []
    for e in sorted(target.get("events", []), key=lambda x: x.get("date") or ""):
        cand = CandidateEvent(
            date=e.get("date", ""), title=e.get("title", ""),
            action=(e.get("description") or "")[:120],
            actors=[country.get(p, p) for p in (e.get("parties") or [])],
            context=target["title"],                 # the article names the war, as most do
        )
        hits = find_candidates(base + founded, cand)
        best = hits[0] if hits else None
        if best and best[1] >= 0.45:
            chosen = best[0]
            assert chosen.id not in existing_ids, (
                f"{e.get('title')!r} was absorbed by an unrelated conflict: {chosen.title!r}")
        else:
            chosen = BaseConflict(
                id=f"new_{len(founded) + 1}", title=clean_name(cand.context) or cand.title,
                country_names=[country.get(p, p) for p in (e.get("parties") or [])],
                start=_year(cand.date), events=[])
            founded.append(chosen)
        chosen.events.append({"date": cand.date, "title": cand.title})

    assert len(founded) == 1, (
        f"{target['title']} came back as {len(founded)} conflicts: "
        f"{[c.title for c in founded]}")
    assert founded[0].title == target["title"], "and it should carry the name the sources use"
    assert len(founded[0].events) == len(target["events"])
