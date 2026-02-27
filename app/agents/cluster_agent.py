"""ClusterAgent — Detects clusters of similar posts via connected components."""

from app.agents.base import Agent
from app.neo4j_client import run_query

CLUSTER_MIN_SIZE = 3


class ClusterAgent(Agent):
    name = "ClusterAgent"

    def execute(self, **kwargs):
        self.log("Finding connected components in SIMILAR_TO graph")

        edges = run_query("""
            MATCH (p1:Post)-[:SIMILAR_TO]-(p2:Post)
            RETURN DISTINCT p1.id AS a, p2.id AS b
        """)

        if not edges:
            self.log("No similarity edges found")
            return []

        # Build adjacency and find connected components via BFS
        adj: dict[str, set[str]] = {}
        for e in edges:
            adj.setdefault(e["a"], set()).add(e["b"])
            adj.setdefault(e["b"], set()).add(e["a"])

        visited: set[str] = set()
        components: list[list[str]] = []
        for node in adj:
            if node in visited:
                continue
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

        clusters = [c for c in components if len(c) >= CLUSTER_MIN_SIZE]
        self.log(f"Found {len(clusters)} clusters (min size={CLUSTER_MIN_SIZE})")

        # Enrich with full data
        enriched = []
        for i, post_ids in enumerate(clusters):
            cluster_data = run_query(
                """
                MATCH (p:Post)-[:POSTED_BY]->(a:Account)
                WHERE p.id IN $ids
                RETURN p.id AS post_id, p.text AS text, p.platform AS platform,
                       p.timestamp AS timestamp, p.media_url AS media_url,
                       p.media_type AS media_type, p.post_type AS post_type,
                       a.id AS account_id, a.username AS username,
                       a.created_at AS account_created_at,
                       a.follower_count AS follower_count,
                       a.is_bot AS is_bot
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

    def summary(self) -> str:
        if not self.result:
            return "no clusters"
        total_posts = sum(len(c["posts"]) for c in self.result)
        return f"{len(self.result)} clusters, {total_posts} posts total"
