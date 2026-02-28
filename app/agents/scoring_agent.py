"""ScoringAgent — Scores clusters on coordination heuristics (0-100)."""

from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.agents.base import Agent
from app.neo4j_client import run_query, run_write


def _to_epoch(val) -> float | None:
    """Convert Neo4j datetime / ISO string / neo4j.time.DateTime to epoch seconds."""
    if val is None:
        return None
    # neo4j driver DateTime objects have .to_native()
    if hasattr(val, "to_native"):
        val = val.to_native()
    if hasattr(val, "timestamp"):
        return val.timestamp()
    if isinstance(val, str):
        return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
    return None


class ScoringAgent(Agent):
    name = "ScoringAgent"

    def execute(self, clusters: list[dict] | None = None, **kwargs):
        if not clusters:
            self.log("No clusters to score")
            return []

        scored = []
        for cluster in clusters:
            s = self._score(cluster)
            scored.append(s)

        scored.sort(key=lambda c: c["score"], reverse=True)

        for c in scored:
            self.log(
                f"{c['cluster_id']}: score={c['score']}, "
                f"posts={c['signals']['total_posts']}, "
                f"platforms={c['signals']['platforms']}"
            )

        # Write narrative nodes for suspicious clusters
        self._write_narratives(scored)

        return scored

    def _score(self, cluster: dict) -> dict:
        posts = cluster["posts"]
        if not posts:
            return {**cluster, "score": 0, "signals": {}}

        # 1. Text similarity
        texts = [p["text"] for p in posts]
        avg_sim = 0.0
        if len(texts) >= 2:
            vec = TfidfVectorizer(stop_words="english")
            tfidf = vec.fit_transform(texts)
            sim = cosine_similarity(tfidf)
            n = len(texts)
            avg_sim = float((sim.sum() - n) / (n * (n - 1))) if n > 1 else 0

        # 2. Account age spread
        account_epochs = []
        seen_accounts = set()
        for p in posts:
            aid = p.get("account_id", "")
            if aid in seen_accounts:
                continue
            seen_accounts.add(aid)
            epoch = _to_epoch(p.get("account_created_at"))
            if epoch:
                account_epochs.append(epoch)

        age_spread_hours = 0.0
        if len(account_epochs) >= 2:
            age_spread_hours = (max(account_epochs) - min(account_epochs)) / 3600

        # 3. Posting velocity
        post_epochs = []
        for p in posts:
            epoch = _to_epoch(p.get("timestamp"))
            if epoch:
                post_epochs.append(epoch)

        velocity_minutes = 0.0
        if len(post_epochs) >= 2:
            velocity_minutes = (max(post_epochs) - min(post_epochs)) / 60

        # 4. Platform spread
        platforms = set(p.get("platform", "") for p in posts)

        # 5. Unique accounts
        unique_accounts = set(p.get("account_id", "") for p in posts)

        # 6. Follower counts
        follower_counts = [p.get("follower_count", 0) or 0 for p in posts]
        avg_followers = float(np.mean(follower_counts)) if follower_counts else 0

        # 7. Media
        media_posts = [p for p in posts if p.get("media_url")]

        # 8. Following counts (ReLU at 5000 — no penalty below, linear increase above)
        following_counts = []
        seen_for_following = set()
        for p in posts:
            aid = p.get("account_id", "")
            if aid in seen_for_following:
                continue
            seen_for_following.add(aid)
            following_counts.append(p.get("following_count", 0) or 0)
        avg_following = float(np.mean(following_counts)) if following_counts else 0

        # 9. Graph connectivity — more edges = more trustworthy = less suspicious
        edge_counts = []
        seen_for_edges = set()
        for p in posts:
            aid = p.get("account_id", "")
            if aid in seen_for_edges:
                continue
            seen_for_edges.add(aid)
            rows = run_query(
                "MATCH (a:Account {id: $id})-[r]-() RETURN count(r) AS edges",
                {"id": aid},
            )
            edge_counts.append(rows[0]["edges"] if rows else 0)
        avg_edges = float(np.mean(edge_counts)) if edge_counts else 0

        # --- Scoring ---
        score = 0

        # High text similarity: 0-30 pts
        score += min(30, int(avg_sim * 40))

        # Account age clustering: 0-20 pts
        if len(account_epochs) >= 2:
            if age_spread_hours <= 24:
                score += 20
            elif age_spread_hours <= 48:
                score += 15
            elif age_spread_hours <= 168:
                score += 5

        # Posting velocity: 0-15 pts
        if velocity_minutes > 0 and len(posts) >= 3:
            posts_per_hour = len(posts) / (velocity_minutes / 60)
            if posts_per_hour >= 10:
                score += 15
            elif posts_per_hour >= 5:
                score += 10
            elif posts_per_hour >= 2:
                score += 5

        # Cross-platform spread: 0-15 pts
        score += min(15, len(platforms) * 5)

        # Cluster size: 0-10 pts
        score += min(10, len(unique_accounts))

        # Low follower counts: 0-5 pts
        if avg_followers < 50:
            score += 5
        elif avg_followers < 200:
            score += 2

        # Media amplifier: 0-5 pts
        if media_posts:
            score += min(5, len(media_posts) * 2)

        # High following count (ReLU at 5000): 0-30 pts
        # No penalty below 5000. Linear ramp above: 10K=5pts, 15K=10pts, 35K=30pts
        relu_following = max(0, avg_following - 5000)
        score += min(30, int(relu_following / 1000))

        # Low connectivity discount: -0 to -15 pts
        # Well-connected accounts (many edges) are trustworthy — reduce suspicion
        # 0 edges = no discount, 5+ edges = -10pts, 10+ edges = -15pts
        connectivity_discount = min(15, int(avg_edges * 1.5))
        score -= connectivity_discount

        score = max(0, min(100, score))

        signals = {
            "avg_text_similarity": round(avg_sim, 3),
            "account_age_spread_hours": round(age_spread_hours, 1),
            "posting_velocity_minutes": round(velocity_minutes, 1),
            "platforms": list(platforms),
            "unique_accounts": len(unique_accounts),
            "avg_followers": round(avg_followers, 1),
            "avg_following": round(avg_following, 1),
            "avg_edges": round(avg_edges, 1),
            "following_penalty": min(30, int(relu_following / 1000)),
            "connectivity_discount": connectivity_discount,
            "media_posts": len(media_posts),
            "total_posts": len(posts),
        }

        return {**cluster, "score": score, "signals": signals}

    def _write_narratives(self, scored_clusters: list[dict]):
        """Write Narrative nodes for high-scoring clusters."""
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

    def summary(self) -> str:
        if not self.result:
            return "no clusters scored"
        suspicious = len([c for c in self.result if c["score"] >= 30])
        top = self.result[0]["score"] if self.result else 0
        return f"{len(self.result)} clusters scored, {suspicious} suspicious (top: {top})"
