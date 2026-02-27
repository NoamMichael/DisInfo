"""AccountTrustAgent — Computes per-account trust from the FOLLOWS graph.

Queries Neo4j for:
- In-degree (how many accounts follow this one → popularity/authority)
- Reciprocity ratio (what fraction of follows are mutual → bot indicator when high + low followers)
- Account age
- Follower count

Writes a trust_score (0.0–1.0) property on each Account node.
Well-connected, old accounts with high in-degree get high trust.
Accounts with tight reciprocal cliques and low followers get low trust.
"""

import math
from datetime import datetime, timezone

from app.agents.base import Agent
from app.neo4j_client import run_query, run_write


class AccountTrustAgent(Agent):
    name = "AccountTrustAgent"

    def execute(self, **kwargs):
        # Pull all account info + graph metrics in one query
        rows = run_query("""
            MATCH (a:Account)
            OPTIONAL MATCH (a)<-[:FOLLOWS]-(follower:Account)
            WITH a, count(DISTINCT follower) AS in_degree,
                 collect(DISTINCT follower.id) AS follower_ids
            OPTIONAL MATCH (a)-[:FOLLOWS]->(following:Account)
            WITH a, in_degree, follower_ids,
                 count(DISTINCT following) AS out_degree,
                 collect(DISTINCT following.id) AS following_ids
            RETURN a.id AS id,
                   a.username AS username,
                   a.follower_count AS follower_count,
                   a.created_at AS created_at,
                   a.is_bot AS is_bot,
                   in_degree,
                   out_degree,
                   follower_ids,
                   following_ids
        """)

        if not rows:
            self.log("No accounts found")
            return {}

        trust_scores = {}
        for row in rows:
            score = self._compute_trust(row)
            trust_scores[row["id"]] = score

            # Write back to Neo4j
            run_write(
                "MATCH (a:Account {id: $id}) SET a.trust_score = $score",
                {"id": row["id"], "score": round(score, 4)},
            )

        self.log(f"Scored {len(trust_scores)} accounts")

        # Log some examples
        sorted_accounts = sorted(trust_scores.items(), key=lambda x: x[1], reverse=True)
        for aid, s in sorted_accounts[:5]:
            name = next((r["username"] for r in rows if r["id"] == aid), aid)
            self.log(f"  {name}: trust={s:.3f}")
        if len(sorted_accounts) > 5:
            for aid, s in sorted_accounts[-3:]:
                name = next((r["username"] for r in rows if r["id"] == aid), aid)
                self.log(f"  {name}: trust={s:.3f}")

        return trust_scores

    def _compute_trust(self, row: dict) -> float:
        """Compute trust score 0.0–1.0 for a single account."""
        in_degree = row["in_degree"] or 0
        out_degree = row["out_degree"] or 0
        follower_count = row["follower_count"] or 0
        follower_ids = set(row["follower_ids"] or [])
        following_ids = set(row["following_ids"] or [])

        # --- Signal 1: In-degree authority (0.0–0.35) ---
        # Logarithmic — diminishing returns for very high in-degree
        # in_degree of 5+ in our graph is very well-connected
        in_degree_score = min(1.0, math.log1p(in_degree) / math.log1p(10)) * 0.35

        # --- Signal 2: Follower count authority (0.0–0.25) ---
        # Logarithmic scale: 1000 followers = decent, 50000+ = very trusted
        follower_score = min(1.0, math.log1p(follower_count) / math.log1p(50000)) * 0.25

        # --- Signal 3: Account age (0.0–0.20) ---
        # Older accounts are more trusted. Sigmoid around 1 year.
        age_years = self._account_age_years(row["created_at"])
        # Sigmoid: 0.5 at 1 year, ~0.88 at 3 years, ~0.95 at 5 years
        age_score = (1.0 / (1.0 + math.exp(-1.5 * (age_years - 1.0)))) * 0.20

        # --- Signal 4: Reciprocity penalty (0.0 to -0.20) ---
        # High reciprocity among LOW-follower accounts = bot network indicator.
        # High reciprocity among HIGH-follower accounts = normal (journalists follow each other).
        reciprocity_penalty = 0.0
        if out_degree > 0 and in_degree > 0:
            mutual = len(follower_ids & following_ids)
            total_connections = len(follower_ids | following_ids)
            reciprocity_ratio = mutual / total_connections if total_connections > 0 else 0

            # Only penalize if the account has low followers AND high reciprocity
            # (bot cliques follow each other but have no real audience)
            if follower_count < 200 and reciprocity_ratio > 0.5:
                # Scale penalty by how extreme the reciprocity is
                reciprocity_penalty = -0.20 * reciprocity_ratio * (1.0 - min(1.0, follower_count / 200))

        # --- Combine ---
        trust = in_degree_score + follower_score + age_score + reciprocity_penalty

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, trust))

    @staticmethod
    def _account_age_years(created_at) -> float:
        """Convert account creation date to age in years."""
        if created_at is None:
            return 0.0
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if hasattr(created_at, "timestamp"):
            now = datetime.now(timezone.utc)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - created_at).total_seconds()
            return max(0.0, age_seconds / (365.25 * 86400))
        return 0.0

    def summary(self) -> str:
        if not self.result:
            return "no accounts scored"
        scores = list(self.result.values())
        avg = sum(scores) / len(scores) if scores else 0
        high_trust = len([s for s in scores if s >= 0.5])
        return f"{len(scores)} accounts scored (avg trust: {avg:.2f}, {high_trust} high-trust)"
