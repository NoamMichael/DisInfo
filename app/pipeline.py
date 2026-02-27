"""
Full autonomous detection pipeline — orchestrates 6 agents.

Agents:
1. SimilarityAgent  — TF-IDF cosine similarity, writes SIMILAR_TO edges (Neo4j)
2. ClusterAgent     — Connected-component cluster detection (Neo4j)
3. ScoringAgent     — Coordination heuristic scoring (0-100)
4. MediaAgent       — Reka media content analysis
5. VerificationAgent — Tavily web-based claim verification
6. BrowsingAgent    — Yutori deep fact-check browsing
"""

import asyncio
from app.agents import (
    SimilarityAgent,
    ClusterAgent,
    ScoringAgent,
    MediaAgent,
    VerificationAgent,
    BrowsingAgent,
)
from app.neo4j_client import run_query
from app.observe import obs


def run_detection() -> list[dict]:
    """Run graph-based detection (agents 1-3). Returns scored clusters."""
    sim = SimilarityAgent()
    sim.run()

    cluster = ClusterAgent()
    clusters = cluster.run()

    scorer = ScoringAgent()
    scored = scorer.run(clusters=clusters)

    return scored


async def run_full_pipeline() -> dict:
    """Run the complete autonomous pipeline (all 6 agents)."""
    obs.clear()
    results = {"stages": {}, "agents_used": []}

    # --- Stage 1: Graph-based detection (sequential: sim -> cluster -> score) ---
    print("[Agents 1-3] Running graph-based coordination detection...")
    scored = run_detection()
    results["stages"]["detection"] = {
        "clusters": scored,
        "total_clusters": len(scored),
        "suspicious": len([c for c in scored if c["score"] >= 30]),
    }
    results["agents_used"].extend(["SimilarityAgent", "ClusterAgent", "ScoringAgent"])
    print(f"  {len(scored)} clusters, {results['stages']['detection']['suspicious']} suspicious")

    # --- Stage 2: Media + Verification in parallel ---
    print("[Agents 4+5] Analyzing media (Reka) + verifying claims (Tavily) in parallel...")
    media_agent = MediaAgent()
    verif_agent = VerificationAgent()
    media_results, claim_results = await asyncio.gather(
        media_agent.arun(),
        verif_agent.arun(),
    )
    results["stages"]["media_analysis"] = {
        "results": media_results,
        "total": len(media_results),
        "analyzed": len([r for r in media_results.values() if r["status"] == "analyzed"]),
    }
    results["stages"]["claim_verification"] = {
        "results": claim_results,
        "total": len(claim_results),
        "debunked": len([r for r in claim_results.values() if r.get("status") == "debunked"]),
        "unverified": len([r for r in claim_results.values() if r.get("status") == "unverified"]),
    }
    results["agents_used"].extend(["MediaAgent", "VerificationAgent"])
    print(f"  Media: {results['stages']['media_analysis']['analyzed']}/{results['stages']['media_analysis']['total']} analyzed")
    print(f"  Claims: {results['stages']['claim_verification']['total']} checked")

    # --- Stage 3: Deep verification ---
    print("[Agent 6] Deep verification via Yutori browsing agent...")
    browse_agent = BrowsingAgent()
    yutori_result = await browse_agent.arun(claims_results=claim_results)
    results["stages"]["deep_verification"] = yutori_result
    results["agents_used"].append("BrowsingAgent")
    if yutori_result and "error" not in yutori_result:
        print(f"  Dispatched for: {yutori_result.get('claim', 'N/A')[:60]}...")
    else:
        print("  Skipped or errored")

    # --- Summary ---
    total_posts = run_query("MATCH (p:Post) RETURN count(p) AS n")[0]["n"]
    results["summary"] = {
        "agents_used": results["agents_used"],
        "sponsor_tools_used": ["Neo4j", "Reka", "Tavily", "Yutori"],
        "total_posts_analyzed": total_posts,
        "suspicious_clusters": results["stages"]["detection"]["suspicious"],
        "media_flagged": results["stages"]["media_analysis"]["analyzed"],
        "claims_checked": results["stages"]["claim_verification"]["total"],
    }
    results["observability"] = obs.summary()

    print(f"\nPipeline complete! {len(results['agents_used'])} agents executed.")
    print(f"  Tools: {', '.join(results['summary']['sponsor_tools_used'])}")
    return results


if __name__ == "__main__":
    result = asyncio.run(run_full_pipeline())
    import json
    print(json.dumps(result["summary"], indent=2))
    print("\n--- Observability ---")
    print(json.dumps(result["observability"], indent=2))
    from app.neo4j_client import close
    close()
