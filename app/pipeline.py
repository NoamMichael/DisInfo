"""
Full autonomous detection pipeline — orchestrates 9 agents.

Three orthogonal scores:
  Suspicion — behavioral coordination signals (ScoringAgent)
  Trust     — account credibility from FOLLOWS graph (AccountTrustAgent)
  Emotion   — content emotional intensity / manipulation (EmotionAgent)

Agents:
1. SimilarityAgent    — TF-IDF cosine similarity, writes SIMILAR_TO edges (Neo4j)
2. ClusterAgent       — Connected-component cluster detection (Neo4j)
3. AccountTrustAgent  — Per-account trust from FOLLOWS graph (Neo4j)
4. ScoringAgent       — Trust-weighted coordination scoring (0-100)
5. EmotionAgent       — Per-post emotional intensity scoring (0-100)
6. MediaAgent         — Reka media content analysis
7. VerificationAgent  — Tavily web-based claim verification
8. BrowsingAgent      — Yutori deep fact-check browsing
9. MemoryAgent        — Campaign fingerprinting + recall (Neo4j)
"""

import asyncio
from app.agents import (
    SimilarityAgent,
    ClusterAgent,
    AccountTrustAgent,
    ScoringAgent,
    EmotionAgent,
    MediaAgent,
    VerificationAgent,
    BrowsingAgent,
    MemoryAgent,
)
from app.neo4j_client import run_query
from app.observe import obs


def run_detection() -> list[dict]:
    """Run graph-based detection (agents 1-4). Returns scored clusters."""
    sim = SimilarityAgent()
    sim.run()

    cluster = ClusterAgent()
    clusters = cluster.run()

    # Compute per-account trust from FOLLOWS graph before scoring
    trust = AccountTrustAgent()
    trust.run()

    scorer = ScoringAgent()
    scored = scorer.run(clusters=clusters)

    return scored


async def run_full_pipeline() -> dict:
    """Run the complete autonomous pipeline (all 9 agents)."""
    obs.clear()
    results = {"stages": {}, "agents_used": []}

    # --- Stage 1: Graph-based detection (sequential: sim -> cluster -> trust -> score) ---
    print("[Agents 1-4] Running graph-based coordination detection...")
    scored = run_detection()
    results["stages"]["detection"] = {
        "clusters": scored,
        "total_clusters": len(scored),
        "suspicious": len([c for c in scored if c["score"] >= 30]),
    }
    results["agents_used"].extend(["SimilarityAgent", "ClusterAgent", "AccountTrustAgent", "ScoringAgent"])
    print(f"  {len(scored)} clusters, {results['stages']['detection']['suspicious']} suspicious")

    # --- Stage 2: Emotion scoring (synchronous, no API) ---
    print("[Agent 5] Scoring emotional intensity / manipulation...")
    emotion_agent = EmotionAgent()
    emotion_results = emotion_agent.run()
    results["stages"]["emotion_analysis"] = {
        "results": emotion_results,
        "total": len(emotion_results),
        "high_emotion": len([r for r in emotion_results.values() if r["emotion_score"] >= 50]),
    }
    results["agents_used"].append("EmotionAgent")
    avg_emotion = (
        sum(r["emotion_score"] for r in emotion_results.values()) / len(emotion_results)
        if emotion_results else 0
    )
    print(f"  {len(emotion_results)} posts scored (avg emotion: {avg_emotion:.0f}, "
          f"{results['stages']['emotion_analysis']['high_emotion']} high-emotion)")

    # --- Stage 3: Media + Verification in parallel ---
    print("[Agents 6-7] Media (Reka) + Claims (Tavily) in parallel...")
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

    # --- Stage 4: Deep verification ---
    print("[Agent 8] Deep verification via Yutori browsing agent...")
    browse_agent = BrowsingAgent()
    yutori_result = {}
    try:
        yutori_result = await browse_agent.arun(claims_results=claim_results)
    except Exception as e:
        yutori_result = {"error": str(e)}
    results["stages"]["deep_verification"] = yutori_result
    results["agents_used"].append("BrowsingAgent")
    if yutori_result and "error" not in yutori_result:
        print(f"  Dispatched for: {yutori_result.get('claim', 'N/A')[:60]}...")
    else:
        print("  Skipped or errored")

    # --- Stage 5: Campaign memory ---
    print("[Agent 9] Campaign fingerprinting + recall...")
    memory_agent = MemoryAgent()
    memory_result = memory_agent.run(scored_clusters=scored)
    results["stages"]["campaign_memory"] = memory_result
    results["agents_used"].append("MemoryAgent")
    print(f"  {len(memory_result['stored'])} fingerprints stored, "
          f"{len(memory_result['matches'])} matches found")

    # --- Summary ---
    total_posts = run_query("MATCH (p:Post) RETURN count(p) AS n")[0]["n"]
    results["summary"] = {
        "agents_used": results["agents_used"],
        "sponsor_tools_used": ["Neo4j", "Reka", "Tavily", "Yutori"],
        "total_posts_analyzed": total_posts,
        "suspicious_clusters": results["stages"]["detection"]["suspicious"],
        "media_flagged": results["stages"]["media_analysis"]["analyzed"],
        "claims_checked": results["stages"]["claim_verification"]["total"],
        "avg_emotion": round(avg_emotion, 1),
        "high_emotion_posts": results["stages"]["emotion_analysis"]["high_emotion"],
        "fingerprints_stored": len(memory_result["stored"]),
        "campaign_matches": len(memory_result["matches"]),
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
