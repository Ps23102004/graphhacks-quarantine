"""Read-only JSON for the red-wave page. Serves web/index.html and two routes.

    uv run python web/server.py [--host 127.0.0.1] [--port 8765] [--graph quarantine]

Only reads: it runs the same statements as queries.py plus a node/edge dump.
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from quarantine import queries as Q
from quarantine.loader import connect, q

HERE = Path(__file__).resolve().parent

NODES = """
MATCH (m:Memory)<-[:AUTHORED]-(a:Agent)
OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory)
RETURN m.id, labels(m)[1], m.tick, m.quarantined, a.name, m.text, old.id, m.value, m.path
ORDER BY m.tick
"""
DOCS = "MATCH (d:Doc) RETURN d.id, d.title, d.flagged, d.flag_reason ORDER BY d.id"
EDGES = """
MATCH (a:Memory)-[r:INFLUENCED_BY|CONSOLIDATED_FROM|EXTRACTED_FROM|SUPERSEDES]->(b)
RETURN a.id, type(r), b.id
"""


def _read_query(g, cypher: str, **params):
    from quarantine import loader
    if hasattr(loader, "rq"):
        return loader.rq(g, cypher, **params)
    if hasattr(g, "ro_query"):
        return g.ro_query(cypher, params).result_set
    return q(g, cypher, **params)


def snapshot(g) -> dict:
    nodes = [dict(id=i, kind=k, tick=t, red=bool(r), agent=a, text=tx, twin_of=tw, value=v, path=p)
             for i, k, t, r, a, tx, tw, v, p in _read_query(g, NODES)]
    docs = [dict(id=i, title=t, flagged=bool(f), reason=r) for i, t, f, r in _read_query(g, DOCS)]
    edges = [dict(src=a, type=t, dst=b) for a, t, b in _read_query(g, EDGES)]
    flagged_docs = [d["id"] for d in docs if d["flagged"]]
    flagged = flagged_docs[0] if flagged_docs else None
    counters = None
    if len(flagged_docs) == 1:                                          # the counters tell one advisory's story
        precise = sum(1 for n in nodes if n["red"])
        counters = dict(precise=precise,
                        per_agent=_read_query(g, Q.NAIVE_PER_AGENT, doc=flagged)[0][0],
                        time_based=_read_query(g, Q.NAIVE_TIME_BASED, doc=flagged)[0][0])
    return dict(nodes=nodes, docs=docs, edges=edges, flagged=flagged, counters=counters)


def receipt(g, mid: str) -> dict | None:
    for (doc,) in _read_query(g, "MATCH (d:Doc {flagged: true}) RETURN d.id ORDER BY d.id"):
        rows = _read_query(g, Q.RECEIPT, **{"from": mid, "doc": doc})
        if rows and rows[0][0]:                                         # first flagged doc this memory actually reaches
            hops, length, via = rows[0]
            return dict(hops=hops, len=length, via=via)
    return None


def get_allowed_hosts() -> set[str]:
    raw = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
    hosts = {h.strip().lower() for h in raw.split(",") if h.strip() and h.strip() != "*"}
    hosts.add("localhost")
    hosts.add("127.0.0.1")
    return hosts


def make_handler(graph: str):
    class H(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _check_host(self) -> bool:
            host_header = self.headers.get("Host", "").rsplit(":", 1)[0].lower()
            if host_header not in get_allowed_hosts():
                self._send(b"forbidden host", "text/plain", 403)
                return False
            return True

        def do_GET(self):  # noqa: N802
            if not self._check_host():
                return
            u = urlparse(self.path)
            try:
                if u.path in ("/", "/index.html"):
                    self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
                elif u.path == "/vendor/vis-network.min.js":
                    self._send((HERE / "vendor" / "vis-network.min.js").read_bytes(), "text/javascript")
                elif u.path == "/graph":
                    host = os.environ.get("FALKORDB_HOST", "localhost")
                    g = connect(graph, host=host)
                    self._send(json.dumps(snapshot(g)).encode(), "application/json")
                elif u.path == "/receipt":
                    mid = parse_qs(u.query).get("id", [""])[0]
                    host = os.environ.get("FALKORDB_HOST", "localhost")
                    g = connect(graph, host=host)
                    self._send(json.dumps(receipt(g, mid)).encode(), "application/json")
                else:
                    self._send(b"not found", "text/plain", 404)
            except Exception as e:  # noqa: BLE001  (graph missing / FalkorDB down: tell the page, keep serving)
                self._send(json.dumps({"error": str(e)}).encode(), "application/json", 503)

        def do_POST(self):  # noqa: N802
            if not self._check_host():
                return
            self._send(b"method not allowed", "text/plain", 405)

        def do_PUT(self):  # noqa: N802
            if not self._check_host():
                return
            self._send(b"method not allowed", "text/plain", 405)

        def do_DELETE(self):  # noqa: N802
            if not self._check_host():
                return
            self._send(b"method not allowed", "text/plain", 405)

        def log_message(self, *a):  # quiet
            pass
    return H


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("WEB_HOST", "127.0.0.1"), help="Host address to bind listener")
    ap.add_argument("--port", type=int, default=int(os.environ.get("WEB_PORT", 8765)), help="Port to bind listener")
    ap.add_argument("--graph", default=os.environ.get("QUARANTINE_GRAPH", "quarantine"), help="FalkorDB graph name")
    a = ap.parse_args()
    print(f"red-wave page: http://{a.host}:{a.port}  (graph {a.graph})", flush=True)
    ThreadingHTTPServer((a.host, a.port), make_handler(a.graph)).serve_forever()


if __name__ == "__main__":
    main()
