"""VerificationAgent — Uses Tavily to fact-check claims."""

import time
from app.agents.base import Agent
from app.neo4j_client import run_query, run_write
from app.api import tavily_client
from app.observe import obs


class VerificationAgent(Agent):
    name = "VerificationAgent"

    async def aexecute(self, **kwargs):
        claims = run_query("MATCH (c:Claim) RETURN c.id AS id, c.text AS text")
        self.log(f"Verifying {len(claims)} claims via Tavily")

        results = {}
        for claim in claims:
            t0 = time.monotonic()
            try:
                search_result = await tavily_client.search(
                    query=f"fact check: {claim['text']}",
                    topic="news",
                    max_results=5,
                )
                dur = (time.monotonic() - t0) * 1000
                answer = search_result.get("answer", "No answer generated")
                sources = [
                    {"title": r["title"], "url": r["url"], "snippet": r["content"]}
                    for r in search_result.get("results", [])
                ]

                answer_lower = answer.lower() if answer else ""
                if any(w in answer_lower for w in ["false", "debunked", "no evidence", "misleading", "fabricated"]):
                    status = "debunked"
                elif any(w in answer_lower for w in ["true", "confirmed", "verified"]):
                    status = "confirmed"
                else:
                    status = "unverified"

                obs.api_call("Tavily", "search", status, dur, claim_id=claim["id"])
                results[claim["id"]] = {
                    "claim": claim["text"],
                    "answer": answer,
                    "sources": sources,
                    "status": status,
                }
                run_write(
                    """
                    MATCH (c:Claim {id: $id})
                    SET c.verification_status = $status,
                        c.verification_answer = $answer
                    """,
                    {"id": claim["id"], "status": status, "answer": answer[:500]},
                )
            except Exception as e:
                dur = (time.monotonic() - t0) * 1000
                obs.api_call("Tavily", "search", f"error: {e}", dur, claim_id=claim["id"])
                results[claim["id"]] = {
                    "claim": claim["text"],
                    "error": str(e),
                    "status": "error",
                }
        return results

    def summary(self) -> str:
        if not self.result:
            return "no claims verified"
        debunked = len([r for r in self.result.values() if r.get("status") == "debunked"])
        return f"{len(self.result)} claims checked, {debunked} debunked"
