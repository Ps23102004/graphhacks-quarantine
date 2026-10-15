"""Read-only JSON for the red-wave page. Serves web/index.html and two routes.

    uv run python web/server.py [--port 8765] [--graph quarantine]

Only reads: it runs the same statements as queries.py plus a node/edge dump.
"""
from __future__ import annotations

import argparse
import json
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


# The baselines as they stood at flag time: healed twins are not part of the world the naive wipe would hit.
PER_AGENT_AT_FLAG = Q.NAIVE_PER_AGENT.replace("MATCH (a)-[:AUTHORED]->(all:Memory)",
                                              "MATCH (a)-[:AUTHORED]->(all:Memory) WHERE NOT (all)-[:SUPERSEDES]->()")
TIME_AT_FLAG = Q.NAIVE_TIME_BASED.replace("WHERE m.tick >= t0", "WHERE m.tick >= t0 AND NOT (m)-[:SUPERSEDES]->()")
assert PER_AGENT_AT_FLAG != Q.NAIVE_PER_AGENT and TIME_AT_FLAG != Q.NAIVE_TIME_BASED


def snapshot(g) -> dict:
    nodes = [dict(id=i, kind=k, tick=t, red=bool(r), agent=a, text=tx, twin_of=tw, value=v, path=p)
             for i, k, t, r, a, tx, tw, v, p in q(g, NODES)]
    docs = [dict(id=i, title=t, flagged=bool(f), reason=r) for i, t, f, r in q(g, DOCS)]
    edges = [dict(src=a, type=t, dst=b) for a, t, b in q(g, EDGES)]
    flagged = next((d["id"] for d in docs if d["flagged"]), None)
    counters = None
    if flagged:
        precise = sum(1 for n in nodes if n["red"])
        counters = dict(precise=precise,
                        per_agent=q(g, PER_AGENT_AT_FLAG, doc=flagged)[0][0],
                        time_based=q(g, TIME_AT_FLAG, doc=flagged)[0][0])
    return dict(nodes=nodes, docs=docs, edges=edges, flagged=flagged, counters=counters)


def receipt(g, mid: str) -> dict | None:
    flagged = q(g, "MATCH (d:Doc {flagged: true}) RETURN d.id LIMIT 1")
    if not flagged:
        return None
    rows = q(g, Q.RECEIPT, **{"from": mid, "doc": flagged[0][0]})
    if not rows or rows[0][0] is None:
        return None
    hops, length, via = rows[0]
    return dict(hops=hops, len=length, via=via)


def make_handler(graph: str):
    class H(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            try:
                if u.path in ("/", "/index.html"):
                    self._send((HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
                elif u.path == "/vendor/vis-network.min.js":
                    self._send((HERE / "vendor" / "vis-network.min.js").read_bytes(), "text/javascript")
                elif u.path == "/graph":
                    self._send(json.dumps(snapshot(connect(graph))).encode(), "application/json")
                elif u.path == "/receipt":
                    mid = parse_qs(u.query).get("id", [""])[0]
                    self._send(json.dumps(receipt(connect(graph), mid)).encode(), "application/json")
                else:
                    self._send(b"not found", "text/plain", 404)
            except Exception as e:  # noqa: BLE001  (graph missing / FalkorDB down: tell the page, keep serving)
                self._send(json.dumps({"error": str(e)}).encode(), "application/json", 503)

        def log_message(self, *a):  # quiet
            pass
    return H


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--graph", default="quarantine")
    a = ap.parse_args()
    print(f"red-wave page: http://localhost:{a.port}  (graph {a.graph})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a.graph)).serve_forever()


if __name__ == "__main__":
    main()
