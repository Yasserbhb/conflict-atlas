import copy
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


def test_validate_flags_incoherence():
    seed = _seed()
    seed["conflicts"][0]["parties"].append({"countryId": "GBR", "role": "funder"})  # not in involvedCountries
    issues = merge.validate(seed)
    assert any("GBR" in i for i in issues)
