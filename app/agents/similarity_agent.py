"""SimilarityAgent — Computes pairwise text similarity and writes SIMILAR_TO edges."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.agents.base import Agent
from app.neo4j_client import run_query, run_write

SIMILARITY_THRESHOLD = 0.30


class SimilarityAgent(Agent):
    name = "SimilarityAgent"

    def execute(self, **kwargs):
        self.log("Fetching posts from Neo4j")
        posts = run_query("""
            MATCH (p:Post)-[:POSTED_BY]->(a:Account)
            RETURN p.id AS id, p.text AS text, p.platform AS platform,
                   p.timestamp AS timestamp, p.media_url AS media_url,
                   p.media_type AS media_type, p.post_type AS post_type,
                   a.id AS account_id, a.username AS username,
                   a.created_at AS account_created_at,
                   a.follower_count AS follower_count,
                   a.is_bot AS is_bot
            ORDER BY p.timestamp
        """)
        self.log(f"Loaded {len(posts)} posts")

        if len(posts) < 2:
            return {"posts": posts, "pairs": [], "edges_written": 0}

        texts = [p["text"] for p in posts]
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        tfidf = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf)

        pairs = []
        for i in range(len(posts)):
            for j in range(i + 1, len(posts)):
                score = float(sim_matrix[i, j])
                if score >= SIMILARITY_THRESHOLD and posts[i]["account_id"] != posts[j]["account_id"]:
                    pairs.append((posts[i]["id"], posts[j]["id"], score))

        self.log(f"Found {len(pairs)} similar pairs (threshold={SIMILARITY_THRESHOLD})")

        # Write edges
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
        self.log(f"Wrote {len(pairs)} SIMILAR_TO edges")

        return {"posts": posts, "pairs": pairs, "edges_written": len(pairs)}

    def summary(self) -> str:
        if not self.result:
            return "no results"
        return (f"{len(self.result['pairs'])} similar pairs from "
                f"{len(self.result['posts'])} posts")
