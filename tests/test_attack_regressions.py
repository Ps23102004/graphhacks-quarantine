"""Regressions for defects the Saturday attack workflow reproduced (one test per defect, each failed before its fix)."""
from __future__ import annotations

import copy

import pytest

from quarantine import queries as Q
from quarantine.answers import why_quarantined
from quarantine.loader import connect, load, q, read_fixture, rework, validate_fixture


def fresh(name):
    g = connect(name)
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass
    return connect(name)


def world(**over):
    """Small valid world: four docs, one fact voted on by four episodes, one step reading it."""
    w = {
        "sessions": {"s1": {"label": "t"}},
        "agents": {"research": {"role": "r"}, "planner": {"role": "p"}, "coder": {"role": "c"}},
        "docs": {f"d{i}": {"uri": f"u{i}", "title": f"t{i}"} for i in range(1, 6)},
        "episodes": {f"e{i}": {"doc": f"d{i}", "tick": i, "text": f"from d{i}"} for i in range(1, 6)},
        "facts": {"f": {"subject": "s", "slot": "x", "tick": 10, "value": "z",
                        "support": [{"ep": "e1", "claim": "x"}, {"ep": "e2", "claim": "x"},
                                    {"ep": "e3", "claim": "y"}, {"ep": "e4", "claim": "z"}]}},
        "steps": {"s": {"order": 1, "tick": 11, "text": "step", "reads": ["f"]}},
        "artifacts": {"a": {"path": "a.py", "tick": 12, "text": "art", "reads": ["s"]}},
    }
    for k, v in over.items():
        w[k] = v
    return w


def flag(g, doc, tick=900):
    q(g, Q.FLAG_DOC, doc=doc, reason="t", tick=tick)
    q(g, Q.TAINT_CLOSURE, doc=doc, tick=tick)
    q(g, Q.SUPPORT_AND_HEALABLE)


# ---------------------------------------------------------------- twin ids cannot collide with real ids
def test_ids_with_the_reserved_twin_suffix_are_refused():
    w = world()
    w["steps"]["s_v2"] = {"order": 2, "tick": 13, "text": "a real step that happens to end in _v2", "reads": ["f"]}
    with pytest.raises(ValueError, match="reserved"):
        validate_fixture(w)


def test_rework_never_deletes_a_memory_it_did_not_create():
    g = fresh("reg_rework_collision")
    try:
        load(g, world())
        flag(g, "d4")
        # a node already holds the twin id but is not a replacement of s (simulates any id collision)
        q(g, "CREATE (:Memory:PlanStep {id: 's_v2', tick: 1, text: 'someone else', quarantined: false})")
        with pytest.raises(ValueError, match="already exists"):
            rework(g, "s", "planner", "redo", [], 950, "s2")
        assert q(g, "MATCH (m:Memory {id: 's_v2'}) RETURN m.text") == [["someone else"]]
    finally:
        connect("reg_rework_collision").delete()


# ---------------------------------------------------------------- an outvoted episode is not provenance
def test_outvoted_episode_is_recorded_but_not_followed_as_provenance():
    g = fresh("reg_outvoted")
    try:
        load(g, world())
        flag(g, "d4")                                                   # f was consolidated from e4 (claim z)
        healed = q(g, Q.HEAL_FACTS, session="s2", tick=901)
        assert healed == [["f_v2", "x", 2]]                             # x: e1, e2; y (e3) outvoted
        assert q(g, "MATCH (:Fact {id: 'f_v2'})-[r:OUTVOTED]->(e) RETURN e.id, r.claim") == [["e3", "y"]]
        flag(g, "d3", tick=950)                                         # the outvoted voter's doc turns out bad
        assert q(g, "MATCH (m:Memory {id: 'f_v2'}) RETURN m.quarantined") == [[False]]
        assert why_quarantined(g, "f_v2")["shape"] == "not_in_graph"   # no receipt through a rejected vote
    finally:
        connect("reg_outvoted").delete()


# ---------------------------------------------------------------- the vote ignores case and stray spaces
def test_vote_groups_claims_that_differ_only_in_case_or_spaces():
    w = world()
    w["facts"]["f"]["support"] = [{"ep": "e1", "claim": "requests"}, {"ep": "e2", "claim": "Requests"},
                                  {"ep": "e3", "claim": "requests "}, {"ep": "e4", "claim": "reqeusts"},
                                  {"ep": "e5", "claim": "reqeusts"}]
    w["facts"]["f"]["value"] = "reqeusts"
    w["episodes"]["e5"]["doc"] = "d4"                                    # the poisoned doc supplied two episodes
    g = fresh("reg_vote_case")
    try:
        load(g, w)
        flag(g, "d4")
        assert q(g, "MATCH (f:Fact {id: 'f'}) RETURN f.healable") == [[True]]
        healed = q(g, Q.HEAL_FACTS, session="s2", tick=901)
        assert len(healed) == 1 and healed[0][0] == "f_v2" and healed[0][2] == 3
        assert healed[0][1].strip().lower() == "requests"
    finally:
        connect("reg_vote_case").delete()


# ---------------------------------------------------------------- session2 heals even when nothing reads the fact
def test_session2_heals_a_fact_that_no_step_reads(tmp_path, capsys):
    import yaml

    from quarantine import cli

    w = world()
    w["steps"], w["artifacts"] = {}, {}
    p = tmp_path / "w.yaml"
    p.write_text(yaml.safe_dump(w))
    try:
        cli.main(["session1", "--fixture", str(p), "--graph", "reg_cli_factonly"])
        cli.main(["flag", "d4", "--fixture", str(p), "--graph", "reg_cli_factonly"])
        cli.main(["session2", "--fixture", str(p), "--graph", "reg_cli_factonly"])
        out = capsys.readouterr().out
        assert "healed f -> f_v2 = x" in out
    finally:
        connect("reg_cli_factonly").delete()


# ---------------------------------------------------------------- bad worlds are refused before anything is written
@pytest.mark.parametrize("breakage,match", [
    (lambda w: w["sessions"].pop("s1"), "s1"),
    (lambda w: w["steps"]["s"].update(agent="nobody"), "unknown agent"),
    (lambda w: w["facts"]["f"]["support"][0].pop("claim"), "claim"),
    (lambda w: w["steps"]["s"].pop("reads"), "reads"),
    (lambda w: w["artifacts"]["a"].pop("path"), "path"),
    (lambda w: w["docs"]["d1"].update(flagged=True), "reserved"),
    (lambda w: w["episodes"]["e1"].update(text=["not", "a", "string"]), "text"),
])
def test_validate_fixture_refuses_worlds_load_would_choke_on(breakage, match):
    w = copy.deepcopy(world())
    breakage(w)
    with pytest.raises(ValueError, match=match):
        validate_fixture(w)


def test_session1_with_a_bad_world_leaves_the_previous_graph_alone(tmp_path):
    import yaml

    from quarantine import cli

    good, bad = tmp_path / "good.yaml", tmp_path / "bad.yaml"
    good.write_text(yaml.safe_dump(world()))
    w = world()
    w["steps"]["s"]["agent"] = "nobody"
    bad.write_text(yaml.safe_dump(w))
    try:
        cli.main(["session1", "--fixture", str(good), "--graph", "reg_cli_bad"])
        with pytest.raises(SystemExit) as e:
            cli.main(["session1", "--fixture", str(bad), "--graph", "reg_cli_bad"])
        assert "unknown agent" in str(e.value)
        assert q(connect("reg_cli_bad"), "MATCH (m:Memory) RETURN count(m)") == [[8]]
    finally:
        connect("reg_cli_bad").delete()


def test_duplicate_keys_in_a_fixture_are_an_error_not_a_silent_overwrite(tmp_path):
    p = tmp_path / "dup.yaml"
    p.write_text("episodes:\n  e1: {doc: d1, tick: 1, text: clean}\n  e1: {doc: d9, tick: 1, text: poisoned}\n")
    with pytest.raises(ValueError, match="duplicate key"):
        read_fixture(p)


@pytest.mark.parametrize("content", [None, "", "- just\n- a list\n", "a: !!python/name:os.system\n", b"\xff\xfe"])
def test_unreadable_fixtures_give_one_line_errors(tmp_path, content):
    from quarantine import cli

    p = tmp_path / "x.yaml"
    if isinstance(content, bytes):
        p.write_bytes(content)
    elif content is not None:
        p.write_text(content)                                          # None: the file does not exist
    with pytest.raises(SystemExit) as e:
        cli.main(["session1", "--fixture", str(p), "--graph", "reg_never_created"])
    assert str(e.value).startswith("quarantine: ")


# ---------------------------------------------------------------- the page on a graph that does not exist yet
def test_snapshot_of_a_graph_that_does_not_exist_is_empty_not_an_error():
    from web.server import snapshot

    snap = snapshot(connect("reg_graph_that_was_never_created"))
    assert snap["nodes"] == [] and snap["docs"] == [] and snap["edges"] == [] and snap["counters"] is None
