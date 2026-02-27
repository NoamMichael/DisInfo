"""Load real-content dataset into Neo4j. Run: python -m app.seed"""

import json
from app.neo4j_client import run_write, run_query, close

DATA_PATH = "data/realtime_data.json"

# --- Account groups (all real — sourced via Yutori & Tavily) ---
X_ACCOUNTS = [
    "acc_01", "acc_02", "acc_03", "acc_04", "acc_05",
    "acc_06", "acc_07", "acc_08", "acc_09", "acc_10",
]
YT_ACCOUNTS = ["acc_11", "acc_12", "acc_13", "acc_14", "acc_15"]
WEB_ACCOUNTS = ["acc_16", "acc_17", "acc_18", "acc_19", "acc_20", "acc_21", "acc_22"]


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


def _generate_follows():
    """Generate follow edges — all real accounts, realistic sparse follows."""
    follows = [
        # X journalists/outlets follow each other
        ("acc_01", "acc_02", "2023-06-01T10:00:00Z"),   # starsandstripes follows DeptofWar
        ("acc_01", "acc_06", "2024-01-15T14:00:00Z"),   # starsandstripes follows nataliealund
        ("acc_03", "acc_01", "2024-03-10T09:00:00Z"),   # pamelafessler follows starsandstripes
        ("acc_03", "acc_10", "2023-08-20T11:00:00Z"),   # pamelafessler follows allenanalysis
        ("acc_06", "acc_03", "2024-05-01T16:00:00Z"),   # nataliealund follows pamelafessler
        ("acc_06", "acc_01", "2023-11-05T12:00:00Z"),   # nataliealund follows starsandstripes
        ("acc_10", "acc_03", "2023-09-01T08:00:00Z"),   # allenanalysis follows pamelafessler
        ("acc_10", "acc_09", "2024-02-15T14:00:00Z"),   # allenanalysis follows Unbranded63
        ("acc_09", "acc_10", "2024-03-01T10:00:00Z"),   # Unbranded63 follows allenanalysis
        ("acc_04", "acc_02", "2023-07-01T12:00:00Z"),   # FLVoiceNews follows DeptofWar
        ("acc_08", "acc_07", "2024-01-01T10:00:00Z"),   # sistertoldjah follows elliscashmore
        # YouTube channels
        ("acc_11", "acc_15", "2022-05-01T10:00:00Z"),   # USA TODAY follows CBS News
        ("acc_13", "acc_14", "2023-06-15T14:00:00Z"),   # NewsNation follows ABC7
        ("acc_14", "acc_13", "2023-07-01T14:00:00Z"),   # ABC7 follows NewsNation
        ("acc_15", "acc_11", "2022-08-01T10:00:00Z"),   # CBS News follows USA TODAY
    ]
    return follows


def load_data():
    with open(DATA_PATH) as f:
        data = json.load(f)

    # --- Accounts ---
    for acc in data["accounts"]:
        run_write(
            """
            MERGE (a:Account {id: $id})
            SET a.username = $username,
                a.display_name = $display_name,
                a.platform = $platform,
                a.created_at = datetime($created_at),
                a.follower_count = $follower_count,
                a.is_bot = $is_bot
            """,
            {**acc, "display_name": acc.get("display_name", acc["username"])},
        )
    print(f"Loaded {len(data['accounts'])} accounts")

    # --- Posts + POSTED_BY ---
    for post in data["posts"]:
        run_write(
            """
            MERGE (p:Post {id: $id})
            SET p.text = $text,
                p.platform = $platform,
                p.timestamp = datetime($timestamp),
                p.media_url = $media_url,
                p.media_type = $media_type,
                p.post_type = $post_type,
                p.source_url = $source_url
            WITH p
            MATCH (a:Account {id: $account_id})
            MERGE (p)-[:POSTED_BY]->(a)
            """,
            {**post, "source_url": post.get("source_url")},
        )
    print(f"Loaded {len(data['posts'])} posts")

    # --- Claims ---
    for claim in data["claims"]:
        run_write(
            """
            MERGE (c:Claim {id: $id})
            SET c.text = $text, c.category = $category
            """,
            claim,
        )
    print(f"Loaded {len(data['claims'])} claims")

    # --- Narratives ---
    for narr in data.get("narratives", []):
        run_write(
            """
            MERGE (n:Narrative {id: $id})
            SET n.label = $label, n.description = $description
            """,
            {"id": narr["id"], "label": narr["label"], "description": narr["description"]},
        )
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

    # --- Post -> Claim keyword matching ---
    claim_keywords = {
        "claim_01": ["end DEI", "end all DEI", "drop DEI", "DEI efforts", "DEI initiatives", "DEI policies", "diversity, equity"],
        "claim_02": ["biological sex", "gender identity", "sex at birth", "sex assigned at birth", "transgender"],
        "claim_03": ["six months", "cut support", "cut ties", "sever", "risk losing", "Pentagon support"],
        "claim_04": ["girls were accepted", "girls allowed", "wounded", "inclusion of girls"],
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

    # --- Post -> Narrative (coordinated posts) ---
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

    # --- Follow graph (generated programmatically) ---
    follows = _generate_follows()
    for from_id, to_id, since in follows:
        run_write(
            """
            MATCH (a:Account {id: $from_id}), (b:Account {id: $to_id})
            MERGE (a)-[:FOLLOWS {since: datetime($since)}]->(b)
            """,
            {"from_id": from_id, "to_id": to_id, "since": since},
        )
    print(f"Created {len(follows)} FOLLOWS edges")

    # --- User mentions (post @mentions account) ---
    user_mentions = data.get("user_mentions", [])
    for mention in user_mentions:
        run_write(
            """
            MATCH (p:Post {id: $post_id}), (a:Account {id: $account_id})
            MERGE (p)-[:MENTIONS_USER]->(a)
            """,
            {"post_id": mention["post_id"], "account_id": mention["mentioned_account_id"]},
        )
    print(f"Created {len(user_mentions)} post->account MENTIONS_USER edges")


def verify():
    counts = run_query(
        """
        OPTIONAL MATCH (a:Account) WITH count(a) AS accounts
        OPTIONAL MATCH (p:Post) WITH accounts, count(p) AS posts
        OPTIONAL MATCH (c:Claim) WITH accounts, posts, count(c) AS claims
        OPTIONAL MATCH (n:Narrative) WITH accounts, posts, claims, count(n) AS narratives
        OPTIONAL MATCH ()-[r:POSTED_BY]->() WITH accounts, posts, claims, narratives, count(r) AS posted_by
        OPTIONAL MATCH ()-[m:MENTIONS]->() WITH accounts, posts, claims, narratives, posted_by, count(m) AS mentions
        OPTIONAL MATCH ()-[pc:PART_OF_CAMPAIGN]->() WITH accounts, posts, claims, narratives, posted_by, mentions, count(pc) AS campaign_edges
        OPTIONAL MATCH ()-[f:FOLLOWS]->() WITH accounts, posts, claims, narratives, posted_by, mentions, campaign_edges, count(f) AS follows
        OPTIONAL MATCH ()-[mu:MENTIONS_USER]->() WITH accounts, posts, claims, narratives, posted_by, mentions, campaign_edges, follows, count(mu) AS user_mentions
        RETURN accounts, posts, claims, narratives, posted_by, mentions, campaign_edges, follows, user_mentions
        """
    )
    c = counts[0]
    print(f"\nGraph summary:")
    print(f"  Accounts:            {c['accounts']}  (all real)")
    print(f"  Posts:               {c['posts']}  (coordinated + organic + echo)")
    print(f"  Claims:              {c['claims']}")
    print(f"  Narratives:          {c['narratives']}")
    print(f"  POSTED_BY edges:     {c['posted_by']}")
    print(f"  MENTIONS edges:      {c['mentions']}  (post -> claim)")
    print(f"  PART_OF_CAMPAIGN:    {c['campaign_edges']}")
    print(f"  FOLLOWS edges:       {c['follows']}")
    print(f"  MENTIONS_USER edges: {c['user_mentions']}  (post -> account)")

    # Platform breakdown
    platform_counts = run_query(
        "MATCH (p:Post) RETURN p.platform AS platform, p.post_type AS type, count(*) AS n ORDER BY platform, type"
    )
    print(f"\n  Posts by platform & type:")
    for row in platform_counts:
        print(f"    {row['platform']:10s} {row['type']:15s} {row['n']}")

    # Follow graph density
    bot_follow_stats = run_query(
        """
        MATCH (a:Account {is_bot: true})-[f:FOLLOWS]->(b:Account {is_bot: true})
        RETURN a.platform AS platform, count(f) AS bot_to_bot_follows
        """
    )
    organic_follow_stats = run_query(
        """
        MATCH (a:Account {is_bot: false})-[f:FOLLOWS]->(b:Account {is_bot: false})
        RETURN count(f) AS organic_follows
        """
    )
    bot_to_organic = run_query(
        """
        MATCH (a:Account {is_bot: true})-[f:FOLLOWS]->(b:Account {is_bot: false})
        RETURN count(f) AS bot_to_organic_follows
        """
    )
    print(f"\n  Follow graph:")
    for row in bot_follow_stats:
        print(f"    bot->bot ({row['platform']}):       {row['bot_to_bot_follows']}")
    if organic_follow_stats:
        print(f"    organic->organic:       {organic_follow_stats[0]['organic_follows']}")
    if bot_to_organic:
        print(f"    bot->organic (camo):    {bot_to_organic[0]['bot_to_organic_follows']}")

    # Mention amplification
    mention_stats = run_query(
        """
        MATCH (p:Post)-[:MENTIONS_USER]->(a:Account)
        WITH a, p,
             CASE WHEN a.is_bot THEN 'bot' ELSE 'organic' END AS target_type
        MATCH (p)-[:POSTED_BY]->(author:Account)
        WITH CASE WHEN author.is_bot THEN 'bot' ELSE 'organic' END AS author_type,
             target_type, count(*) AS n
        RETURN author_type + ' -> ' + target_type AS pattern, n
        ORDER BY n DESC
        """
    )
    print(f"\n  @mention patterns:")
    for row in mention_stats:
        print(f"    {row['pattern']:25s} {row['n']}")

    # Media posts
    media_posts = run_query(
        "MATCH (p:Post) WHERE p.media_url IS NOT NULL RETURN p.id AS id, p.media_type AS type, p.media_url AS url"
    )
    print(f"\n  Media posts ({len(media_posts)}):")
    for row in media_posts:
        print(f"    {row['id']:10s} [{row['type']}] {row['url'][:60]}...")


if __name__ == "__main__":
    print("Seeding Neo4j with real-content data...")
    clear_graph()
    create_constraints()
    load_data()
    verify()
    close()
    print("\nDone!")
