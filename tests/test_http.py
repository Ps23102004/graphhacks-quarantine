"""HTTP level test suite for web/server.py."""
from __future__ import annotations

import json
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest

from quarantine.loader import connect, q
from web.server import make_handler

PORT = int(os.environ.get("FALKORDB_PORT", 6379))
GRAPH = "quarantine_http_test"


@pytest.fixture
def running_server(monkeypatch):
    monkeypatch.setenv("FALKORDB_PORT", str(PORT))                     # restored after the test: no leak into other files
    g = connect(GRAPH, port=PORT)
    try:
        g.delete()
    except Exception:
        pass
    # Seed a basic node for /graph and /receipt
    q(g, "CREATE (d:Doc {id: 'doc_1', title: 'Test doc', flagged: true})")
    q(g, "CREATE (a:Agent {name: 'test_agent'}), (m:Memory:Episode {id: 'ep_1', quarantined: true, tick: 1, text: 'test text'}) CREATE (a)-[:AUTHORED]->(m)")
    q(g, "MATCH (m:Memory {id: 'ep_1'}), (d:Doc {id: 'doc_1'}) CREATE (m)-[:EXTRACTED_FROM]->(d)")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(GRAPH))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base_url = f"http://127.0.0.1:{srv.server_port}"

    yield base_url, srv

    srv.shutdown()
    try:
        g.delete()
    except Exception:
        pass


def test_http_root_and_index_html(running_server):
    base_url, _ = running_server
    for path in ("/", "/index.html"):
        req = Request(f"{base_url}{path}")
        with urlopen(req) as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")
            body = resp.read().decode()
            assert "Quarantine" in body and "id=\"stage\"" in body


def test_http_page_is_self_contained(running_server):
    """The hive page loads no script or stylesheet from anywhere: it works offline and on a judge's locked-down laptop."""
    base_url, _ = running_server
    with urlopen(Request(f"{base_url}/")) as resp:
        body = resp.read().decode()
    assert "<script src=" not in body and "<link rel=\"stylesheet\"" not in body
    try:
        urlopen(Request(f"{base_url}/vendor/vis-network.min.js"))
        raise AssertionError("the old vendored library should be gone")
    except HTTPError as e:
        assert e.code == 404


def test_http_graph_snapshot(running_server):
    base_url, _ = running_server
    req = Request(f"{base_url}/graph")
    with urlopen(req) as resp:
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")
        data = json.loads(resp.read().decode())
        assert "nodes" in data
        assert "docs" in data
        assert "edges" in data
        assert any(n["id"] == "ep_1" for n in data["nodes"])


def test_http_receipt(running_server):
    base_url, _ = running_server
    req = Request(f"{base_url}/receipt?id=ep_1")
    with urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data is not None
        assert data["hops"] == ["ep_1", "doc_1"]
        assert data["len"] == 1


def test_http_not_found(running_server):
    base_url, _ = running_server
    req = Request(f"{base_url}/nonexistent_route")
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 404
    assert exc_info.value.read() == b"not found"


def test_http_no_mutation_methods(running_server):
    base_url, _ = running_server
    for method in ("POST", "PUT", "DELETE"):
        req = Request(f"{base_url}/graph", method=method)
        with pytest.raises(HTTPError) as exc_info:
            urlopen(req)
        assert exc_info.value.code == 405
        assert exc_info.value.read() == b"method not allowed"


def test_http_host_allowlist_acceptance_and_rejection(running_server):
    base_url, _ = running_server

    # Localhost and 127.0.0.1 accepted by default
    req_local = Request(f"{base_url}/graph", headers={"Host": "localhost"})
    with urlopen(req_local) as resp:
        assert resp.status == 200

    req_ip = Request(f"{base_url}/graph", headers={"Host": "127.0.0.1"})
    with urlopen(req_ip) as resp:
        assert resp.status == 200

    # Foreign host rejected by default
    req_foreign = Request(f"{base_url}/graph", headers={"Host": "evil.example"})
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req_foreign)
    assert exc_info.value.code == 403

    # Configured allowed host accepted
    os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,custom.local,web"
    try:
        req_custom = Request(f"{base_url}/graph", headers={"Host": "custom.local"})
        with urlopen(req_custom) as resp:
            assert resp.status == 200

        req_web = Request(f"{base_url}/graph", headers={"Host": "web:8765"})
        with urlopen(req_web) as resp:
            assert resp.status == 200

        # Still rejects unlisted host
        req_unlisted = Request(f"{base_url}/graph", headers={"Host": "other.attacker"})
        with pytest.raises(HTTPError) as exc_info2:
            urlopen(req_unlisted)
        assert exc_info2.value.code == 403
    finally:
        os.environ.pop("ALLOWED_HOSTS", None)


def test_http_db_unavailable_returns_503():
    # Server pointed to an unavailable FalkorDB port
    os.environ["FALKORDB_PORT"] = "6398"
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("nonexistent_graph"))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        req = Request(f"http://127.0.0.1:{srv.server_port}/graph")
        with pytest.raises(HTTPError) as exc_info:
            urlopen(req)
        assert exc_info.value.code == 503
        data = json.loads(exc_info.value.read().decode())
        assert "error" in data
    finally:
        srv.shutdown()
        os.environ["FALKORDB_PORT"] = str(PORT)
