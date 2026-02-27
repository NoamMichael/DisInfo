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
                a.follower_count = $follower_count,
                a.is_bot = $is_bot
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
                p.media_type = $media_type,
                p.post_type = $post_type
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

    # Create narratives
    for narr in data.get("narratives", []):
        run_write(
            """
            MERGE (n:Narrative {id: $id})
            SET n.label = $label, n.description = $description
            """,
            {"id": narr["id"], "label": narr["label"], "description": narr["description"]},
        )
        # Link claims to narrative
        for wave in narr.get("waves", []):
            for claim_id in wave.get("claim_ids", []):
                run_write(
                    """
                    MATCH (c:Claim {id: $claim_id}), (n:Narrative {id: $narr_id})
                    MERGE (c)-[:PART_OF_NARRATIVE]->(n)
                    """,
                    {"claim_id": claim_id, "narr_id": narr["id"]},
                )
    print(f"Loaded {len(data.get('narratives', []))} narratives")

    # Link posts to claims by keyword matching
    claim_keywords = {
        "claim_01": ["contaminated", "contaminating", "industrial chemicals", "water treatment"],
        "claim_02": ["covered it up", "coverup", "cover up", "cover-up", "kept it quiet"],
        "claim_03": ["hospitals", "overwhelmed", "sick", "poisoned", "ERs packed"],
        "claim_04": ["CDC", "deliberate", "testing", "lab rats", "whistleblower", "Tuskegee"],
        "claim_05": ["media blackout", "media silence", "mainstream media", "MSM", "not covering"],
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

    # Link coordinated posts to narrative
    campaign_links = 0
    for post in data["posts"]:
        if post["post_type"] == "coordinated":
            run_write(
                """
                MATCH (p:Post {id: $post_id}), (n:Narrative {id: 'narr_01'})
                MERGE (p)-[:PART_OF_CAMPAIGN]->(n)
                """,
                {"post_id": post["id"]},
            )
            campaign_links += 1
    print(f"Created {campaign_links} post->narrative PART_OF_CAMPAIGN edges")


def verify():
    counts = run_query(
        """
        MATCH (a:Account) WITH count(a) AS accounts
        MATCH (p:Post) WITH accounts, count(p) AS posts
        MATCH (c:Claim) WITH accounts, posts, count(c) AS claims
        MATCH (n:Narrative) WITH accounts, posts, claims, count(n) AS narratives
        MATCH ()-[r:POSTED_BY]->() WITH accounts, posts, claims, narratives, count(r) AS posted_by
        MATCH ()-[m:MENTIONS]->() WITH accounts, posts, claims, narratives, posted_by, count(m) AS mentions
        MATCH ()-[pc:PART_OF_CAMPAIGN]->() WITH accounts, posts, claims, narratives, posted_by, mentions, count(pc) AS campaign_edges
        RETURN accounts, posts, claims, narratives, posted_by, mentions, campaign_edges
        """
    )
    c = counts[0]
    print(f"\nGraph summary:")
    print(f"  Accounts:            {c['accounts']}  (20 bot + 10 organic)")
    print(f"  Posts:               {c['posts']}  (coordinated + organic + echo)")
    print(f"  Claims:              {c['claims']}")
    print(f"  Narratives:          {c['narratives']}")
    print(f"  POSTED_BY edges:     {c['posted_by']}")
    print(f"  MENTIONS edges:      {c['mentions']}")
    print(f"  PART_OF_CAMPAIGN:    {c['campaign_edges']}")

    # Show platform breakdown
    platform_counts = run_query(
        "MATCH (p:Post) RETURN p.platform AS platform, p.post_type AS type, count(*) AS n ORDER BY platform, type"
    )
    print(f"\n  Posts by platform & type:")
    for row in platform_counts:
        print(f"    {row['platform']:10s} {row['type']:15s} {row['n']}")

    # Show media posts
    media_posts = run_query(
        "MATCH (p:Post) WHERE p.media_url IS NOT NULL RETURN p.id AS id, p.media_type AS type, p.media_url AS url"
    )
    print(f"\n  Media posts ({len(media_posts)}):")
    for row in media_posts:
        print(f"    {row['id']:10s} [{row['type']}] {row['url'][:60]}...")


if __name__ == "__main__":
    print("Seeding Neo4j with synthetic data...")
    clear_graph()
    create_constraints()
    load_data()
    verify()
    close()
    print("\nDone!")
