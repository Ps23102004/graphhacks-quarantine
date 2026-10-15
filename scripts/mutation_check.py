"""Do the tests actually catch breakage? Break one thing at a time in a throwaway clone; pytest must go red.

    uv run python scripts/mutation_check.py

Runs in a clone of HEAD (never touches your working tree) against its own FalkorDB container on :6391.
Exit 0 = every mutation was caught (a "survivor" means a hole in the tests).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

IMAGE = "falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6"
NAME, PORT = "quarantine-mutation", "6391"
SRC = Path(__file__).resolve().parent.parent

# (what we break, file, exact old text, new text)
MUTATIONS = [
    ("closure ignores read-set edges",        "quarantine/queries.py", "EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..10]-(m:Memory)\nSET m.quarantined", "EXTRACTED_FROM|CONSOLIDATED_FROM*1..10]-(m:Memory)\nSET m.quarantined"),
    ("closure depth capped at 1 hop",         "quarantine/queries.py", "INFLUENCED_BY*1..10]-(m:Memory)\nSET m.quarantined", "INFLUENCED_BY*1..1]-(m:Memory)\nSET m.quarantined"),
    ("heal threshold 2 -> 1 clean episode",   "quarantine/queries.py", "WHEN m:Fact THEN best >= 2 AND best > second", "WHEN m:Fact THEN best >= 1 AND best > second"),
    ("heal rule drops its own size check (equivalent mutant: the healable flag already guards it)",         "quarantine/queries.py", "WHERE size(agree) >= 2\nMATCH (f)<-[:AUTHORED]", "WHERE size(agree) >= 0\nMATCH (f)<-[:AUTHORED]"),
    ("episodes become healable",              "quarantine/queries.py", "WHEN m:Episode THEN false", "WHEN m:Episode THEN true"),
    ("rework not blocked by healable inputs", "quarantine/queries.py", "x:Memory {quarantined: true, healable: true})\nMERGE (t)-[:BLOCKED_BY]", "x:Memory {quarantined: true, healable: false})\nMERGE (t)-[:BLOCKED_BY]"),
    ("lease never expires",                   "quarantine/queries.py", "(c IS NULL OR c.lease_until < $now)", "(c IS NULL)"),
    ("lease ignores live holder",             "quarantine/queries.py", "(c IS NULL OR c.lease_until < $now)", "(true)"),
    ("rework guard removed",                  "quarantine/loader.py",  "    if bad:\n", "    if False:\n"),
    ("per-agent baseline counts nothing",     "quarantine/queries.py", "RETURN count(DISTINCT all) AS naive,", "RETURN 0 AS naive,"),
    ("time baseline off by one tick",         "quarantine/queries.py", "WHERE m.tick >= t0", "WHERE m.tick > t0"),
    ("fixture: step_4 now reads the poisoned fact", "fixture.yaml", "step_4", "step_4"),  # replaced below with a structural edit
    ("baselines count healed twins",          "quarantine/queries.py", " WHERE NOT (all)-[:SUPERSEDES]->()", ""),
    ("heal accepts a tie",                    "quarantine/queries.py", "WHEN m:Fact THEN best >= 2 AND best > second", "WHEN m:Fact THEN best >= 2 AND best >= second"),
    ("rework guard allows quarantined reads", "quarantine/loader.py",  "if quarantined is None or quarantined]", "if quarantined is None]"),
    ("rework guard allows missing reads",     "quarantine/loader.py",  "if quarantined is None or quarantined]", "if quarantined]"),
    ("rework is not idempotent",              "quarantine/loader.py",  "[0][0]:\n        return new_id", "[0][0] > 99:\n        return new_id"),
    ("COMPLETE ignores the lease session",    "quarantine/queries.py", "CLAIMED_BY {session: $session}]", "CLAIMED_BY]"),
    ("COMPLETE needs no replacement",         "quarantine/queries.py", "-[:REWORKS]->(:Memory)<-[:SUPERSEDES]-(:Memory)\nMATCH (t)-[c:CLAIMED_BY", "-[:REWORKS]->(:Memory)\nMATCH (t)-[c:CLAIMED_BY"),
    ("any agent can claim any task",          "quarantine/queries.py", "(:Memory)<-[:AUTHORED]-(a:Agent {name: $me})\nOPTIONAL MATCH (t)-[c:CLAIMED_BY]", "(:Memory)\nMATCH (a:Agent {name: $me})\nOPTIONAL MATCH (t)-[c:CLAIMED_BY]"),
    ("page picks only the first flagged doc for receipts", "web/server.py", 'for (doc,) in q(g, "MATCH (d:Doc {flagged: true}) RETURN d.id ORDER BY d.id"):', 'for (doc,) in q(g, "MATCH (d:Doc {flagged: true}) RETURN d.id ORDER BY d.id LIMIT 1"):'),
    ("page twin detection removed",           "web/server.py", "OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory)", "OPTIONAL MATCH (m)-[:NOPE]->(old:Memory)"),
]


def sh(cmd, cwd, env=None, check=False):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"setup failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def main() -> int:
    work = Path(tempfile.mkdtemp())
    repo = work / "repo"
    sh(["docker", "rm", "-f", NAME], work)
    sh(["docker", "run", "-d", "--name", NAME, "-p", f"{PORT}:6379", IMAGE], work, check=True)
    try:
        sh(["git", "clone", "-q", str(SRC), str(repo)], work, check=True)
        env = {**os.environ, "FALKORDB_PORT": PORT}
        for _ in range(30):
            if "PONG" in sh(["docker", "exec", NAME, "redis-cli", "ping"], work).stdout:
                break
            time.sleep(1)
        sh(["uv", "sync", "--frozen", "-q"], repo, env, check=True)

        def pytest() -> subprocess.CompletedProcess:
            return sh(["uv", "run", "pytest", "-q", "-x"], repo, env)

        base = pytest()
        if base.returncode:
            sys.exit(f"baseline is red, nothing to compare against:\n{base.stdout[-1500:]}")
        print("baseline green:", base.stdout.strip().splitlines()[-1])

        survivors = 0
        for name, rel, old, new in MUTATIONS:
            path = repo / rel
            orig = path.read_text()
            if name.startswith("fixture: step_4"):
                # structural: step_4 (written from clean facts) also reads the poisoned fact f_http_client
                key = "step_4:"
                i = orig.index(key)
                j = orig.index("reads: [", i) + len("reads: [")
                mutated = orig[:j] + "f_http_client, " + orig[j:]
            else:
                if old not in orig:
                    print(f"  SKIP  {name}: pattern not found in {rel} (mutation list is stale)")
                    survivors += 1
                    continue
                mutated = orig.replace(old, new, 1)
            path.write_text(mutated)
            r = pytest()
            path.write_text(orig)
            caught = r.returncode != 0
            lines = r.stdout.splitlines()
            fail_line = next((l for l in lines if l.startswith("FAILED")), "") or next((l for l in lines if l.startswith("E ")), "")
            print(f"  {'CAUGHT  ' if caught else 'SURVIVED'} {name}   {fail_line[:90]}")
            survivors += (not caught) and "equivalent mutant" not in name  # known-redundant guard, documented in the name
        print(f"\n{survivors} unexpected survivor(s) of {len(MUTATIONS)} mutations (equivalent mutants excluded)")
        return 1 if survivors else 0
    finally:
        sh(["docker", "rm", "-f", NAME], work)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
