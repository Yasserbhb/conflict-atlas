import copy
from datetime import date
from conflict_updater import merge
from conflict_updater.schema import Proposal, Event, Source, Party, Conflict


def _seed():
    return {
        "version": "2.0.0",
        "conflicts": [{
            "id": "seed_gaza", "title": "Gaza War & Genocide", "type": "genocide", "severity": 4,
            "startDate": "2023", "ongoing": True, "status": "active",
            "parties": [{"countryId": "ISR", "role": "aggressor"}, {"countryId": "PSE", "role": "victim"}],
            "involvedCountries": ["ISR", "PSE"], "aliases": [], "tags": [],
            "events": [{"id": "seed_gaza_e1", "date": "2023-10-07", "title": "Oct 7 attack",
                        "kind": "attack", "severity": 5, "location": None,
                        "parties": ["PSE", "ISR"], "description": "", "sources": []}],
        }],
    }


def _attach(**over):
    p = dict(
        kind="attach", target_conflict_id="seed_gaza",
        event=Event(date="2024-05-01", title="Strike on Rafah", kind="attack", severity=5,
                    parties=["ISR", "PSE", "USA"], sources=[Source(url="http://a")]),
        roles=[Party(country_id="ISR", role="aggressor"), Party(country_id="PSE", role="victim"),
               Party(country_id="USA", role="funder")],
        status="active", needs_human=False, provisional=False,
    )
    p.update(over)
    return Proposal(**p)


def test_attach_updates_derived_fields_and_stays_coherent():
    seed = _seed()
    seed2, report = merge.apply([_attach()], seed)
    c = seed2["conflicts"][0]
    assert len(c["events"]) == 2
    assert "USA" in c["involvedCountries"]
    assert {"countryId": "USA", "role": "funder"} in c["parties"]
    assert c["severity"] == 5
    assert seed2["version"] == "2.0.1"
    assert merge.validate(seed2) == []  # dataset stays coherent


def test_needs_human_and_provisional_are_not_applied():
    seed = _seed()
    seed2, _ = merge.apply([_attach(needs_human=True), _attach(provisional=True)], seed)
    assert len(seed2["conflicts"][0]["events"]) == 1  # nothing attached
    assert seed2["version"] == "2.0.0"                # no bump


def test_status_only_changes_from_the_latest_event():
    # a backfilled OLD event must not flip current status
    seed = _seed()
    old = _attach(event=Event(date="2023-09-01", title="Older strike", kind="attack", severity=3,
                              parties=["ISR", "PSE"]),
                  status="ended")
    seed2, _ = merge.apply([old], seed)
    c = seed2["conflicts"][0]
    assert c["status"] == "active"   # unchanged: the new event isn't the latest
    assert c["ongoing"] is True


def test_latest_ceasefire_sets_suspended():
    seed = _seed()
    cf = _attach(event=Event(date="2025-01-19", title="Ceasefire", kind="ceasefire", severity=2,
                             parties=["ISR", "PSE"]),
                 status="suspended")
    seed2, _ = merge.apply([cf], seed)
    c = seed2["conflicts"][0]
    assert c["status"] == "suspended" and c["ongoing"] is True


_ISR_PSE = [Party(country_id="ISR", role="aggressor"), Party(country_id="PSE", role="victim")]


def test_attach_earlier_event_pulls_start_date_back():
    seed = _seed()   # seed_gaza startDate "2023", earliest event 2023-10-07
    early = _attach(event=Event(date="2022-01-01", title="Earlier incident", kind="attack",
                                severity=3, parties=["ISR", "PSE"]), roles=_ISR_PSE, status="active")
    seed2, _ = merge.apply([early], seed)
    c = seed2["conflicts"][0]
    assert c["startDate"] == "2022-01-01"   # span self-corrected backwards
    assert c["endDate"] is None             # still active → no end
    assert merge.validate(seed2) == []


def test_attach_latest_terminal_event_closes_end_date():
    seed = _seed()
    ender = _attach(event=Event(date="2025-06-01", title="Full withdrawal", kind="treaty",
                                severity=1, parties=["ISR", "PSE"]), roles=_ISR_PSE, status="ended")
    seed2, _ = merge.apply([ender], seed)
    c = seed2["conflicts"][0]
    assert c["status"] == "ended" and c["ongoing"] is False
    assert c["endDate"] == "2025-06-01"     # the terminal event closed the span
    assert c["startDate"] == "2023"
    assert merge.validate(seed2) == []


def test_new_conflict_is_added():
    seed = _seed()
    nc = Conflict(id="seed_new_sand_war", title="Sand War", type="war", severity=2,
                  start_date="1963", ongoing=False, status="ended",
                  parties=[Party(country_id="MAR", role="aggressor"), Party(country_id="DZA", role="defender")],
                  involved_countries=["MAR", "DZA"],
                  events=[Event(id="e1", date="1963-10-01", title="Clashes", kind="escalation",
                                severity=2, parties=["MAR", "DZA"])])
    p = Proposal(kind="new_conflict", event=nc.events[0], new_conflict=nc, needs_human=False)
    seed2, report = merge.apply([p], seed)
    ids = [c["id"] for c in seed2["conflicts"]]
    assert "seed_new_sand_war" in ids
    assert merge.validate(seed2) == []


def test_attach_to_a_same_batch_new_conflict_applies_regardless_of_list_order():
    # the attach proposal is listed BEFORE its founding new_conflict proposal — apply() must
    # not care about that ordering, since a scan may emit them either way.
    seed = _seed()
    nc = Conflict(id="seed_new_mokrani_revolt", title="Mokrani Revolt", type="war", severity=3,
                  start_date="1871", ongoing=False, status="ended",
                  parties=[Party(country_id="FRA", role="occupier"), Party(country_id="DZA", role="victim")],
                  involved_countries=["FRA", "DZA"],
                  events=[Event(id="e1", date="1871-03-15", title="Revolt begins", kind="escalation",
                                severity=3, parties=["FRA", "DZA"])])
    founding = Proposal(kind="new_conflict", event=nc.events[0], new_conflict=nc, needs_human=False)
    followup = Proposal(kind="attach", target_conflict_id="seed_new_mokrani_revolt",
                        event=Event(date="1871-05-01", title="Revolt crushed", kind="battle", severity=3,
                                   parties=["FRA", "DZA"]),
                        roles=[Party(country_id="FRA", role="occupier"), Party(country_id="DZA", role="victim")],
                        status="ended", needs_human=False)

    seed2, report = merge.apply([followup, founding], seed)  # attach listed FIRST
    c = next(c for c in seed2["conflicts"] if c["id"] == "seed_new_mokrani_revolt")
    assert len(c["events"]) == 2
    assert merge.validate(seed2) == []


def test_attach_to_an_unapproved_founding_conflict_is_skipped_clearly():
    seed = _seed()
    followup = Proposal(kind="attach", target_conflict_id="seed_new_unapproved_thing",
                        event=Event(date="1871-05-01", title="Some event", kind="battle", severity=3,
                                   parties=["FRA", "DZA"]),
                        needs_human=False)
    seed2, report = merge.apply([followup], seed)
    assert any("founding new_conflict proposal wasn't approved" in line for line in report)


def test_proposals_round_trip_through_json(tmp_path):
    # the `apply` CLI reads proposals back from disk — prove that path is coherent
    from conflict_updater.schema import ScanResult, ScanRequest
    from conflict_updater import store
    result = ScanResult(request=ScanRequest(period_start="2024", period_end="2024"),
                        proposals=[_attach()])
    path = tmp_path / "proposals.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    loaded = store.load_proposals(path)
    seed2, _ = merge.apply(loaded, _seed())
    assert len(seed2["conflicts"][0]["events"]) == 2
    assert merge.validate(seed2) == []


def test_accept_reviewed_flips_the_chosen_items():
    from conflict_updater.store import accept_reviewed
    props = [_attach(needs_human=True), _attach(needs_human=False), _attach(needs_human=True)]
    # human items (in order): props[0]=#1, props[2]=#2
    n = accept_reviewed(props, indices=[2])   # accept the 2nd needs-review item (props[2])
    assert n == 1
    assert props[2].needs_human is False and props[0].needs_human is True


def test_accept_reviewed_all():
    from conflict_updater.store import accept_reviewed
    props = [_attach(needs_human=True), _attach(needs_human=True)]
    assert accept_reviewed(props, approve_all=True) == 2
    assert all(not p.needs_human for p in props)


def test_apply_introduces_no_new_issues_despite_a_preexisting_one():
    # a pre-existing incoherence in an UNRELATED conflict must not be attributed to this apply
    seed = _seed()
    seed["conflicts"].append({
        "id": "seed_other", "title": "Other", "type": "war", "severity": 3,
        "startDate": "1900", "ongoing": False, "status": "ended",
        "parties": [{"countryId": "FRA", "role": "aggressor"}],
        "involvedCountries": [],  # FRA missing → a pre-existing issue
        "events": [],
    })
    before = set(merge.validate(seed))
    assert before  # confirm there IS a pre-existing issue
    seed2, _ = merge.apply([_attach()], seed)
    new_issues = set(merge.validate(seed2)) - before
    assert new_issues == set()  # the merge itself introduced nothing new


def test_validate_flags_incoherence():
    seed = _seed()
    seed["conflicts"][0]["parties"].append({"countryId": "GBR", "role": "funder"})  # not in involvedCountries
    issues = merge.validate(seed)
    assert any("GBR" in i for i in issues)


def test_attach_with_status_change_appends_to_status_history():
    seed = _seed()  # seed_gaza starts status="active"
    cf = _attach(event=Event(date="2025-01-19", title="Ceasefire", kind="ceasefire", severity=2,
                             parties=["ISR", "PSE"]), status="suspended")
    seed2, _ = merge.apply([cf], seed)
    c = seed2["conflicts"][0]
    assert c["statusHistory"] == [{"status": "suspended", "date": "2025-01-19", "eventId": c["events"][-1]["id"]}]


def test_attach_without_status_change_leaves_history_untouched_but_bumps_last_checked():
    seed = _seed()  # status already "active"
    seed2, _ = merge.apply([_attach(status="active")], seed)
    c = seed2["conflicts"][0]
    assert c.get("statusHistory", []) == []
    assert c["lastCheckedAt"] == date.today().isoformat()


def test_event_to_app_emits_corroboration_fields_when_present():
    seed = _seed()
    ev = Event(date="2024-05-01", title="Strike on Rafah", kind="attack", severity=5,
              parties=["ISR", "PSE"], sources=[Source(url="http://a")],
              independent_sources=3, cross_alignment=True)
    p = _attach(event=ev)
    seed2, _ = merge.apply([p], seed)
    added = seed2["conflicts"][0]["events"][-1]
    assert added["independentSources"] == 3
    assert added["crossAlignment"] is True


def test_event_to_app_nulls_corroboration_fields_when_absent():
    seed = _seed()
    seed2, _ = merge.apply([_attach()], seed)  # default Event() has no corroboration fields set
    added = seed2["conflicts"][0]["events"][-1]
    assert added["independentSources"] is None
    assert added["crossAlignment"] is None


def test_new_conflict_emits_empty_status_history_and_null_last_checked():
    seed = _seed()
    nc = Conflict(id="seed_new_sand_war2", title="Sand War", type="war", severity=2,
                  start_date="1963", ongoing=False, status="ended",
                  parties=[Party(country_id="MAR", role="aggressor"), Party(country_id="DZA", role="defender")],
                  involved_countries=["MAR", "DZA"],
                  events=[Event(id="e1", date="1963-10-01", title="Clashes", kind="escalation",
                                severity=2, parties=["MAR", "DZA"])])
    p = Proposal(kind="new_conflict", event=nc.events[0], new_conflict=nc, needs_human=False)
    seed2, _ = merge.apply([p], seed)
    c = next(c for c in seed2["conflicts"] if c["id"] == "seed_new_sand_war2")
    assert c["statusHistory"] == []
    assert c["lastCheckedAt"] is None
