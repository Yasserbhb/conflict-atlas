from conflict_updater.schema import Event, Conflict, Proposal, Location, Party, Source


def test_event_roundtrips():
    e = Event(
        date="1944-06-06", title="D-Day", kind="offensive", severity=5,
        location=Location(lat=49.34, lng=-0.51, label="Normandy"),
        parties=["USA", "GBR", "FRA", "DEU"],
        description="Allied landings.",
        sources=[Source(url="https://en.wikipedia.org/wiki/Normandy_landings")],
    )
    back = Event.model_validate_json(e.model_dump_json())
    assert back.kind == "offensive" and back.severity == 5
    assert back.location and back.location.label == "Normandy"


def test_place_less_event():
    e = Event(date="1933", title="Famine peaks", kind="atrocity", severity=5, location=None)
    assert e.location is None


def test_severity_bounds():
    import pytest
    with pytest.raises(Exception):
        Event(date="2020", title="x", severity=9)


def test_conflict_and_proposal():
    c = Conflict(
        id="seed_x", title="Example War", type="war", severity=4,
        start_date="2001", parties=[Party(country_id="USA", role="aggressor")],
        involved_countries=["USA"], aliases=["The X War"],
    )
    p = Proposal(kind="attach", target_conflict_id="seed_x",
                 event=Event(date="2001", title="e", kind="battle", severity=3))
    assert Proposal.model_validate_json(p.model_dump_json()).kind == "attach"
    assert "The X War" in c.aliases
