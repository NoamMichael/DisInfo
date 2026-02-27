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
        "**8 autonomous agents**, 5 sponsor tools:\n"
        "1. **SimilarityAgent** — TF-IDF text similarity (Neo4j)\n"
        "2. **ClusterAgent** — Connected-component detection (Neo4j)\n"
        "3. **ScoringAgent** — Coordination heuristic scoring\n"
        "4. **MediaAgent** — Media content analysis (Reka)\n"
        "5. **VerificationAgent** — Claim fact-checking (Tavily)\n"
        "6. **EntityAgent** — Entity extraction + classification (Pioneer/GLiNER-2)\n"
        "7. **BrowsingAgent** — Deep verification (Yutori)\n"
        "8. **MemoryAgent** — Campaign fingerprinting + recall (Neo4j)"
    )

    if st.button("Run Full Pipeline", type="primary", use_container_width=True):
        progress = st.empty()
        status_text = st.empty()

        try:
            progress.progress(0, "Starting pipeline...")
            status_text.info("Agents 1-3: SimilarityAgent -> ClusterAgent -> ScoringAgent...")

            from app.pipeline import run_detection
            from app.agents import MediaAgent, VerificationAgent, BrowsingAgent, EntityAgent, MemoryAgent

            clusters = run_detection()
            st.session_state.clusters = clusters
            progress.progress(15, "Detection complete")

            status_text.info("Agents 4-6: MediaAgent + VerificationAgent + EntityAgent (parallel)...")
            media_agent = MediaAgent()
            verif_agent = VerificationAgent()
            entity_agent = EntityAgent()
            loop = asyncio.new_event_loop()

            media_results, claim_results, entity_results = {}, {}, {}
            try:
                media_results, claim_results, entity_results = loop.run_until_complete(
                    asyncio.gather(media_agent.arun(), verif_agent.arun(), entity_agent.arun())
                )
            except Exception as e:
                st.warning(f"Some parallel agents had issues: {e}")
            progress.progress(60, "Media + claims + entities analyzed")

            status_text.info("Agent 7: BrowsingAgent dispatching to Snopes...")
            browse_agent = BrowsingAgent()
            yutori_result = {}
            try:
                yutori_result = loop.run_until_complete(browse_agent.arun(claims_results=claim_results))
            except Exception as e:
                yutori_result = {"error": f"Yutori unavailable: {e}"}
            progress.progress(80, "Deep verification complete")

            status_text.info("Agent 8: MemoryAgent fingerprinting campaigns...")
            memory_agent = MemoryAgent()
            memory_result = {}
            try:
                memory_result = memory_agent.run(
                    scored_clusters=clusters,
                    entity_results=entity_results,
                )
            except Exception as e:
                memory_result = {"error": f"Memory agent failed: {e}", "stored": [], "matches": []}
            loop.close()
            progress.progress(100, "Pipeline complete!")

            st.session_state.pipeline_results = {
                "clusters": clusters,
                "media": media_results,
                "claims": claim_results,
                "entities": entity_results,
                "yutori": yutori_result,
                "memory": memory_result,
            }
            st.session_state.pipeline_ran = True
            status_text.empty()
            progress.empty()
            st.rerun()

        except Exception as e:
            progress.empty()
            status_text.empty()
            st.error(f"Pipeline failed: {e}")

    if st.session_state.pipeline_ran:
        results = st.session_state.pipeline_results
        n_clusters = len(results["clusters"])
        suspicious = len([c for c in results["clusters"] if c["score"] >= 30])
        media_ok = len([r for r in results["media"].values() if r.get("status") == "analyzed"])
        claims_ok = len([r for r in results["claims"].values() if "error" not in r])
        debunked = len([r for r in results["claims"].values() if r.get("status") == "debunked"])
        entity_ok = len([r for r in results.get("entities", {}).values() if r.get("status") == "analyzed"])
        entity_flagged = len([
            r for r in results.get("entities", {}).values()
            if r.get("classification", {}).get("label") in ("disinformation", "conspiracy_theory")
        ])

        st.success(f"Pipeline complete — 5 sponsor tools executed autonomously")
        res_cols = st.columns(3)
        res_cols[0].metric("Suspicious Clusters", f"{suspicious}/{n_clusters}")
        res_cols[1].metric("Claims Checked", f"{claims_ok} ({debunked} debunked)")
        res_cols[2].metric("Disinfo Flagged", f"{entity_flagged}/{entity_ok} posts")

        st.markdown("**Sponsor Tools Used:**")
        tools_md = (
            "| Tool | Role | Status |\n"
            "|------|------|--------|\n"
            f"| Neo4j | Graph coordination detection | {n_clusters} clusters found |\n"
            f"| Reka | Media content analysis | {media_ok} posts analyzed |\n"
            f"| Tavily | Web claim verification | {claims_ok} claims checked |\n"
            f"| Pioneer/GLiNER-2 | Entity extraction + classification | {entity_ok} posts, {entity_flagged} flagged |\n"
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
                    color = {"background": "#ff2222", "border": "#cc0000"}
                elif score >= 30:
                    color = {"background": "#ff8800", "border": "#cc6600"}
                else:
                    color = {"background": "#22cc44", "border": "#119933"}

                platform_shape = {
                    "x": "dot", "twitter": "dot", "reddit": "square", "youtube": "triangle"
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
                w = e["weight"] or 0.3
                edge_color = "#ff4444" if w >= 0.7 else ("#ff8844" if w >= 0.5 else "#666666")
                vis_edges.append({
                    "from": e["source"],
                    "to": e["target"],
                    "width": 1 + w * 4,
                    "color": {"color": edge_color, "opacity": 0.6},
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
                "● X/Twitter | ■ Reddit | ▲ YouTube"
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
                pe = {"x": "🐦", "twitter": "🐦", "reddit": "📋", "youtube": "📺"}.get(post.get("platform", ""), "📝")
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

# ─── Entity Analysis (Pioneer/GLiNER-2) ────────────────────────────
if st.session_state.pipeline_ran and st.session_state.pipeline_results.get("entities"):
    st.divider()
    st.subheader("Entity Extraction & Classification (Pioneer/GLiNER-2)")

    entity_data = st.session_state.pipeline_results["entities"]

    # Summary stats
    classifications = {}
    all_entities_by_type = {}
    for post_id, result in entity_data.items():
        if result.get("status") != "analyzed":
            continue
        label = result.get("classification", {}).get("label", "unknown")
        classifications[label] = classifications.get(label, 0) + 1
        for etype, ents in result.get("entities", {}).items():
            for ent in ents:
                key = ent["text"]
                if etype not in all_entities_by_type:
                    all_entities_by_type[etype] = {}
                all_entities_by_type[etype][key] = all_entities_by_type[etype].get(key, 0) + 1

    # Classification breakdown
    class_cols = st.columns(len(classifications) if classifications else 1)
    for i, (label, count) in enumerate(sorted(classifications.items(), key=lambda x: -x[1])):
        icon = {"disinformation": "🚨", "conspiracy_theory": "⚠️", "news_report": "📰",
                "personal_opinion": "💬", "satire": "😄", "legitimate_concern": "✅"}.get(label, "📝")
        class_cols[i % len(class_cols)].metric(f"{icon} {label.replace('_', ' ').title()}", count)

    # Most-mentioned entities
    if all_entities_by_type:
        st.markdown("**Top Extracted Entities:**")
        ent_cols = st.columns(min(len(all_entities_by_type), 4))
        for i, (etype, entities) in enumerate(all_entities_by_type.items()):
            top = sorted(entities.items(), key=lambda x: -x[1])[:5]
            col = ent_cols[i % len(ent_cols)]
            col.markdown(f"**{etype.replace('_', ' ').title()}**")
            for name, count in top:
                col.markdown(f"- {name} ({count}x)")

    # Per-post details (expandable)
    with st.expander("Per-Post Details", expanded=False):
        for post_id, result in entity_data.items():
            if result.get("status") != "analyzed":
                continue
            cls = result.get("classification", {})
            label = cls.get("label", "unknown")
            conf = cls.get("confidence", 0)
            icon = {"disinformation": "🚨", "conspiracy_theory": "⚠️"}.get(label, "📝")

            entities_summary = []
            for etype, ents in result.get("entities", {}).items():
                for ent in ents:
                    entities_summary.append(f"`{ent['text']}` ({etype})")

            st.markdown(
                f"{icon} **{post_id}** — **{label.replace('_', ' ')}** ({conf:.0%})  \n"
                f"> _{result['post_text'][:120]}{'...' if len(result['post_text']) > 120 else ''}_  \n"
                f"Entities: {', '.join(entities_summary[:8])}"
                f"{'...' if len(entities_summary) > 8 else ''}"
            )

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

# ─── Campaign Memory ──────────────────────────────────────────────
if st.session_state.pipeline_ran and st.session_state.pipeline_results.get("memory"):
    st.divider()
    st.subheader("Campaign Memory (MemoryAgent)")

    mem = st.session_state.pipeline_results["memory"]
    mem_cols = st.columns(2)
    mem_cols[0].metric("Fingerprints Stored", len(mem.get("stored", [])))
    mem_cols[1].metric("Pattern Matches", len(mem.get("matches", [])))

    # Show matches (the wow-factor)
    if mem.get("matches"):
        st.markdown("**Recognized Patterns — Seen Before:**")
        for m in mem["matches"]:
            st.warning(
                f"**{m['cluster_id']}** matches stored fingerprint **{m['matched_fingerprint']}**  \n"
                f"Keyword overlap: **{m['keyword_overlap']:.0%}** | "
                f"Shared accounts: **{m['account_overlap']}**  \n"
                f"Shared keywords: {', '.join(f'`{k}`' for k in m['shared_keywords'][:8])}"
            )

    # Show stored fingerprints
    if mem.get("stored"):
        with st.expander("Stored Campaign Fingerprints", expanded=False):
            for fp in mem["stored"]:
                st.markdown(
                    f"**{fp['cluster_id']}** (score: {fp['score']})  \n"
                    f"Keywords: {', '.join(f'`{k}`' for k in fp['keywords'][:10])}  \n"
                    f"Platforms: {', '.join(fp['platforms'])} | "
                    f"Accounts: {fp['account_count']} | "
                    f"Posts: {fp['post_count']} | "
                    f"Velocity: {fp['velocity_minutes']:.0f}min"
                )
                if fp.get("entities"):
                    ent_parts = []
                    for etype, ents in fp["entities"].items():
                        for e in ents[:3]:
                            ent_parts.append(f"{e['text']} ({etype})")
                    if ent_parts:
                        st.markdown(f"Entities: {', '.join(ent_parts)}")
                st.markdown("---")

# ─── Observability ─────────────────────────────────────────────────
if st.session_state.pipeline_ran:
    from app.observe import obs

    st.divider()
    st.subheader("Pipeline Observability")

    summary = obs.summary()

    # Top-level metrics
    obs_cols = st.columns(4)
    obs_cols[0].metric("Total API Calls", summary["api_calls"])
    obs_cols[1].metric("Errors", summary["errors"])
    obs_cols[2].metric("API Time", f"{summary['total_api_time_ms'] / 1000:.1f}s")
    obs_cols[3].metric("Pipeline Time", f"{summary['total_pipeline_time_ms'] / 1000:.1f}s")

    # Per-tool breakdown
    if summary["by_tool"]:
        st.markdown("**Per-Tool Breakdown:**")
        tool_rows = []
        for tool, stats in summary["by_tool"].items():
            tool_rows.append({
                "Tool": tool,
                "Calls": stats["calls"],
                "Total Time": f"{stats['total_ms'] / 1000:.1f}s",
                "Avg Latency": f"{stats['total_ms'] / stats['calls']:.0f}ms" if stats["calls"] else "N/A",
                "Errors": stats["errors"],
            })
        st.table(tool_rows)

    # Stage timings
    if summary["stage_timings"]:
        st.markdown("**Stage Timings:**")
        for stage, ms in summary["stage_timings"].items():
            pct = (ms / summary["total_pipeline_time_ms"] * 100) if summary["total_pipeline_time_ms"] > 0 else 0
            st.progress(min(pct / 100, 1.0), text=f"{stage}: {ms / 1000:.1f}s ({pct:.0f}%)")

    # Event log
    with st.expander("Event Log", expanded=False):
        events = obs.get_events()
        for evt in events:
            kind = evt["kind"]
            icon = {"start": "▶", "end": "✅", "api_call": "🔗", "error": "❌", "info": "ℹ️"}.get(kind, "·")
            dur = f" ({evt['duration_ms']:.0f}ms)" if evt.get("duration_ms") else ""
            ts = evt["timestamp"].split("T")[1][:12]
            st.text(f"{ts} {icon} [{evt['stage']}] {evt['message']}{dur}")

# ─── Footer ──────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Disinfo Detector | Autonomous Agents Hackathon 2026 | "
    "Sponsor tools: Neo4j, Tavily, Reka, Yutori, Pioneer/Fastino"
)
