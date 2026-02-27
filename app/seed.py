"""Load synthetic dataset into Neo4j. Run: python -m app.seed"""

import json
from app.neo4j_client import run_write, run_query, close

DATA_PATH = "data/synthetic_posts.json"


def clear_graph():
    run_write("MATCH (n) DETACH DELETE n")
    print("Cleared existing graph data")


def create_constraints():
    for label in ["Post", "Account", "Claim", "Narrative"]:
        run_write(
            f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        )
    print("Constraints created")


def load_data():
    with open(DATA_PATH) as f:
        data = json.load(f)

    # Create accounts
    for acc in data["accounts"]:
        run_write(
            """
            MERGE (a:Account {id: $id})
            SET a.username = $username,
                a.platform = $platform,
                a.created_at = datetime($created_at),
                a.follower_count = $follower_count
            """,
            acc,
        )
    print(f"Loaded {len(data['accounts'])} accounts")

    # Create posts + POSTED_BY edges
    for post in data["posts"]:
        run_write(
            """
            MERGE (p:Post {id: $id})
            SET p.text = $text,
                p.platform = $platform,
                p.timestamp = datetime($timestamp),
                p.media_url = $media_url,
                p.media_type = $media_type
            WITH p
            MATCH (a:Account {id: $account_id})
            MERGE (p)-[:POSTED_BY]->(a)
            """,
            post,
        )
    print(f"Loaded {len(data['posts'])} posts")

    # Create claims
    for claim in data["claims"]:
        run_write(
            """
            MERGE (c:Claim {id: $id})
            SET c.text = $text, c.category = $category
            """,
            claim,
        )
    print(f"Loaded {len(data['claims'])} claims")

    # Link posts to claims by keyword matching
    claim_keywords = {
        "claim_01": ["contaminated", "contaminating", "industrial chemicals", "water treatment"],
        "claim_02": ["covered it up", "coverup", "cover up"],
        "claim_03": ["hospitals", "overwhelmed", "sick", "poisoned"],
        "claim_04": ["CDC", "deliberate", "testing", "lab rats"],
        "claim_05": ["media blackout", "media silence", "mainstream media", "MSM"],
    }
    links = 0
    for claim_id, keywords in claim_keywords.items():
        for post in data["posts"]:
            text_lower = post["text"].lower()
            if any(kw.lower() in text_lower for kw in keywords):
                run_write(
                    """
                    MATCH (p:Post {id: $post_id}), (c:Claim {id: $claim_id})
                    MERGE (p)-[:MENTIONS]->(c)
                    """,
                    {"post_id": post["id"], "claim_id": claim_id},
                )
                links += 1
    print(f"Created {links} post->claim MENTIONS edges")


def verify():
    counts = run_query(
        """
        MATCH (a:Account) WITH count(a) AS accounts
        MATCH (p:Post) WITH accounts, count(p) AS posts
        MATCH (c:Claim) WITH accounts, posts, count(c) AS claims
        MATCH ()-[r:POSTED_BY]->() WITH accounts, posts, claims, count(r) AS posted_by
        MATCH ()-[m:MENTIONS]->() WITH accounts, posts, claims, posted_by, count(m) AS mentions
        RETURN accounts, posts, claims, posted_by, mentions
        """
    )
    c = counts[0]
    print(f"\nGraph summary:")
    print(f"  Accounts: {c['accounts']}")
    print(f"  Posts: {c['posts']}")
    print(f"  Claims: {c['claims']}")
    print(f"  POSTED_BY edges: {c['posted_by']}")
    print(f"  MENTIONS edges: {c['mentions']}")


if __name__ == "__main__":
    print("Seeding Neo4j with synthetic data...")
    clear_graph()
    create_constraints()
    load_data()
    verify()
    close()
    print("\nDone!")
