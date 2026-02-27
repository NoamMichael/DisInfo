"""
Core coordination detection — delegates to agents.

Kept as a thin compatibility layer. The real logic lives in:
  app/agents/similarity_agent.py
  app/agents/cluster_agent.py
  app/agents/scoring_agent.py
"""

from app.neo4j_client import run_query


def fetch_posts() -> list[dict]:
    """Get all posts with their account info from Neo4j."""
    return run_query("""
        MATCH (p:Post)-[:POSTED_BY]->(a:Account)
        RETURN p.id AS id, p.text AS text, p.platform AS platform,
               p.timestamp AS timestamp, p.media_url AS media_url,
               p.media_type AS media_type,
               a.id AS account_id, a.username AS username,
               a.created_at AS account_created_at,
               a.follower_count AS follower_count
        ORDER BY p.timestamp
    """)


def run_detection() -> list[dict]:
    """Run the full detection pipeline via agents. Returns scored clusters."""
    from app.pipeline import run_detection as _run
    return _run()


if __name__ == "__main__":
    results = run_detection()
    print(f"\nDetection complete. {len(results)} clusters analyzed.")
    for c in results:
        print(f"  {c['cluster_id']}: score={c['score']}, "
              f"posts={c['signals']['total_posts']}, "
              f"platforms={c['signals']['platforms']}")
    from app.neo4j_client import close
    close()
