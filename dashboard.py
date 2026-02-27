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
        "**9 autonomous agents**, 4 sponsor tools — 3 orthogonal scores:\n"
        "1. **SimilarityAgent** — TF-IDF text similarity (Neo4j)\n"
        "2. **ClusterAgent** — Connected-component detection (Neo4j)\n"
        "3. **AccountTrustAgent** — FOLLOWS graph trust scoring (Neo4j)\n"
        "4. **ScoringAgent** — Trust-weighted coordination scoring\n"
        "5. **EmotionAgent** — Emotional intensity / manipulation scoring\n"
        "6. **MediaAgent** — Media content analysis (Reka)\n"
        "7. **VerificationAgent** — Claim fact-checking (Tavily)\n"
        "8. **BrowsingAgent** — Deep verification (Yutori)\n"
        "9. **MemoryAgent** — Campaign fingerprinting + recall (Neo4j)"
    )

    if st.button("Run Full Pipeline", type="primary", use_container_width=True):
        progress = st.empty()
        status_text = st.empty()

        try:
            progress.progress(0, "Starting pipeline...")
            status_text.info("Agents 1-4: SimilarityAgent -> ClusterAgent -> AccountTrustAgent -> ScoringAgent...")

            from app.pipeline import run_detection
            from app.agents import AccountTrustAgent, EmotionAgent, MediaAgent, VerificationAgent, BrowsingAgent, MemoryAgent

            clusters = run_detection()
            st.session_state.clusters = clusters
            progress.progress(15, "Detection complete")

            status_text.info("Agent 5: EmotionAgent scoring emotional intensity...")
            emotion_agent = EmotionAgent()
            emotion_results = emotion_agent.run()
            progress.progress(25, "Emotion scoring complete")

            status_text.info("Agents 6-7: MediaAgent + VerificationAgent (parallel)...")
            media_agent = MediaAgent()
            verif_agent = VerificationAgent()
            loop = asyncio.new_event_loop()

            media_results, claim_results = {}, {}
            try:
                media_results, claim_results = loop.run_until_complete(
                    asyncio.gather(media_agent.arun(), verif_agent.arun())
                )
            except Exception as e:
                st.warning(f"Some parallel agents had issues: {e}")
            progress.progress(60, "Media + claims analyzed")

            status_text.info("Agent 8: BrowsingAgent dispatching to Snopes...")
            browse_agent = BrowsingAgent()
            yutori_result = {}
            try:
                yutori_result = loop.run_until_complete(browse_agent.arun(claims_results=claim_results))
            except Exception as e:
                yutori_result = {"error": f"Yutori unavailable: {e}"}
            progress.progress(80, "Deep verification complete")

            status_text.info("Agent 9: MemoryAgent fingerprinting campaigns...")
            memory_agent = MemoryAgent()
            memory_result = {}
            try:
                memory_result = memory_agent.run(scored_clusters=clusters)
            except Exception as e:
                memory_result = {"error": f"Memory agent failed: {e}", "stored": [], "matches": []}
            loop.close()
            progress.progress(100, "Pipeline complete!")

            st.session_state.pipeline_results = {
                "clusters": clusters,
                "media": media_results,
                "claims": claim_results,
                "emotion": emotion_results,
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
        emotion_data = results.get("emotion", {})
        emotion_scores = [r["emotion_score"] for r in emotion_data.values() if r.get("status") == "analyzed"]
        avg_emotion = sum(emotion_scores) / len(emotion_scores) if emotion_scores else 0
        high_emotion = len([s for s in emotion_scores if s >= 50])

        st.success(f"Pipeline complete — 4 sponsor tools, 3 orthogonal scores")

        # Three orthogonal scores — the headline
        st.markdown("### Suspicion | Trust | Emotion")
        score_cols = st.columns(3)
        top_suspicion = max((c["score"] for c in results["clusters"]), default=0)
        avg_trust_vals = [c["signals"].get("avg_trust", 0) for c in results["clusters"] if c.get("signals")]
        avg_trust = sum(avg_trust_vals) / len(avg_trust_vals) if avg_trust_vals else 0
        score_cols[0].metric("Suspicion (top cluster)", f"{top_suspicion}/100",
                             help="Behavioral coordination — are accounts acting together?")
        score_cols[1].metric("Trust (avg account)", f"{avg_trust:.0%}",
                             help="Account credibility — follower graph, age, authority")
        score_cols[2].metric("Emotion (avg post)", f"{avg_emotion:.0f}/100",
                             help="Emotional manipulation — loaded language, urgency, caps")

        res_cols = st.columns(3)
        res_cols[0].metric("Suspicious Clusters", f"{suspicious}/{n_clusters}")
        res_cols[1].metric("Claims Checked", f"{claims_ok} ({debunked} debunked)")
        res_cols[2].metric("High Emotion Posts", f"{high_emotion}/{len(emotion_scores)}")

        st.markdown("**Sponsor Tools Used:**")
        tools_md = (
            "| Tool | Role | Status |\n"
            "|------|------|--------|\n"
            f"| Neo4j | Graph coordination detection + campaign memory | {n_clusters} clusters found |\n"
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
                   coalesce(a.trust_score, 0.0) AS trust_score,
                   coalesce(p.emotion_score, 0) AS emotion_score,
                   substring(p.text, 0, 60) AS text_preview,
                   p.text AS full_text,
                   p.source_url AS source_url,
                   p.media_url AS media_url,
                   p.timestamp AS timestamp
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
                trust = n.get("trust_score") or 0.0
                emotion = n.get("emotion_score") or 0
                if score >= 50:
                    color = {"background": "#ff2222", "border": "#cc0000"}
                elif score >= 30:
                    color = {"background": "#ff8800", "border": "#cc6600"}
                else:
                    color = {"background": "#22cc44", "border": "#119933"}

                # Emotion glow: high-emotion posts get a thicker border
                border_width = 2 + (emotion / 25)

                platform_shape = {
                    "x": "dot", "twitter": "dot", "reddit": "square", "youtube": "triangle", "web": "diamond"
                }.get(n["platform"], "dot")

                source_url = n.get("source_url") or ""
                full_text = (n.get("full_text") or "")
                media_url = n.get("media_url") or ""
                timestamp = str(n.get("timestamp") or "")

                trust_pct = int(trust * 100)
                vis_nodes.append({
                    "id": n["id"],
                    "label": n["username"][:15],
                    "title": (
                        f"{n['text_preview']}...<br>Platform: {n['platform']}<br>"
                        f"Suspicion: {score} | Trust: {trust_pct}% | Emotion: {emotion}<br>"
                        f"<i>Click to view post</i>"
                    ),
                    "color": color,
                    "shape": platform_shape,
                    "size": 12 + (score / 4),
                    "borderWidth": border_width,
                    "fullText": full_text,
                    "sourceUrl": source_url,
                    "mediaUrl": media_url,
                    "username": n["username"],
                    "platform": n["platform"],
                    "timestamp": timestamp,
                    "score": score,
                    "trust": trust_pct,
                    "emotion": emotion,
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
                <style>
                    #graph {{width:100%;height:450px;border:1px solid #333;border-radius:8px 8px 0 0;background:#0e1117;}}
                    #detail {{
                        display:none;width:100%;min-height:80px;padding:12px 16px;
                        background:#161b22;border:1px solid #333;border-top:none;border-radius:0 0 8px 8px;
                        color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;
                        box-sizing:border-box;
                    }}
                    #detail .header {{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}}
                    #detail .username {{color:#58a6ff;font-weight:600;font-size:14px;}}
                    #detail .platform {{
                        background:#30363d;color:#8b949e;padding:2px 8px;border-radius:12px;font-size:11px;
                    }}
                    #detail .score-badge {{
                        padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;
                    }}
                    #detail .text {{color:#c9d1d9;line-height:1.5;margin:8px 0;white-space:pre-wrap;}}
                    #detail .link {{
                        display:inline-block;margin-top:8px;padding:6px 14px;
                        background:#238636;color:#fff;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;
                        cursor:pointer;
                    }}
                    #detail .link:hover {{background:#2ea043;}}
                    #detail .link.media {{background:#1f6feb;}}
                    #detail .link.media:hover {{background:#388bfd;}}
                    #detail .meta {{color:#8b949e;font-size:11px;margin-top:6px;}}
                    #detail .close-btn {{
                        cursor:pointer;color:#8b949e;font-size:18px;float:right;margin:-4px 0 0 8px;
                    }}
                    #detail .close-btn:hover {{color:#e6edf3;}}
                </style>
            </head>
            <body style="margin:0;background:#0e1117;">
                <div id="graph"></div>
                <div id="detail">
                    <span class="close-btn" onclick="document.getElementById('detail').style.display='none'">&times;</span>
                    <div class="header">
                        <span><span class="username" id="d-user"></span> <span class="platform" id="d-plat"></span> <span class="score-badge" id="d-score"></span></span>
                        <span class="meta" id="d-time"></span>
                    </div>
                    <div class="text" id="d-text"></div>
                    <span id="d-links"></span>
                </div>
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
                    var network = new vis.Network(document.getElementById('graph'), {{nodes:nodes,edges:edges}}, options);

                    network.on("click", function(params) {{
                        if (params.nodes.length === 0) {{
                            document.getElementById('detail').style.display = 'none';
                            return;
                        }}
                        var nodeId = params.nodes[0];
                        var node = nodes.get(nodeId);
                        if (!node) return;

                        document.getElementById('d-user').textContent = '@' + node.username;
                        document.getElementById('d-plat').textContent = node.platform;
                        document.getElementById('d-text').textContent = node.fullText || node.label;
                        document.getElementById('d-time').textContent = node.timestamp ? node.timestamp.split('.')[0].replace('T', ' ') : '';

                        var scoreBadge = document.getElementById('d-score');
                        var trustPct = node.trust || 0;
                        var emotionVal = node.emotion || 0;
                        scoreBadge.innerHTML = (
                            '<span style="background:' + (node.score >= 50 ? '#da3633' : (node.score >= 30 ? '#d29922' : '#238636')) + ';padding:2px 6px;border-radius:8px;margin-right:4px;">Suspicion: ' + (node.score || 0) + '</span>' +
                            '<span style="background:' + (trustPct >= 50 ? '#238636' : '#d29922') + ';padding:2px 6px;border-radius:8px;margin-right:4px;">Trust: ' + trustPct + '%</span>' +
                            '<span style="background:' + (emotionVal >= 50 ? '#da3633' : (emotionVal >= 25 ? '#d29922' : '#238636')) + ';padding:2px 6px;border-radius:8px;">Emotion: ' + emotionVal + '</span>'
                        );
                        scoreBadge.style.color = '#fff';

                        var links = '';
                        var isReal = function(url) {{ return url && url.indexOf('example.com') === -1; }};
                        if (isReal(node.sourceUrl)) {{
                            links += '<a class="link" href="' + node.sourceUrl + '" target="_blank">Open Source Article &#8599;</a> ';
                        }}
                        if (isReal(node.mediaUrl) && node.mediaUrl !== node.sourceUrl) {{
                            links += '<a class="link media" href="' + node.mediaUrl + '" target="_blank">View Media &#8599;</a> ';
                        }}
                        if (!isReal(node.sourceUrl) && !isReal(node.mediaUrl)) {{
                            links += '<span class="meta">Synthetic post — no external link</span>';
                        }}
                        document.getElementById('d-links').innerHTML = links;
                        document.getElementById('detail').style.display = 'block';
                    }});
                </script>
            </body>
            </html>
            """
            components.html(html, height=620)

            st.markdown(
                "**Legend:** "
                "🔴 High suspicion (50+) | "
                "🟠 Medium (30-49) | "
                "🟢 Low (<30) | "
                "● X/Twitter | ■ Reddit | ▲ YouTube | ◆ Web/News"
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
            sig_cols = st.columns(6)
            sig_cols[0].metric("Text Similarity", f"{signals['avg_text_similarity']:.0%}")
            sig_cols[1].metric("Acct Age Spread", f"{signals['account_age_spread_hours']:.0f}h")
            sig_cols[2].metric("Post Window", f"{signals['posting_velocity_minutes']:.0f} min")
            sig_cols[3].metric("Avg Followers", f"{signals['avg_followers']:.0f}")
            sig_cols[4].metric("Avg Trust", f"{signals.get('avg_trust', 0):.0%}")
            sig_cols[5].metric("Trust Multiplier", f"{signals.get('trust_multiplier', 1.0):.2f}x")

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

# ─── Emotion Analysis ─────────────────────────────────────────────
if st.session_state.pipeline_ran and st.session_state.pipeline_results.get("emotion"):
    st.divider()
    st.subheader("Emotional Intensity Analysis")

    emotion_data = st.session_state.pipeline_results["emotion"]
    emotion_posts = [r for r in emotion_data.values() if r.get("status") == "analyzed"]
    emotion_scores_list = [r["emotion_score"] for r in emotion_posts]

    if emotion_scores_list:
        # Distribution buckets
        low = len([s for s in emotion_scores_list if s < 25])
        med = len([s for s in emotion_scores_list if 25 <= s < 50])
        high = len([s for s in emotion_scores_list if 50 <= s < 75])
        extreme = len([s for s in emotion_scores_list if s >= 75])

        dist_cols = st.columns(4)
        dist_cols[0].metric("Low (0-24)", low)
        dist_cols[1].metric("Medium (25-49)", med)
        dist_cols[2].metric("High (50-74)", high)
        dist_cols[3].metric("Extreme (75+)", extreme)

        # Signal breakdown across all posts
        all_breakdowns = [r["breakdown"] for r in emotion_posts if r.get("breakdown")]
        if all_breakdowns:
            avg_signals = {}
            for key in all_breakdowns[0]:
                avg_signals[key] = sum(b[key] for b in all_breakdowns) / len(all_breakdowns)

            st.markdown("**Average Signal Strength Across All Posts:**")
            sig_cols = st.columns(len(avg_signals))
            signal_labels = {
                "loaded_vocab": "Loaded Vocab",
                "sentiment_extremity": "Sentiment",
                "urgency": "Urgency",
                "caps_ratio": "ALL CAPS",
                "punctuation": "Punctuation",
                "absolutism": "Absolutism",
            }
            for i, (key, val) in enumerate(avg_signals.items()):
                sig_cols[i].metric(signal_labels.get(key, key), f"{val:.0%}")

    # Top emotional posts
    sorted_emotion = sorted(emotion_posts, key=lambda r: r["emotion_score"], reverse=True)
    with st.expander("Most Emotionally Charged Posts", expanded=True):
        for r in sorted_emotion[:10]:
            score = r["emotion_score"]
            icon = "🔴" if score >= 50 else ("🟠" if score >= 25 else "🟢")
            bd = r.get("breakdown", {})
            top_signals = sorted(bd.items(), key=lambda x: -x[1])[:3]
            signal_str = ", ".join(f"{signal_labels.get(k, k)}: {v:.0%}" for k, v in top_signals if v > 0)
            st.markdown(
                f"{icon} **Emotion: {score}/100** — @{r['username']} ({r['platform']})  \n"
                f"> _{r['post_text'][:140]}{'...' if len(r['post_text']) > 140 else ''}_  \n"
                f"Signals: {signal_str or 'none'}"
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
    "Sponsor tools: Neo4j, Tavily, Reka, Yutori | "
    "Three scores: Suspicion | Trust | Emotion"
)
