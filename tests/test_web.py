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
