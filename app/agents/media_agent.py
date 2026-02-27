"""MediaAgent — Uses Reka to analyze media content in posts."""

import time
from app.agents.base import Agent
from app.neo4j_client import run_query, run_write
from app.api import reka_client
from app.observe import obs


class MediaAgent(Agent):
    name = "MediaAgent"

    async def aexecute(self, **kwargs):
        media_posts = run_query("""
            MATCH (p:Post)-[:POSTED_BY]->(a:Account)
            WHERE p.media_url IS NOT NULL
            RETURN p.id AS id, p.text AS text, p.media_url AS url,
                   p.media_type AS type, a.username AS username
        """)
        self.log(f"Found {len(media_posts)} media posts to analyze")

        results = {}
        for post in media_posts:
            t0 = time.monotonic()
            try:
                analysis = await reka_client.chat(
                    f"A social media post by @{post['username']} titled: "
                    f"'{post['text']}'\n\n"
                    f"This post contains a {post['type']}. Based on the title and context:\n"
                    "1. Is the title sensationalized or misleading?\n"
                    "2. Does it use manipulation tactics (urgency, fear, conspiracy framing)?\n"
                    "3. Are there red flags suggesting coordinated disinformation?\n"
                    "Rate manipulation likelihood 0-100 and explain briefly."
                )
                dur = (time.monotonic() - t0) * 1000
                content = (
                    analysis.get("responses", [{}])[0]
                    .get("message", {})
                    .get("content", "No analysis available")
                )
                obs.api_call("Reka", "chat", "ok", dur, post_id=post["id"])
                results[post["id"]] = {
                    "post_text": post["text"],
                    "media_url": post["url"],
                    "media_type": post["type"],
                    "analysis": content,
                    "status": "analyzed",
                }
                run_write(
                    "MATCH (p:Post {id: $id}) SET p.reka_analysis = $analysis",
                    {"id": post["id"], "analysis": content[:500]},
                )
            except Exception as e:
                dur = (time.monotonic() - t0) * 1000
                obs.api_call("Reka", "chat", f"error: {e}", dur, post_id=post["id"])
                results[post["id"]] = {
                    "post_text": post["text"],
                    "error": str(e),
                    "status": "error",
                }
        return results

    def summary(self) -> str:
        if not self.result:
            return "no media analyzed"
        ok = len([r for r in self.result.values() if r["status"] == "analyzed"])
        return f"{ok}/{len(self.result)} media posts analyzed"
