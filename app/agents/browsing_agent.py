"""BrowsingAgent — Uses Yutori to deep-verify claims on fact-check sites."""

import time
from app.agents.base import Agent
from app.api import yutori_client
from app.observe import obs


class BrowsingAgent(Agent):
    name = "BrowsingAgent"

    async def aexecute(self, claims_results: dict | None = None, **kwargs):
        if not claims_results:
            self.log("No claims to verify")
            return None

        # Pick best target claim
        target = None
        for cid, result in claims_results.items():
            if result.get("status") in ("debunked", "unverified") and "error" not in result:
                target = result
                break
        if not target:
            self.log("No claims needed deep verification")
            return None

        self.log(f"Deep-verifying: {target['claim'][:60]}...")

        t0 = time.monotonic()
        try:
            browse_result = await yutori_client.browse(
                task=(
                    f"Search this fact-checking website for information about this claim: "
                    f"'{target['claim']}'. Report what you find — has this claim been "
                    f"fact-checked? What is the verdict?"
                ),
                start_url="https://www.snopes.com",
            )
            dur = (time.monotonic() - t0) * 1000
            obs.api_call("Yutori", "browse", "dispatched", dur, claim=target["claim"][:60])
            return {
                "claim": target["claim"],
                "yutori_result": browse_result,
                "source": "snopes.com",
            }
        except Exception as e:
            dur = (time.monotonic() - t0) * 1000
            obs.api_call("Yutori", "browse", f"error: {e}", dur)
            return {"claim": target["claim"], "error": str(e)}

    def summary(self) -> str:
        if not self.result:
            return "skipped"
        if "error" in self.result:
            return f"error: {self.result['error'][:40]}"
        return f"dispatched for: {self.result['claim'][:50]}..."
