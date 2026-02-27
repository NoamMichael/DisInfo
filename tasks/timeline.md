# Hackathon Day Timeline & Task Tracker

**Date:** February 27, 2026
**Venue:** AWS Builder Loft
**Coding window:** 11:00 AM - 4:30 PM (5.5 hours)
**Submissions due:** 4:30 PM
**Presentations:** ~4:30 PM onward

---

## Pre-Hackathon (Before 11 AM)

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| P1 | Provision Neo4j AuraDB free instance | | [Done] | AuraDB free instance up, schema constraints created, smoke test passed |
| P2 | Get all API keys (Yutori, Modulate, Reka, Fastino, Tavily) | | [Done] | All keys in `.env`, `.env.example` has placeholders |
| P3 | Prepare synthetic dataset (JSON/CSV) | | [Done] | 30 accounts, 50 posts, 5 claims, 1 narrative, 8 media URLs. 4-wave campaign. |
| P4 | Pre-install key packages locally to avoid wifi issues | | [Done] | All packages installed and verified: neo4j 6.1.0, fastapi 0.133.1, streamlit 1.54.0, requests 2.32.5, numpy 2.4.2, scikit-learn 1.8.0, httpx 0.28.1, uvicorn 0.41.0 |

---

## Phase 1: Foundation (11:00 AM - 12:00 PM)

**Goal:** Skeleton app running. Neo4j loaded. All APIs returning responses.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 1.1 | Project scaffold: FastAPI app, folder structure, `.env` loading | | [Done] | 11:15 | `app/`, `scripts/`, `data/`, `main.py` FastAPI entry point |
| 1.2 | Neo4j schema + seed data loader | | [Done] | 11:30 | 30 accounts, 57 posts, 5 claims, 1 narrative, 55 MENTIONS edges, 39 PART_OF_CAMPAIGN, 198 FOLLOWS, 26 MENTIONS_USER |
| 1.3 | Yutori API smoke test | | [Done] | 11:30 | OK: browse task created, returns task_id + view_url |
| 1.4 | Modulate API smoke test | | [Blocked] | 11:30 | No REST API -- C/C++ SDK only. ToxMod has platform APIs but not direct deepfake detection. Will check with sponsor at event. |
| 1.5 | Reka API smoke test | | [Done] | 11:30 | OK: reka-flash model responds to text and image/video prompts |
| 1.6 | Fastino API smoke test | | [Blocked] | 11:30 | 404 on /personalization/ingest. Docs are MCP-based, not REST. Will check with sponsor at event. |
| 1.7 | Tavily API smoke test (backup) | | [Done] | 11:30 | OK: search returns results with answers |
| 1.8 | Basic Streamlit shell with placeholder sections | | [Done] | 12:00 | Full dashboard: graph viz, cluster details, claim verification, media analysis sections |

**Checkpoint @ 12:00:** All APIs confirmed working or fallbacks identified. Neo4j loaded with seed data. Streamlit shows something.

---

## Phase 2: Core Detection Pipeline (12:00 PM - 1:30 PM)

**Goal:** Text-based coordination detection works end-to-end.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 2.1 | Text similarity engine | | [Done] | 12:30 | SimilarityAgent: TF-IDF cosine, threshold=0.30, writes SIMILAR_TO edges. 73+ pairs found. |
| 2.2 | Cluster detection in Neo4j | | [Done] | 1:00 | ClusterAgent: BFS connected components on SIMILAR_TO graph. 3 clusters detected. |
| 2.3 | Coordination scoring heuristics | | [Done] | 1:15 | ScoringAgent: 7 signals, fixed datetime parsing. Top cluster scores 75/100 (was 42). |
| 2.4 | Wire Neo4j results to Streamlit | | [Done] | 1:30 | Dashboard shows agents, graph viz, cluster details. 6 agents orchestrated in pipeline. |

**Checkpoint @ 1:30:** Can click a button, see Neo4j find a suspicious cluster, display it as a graph with a suspicion score.

---

## Phase 3: Multimodal + Verification (1:30 PM - 3:00 PM)

**Goal:** Modulate, Reka, Yutori, and Fastino integrated into the pipeline.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 3.1 | Modulate integration: deepfake detection on video posts | | [Blocked] | 2:00 | No REST API (C/C++ SDK only). Skipped per panic protocols -- 5 other tools working. |
| 3.2 | Reka integration: video analysis on video posts | | [Done] | 2:00 | MediaAgent analyzes 8/8 media posts via Reka chat. Stores reka_analysis on Post nodes. |
| 3.3 | Yutori verification: dispatch Scout on flagged claims | | [Done] | 2:30 | BrowsingAgent dispatches to Snopes for top debunked/unverified claim. Returns task_id + view_url. |
| 3.4 | Campaign memory: store + recall | | [Done] | 2:30 | MemoryAgent: TF-IDF keyword fingerprints + entity patterns stored as CampaignFingerprint nodes in Neo4j. Second run finds 9 matches across clusters. |
| 3.5 | Wire all results into Streamlit dashboard | | [Done] | 3:00 | EntityAgent (Pioneer), MemoryAgent, all sections wired. 8 agents, 5 sponsor tools, full observability. |

**Checkpoint @ 3:00:** Full pipeline works. Click button -> text analysis -> media analysis -> verification -> memory -> dashboard shows everything.

---

## Phase 4: Polish & Demo Prep (3:00 PM - 4:00 PM)

**Goal:** Demo-ready. No new features. Only fix and polish.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 4.1 | Happy-path demo walkthrough (run it 3x) | | [ ] | 3:15 | If it breaks, fix it. If it's slow, cache it. |
| 4.2 | UI cleanup: labels, colors, layout | | [ ] | 3:30 | Make the graph viz pop. Red = suspicious, green = verified. |
| 4.3 | Error handling for flaky APIs | | [ ] | 3:30 | If any API times out, show "unavailable" gracefully, don't crash. |
| 4.4 | Write demo script (what to say, what to click) | | [ ] | 3:45 | See "Demo Script" below. Practice once. |
| 4.5 | Record backup demo video (screen capture) | | [ ] | 4:00 | In case live demo fails. OBS or loom. |

**Checkpoint @ 4:00:** Demo runs clean. Backup video recorded. Script written.

---

## Phase 5: Submission (4:00 PM - 4:30 PM)

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 5.1 | Push final code to GitHub | | [ ] | 4:10 | Clean up any secrets from code. Check `.gitignore`. |
| 5.2 | Write README.md (project description, setup, screenshots) | | [ ] | 4:20 | Keep it short. 1 paragraph + architecture diagram + screenshot. |
| 5.3 | Submit to Devpost | | [ ] | 4:25 | Link GitHub repo. List all sponsor tools used. |
| 5.4 | Final demo rehearsal | | [ ] | 4:30 | One more run-through while waiting. |

---

## Decision Points (Decide Fast, Don't Debate)

| Time | Decision | If YES | If NO |
|------|----------|--------|-------|
| 11:30 | Does Yutori work? | Use for verification | Switch to Tavily |
| 11:30 | Does Modulate work? | Integrate deepfake detection | Skip audio track, text + video only |
| 1:30 | Is text clustering working? | Proceed to Phase 3 | Drop media track, focus on making text pipeline solid |
| 3:00 | Is the full pipeline working? | Polish the UI | Cut features. Ship what works. |
| 3:30 | Is the demo clean? | Practice the script | Record backup video immediately |

---

## Demo Script (3 Minutes)

**[0:00 - 0:30] Problem Statement**
"Coordinated disinformation campaigns flood social media with identical narratives from fake accounts. Current detection is manual and slow. We built an autonomous agent that detects these campaigns in seconds."

**[0:30 - 1:00] Show the Graph**
Open Streamlit. Show the Neo4j graph -- posts, accounts, connections. "Here's what social media data looks like as a graph."

**[1:00 - 2:00] Run Detection**
Click "Analyze." Walk through results as they appear:
- "23 accounts created within 12 hours, posting 94% identical text -- flagged as coordinated."
- "Modulate detected deepfake voice in this video post -- score 0.91."
- "Reka found manipulated statistics in this on-screen graphic."
- "Yutori Scout checked PolitiFact -- this claim was debunked last week."

**[2:00 - 2:30] Show Memory**
"Fastino stored this campaign's fingerprint. If similar phrasing appears next week, the system instantly recognizes it." Show the retrieval.

**[2:30 - 3:00] Wrap Up**
"Five sponsor tools, zero human intervention, detects coordinated disinfo across platforms in seconds. This is DisInfo Detector."

---

## Panic Protocols

| Scenario | Action |
|----------|--------|
| An API is completely down | Remove it from the pipeline. 4 tools still qualifies (need 3+). |
| Neo4j won't connect | Use in-memory Python dicts + networkx. Ugly but works. |
| Streamlit is too slow | Switch to plain HTML served by FastAPI. |
| Nothing works at 2:00 PM | Pivot to ScamShield (single video analysis, simpler pipeline). |
| WiFi is bad | Hotspot from phone. Pre-download all pip packages. |
