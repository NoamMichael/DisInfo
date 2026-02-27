"""
Smoke test for Neo4j AuraDB connection.
Run: python scripts/neo4j_test.py

Verifies:
1. Connection to AuraDB instance
2. Schema constraints can be created
3. Basic CRUD operations work
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_URI or not NEO4J_PASSWORD:
    print("ERROR: Set NEO4J_URI and NEO4J_PASSWORD in .env")
    sys.exit(1)

import neo4j

driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# Test connection
with driver.session() as session:
    result = session.run("RETURN 1 AS n")
    record = result.single()
    assert record["n"] == 1
    print("OK: Connected to Neo4j")

# Create schema constraints (idempotent)
CONSTRAINTS = [
    "CREATE CONSTRAINT post_id IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT narrative_id IF NOT EXISTS FOR (n:Narrative) REQUIRE n.id IS UNIQUE",
]

with driver.session() as session:
    for stmt in CONSTRAINTS:
        session.run(stmt)
    print("OK: Schema constraints created")

# Verify by listing constraints
with driver.session() as session:
    result = session.run("SHOW CONSTRAINTS")
    constraints = [r["name"] for r in result]
    print(f"OK: {len(constraints)} constraints active: {constraints}")

# Quick write/read test
with driver.session() as session:
    session.run("MERGE (t:_Test {id: 'smoke'}) SET t.ok = true")
    result = session.run("MATCH (t:_Test {id: 'smoke'}) RETURN t.ok AS ok")
    assert result.single()["ok"] is True
    session.run("MATCH (t:_Test {id: 'smoke'}) DELETE t")
    print("OK: Write/read/delete cycle works")

driver.close()
print("\nNeo4j AuraDB is ready.")
