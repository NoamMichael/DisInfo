"""
Full autonomous detection pipeline.

Orchestrates:
1. Neo4j graph analysis (coordination detection)
2. Reka media analysis (video/image content)
3. Tavily web verification (fact-checking claims)
4. Yutori browsing (deep verification on fact-check sites)
"""

import asyncio
from app.detector import run_detection, fetch_posts
from app.neo4j_client import run_query, run_write
from app.api import tavily_client, reka_client, yutori_client


async def analyze_media_posts() -> dict[str, dict]:
    """Use Reka to analyze all posts with media content."""
    media_posts = run_query("""
        MATCH (p:Post)-[:POSTED_BY]->(a:Account)
        WHERE p.media_url IS NOT NULL
        RETURN p.id AS id, p.text AS text, p.media_url AS url,
               p.media_type AS type, a.username AS username
    """)

    results = {}
    for post in media_posts:
        try:
            analysis = await reka_client.chat(
                f"A social media post by @{post['username']} titled: "
                f"'{post['text']}'\n\n"
                f"This post contains a {post['type']}. Based on the title and context:\n"
                "1. Is the title sensationalized or misleading?\n"
                "2. Does it use manipulation tactics (urgency, fear, conspiracy framing)?\n"
                "3. Are there red flags suggesting coordinated disinformation?\n"
                "Rate manipulation likelihood 0-100 and explain."
            )
            content = (
                analysis.get("responses", [{}])[0]
                .get("message", {})
                .get("content", "No analysis available")
            )
            results[post["id"]] = {
                "post_text": post["text"],
                "media_url": post["url"],
                "media_type": post["type"],
                "analysis": content,
                "status": "analyzed",
            }
            # Store result back in Neo4j
            run_write(
                "MATCH (p:Post {id: $id}) SET p.reka_analysis = $analysis",
                {"id": post["id"], "analysis": content[:500]},
            )
        except Exception as e:
            results[post["id"]] = {
                "post_text": post["text"],
                "error": str(e),
                "status": "error",
            }
    return results


async def verify_claims_tavily() -> dict[str, dict]:
    """Use Tavily to web-search for each claim."""
    claims = run_query("MATCH (c:Claim) RETURN c.id AS id, c.text AS text")
    results = {}

    for claim in claims:
        try:
            search_result = await tavily_client.search(
                query=f"fact check: {claim['text']}",
                topic="news",
                max_results=5,
            )
            answer = search_result.get("answer", "No answer generated")
            sources = [
                {"title": r["title"], "url": r["url"], "snippet": r["content"]}
                for r in search_result.get("results", [])
            ]

            # Determine verification status from results
            answer_lower = answer.lower() if answer else ""
            if any(w in answer_lower for w in ["false", "debunked", "no evidence", "misleading", "fabricated"]):
                status = "debunked"
            elif any(w in answer_lower for w in ["true", "confirmed", "verified"]):
                status = "confirmed"
            else:
                status = "unverified"

            results[claim["id"]] = {
                "claim": claim["text"],
                "answer": answer,
                "sources": sources,
                "status": status,
            }

            # Update claim in Neo4j
            run_write(
                """
                MATCH (c:Claim {id: $id})
                SET c.verification_status = $status,
                    c.verification_answer = $answer
                """,
                {"id": claim["id"], "status": status, "answer": answer[:500]},
            )
        except Exception as e:
            results[claim["id"]] = {
                "claim": claim["text"],
                "error": str(e),
                "status": "error",
            }
    return results


async def verify_top_claim_yutori(claims_results: dict) -> dict | None:
    """Use Yutori to browse fact-check sites for the top claim."""
    # Pick the most interesting claim (prefer debunked or unverified)
    target = None
    for cid, result in claims_results.items():
        if result.get("status") in ("debunked", "unverified") and "error" not in result:
            target = result
            break
    if not target:
        return None

    try:
        browse_result = await yutori_client.browse(
            task=(
                f"Search this fact-checking website for information about this claim: "
                f"'{target['claim']}'. Report what you find — has this claim been "
                f"fact-checked? What is the verdict?"
            ),
            start_url="https://www.snopes.com",
        )
        return {
            "claim": target["claim"],
            "yutori_result": browse_result,
            "source": "snopes.com",
        }
    except Exception as e:
        return {"claim": target["claim"], "error": str(e)}


async def run_full_pipeline() -> dict:
    """Run the complete autonomous detection pipeline."""
    results = {"stages": {}}

    # Stage 1: Graph-based coordination detection
    print("[1/4] Running coordination detection...")
    clusters = run_detection()
    results["stages"]["detection"] = {
        "clusters": clusters,
        "total_clusters": len(clusters),
        "suspicious": len([c for c in clusters if c["score"] >= 30]),
    }
    print(f"  Found {len(clusters)} clusters, "
          f"{results['stages']['detection']['suspicious']} suspicious")

    # Stage 2 & 3: Run media analysis and claim verification in parallel
    print("[2/4] Analyzing media content (Reka)...")
    print("[3/4] Verifying claims (Tavily)...")
    media_results, claim_results = await asyncio.gather(
        analyze_media_posts(),
        verify_claims_tavily(),
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
    print(f"  Media: {results['stages']['media_analysis']['analyzed']}/{results['stages']['media_analysis']['total']} analyzed")
    print(f"  Claims: {results['stages']['claim_verification']['total']} checked")

    # Stage 4: Deep verification with Yutori
    print("[4/4] Deep verification via Yutori browsing agent...")
    yutori_result = await verify_top_claim_yutori(claim_results)
    results["stages"]["deep_verification"] = yutori_result
    if yutori_result:
        print(f"  Yutori dispatched for: {yutori_result.get('claim', 'N/A')[:60]}...")
    else:
        print("  No claims needed deep verification")

    results["summary"] = {
        "sponsor_tools_used": ["Neo4j", "Reka", "Tavily", "Yutori"],
        "total_posts_analyzed": len(fetch_posts()),
        "suspicious_clusters": results["stages"]["detection"]["suspicious"],
        "media_flagged": results["stages"]["media_analysis"]["analyzed"],
        "claims_checked": results["stages"]["claim_verification"]["total"],
    }

    print("\nPipeline complete!")
    print(f"  Tools used: {', '.join(results['summary']['sponsor_tools_used'])}")
    return results


if __name__ == "__main__":
    result = asyncio.run(run_full_pipeline())
    import json
    print(json.dumps(result["summary"], indent=2))
    from app.neo4j_client import close
    close()
