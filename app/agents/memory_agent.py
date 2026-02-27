"""MemoryAgent — Stores and recalls campaign fingerprints.

After detection, builds a fingerprint from each suspicious cluster:
  - Top TF-IDF keywords
  - Extracted entities (from Pioneer/GLiNER-2)
  - Account creation patterns
  - Platform spread + velocity

On future scans, compares new clusters against stored fingerprints
and reports "seen before" matches.

Stored as CampaignFingerprint nodes in Neo4j.
"""

from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer

from app.agents.base import Agent
from app.neo4j_client import run_query, run_write


class MemoryAgent(Agent):
    name = "MemoryAgent"

    def execute(self, scored_clusters: list[dict] | None = None,
                entity_results: dict | None = None, **kwargs):
        if not scored_clusters:
            self.log("No clusters to fingerprint")
            return {"stored": [], "matches": []}

        # Phase A: Check for matches against existing fingerprints
        matches = self._recall(scored_clusters)

        # Phase B: Store new fingerprints for suspicious clusters
        stored = self._store(scored_clusters, entity_results)

        return {"stored": stored, "matches": matches}

    def _extract_keywords(self, texts: list[str], top_n: int = 10) -> list[str]:
        """Extract top TF-IDF keywords from cluster texts."""
        if len(texts) < 2:
            return texts[0].split()[:top_n] if texts else []
        vec = TfidfVectorizer(stop_words="english", max_features=200)
        tfidf = vec.fit_transform(texts)
        feature_names = vec.get_feature_names_out()
        # Sum TF-IDF scores across all docs, take top N
        scores = tfidf.sum(axis=0).A1
        top_indices = scores.argsort()[-top_n:][::-1]
        return [feature_names[i] for i in top_indices]

    def _build_fingerprint(self, cluster: dict,
                           entity_results: dict | None) -> dict:
        """Build a campaign fingerprint from a scored cluster."""
        posts = cluster["posts"]
        signals = cluster["signals"]
        texts = [p["text"] for p in posts]

        # Keywords
        keywords = self._extract_keywords(texts)

        # Entities from Pioneer results (if available)
        entities = {}
        if entity_results:
            for p in posts:
                pid = p.get("post_id") or p.get("id", "")
                er = entity_results.get(pid, {})
                for etype, ents in er.get("entities", {}).items():
                    if etype not in entities:
                        entities[etype] = {}
                    for ent in ents:
                        name = ent["text"]
                        entities[etype][name] = entities[etype].get(name, 0) + 1

        # Flatten to top entities per type
        top_entities = {}
        for etype, counts in entities.items():
            sorted_ents = sorted(counts.items(), key=lambda x: -x[1])[:5]
            top_entities[etype] = [{"text": name, "count": c} for name, c in sorted_ents]

        # Account pattern
        account_ids = list(set(p.get("account_id", "") for p in posts))

        return {
            "cluster_id": cluster["cluster_id"],
            "score": cluster["score"],
            "keywords": keywords,
            "entities": top_entities,
            "platforms": signals.get("platforms", []),
            "account_count": signals.get("unique_accounts", 0),
            "account_ids": account_ids,
            "post_count": signals.get("total_posts", 0),
            "avg_similarity": signals.get("avg_text_similarity", 0),
            "velocity_minutes": signals.get("posting_velocity_minutes", 0),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _store(self, scored_clusters: list[dict],
               entity_results: dict | None) -> list[dict]:
        """Store fingerprints for suspicious clusters."""
        stored = []
        for cluster in scored_clusters:
            if cluster["score"] < 30:
                continue

            fp = self._build_fingerprint(cluster, entity_results)
            fp_id = f"fp_{cluster['cluster_id']}"

            run_write(
                """
                MERGE (f:CampaignFingerprint {id: $id})
                SET f.cluster_id = $cluster_id,
                    f.score = $score,
                    f.keywords = $keywords,
                    f.platforms = $platforms,
                    f.account_count = $account_count,
                    f.post_count = $post_count,
                    f.avg_similarity = $avg_similarity,
                    f.velocity_minutes = $velocity_minutes,
                    f.created_at = datetime($created_at),
                    f.entities_summary = $entities_summary
                """,
                {
                    "id": fp_id,
                    "cluster_id": fp["cluster_id"],
                    "score": fp["score"],
                    "keywords": fp["keywords"],
                    "platforms": fp["platforms"],
                    "account_count": fp["account_count"],
                    "post_count": fp["post_count"],
                    "avg_similarity": fp["avg_similarity"],
                    "velocity_minutes": fp["velocity_minutes"],
                    "created_at": fp["created_at"],
                    "entities_summary": str(fp["entities"]),
                },
            )

            # Link fingerprint to the cluster's narrative
            run_write(
                """
                MATCH (f:CampaignFingerprint {id: $fp_id})
                MATCH (n:Narrative {id: $cluster_id})
                MERGE (f)-[:FINGERPRINT_OF]->(n)
                """,
                {"fp_id": fp_id, "cluster_id": cluster["cluster_id"]},
            )

            # Link fingerprint to accounts
            for acc_id in fp["account_ids"]:
                run_write(
                    """
                    MATCH (f:CampaignFingerprint {id: $fp_id})
                    MATCH (a:Account {id: $acc_id})
                    MERGE (f)-[:INVOLVES]->(a)
                    """,
                    {"fp_id": fp_id, "acc_id": acc_id},
                )

            self.log(f"Stored fingerprint {fp_id}: {len(fp['keywords'])} keywords, "
                     f"score={fp['score']}")
            stored.append(fp)

        return stored

    def _recall(self, scored_clusters: list[dict]) -> list[dict]:
        """Check new clusters against stored fingerprints for matches."""
        existing = run_query("""
            MATCH (f:CampaignFingerprint)
            RETURN f.id AS id, f.keywords AS keywords, f.score AS score,
                   f.platforms AS platforms, f.account_count AS account_count,
                   f.created_at AS created_at
        """)

        if not existing:
            self.log("No stored fingerprints to match against")
            return []

        matches = []
        for cluster in scored_clusters:
            if cluster["score"] < 30:
                continue

            texts = [p["text"] for p in cluster["posts"]]
            cluster_keywords = set(self._extract_keywords(texts))
            cluster_accounts = set(p.get("account_id", "") for p in cluster["posts"])

            for fp in existing:
                fp_keywords = set(fp.get("keywords", []))
                if not fp_keywords:
                    continue

                # Keyword overlap
                overlap = cluster_keywords & fp_keywords
                keyword_score = len(overlap) / max(len(fp_keywords), 1)

                # Account overlap (check via graph)
                account_overlap = run_query(
                    """
                    MATCH (f:CampaignFingerprint {id: $fp_id})-[:INVOLVES]->(a:Account)
                    WHERE a.id IN $account_ids
                    RETURN count(a) AS overlap
                    """,
                    {"fp_id": fp["id"], "account_ids": list(cluster_accounts)},
                )
                acc_overlap = account_overlap[0]["overlap"] if account_overlap else 0

                if keyword_score >= 0.3 or acc_overlap >= 2:
                    matches.append({
                        "cluster_id": cluster["cluster_id"],
                        "matched_fingerprint": fp["id"],
                        "keyword_overlap": round(keyword_score, 2),
                        "shared_keywords": list(overlap)[:10],
                        "account_overlap": acc_overlap,
                        "fingerprint_score": fp["score"],
                        "fingerprint_created": str(fp.get("created_at", "")),
                    })
                    self.log(
                        f"MATCH: {cluster['cluster_id']} matches {fp['id']} "
                        f"(keywords={keyword_score:.0%}, accounts={acc_overlap})"
                    )

        return matches

    def summary(self) -> str:
        if not self.result:
            return "no results"
        stored = len(self.result.get("stored", []))
        matches = len(self.result.get("matches", []))
        return f"{stored} fingerprints stored, {matches} matches found"
