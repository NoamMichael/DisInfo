"""
Core coordination detection pipeline.

1. Fetch posts from Neo4j
2. Compute text similarity (TF-IDF cosine)
3. Write SIMILAR_TO edges for high-similarity pairs
4. Detect suspicious clusters via graph traversal
5. Score each cluster on coordination heuristics
"""

from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.neo4j_client import run_query, run_write

SIMILARITY_THRESHOLD = 0.35  # Pairs above this get SIMILAR_TO edges
CLUSTER_MIN_SIZE = 3  # Minimum posts to form a suspicious cluster


def fetch_posts() -> list[dict]:
    """Get all posts with their account info from Neo4j."""
    return run_query("""
        MATCH (p:Post)-[:POSTED_BY]->(a:Account)
        RETURN p.id AS id, p.text AS text, p.platform AS platform,
               p.timestamp AS timestamp, p.media_url AS media_url,
               p.media_type AS media_type,
               a.id AS account_id, a.username AS username,
               a.created_at AS account_created_at,
               a.follower_count AS follower_count
        ORDER BY p.timestamp
    """)


def compute_similarity(posts: list[dict]) -> list[tuple[str, str, float]]:
    """Compute pairwise TF-IDF cosine similarity. Return high-similarity pairs."""
    if len(posts) < 2:
        return []

    texts = [p["text"] for p in posts]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    tfidf = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(tfidf)

    pairs = []
    for i in range(len(posts)):
        for j in range(i + 1, len(posts)):
            score = float(sim_matrix[i, j])
            if score >= SIMILARITY_THRESHOLD:
                # Only flag if different accounts
                if posts[i]["account_id"] != posts[j]["account_id"]:
                    pairs.append((posts[i]["id"], posts[j]["id"], score))
    return pairs


def write_similarity_edges(pairs: list[tuple[str, str, float]]):
    """Write SIMILAR_TO relationships to Neo4j."""
    # Clear old similarity edges first
    run_write("MATCH ()-[r:SIMILAR_TO]->() DELETE r")

    for post_a, post_b, score in pairs:
        run_write(
            """
            MATCH (a:Post {id: $a}), (b:Post {id: $b})
            MERGE (a)-[r:SIMILAR_TO]->(b)
            SET r.score = $score
            """,
            {"a": post_a, "b": post_b, "score": score},
        )
    return len(pairs)


def detect_clusters() -> list[dict]:
    """Find clusters of similar posts using connected components in Python."""
    # Get all SIMILAR_TO edges
    edges = run_query("""
        MATCH (p1:Post)-[:SIMILAR_TO]-(p2:Post)
        RETURN DISTINCT p1.id AS a, p2.id AS b
    """)

    if not edges:
        return []

    # Build adjacency list and find connected components via BFS
    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e["a"], set()).add(e["b"])
        adj.setdefault(e["b"], set()).add(e["a"])

    visited: set[str] = set()
    components: list[list[str]] = []
    for node in adj:
        if node in visited:
            continue
        # BFS
        component = []
        queue = [node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        components.append(component)

    unique_clusters = [c for c in components if len(c) >= CLUSTER_MIN_SIZE]

    # Enrich each cluster with full data
    enriched = []
    for i, post_ids in enumerate(unique_clusters):
        cluster_data = run_query(
            """
            MATCH (p:Post)-[:POSTED_BY]->(a:Account)
            WHERE p.id IN $ids
            RETURN p.id AS post_id, p.text AS text, p.platform AS platform,
                   p.timestamp AS timestamp, p.media_url AS media_url,
                   p.media_type AS media_type,
                   a.id AS account_id, a.username AS username,
                   a.created_at AS account_created_at,
                   a.follower_count AS follower_count
            ORDER BY p.timestamp
            """,
            {"ids": post_ids},
        )
        enriched.append({
            "cluster_id": f"cluster_{i:02d}",
            "post_ids": post_ids,
            "posts": cluster_data,
        })

    return enriched


def score_cluster(cluster: dict) -> dict:
    """Score a cluster on coordination heuristics. Returns 0-100 suspicion score."""
    posts = cluster["posts"]
    if not posts:
        return {**cluster, "score": 0, "signals": {}}

    # 1. Text similarity (already filtered by threshold, but compute avg)
    texts = [p["text"] for p in posts]
    if len(texts) >= 2:
        vec = TfidfVectorizer(stop_words="english")
        tfidf = vec.fit_transform(texts)
        sim = cosine_similarity(tfidf)
        # Average off-diagonal similarity
        n = len(texts)
        avg_sim = (sim.sum() - n) / (n * (n - 1)) if n > 1 else 0
    else:
        avg_sim = 0

    # 2. Account age uniformity (accounts created around same time = suspicious)
    account_ages = []
    for p in posts:
        if p.get("account_created_at"):
            created = p["account_created_at"]
            if hasattr(created, "timestamp"):
                account_ages.append(created.timestamp())
            elif isinstance(created, str):
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                account_ages.append(dt.timestamp())

    age_spread_hours = 0
    if len(account_ages) >= 2:
        age_spread_hours = (max(account_ages) - min(account_ages)) / 3600

    # 3. Posting velocity (time between first and last post)
    timestamps = []
    for p in posts:
        ts = p.get("timestamp")
        if ts:
            if hasattr(ts, "timestamp"):
                timestamps.append(ts.timestamp())
            elif isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                timestamps.append(dt.timestamp())

    velocity_minutes = 0
    if len(timestamps) >= 2:
        velocity_minutes = (max(timestamps) - min(timestamps)) / 60

    # 4. Platform spread
    platforms = set(p.get("platform", "") for p in posts)

    # 5. Unique accounts
    unique_accounts = set(p.get("account_id", "") for p in posts)

    # 6. Low follower counts
    follower_counts = [p.get("follower_count", 0) or 0 for p in posts]
    avg_followers = np.mean(follower_counts) if follower_counts else 0

    # 7. Media presence (videos/audio in cluster amplify suspicion)
    media_posts = [p for p in posts if p.get("media_url")]

    # --- Scoring ---
    score = 0

    # High text similarity: 0-30 points
    score += min(30, int(avg_sim * 35))

    # Account age clustering (all created within 48 hours): 0-20 points
    if age_spread_hours > 0:
        if age_spread_hours <= 24:
            score += 20
        elif age_spread_hours <= 48:
            score += 15
        elif age_spread_hours <= 168:  # 1 week
            score += 5

    # Posting velocity (many posts in short window): 0-15 points
    if velocity_minutes > 0 and len(posts) >= 3:
        posts_per_hour = len(posts) / (velocity_minutes / 60) if velocity_minutes > 0 else 0
        if posts_per_hour >= 10:
            score += 15
        elif posts_per_hour >= 5:
            score += 10
        elif posts_per_hour >= 2:
            score += 5

    # Cross-platform spread: 0-15 points
    score += min(15, len(platforms) * 5)

    # Cluster size: 0-10 points
    score += min(10, len(unique_accounts) * 2)

    # Low follower counts: 0-5 points
    if avg_followers < 50:
        score += 5
    elif avg_followers < 200:
        score += 2

    # Media amplifier: 0-5 points
    if media_posts:
        score += min(5, len(media_posts) * 2)

    score = min(100, score)

    signals = {
        "avg_text_similarity": round(avg_sim, 3),
        "account_age_spread_hours": round(age_spread_hours, 1),
        "posting_velocity_minutes": round(velocity_minutes, 1),
        "platforms": list(platforms),
        "unique_accounts": len(unique_accounts),
        "avg_followers": round(avg_followers, 1),
        "media_posts": len(media_posts),
        "total_posts": len(posts),
    }

    return {**cluster, "score": score, "signals": signals}


def create_narratives(scored_clusters: list[dict]):
    """Write Narrative nodes and PART_OF_CAMPAIGN edges for high-scoring clusters."""
    run_write("MATCH (n:Narrative) DETACH DELETE n")

    for cluster in scored_clusters:
        if cluster["score"] < 30:
            continue

        narrative_id = cluster["cluster_id"]
        run_write(
            """
            MERGE (n:Narrative {id: $id})
            SET n.label = $label,
                n.suspicion_score = $score,
                n.signals = $signals_str,
                n.post_count = $post_count,
                n.platform_count = $platform_count
            """,
            {
                "id": narrative_id,
                "label": f"Suspicious campaign ({cluster['signals']['total_posts']} posts, "
                         f"score: {cluster['score']})",
                "score": cluster["score"],
                "signals_str": str(cluster["signals"]),
                "post_count": cluster["signals"]["total_posts"],
                "platform_count": len(cluster["signals"]["platforms"]),
            },
        )

        for post_id in cluster["post_ids"]:
            run_write(
                """
                MATCH (p:Post {id: $post_id}), (n:Narrative {id: $narrative_id})
                MERGE (p)-[:PART_OF_CAMPAIGN]->(n)
                """,
                {"post_id": post_id, "narrative_id": narrative_id},
            )


def run_detection() -> list[dict]:
    """Run the full detection pipeline. Returns scored clusters."""
    print("Fetching posts...")
    posts = fetch_posts()
    print(f"  {len(posts)} posts loaded")

    print("Computing text similarity...")
    pairs = compute_similarity(posts)
    print(f"  {len(pairs)} similar pairs found")

    print("Writing SIMILAR_TO edges...")
    n_edges = write_similarity_edges(pairs)
    print(f"  {n_edges} edges written")

    print("Detecting clusters...")
    clusters = detect_clusters()
    print(f"  {len(clusters)} clusters found")

    print("Scoring clusters...")
    scored = [score_cluster(c) for c in clusters]
    scored.sort(key=lambda c: c["score"], reverse=True)

    for c in scored:
        print(f"  {c['cluster_id']}: score={c['score']}, "
              f"posts={c['signals']['total_posts']}, "
              f"platforms={c['signals']['platforms']}")

    print("Writing narrative nodes...")
    create_narratives(scored)

    return scored


if __name__ == "__main__":
    results = run_detection()
    print(f"\nDetection complete. {len(results)} clusters analyzed.")
    from app.neo4j_client import close
    close()
