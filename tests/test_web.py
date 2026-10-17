"""The red-wave page shows the same numbers the CLI and the video say, before and after healing."""
from __future__ import annotations

import subprocess
import sys

from quarantine.loader import connect, read_fixture
from web.server import receipt, snapshot

GRAPH = "quarantine_web_test"


def run(*args):
    r = subprocess.run([sys.executable, "-m", "quarantine.cli", *args, "--graph", GRAPH],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_page_numbers_match_the_demo_before_and_after_healing():
    ex = read_fixture()["expected"]
    try:
        run("session1")
        s = snapshot(connect(GRAPH))
        assert s["flagged"] is None and s["counters"] is None and len(s["nodes"]) == 25

        run("flag", "doc_7")
        want = dict(precise=ex["precise"], per_agent=ex["naive_per_agent"], time_based=ex["naive_time_based"])
        s = snapshot(connect(GRAPH))
        assert s["counters"] == want
        assert sorted(n["id"] for n in s["nodes"] if n["red"]) == sorted(
            ["ep_7a", "ep_7b", "f_http_client", "f_http_pin", "step_3", "a_requirements"])
        assert receipt(connect(GRAPH), "a_requirements")["len"] == 4

        run("session2")
        s = snapshot(connect(GRAPH))
        assert s["counters"] == want, "baselines are frozen at flag time; healed twins must not move them"
        assert sorted(n["id"] for n in s["nodes"] if n["twin_of"]) == [
            "a_requirements_v2", "f_http_client_v2", "step_3_v2"]
    finally:
        connect(GRAPH).delete()


def test_server_refuses_non_loopback_host_header():
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from web.server import make_handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(GRAPH))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = Request(f"http://127.0.0.1:{srv.server_port}/graph", headers={"Host": "evil.example"})
        try:
            urlopen(req)
            raise AssertionError("expected 403")
        except HTTPError as e:
            assert e.code == 403
    finally:
        srv.shutdown()


def test_page_overlay_flags_add_up_to_the_counters():
    """The orange 'clean work a naive wipe would lose' view paints exactly the nodes the counters count."""
    g = connect("quarantine_overlay_test")
    try:
        try:
            g.delete()
        except Exception:  # noqa: BLE001
            pass
        g = connect("quarantine_overlay_test")
        from quarantine import queries as Q
        from quarantine.loader import load, q
        fx = read_fixture()
        load(g, fx)
        q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
        s = snapshot(g)
        c = s["counters"]
        assert sum(n["naive_agent"] for n in s["nodes"]) == c["per_agent"] == fx["expected"]["naive_per_agent"]
        assert sum(n["naive_time"] for n in s["nodes"]) == c["time_based"] == fx["expected"]["naive_time_based"]
        assert all(n["naive_agent"] for n in s["nodes"] if n["red"]) and all(n["naive_time"] for n in s["nodes"] if n["red"])
        lost = [n["id"] for n in s["nodes"] if n["naive_time"] and not n["red"]]
        assert len(lost) == c["time_based"] - c["precise"]               # 13 clean memories the time-based wipe would lose
    finally:
        connect("quarantine_overlay_test").delete()


def test_page_tells_placeholders_and_quarantined_twins_apart_from_healed_work():
    """A second advisory can quarantine a healed twin, and a twin with no clean grounding is only a placeholder:
    the snapshot carries what the page needs to draw neither of them as clean healed work."""
    try:
        run("session1"); run("flag", "doc_1"); run("session2")
        twins = [n for n in snapshot(connect(GRAPH))["nodes"] if n["twin_of"]]
        assert twins and all(not n["red"] for n in twins)
        assert any(n["needs_regeneration"] for n in twins), "doc_1 twins are placeholders until an agent rewrites them"
        assert all(n["needs_regeneration"] == n["text"].startswith("[needs regeneration") for n in twins)

        run("session1"); run("flag", "doc_7"); run("session2"); run("flag", "doc_2"); run("session2")
        s = snapshot(connect(GRAPH))
        red_twins = sorted(n["id"] for n in s["nodes"] if n["twin_of"] and n["red"])
        assert red_twins == ["a_requirements_v2", "f_http_client_v2", "step_3_v2"]
        assert {n["twin_of"] for n in s["nodes"]} >= {"f_http_client_v2", "step_3_v2", "a_requirements_v2"}   # twins of twins
    finally:
        connect(GRAPH).delete()


def test_precise_counter_counts_originals_like_the_baselines():
    """With one flagged doc and a quarantined twin, 'precise' must count the same population as the two baselines."""
    from quarantine import queries as Q
    from quarantine.loader import load, q
    g = connect(GRAPH)
    try:
        load(g, read_fixture())
        q(g, Q.FLAG_AND_CLOSE, doc="doc_7", reason="t", tick=40)
        q(g, "MATCH (o:Memory {id: 'f_http_client'})<-[:AUTHORED]-(a:Agent) "
             "CREATE (a)-[:AUTHORED]->(t:Memory:Fact {id: 'f_http_client_v2', tick: 41, quarantined: true})-[:SUPERSEDES]->(o)")
        s = snapshot(g)
        assert s["counters"]["precise"] == read_fixture()["expected"]["precise"]
    finally:
        g.delete()
