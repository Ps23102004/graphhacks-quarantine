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
    (lambda w: w["facts"]["f"].update(reads=["e1"]), "unknown key"),          # provenance that load() would drop
    (lambda w: w["facts"]["f"]["support"].append({"ep": "e1", "claim": "x"}), "same episode twice"),
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


# ---------------------------------------------------------------- crash consistency (torn writes are repaired, never shown as done)
def _demo(name):
    g = fresh(name)
    load(g, read_fixture("fixture.yaml"))
    return g


def red_ids(g):
    return {r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id")}


SIX = {"ep_7a", "ep_7b", "f_http_client", "f_http_pin", "step_3", "a_requirements"}


def test_flag_and_its_closure_are_one_write():
    g = _demo("reg_atomic_flag")
    try:
        precise, ids_ = q(g, Q.FLAG_AND_CLOSE, doc="doc_7", reason="t", tick=40)[0]
        assert precise == 6 and set(ids_) == SIX == red_ids(g)
    finally:
        connect("reg_atomic_flag").delete()


def test_status_reports_a_torn_flag_and_reconcile_repairs_it():
    from quarantine.agent_runtime import recovery_status
    from quarantine.loader import reconcile

    g = _demo("reg_torn_flag")
    try:
        q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)              # the process died before the closure
        st = recovery_status(g)
        assert st["complete"] is False and any("not quarantined" in w for w in st["warnings"])
        reconcile(g)
        assert red_ids(g) == SIX
        assert q(g, "MATCH (t:Task) RETURN count(t)")[0][0] == 2          # rework_step_3, rework_a_requirements
        assert recovery_status(g)["warnings"] == ["2 rework task(s) remaining to reach fixpoint", "1 healable fact(s) not healed yet"]
    finally:
        connect("reg_torn_flag").delete()


def test_unflag_never_passes_through_a_state_where_a_still_flagged_doc_is_clean():
    from quarantine.loader import unflag

    g = _demo("reg_unflag_atomic")
    try:
        q(g, Q.FLAG_AND_CLOSE, doc="doc_7", reason="t", tick=40)
        q(g, Q.FLAG_AND_CLOSE, doc="doc_5", reason="t", tick=41)
        unflag(g, "doc_5")
        assert red_ids(g) == SIX
        assert {r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) RETURN DISTINCT m.quarantine_doc")} == {"doc_7"}
        with pytest.raises(KeyError, match="not flagged"):
            unflag(g, "doc_5")                                          # retracting twice is an error, not a success
    finally:
        connect("reg_unflag_atomic").delete()


def test_session1_writes_each_memory_with_its_read_set_in_one_statement():
    g = _demo("reg_s1_atomic")
    try:
        assert q(g, "MATCH (s:Session {id: 's1'}) RETURN s.complete") == [[True]]
        bare = q(g, "MATCH (m:Memory) WHERE (m:PlanStep OR m:Artifact) AND NOT (m)-[:INFLUENCED_BY]->() RETURN count(m)")
        assert bare == [[0]]
    finally:
        connect("reg_s1_atomic").delete()


def test_a_restarted_session2_resumes_its_own_dead_claim(capsys):
    from quarantine import cli

    try:
        cli.main(["session1", "--graph", "reg_resume"])
        cli.main(["flag", "doc_7", "--graph", "reg_resume"])
        g = connect("reg_resume")
        q(g, Q.SUPPORT_AND_HEALABLE)
        q(g, Q.HEAL_FACTS, session="s2", tick=41)
        q(g, Q.PROMOTE_READY)
        assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=42, lease=5, session="s2")   # then the process died
        cli.main(["session2", "--graph", "reg_resume"])
        out = capsys.readouterr().out
        assert "fixpoint" in out and "could not" not in out
        assert q(g, "MATCH (t:Task) WHERE t.state <> 'done' RETURN count(t)") == [[0]]
    finally:
        connect("reg_resume").delete()


def test_status_and_session2_on_a_missing_graph_give_one_line_errors():
    from quarantine import cli

    for cmd in ("status", "session2"):
        with pytest.raises(SystemExit) as e:
            cli.main([cmd, "--graph", "reg_graph_that_was_never_created"])
        assert "does not exist" in str(e.value)
        g = connect("reg_graph_that_was_never_created")
        with pytest.raises(Exception, match="empty key"):
            g.ro_query("MATCH (n) RETURN n")                            # and the command did not create it


def test_live_placeholders_and_unhealed_facts_are_not_reported_complete():
    from quarantine.agent_runtime import recovery_status
    from quarantine.loader import derive_rework, rework

    g = _demo("reg_placeholders")
    try:
        q(g, Q.FLAG_AND_CLOSE, doc="doc_7", reason="t", tick=40)
        q(g, Q.SUPPORT_AND_HEALABLE)
        st = recovery_status(g)
        assert st["complete"] is False and any("healable" in w for w in st["warnings"])
        q(g, Q.HEAL_FACTS, session="s2", tick=41)
        spec = derive_rework(g, "step_3")
        rework(g, "step_3", "planner", spec["text"], spec["reads"], 42, "s2", needs_regeneration=True)
        assert any("needs regeneration" in w for w in recovery_status(g)["warnings"])
    finally:
        connect("reg_placeholders").delete()


# ---------------------------------------------------------------- scripted rework must be checked against the current graph (Aashna, Windows run)
import itertools

_DOCS = [f"doc_{i}" for i in range(1, 9)]


@pytest.mark.parametrize("docs", [[d] for d in _DOCS] + [list(c) for c in itertools.combinations(_DOCS, 2)])
def test_session2_reaches_a_fixpoint_for_any_flagged_documents(docs, capsys):
    from quarantine import cli
    from quarantine.agent_runtime import recovery_status

    g = "reg_any_flag"
    try:
        cli.main(["session1", "--graph", g])
        for d in docs:
            cli.main(["flag", d, "--graph", g])
        cli.main(["session2", "--graph", g])
        out = capsys.readouterr().out
        assert "fixpoint" in out
        st = recovery_status(connect(g))
        assert st["complete"] is True or st["warnings"] == [] or all("placeholder" in w for w in st["warnings"]), st["warnings"]
        assert q(connect(g), "MATCH (t:Task) WHERE t.state <> 'done' RETURN count(t)") == [[0]]
        for audit in (Q.AUDIT_CLEAN_NEVER_CITES_QUARANTINED, Q.AUDIT_CLOSURE_IS_CLOSED):
            assert q(connect(g), audit)[0][0] == 0
    finally:
        connect(g).delete()


# ---------------------------------------------------------------- Aashna's second report (Windows run)
def test_status_lists_the_agents_of_any_world():
    from quarantine.agent_runtime import recovery_status

    g = fresh("reg_status_agents")
    try:
        load(g, read_fixture("fixtures/support-crew.yaml"))
        agents = recovery_status(g)["agents"]
        assert set(agents) == {"ingest", "triage", "responder"} and sum(a["total_authored"] for a in agents.values()) == 21
    finally:
        connect("reg_status_agents").delete()


def test_fixture_path_falls_back_to_the_installed_share_directory(tmp_path, monkeypatch):
    import quarantine.loader as L

    monkeypatch.chdir(tmp_path)                                          # not a checkout: relative path does not exist here
    assert L.read_fixture("fixtures/support-crew.yaml")["docs"]


def test_tools_never_hand_quarantined_text_to_an_agent():
    """Security review: a quarantined memory's text may be the injection itself; recall and inspect withhold it."""
    from quarantine.answers import WITHHELD, recall

    g = _demo("reg_withhold")
    try:
        assert "reqeusts" in recall(g, "f_http_client")["answer"]                  # before the advisory it is just memory
        q(g, Q.FLAG_AND_CLOSE, doc="doc_7", reason="t", tick=40)
        r = recall(g, "f_http_client")
        assert r["answer"] == WITHHELD and r["quarantined"] is True
        assert recall(g, "f_goal")["answer"] != WITHHELD                             # clean memory still answers
    finally:
        connect("reg_withhold").delete()


# ---------------------------------------------------------------- round 2 (engine): supersession chains, the clock, torn states, hostile worlds
def _cli(*argv):
    from quarantine import cli

    cli.main(list(argv))


def _unfinished(g):
    return q(g, "MATCH (t:Task) WHERE t.state <> 'done' RETURN t.id, t.state ORDER BY t.id")


def test_a_second_advisory_after_a_heal_reworks_through_the_supersedes_chain(capsys):
    """session2 died after its first heal; then doc_5 reaches the healed twin. The blocker resolves to the chain head."""
    g = "r2engine_chain"
    try:
        _cli("session1", "--graph", g)
        _cli("flag", "doc_7", "--graph", g)
        q(connect(g), Q.HEAL_FACTS, session="s2", tick=41)               # then the process died
        _cli("flag", "doc_5", "--graph", g)
        _cli("session2", "--graph", g)
        gg = connect(g)
        assert _unfinished(gg) == []
        assert q(gg, "MATCH (:Memory {id: 'step_3_v2'})-[:INFLUENCED_BY]->(x) RETURN x.id ORDER BY x.id") \
            == [["f_deps"], ["f_http_client_v2_v2"]]
        st = __import__("quarantine.agent_runtime", fromlist=["x"]).recovery_status(gg)
        assert st["agents"]["planner"]["unresolved"] == st["agents"]["coder"]["unresolved"] == 0, st["agents"]
    finally:
        connect(g).delete()


def _outvote_world():
    """f: x from da, y from db (3 episodes), z from dc (2). Flag da heals f to y; flag db then kills that twin while the
    root f still has a clean z majority, which HEAL_FACTS re-heals from the root's full support (f_v2_v2 = z)."""
    eps = {"ea": "da", "eb1": "db", "eb2": "db", "eb3": "db", "ec1": "dc", "ec2": "dc"}
    claims = {"ea": "x", "eb1": "y", "eb2": "y", "eb3": "y", "ec1": "z", "ec2": "z"}
    return world(docs={d: {"uri": d} for d in ("da", "db", "dc")},
                 episodes={e: {"doc": d, "tick": i + 1, "text": e} for i, (e, d) in enumerate(eps.items())},
                 facts={"f": {"subject": "s", "slot": "x", "tick": 10, "value": "x",
                              "support": [{"ep": e, "claim": c} for e, c in claims.items()]}})


def test_session2_fails_loudly_when_tasks_remain_at_its_fixpoint(tmp_path):
    import yaml

    p = tmp_path / "ov.yaml"
    p.write_text(yaml.safe_dump(_outvote_world()))
    g = "r2engine_unfinished"
    try:
        _cli("session1", "--fixture", str(p), "--graph", g)
        _cli("flag", "da", "--fixture", str(p), "--graph", g)
        q(connect(g), Q.HEAL_FACTS, session="s2", tick=41)               # then the process died
        _cli("flag", "db", "--fixture", str(p), "--graph", g)
        # no advisory order strands a task any more (see test_healing_is_independent_...), so strand one by hand
        q(connect(g), "CREATE (:Task {id: 'rework_ghost', kind: 'rework', state: 'claimed'})")
        with pytest.raises(SystemExit) as e:
            _cli("session2", "--fixture", str(p), "--graph", g)
        assert "unfinished" in str(e.value) and "rework_ghost" in str(e.value) and "rework_s" not in str(e.value)
    finally:
        connect(g).delete()


def test_a_restarted_session2_starts_after_every_live_lease(capsys):
    """--kill-planner died right after s2b took over the lease: a rerun must be able to outlast that lease."""
    g = "r2engine_clock"
    try:
        _cli("session1", "--graph", g)
        _cli("flag", "doc_7", "--graph", g)
        gg = connect(g)
        q(gg, Q.HEAL_FACTS, session="s2", tick=41)
        q(gg, Q.PROMOTE_READY)
        assert q(gg, Q.CLAIM, task="rework_step_3", me="planner", now=48, lease=5, session="s2b")   # then it died
        _cli("session2", "--graph", g)
        assert "could not" not in capsys.readouterr().out
        assert _unfinished(gg) == []
    finally:
        connect(g).delete()


def test_status_does_not_call_a_half_written_session1_complete():
    from quarantine.agent_runtime import recovery_status

    g = _demo("r2engine_torn_s1")
    try:
        q(g, "MATCH (s:Session {id: 's1'}) REMOVE s.complete")           # session1 was killed before its last write
        st = recovery_status(g)
        assert st["complete"] is False and any("session 1 did not finish" in w for w in st["warnings"])
    finally:
        connect("r2engine_torn_s1").delete()


def test_unflag_is_one_write_and_a_retry_repairs_a_torn_one():
    from quarantine.loader import unflag

    g = _demo("r2engine_unflag")
    try:
        q(g, Q.FLAG_AND_CLOSE, doc="doc_7", reason="t", tick=40)
        q(g, Q.FLAG_AND_CLOSE, doc="doc_5", reason="t", tick=41)
        q(g, Q.UNFLAG_DOC, doc="doc_5")                                  # the process dies right after this statement
        assert red_ids(g) == SIX
        assert {r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) RETURN DISTINCT m.quarantine_doc")} == {"doc_7"}
        q(g, Q.FLAG_AND_CLOSE, doc="doc_5", reason="t", tick=42)
        q(g, "MATCH (d:Doc {id: 'doc_5'}) SET d.flagged = false")        # a torn retraction written by an older version
        out = unflag(g, "doc_5")                                         # the retry repairs it instead of 'nothing to do'
        assert red_ids(g) == SIX and out["repaired"] == ["ep_5"]
    finally:
        connect("r2engine_unflag").delete()


def test_a_second_advisory_does_not_list_done_tasks_or_resolved_memories(capsys):
    from quarantine.agent_runtime import recovery_status

    g = "r2engine_second"
    try:
        _cli("session1", "--graph", g)
        _cli("flag", "doc_7", "--graph", g)
        _cli("session2", "--graph", g)
        capsys.readouterr()
        _cli("flag", "doc_2", "--graph", g)
        _cli("session2", "--graph", g)
        out = capsys.readouterr().out
        assert "  done  waiting_on [f" not in out and "  done  waiting_on [s" not in out
        st = recovery_status(connect(g))
        assert st["agents"]["planner"]["unresolved"] == st["agents"]["coder"]["unresolved"] == 0, st["agents"]
        assert all(t["blocked_by"] == [] for t in st["tasks"] if t["state"] == "done"), st["tasks"]
        _cli("flag", "doc_7", "--graph", g)                              # re-flag after healing: nothing is blocked
        assert "blocked_by" not in capsys.readouterr().out
    finally:
        connect(g).delete()


import datetime  # noqa: E402


@pytest.mark.parametrize("breakage,match", [
    (lambda w: w["docs"]["d1"].update(published=datetime.date(2026, 1, 1)), "published"),
    (lambda w: w["sessions"]["s1"].update(meta={"a": 1}), "meta"),
    (lambda w: w["sessions"]["s1"].update(complete=True), "reserved"),
    (lambda w: w["sessions"]["s1"].update({"": 1}), "key"),
    (lambda w: w["docs"]["d1"].update(score=float("nan")), "score"),
    (lambda w: w["docs"]["d1"].update(tags=[[1]]), "tags"),
    (lambda w: w["episodes"]["e1"].update(tick=2 ** 63), "tick"),
    (lambda w: w["episodes"]["e1"].update(text="a\x00b"), "NUL"),
    (lambda w: w["episodes"].update({"e\x00": {"doc": "d1", "tick": 1, "text": "x"}}), "NUL"),
    (lambda w: w["episodes"].update({"e" * 300: {"doc": "d1", "tick": 1, "text": "x"}}), "id"),
    (lambda w: w["docs"].update({"d" * 300: {}}), "id"),
    (lambda w: w["steps"]["s"].update(agent=["planner"]), "agent"),
    (lambda w: w.update(procedure=5), "procedure"),
    (lambda w: w.update(procedure={"lease_ticks": -3}), "lease_ticks"),
    (lambda w: w.update(procedure={"lease_ticks": 0}), "lease_ticks"),
    (lambda w: w.update(procedure={"heal_min_clean": 3}), "heal_min_clean"),
    (lambda w: w.update(flag=5), "flag"),
    (lambda w: w.update(flag=["d3"]), "flag"),
    (lambda w: w.update(flag={"doc": "d3", "tick": "40", "reason": "bad"}), "tick"),
    (lambda w: w.update(flag={"doc": "d3", "reason": "bad"}), "tick"),
    (lambda w: w.update(flag={"doc": "nope", "tick": 40, "reason": "bad"}), "doc"),
    (lambda w: w.update(rework=5), "rework"),
    (lambda w: w.update(rework={"s": {"text": "redo", "reads": "f_v2"}}), "reads"),
    (lambda w: w.update(rework={"s": {"reads": ["f_v2"]}}), "text"),
])
def test_validate_fixture_refuses_values_falkordb_or_the_cli_cannot_use(breakage, match):
    w = copy.deepcopy(world())
    breakage(w)
    with pytest.raises(ValueError, match=match):
        validate_fixture(w)


def test_session1_probes_the_world_before_deleting_the_graph(tmp_path, monkeypatch):
    """Even a world validation misses can never cost the user the graph they had."""
    import yaml

    from quarantine import cli

    good, bad = tmp_path / "good.yaml", tmp_path / "bad.yaml"
    good.write_text(yaml.safe_dump(world()))
    w = world()
    w["docs"]["d1"]["published"] = datetime.date(2026, 1, 1)             # FalkorDB cannot store a date
    bad.write_text(yaml.safe_dump(w))
    g = "r2engine_probe"
    try:
        cli.main(["session1", "--fixture", str(good), "--graph", g])
        monkeypatch.setattr(cli, "validate_fixture", lambda fx: None)
        monkeypatch.setattr("quarantine.loader.validate_fixture", lambda fx: None)
        with pytest.raises(SystemExit) as e:
            cli.main(["session1", "--fixture", str(bad), "--graph", g])
        assert str(e.value).startswith("quarantine: ") and "left as it was" in str(e.value)
        assert q(connect(g), "MATCH (m:Memory) RETURN count(m)") == [[8]]
    finally:
        connect(g).delete()


@pytest.mark.parametrize("content,match", [
    ("? [x, y]\n: 1\n", "unhashable"),
    ("steps: {s: {agent: [planner]}}\n", None),
])
def test_odd_yaml_keys_give_one_line_errors(tmp_path, content, match):
    from quarantine import cli

    p = tmp_path / "x.yaml"
    p.write_text(content)
    with pytest.raises(SystemExit) as e:
        cli.main(["session1", "--fixture", str(p), "--graph", "r2engine_never_created"])
    assert str(e.value).startswith("quarantine: ") and (match is None or match in str(e.value))


def test_yaml_merge_keys_are_read_like_safe_load(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text("a: &b {x: 1, y: 1}\nc: {<<: *b, y: 2}\n")
    assert read_fixture(p) == {"a": {"x": 1, "y": 1}, "c": {"x": 1, "y": 2}}
    p.write_text("a: &b {x: 1}\nc: {<<: *b, y: 2, y: 3}\n")
    with pytest.raises(ValueError, match="duplicate key"):
        read_fixture(p)


def test_steps_listed_out_of_tick_order_or_reading_an_artifact_load():
    w = world()
    w["steps"] = {"s2": {"order": 2, "tick": 14, "text": "second", "reads": ["s1", "a"]},
                  "s1": {"order": 1, "tick": 11, "text": "first", "reads": ["f"]}}
    w["artifacts"] = {"a": {"path": "a.py", "tick": 12, "text": "art", "reads": ["s1"]}}
    validate_fixture(w)
    g = fresh("r2engine_order")
    try:
        load(g, w)
        assert q(g, "MATCH (:Memory {id: 's2'})-[:INFLUENCED_BY]->(x) RETURN x.id ORDER BY x.id") == [["a"], ["s1"]]
    finally:
        connect("r2engine_order").delete()


def test_the_unknown_key_message_does_not_claim_note_is_stored():
    w = world()
    w["facts"]["f"]["reads"] = ["e1"]
    with pytest.raises(ValueError) as e:
        validate_fixture(w)
    assert "not stored" in str(e.value)


# ---------------------------------------------------------------- healing does not depend on the order advisories arrive
def _heal_world():
    w = world()
    w["docs"] = {d: {"uri": d, "title": d} for d in ("da", "db", "dc")}
    eps = {"ea": ("da", 1), "eb1": ("db", 2), "eb2": ("db", 3), "eb3": ("db", 4), "ec1": ("dc", 5), "ec2": ("dc", 6)}
    w["episodes"] = {e: {"doc": d, "tick": t, "text": e} for e, (d, t) in eps.items()}
    w["facts"] = {"f": {"subject": "s", "slot": "v", "tick": 10, "value": "x",
                        "support": [{"ep": e, "claim": c} for e, c in
                                    (("ea", "x"), ("eb1", "y"), ("eb2", "y"), ("eb3", "y"), ("ec1", "z"), ("ec2", "Z "))]}}
    w["steps"] = {"st": {"order": 1, "tick": 20, "text": "uses f", "reads": ["f"]}}
    w["artifacts"] = {"ar": {"path": "a.py", "tick": 30, "text": "code", "reads": ["st"]}}
    return w


def _advise_and_heal(g, docs, tick):
    from quarantine.loader import reconcile

    for d in docs:
        q(g, Q.FLAG_AND_CLOSE, doc=d, reason="t", tick=tick)
        tick += 1
    reconcile(g)
    while q(g, Q.HEAL_FACTS, session="s2", tick=tick):
        tick += 1
        reconcile(g)
    return tick + 1


def _healed_state(g):
    heads = q(g, "MATCH (f:Fact {quarantined: false}) WHERE f.id STARTS WITH 'f_v2' OR f.id = 'f' "
                 "RETURN f.id, f.value, f.support_clean ORDER BY f.id")
    unhealed = q(g, "MATCH (f:Fact {quarantined: true, healable: true}) WHERE NOT (f)<-[:SUPERSEDES*1..]-(:Memory {quarantined: false}) "
                    "RETURN f.id")
    return [(r[1], r[2]) for r in heads], unhealed


@pytest.mark.parametrize("steps", [[["da"], ["db"]], [["db"], ["da"]], [["da", "db"]], [["dc"], ["db"], ["da"]]])
def test_healing_is_independent_of_the_order_advisories_arrive(steps):
    g = fresh("qheal_order")
    try:
        load(g, _heal_world())
        tick = 900
        for docs in steps:
            tick = _advise_and_heal(g, docs, tick)
        got = _healed_state(g)
    finally:
        connect("qheal_order").delete()
    g = fresh("qheal_order_ref")
    try:
        load(g, _heal_world())
        _advise_and_heal(g, [d for docs in steps for d in docs], 900)
        want = _healed_state(g)
    finally:
        connect("qheal_order_ref").delete()
    assert got == want


def test_a_second_advisory_rebuilds_the_fact_from_the_roots_full_clean_support():
    g = fresh("qheal_order_chain")
    try:
        load(g, _heal_world())
        t = _advise_and_heal(g, ["da"], 900)
        assert q(g, "MATCH (f:Fact {id: 'f_v2', quarantined: false}) RETURN f.value, f.support_clean") == [["y", 3]]
        _advise_and_heal(g, ["db"], t)                  # quarantines the healed twin; the outvoted z voters are still clean
        assert q(g, "MATCH (f:Fact {id: 'f_v2_v2'})-[:SUPERSEDES]->(:Fact {id: 'f_v2'}) RETURN f.value, f.quarantined, f.support_clean, f.runner_up_count") \
            == [["Z ", False, 2, 0]]
        assert q(g, "MATCH (f:Fact {id: 'f_v2_v2'})-[:CONSOLIDATED_FROM]->(e) RETURN e.id ORDER BY e.id") == [["ec1"], ["ec2"]]
    finally:
        connect("qheal_order_chain").delete()


def test_session2_says_nothing_to_repair_when_a_flagged_doc_reaches_no_memory(capsys, tmp_path):
    import yaml

    from quarantine import cli

    w = world()
    w["docs"]["dx"] = {"uri": "ux", "title": "a document nothing was derived from"}
    p = tmp_path / "w.yaml"
    p.write_text(yaml.safe_dump(w))
    base = ["--fixture", str(p), "--graph", "reg_nothing_to_repair"]
    try:
        cli.main(["session1", *base])
        cli.main(["flag", "dx", *base])
        capsys.readouterr()
        cli.main(["session2", *base])
        assert "nothing to repair: [dx] flagged" in capsys.readouterr().out
        cli.main(["unflag", "dx", *base])
        with pytest.raises(SystemExit, match="no advisory is flagged"):
            cli.main(["session2", *base])
    finally:
        connect("reg_nothing_to_repair").delete()
