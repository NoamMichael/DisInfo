"""EntityAgent — Uses Pioneer/GLiNER-2 to extract entities and classify posts."""

import time
import asyncio
from app.agents.base import Agent
from app.neo4j_client import run_query, run_write
from app.api import fastino_client
from app.observe import obs


class EntityAgent(Agent):
    name = "EntityAgent"

    async def aexecute(self, **kwargs):
        posts = run_query("""
            MATCH (p:Post)-[:POSTED_BY]->(a:Account)
            RETURN p.id AS id, p.text AS text, a.username AS username,
                   p.platform AS platform
        """)
        self.log(f"Found {len(posts)} posts for entity extraction + classification")

        entity_labels = [
            "organization", "person", "location", "chemical",
            "health_condition", "government_agency",
        ]
        categories = [
            "disinformation", "conspiracy_theory", "news_report",
            "personal_opinion", "satire", "legitimate_concern",
        ]

        results = {}

        # Process in batches of 10 to avoid overwhelming the API
        batch_size = 10
        for i in range(0, len(posts), batch_size):
            batch = posts[i:i + batch_size]
            tasks = []
            for post in batch:
                tasks.append(self._analyze_post(
                    post, entity_labels, categories
                ))
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for post, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    obs.error(self.name, f"Error on {post['id']}: {result}")
                    results[post["id"]] = {
                        "post_text": post["text"],
                        "error": str(result),
                        "status": "error",
                    }
                else:
                    results[post["id"]] = result

        return results

    async def _analyze_post(self, post: dict, entity_labels: list,
                            categories: list) -> dict:
        t0 = time.monotonic()
        try:
            entities_resp, classify_resp = await asyncio.gather(
                fastino_client.extract_entities(
                    post["text"], entity_labels, threshold=0.3
                ),
                fastino_client.classify_text(
                    post["text"], categories, threshold=0.3
                ),
            )
            dur = (time.monotonic() - t0) * 1000

            entities = entities_resp.get("result", {}).get("entities", {})
            classification = classify_resp.get("result", {}).get("category", {})

            obs.api_call("Pioneer", "gliner-2", "ok", dur, post_id=post["id"])

            # Flatten entities for Neo4j storage
            entity_strs = []
            for label, ents in entities.items():
                for ent in ents:
                    entity_strs.append(f"{label}:{ent['text']}({ent['confidence']:.2f})")

            # Write results back to Neo4j
            run_write(
                """
                MATCH (p:Post {id: $id})
                SET p.gliner_entities = $entities,
                    p.gliner_classification = $classification,
                    p.gliner_confidence = $confidence
                """,
                {
                    "id": post["id"],
                    "entities": "|".join(entity_strs),
                    "classification": classification.get("label", "unknown"),
                    "confidence": classification.get("confidence", 0),
                },
            )

            return {
                "post_text": post["text"],
                "entities": entities,
                "classification": classification,
                "status": "analyzed",
            }
        except Exception as e:
            dur = (time.monotonic() - t0) * 1000
            obs.api_call("Pioneer", "gliner-2", f"error: {e}", dur, post_id=post["id"])
            raise

    def summary(self) -> str:
        if not self.result:
            return "no posts analyzed"
        ok = len([r for r in self.result.values() if r["status"] == "analyzed"])
        disinfo = len([
            r for r in self.result.values()
            if r.get("classification", {}).get("label") in ("disinformation", "conspiracy_theory")
        ])
        return f"{ok}/{len(self.result)} posts analyzed, {disinfo} flagged as disinfo/conspiracy"
