"""
Disinfo Detector Dashboard — Streamlit frontend.
Run: streamlit run dashboard.py
"""

import streamlit as st
import json
import asyncio
from datetime import datetime

st.set_page_config(
    page_title="Disinfo Detector",
    page_icon="🔍",
    layout="wide",
)

# ─── State ───────────────────────────────────────────────────────────
for key in ["clusters", "pipeline_results", "pipeline_ran"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "clusters" else (False if key == "pipeline_ran" else None)


# ─── Header ──────────────────────────────────────────────────────────
st.title("Disinfo Detector")
st.markdown("**Coordinated Inauthentic Behavior Detection** — Autonomous Agent Pipeline")

col_stats = st.columns(5)


def get_graph_stats():
    from app.neo4j_client import run_query
    stats = run_query("""
        MATCH (a:Account) WITH count(a) AS accounts
        MATCH (p:Post) WITH accounts, count(p) AS posts
        MATCH (c:Claim) WITH accounts, posts, count(c) AS claims
        OPTIONAL MATCH ()-[s:SIMILAR_TO]->() WITH accounts, posts, claims, count(s) AS sim_edges
        OPTIONAL MATCH ()-[:PART_OF_CAMPAIGN]->(n:Narrative) WITH accounts, posts, claims, sim_edges, count(DISTINCT n) AS campaigns
        RETURN accounts, posts, claims, sim_edges, campaigns
    """)
    return stats[0] if stats else {"accounts": 0, "posts": 0, "claims": 0, "sim_edges": 0, "campaigns": 0}


stats = get_graph_stats()
col_stats[0].metric("Accounts", stats["accounts"])
col_stats[1].metric("Posts", stats["posts"])
col_stats[2].metric("Claims", stats["claims"])
col_stats[3].metric("Similarity Links", stats["sim_edges"])
col_stats[4].metric("Campaigns Flagged", stats["campaigns"])

st.divider()

# ─── Pipeline Controls ──────────────────────────────────────────────
col_left, col_right = st.columns([2, 3])

with col_left:
    st.subheader("Autonomous Pipeline")
    st.markdown(
        "Runs 4 sponsor tools autonomously:\n"
        "1. **Neo4j** — Graph-based coordination detection\n"
        "2. **Reka** — Media content analysis\n"
        "3. **Tavily** — Web-based claim verification\n"
        "4. **Yutori** — Deep fact-check browsing"
    )

    if st.button("Run Full Pipeline", type="primary", use_container_width=True):
        progress = st.empty()
        status_text = st.empty()

        progress.progress(0, "Starting pipeline...")
        status_text.info("Stage 1/4: Analyzing graph for coordinated behavior...")

        from app.detector import run_detection
        clusters = run_detection()
        st.session_state.clusters = clusters
        progress.progress(25, "Detection complete")

        status_text.info("Stage 2/4: Analyzing media with Reka + verifying claims with Tavily...")
        from app.pipeline import analyze_media_posts, verify_claims_tavily, verify_top_claim_yutori

        loop = asyncio.new_event_loop()
        media_results, claim_results = loop.run_until_complete(
            asyncio.gather(analyze_media_posts(), verify_claims_tavily())
        )
        progress.progress(70, "Media + claims analyzed")

        status_text.info("Stage 4/4: Dispatching Yutori browsing agent...")
        yutori_result = loop.run_until_complete(verify_top_claim_yutori(claim_results))
        loop.close()
        progress.progress(100, "Pipeline complete!")

        st.session_state.pipeline_results = {
            "clusters": clusters,
            "media": media_results,
            "claims": claim_results,
            "yutori": yutori_result,
        }
        st.session_state.pipeline_ran = True
        status_text.empty()
        progress.empty()
        st.rerun()

    if st.session_state.pipeline_ran:
        results = st.session_state.pipeline_results
        n_clusters = len(results["clusters"])
        suspicious = len([c for c in results["clusters"] if c["score"] >= 30])
        media_ok = len([r for r in results["media"].values() if r.get("status") == "analyzed"])
        claims_ok = len([r for r in results["claims"].values() if "error" not in r])
        debunked = len([r for r in results["claims"].values() if r.get("status") == "debunked"])

        st.success(f"Pipeline complete — 4 sponsor tools executed autonomously")
        res_cols = st.columns(2)
        res_cols[0].metric("Suspicious Clusters", f"{suspicious}/{n_clusters}")
        res_cols[1].metric("Claims Checked", f"{claims_ok} ({debunked} debunked)")

        st.markdown("**Sponsor Tools Used:**")
        tools_md = (
            "| Tool | Role | Status |\n"
            "|------|------|--------|\n"
            f"| Neo4j | Graph coordination detection | {n_clusters} clusters found |\n"
            f"| Reka | Media content analysis | {media_ok} posts analyzed |\n"
            f"| Tavily | Web claim verification | {claims_ok} claims checked |\n"
            f"| Yutori | Deep fact-check browsing | {'Dispatched' if results.get('yutori') else 'N/A'} |"
        )
        st.markdown(tools_md)

# ─── Network Graph ───────────────────────────────────────────────────
with col_right:
    st.subheader("Network Graph")

    if st.session_state.pipeline_ran:
        from app.neo4j_client import run_query

        nodes_data = run_query("""
            MATCH (p:Post)-[:POSTED_BY]->(a:Account)
            OPTIONAL MATCH (p)-[:PART_OF_CAMPAIGN]->(n:Narrative)
            RETURN p.id AS id, p.platform AS platform, a.username AS username,
                   n.suspicion_score AS suspicion_score,
                   substring(p.text, 0, 60) AS text_preview
        """)

        edges_data = run_query("""
            MATCH (p1:Post)-[r:SIMILAR_TO]->(p2:Post)
            RETURN p1.id AS source, p2.id AS target, r.score AS weight
        """)

        if nodes_data:
            import streamlit.components.v1 as components

            vis_nodes = []
            for n in nodes_data:
                score = n.get("suspicion_score") or 0
                if score >= 50:
                    color = "#ff4444"
                elif score >= 30:
                    color = "#ff8800"
                else:
                    color = "#44aa44"

                platform_shape = {
                    "twitter": "dot", "reddit": "square", "youtube": "triangle"
                }.get(n["platform"], "dot")

                vis_nodes.append({
                    "id": n["id"],
                    "label": n["username"][:15],
                    "title": f"{n['text_preview']}...<br>Platform: {n['platform']}<br>Suspicion: {score}",
                    "color": color,
                    "shape": platform_shape,
                    "size": 12 + (score / 4),
                })

            vis_edges = []
            for e in edges_data:
                vis_edges.append({
                    "from": e["source"],
                    "to": e["target"],
                    "value": e["weight"],
                    "color": {"color": "#666666", "opacity": 0.5},
                })

            html = f"""
            <html>
            <head>
                <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
                <style>#graph {{width:100%;height:500px;border:1px solid #333;border-radius:8px;background:#0e1117;}}</style>
            </head>
            <body style="margin:0;background:#0e1117;">
                <div id="graph"></div>
                <script>
                    var nodes = new vis.DataSet({json.dumps(vis_nodes)});
                    var edges = new vis.DataSet({json.dumps(vis_edges)});
                    var options = {{
                        physics: {{
                            forceAtlas2Based: {{gravitationalConstant:-40, centralGravity:0.01, springLength:100, springConstant:0.05}},
                            solver:'forceAtlas2Based',
                            stabilization:{{iterations:150}}
                        }},
                        nodes:{{font:{{color:'#ffffff',size:10}},borderWidth:2}},
                        edges:{{smooth:{{type:'continuous'}}}},
                        interaction:{{hover:true,tooltipDelay:100}}
                    }};
                    new vis.Network(document.getElementById('graph'), {{nodes:nodes,edges:edges}}, options);
                </script>
            </body>
            </html>
            """
            components.html(html, height=520)

            st.markdown(
                "**Legend:** "
                "🔴 High suspicion (50+) | "
                "🟠 Medium (30-49) | "
                "🟢 Low (<30) | "
                "● Twitter | ■ Reddit | ▲ YouTube"
            )
    else:
        st.info("Click **Run Full Pipeline** to analyze the social media graph.")

# ─── Cluster Details ─────────────────────────────────────────────────
if st.session_state.pipeline_ran and st.session_state.clusters:
    st.divider()
    st.subheader("Detected Clusters")

    for cluster in st.session_state.clusters:
        score = cluster["score"]
        signals = cluster["signals"]
        icon = "🔴" if score >= 50 else ("🟠" if score >= 30 else "🟢")

        with st.expander(
            f"{icon} {cluster['cluster_id']} — Score: {score}/100 | "
            f"{signals['total_posts']} posts from {signals['unique_accounts']} accounts | "
            f"Platforms: {', '.join(signals['platforms'])}", expanded=(score >= 30)
        ):
            sig_cols = st.columns(5)
            sig_cols[0].metric("Text Similarity", f"{signals['avg_text_similarity']:.0%}")
            sig_cols[1].metric("Acct Age Spread", f"{signals['account_age_spread_hours']:.0f}h")
            sig_cols[2].metric("Post Window", f"{signals['posting_velocity_minutes']:.0f} min")
            sig_cols[3].metric("Avg Followers", f"{signals['avg_followers']:.0f}")
            sig_cols[4].metric("Media Posts", signals["media_posts"])

            st.markdown("**Posts in this cluster:**")
            for post in cluster["posts"]:
                pe = {"twitter": "🐦", "reddit": "📋", "youtube": "📺"}.get(post.get("platform", ""), "📝")
                media_badge = " 🎬" if post.get("media_url") else ""
                st.markdown(
                    f"{pe} **@{post['username']}** · {post['platform']}{media_badge}  \n"
                    f"> _{post['text'][:150]}{'...' if len(post['text']) > 150 else ''}_"
                )

# ─── Claim Verification ─────────────────────────────────────────────
if st.session_state.pipeline_ran and st.session_state.pipeline_results.get("claims"):
    st.divider()
    st.subheader("Claim Verification (Tavily)")

    for claim_id, result in st.session_state.pipeline_results["claims"].items():
        status = result.get("status", "unknown")
        badge = {"debunked": "🚫", "confirmed": "✅", "unverified": "❓", "error": "⚠️"}.get(status, "❓")
        claim_short = result["claim"][:80] + ("..." if len(result["claim"]) > 80 else "")

        with st.expander(f"{badge} [{status.upper()}] {claim_short}"):
            if "error" in result:
                st.error(f"Verification failed: {result['error']}")
            else:
                st.markdown(f"**Verdict:** {result.get('answer', 'N/A')}")
                if result.get("sources"):
                    st.markdown("**Sources:**")
                    for src in result["sources"]:
                        st.markdown(f"- [{src['title']}]({src['url']})")

# ─── Media Analysis ─────────────────────────────────────────────────
if st.session_state.pipeline_ran and st.session_state.pipeline_results.get("media"):
    st.divider()
    st.subheader("Media Analysis (Reka)")

    for post_id, result in st.session_state.pipeline_results["media"].items():
        status = result.get("status", "unknown")
        badge = "✅" if status == "analyzed" else "⚠️"
        title = result.get("post_text", "Unknown post")[:80]

        with st.expander(f"{badge} {title}..."):
            if "error" in result:
                st.error(f"Analysis failed: {result['error']}")
            else:
                st.markdown(result.get("analysis", "No analysis available"))

# ─── Yutori Deep Verification ───────────────────────────────────────
if st.session_state.pipeline_ran and st.session_state.pipeline_results.get("yutori"):
    st.divider()
    st.subheader("Deep Verification (Yutori)")
    yr = st.session_state.pipeline_results["yutori"]
    st.markdown(f"**Claim investigated:** {yr.get('claim', 'N/A')}")
    if "error" in yr:
        st.error(f"Yutori error: {yr['error']}")
    else:
        yutori_data = yr.get("yutori_result", {})
        if isinstance(yutori_data, dict):
            if "task_id" in yutori_data:
                st.info(f"Yutori task dispatched (ID: {yutori_data['task_id']})")
            if "view_url" in yutori_data:
                st.markdown(f"[View Yutori agent session]({yutori_data['view_url']})")
            # Show any text results
            for key in ["result", "output", "response", "text"]:
                if key in yutori_data:
                    st.markdown(f"**Result:** {yutori_data[key]}")
        else:
            st.json(yutori_data)

# ─── Footer ──────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Disinfo Detector | Autonomous Agents Hackathon 2026 | "
    "Sponsor tools: Neo4j, Tavily, Reka, Yutori"
)
