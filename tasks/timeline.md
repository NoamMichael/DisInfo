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
| P3 | Prepare synthetic dataset (JSON/CSV) | | [In Progress] | ~50 posts, 5 accounts, 3-4 video URLs, timestamps |
| P4 | Decide team role assignments | | [ ] | See "Team Roles" below |
| P5 | Clone repo on all team laptops, confirm Python 3.10+ | | [ ] | |
| P6 | Pre-install key packages locally to avoid wifi issues | | [ ] | neo4j, fastapi, streamlit, requests, numpy |

---

## Phase 1: Foundation (11:00 AM - 12:00 PM)

**Goal:** Skeleton app running. Neo4j loaded. All APIs returning responses.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 1.1 | Project scaffold: FastAPI app, folder structure, `.env` loading | | [ ] | 11:15 | Keep it minimal: `app/`, `scripts/`, `data/` |
| 1.2 | Neo4j schema + seed data loader | | [ ] | 11:30 | Nodes: Post, Account, Claim, Narrative. Edges: POSTED_BY, SIMILAR_TO, MENTIONS. Load synthetic dataset. |
| 1.3 | Yutori API smoke test | | [ ] | 11:30 | Get a Scout to navigate to any URL and return content. If broken, switch to Tavily immediately. |
| 1.4 | Modulate API smoke test | | [ ] | 11:30 | Send a short audio clip, get deepfake score back. If broken, note it and move on. |
| 1.5 | Reka API smoke test | | [ ] | 11:30 | Send an image or video URL, get analysis back. |
| 1.6 | Fastino API smoke test | | [ ] | 11:30 | Register a user, store a memory, retrieve it. |
| 1.7 | Tavily API smoke test (backup) | | [ ] | 11:30 | Run a search query, confirm results come back. |
| 1.8 | Basic Streamlit shell with placeholder sections | | [ ] | 12:00 | Graph viz area, results table, status indicators. Ugly is fine. |

**Checkpoint @ 12:00:** All APIs confirmed working or fallbacks identified. Neo4j loaded with seed data. Streamlit shows something.

---

## Phase 2: Core Detection Pipeline (12:00 PM - 1:30 PM)

**Goal:** Text-based coordination detection works end-to-end.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 2.1 | Text similarity engine | | [ ] | 12:30 | Compute pairwise similarity on post text. TF-IDF or simple embedding cosine. Don't overthink -- even Jaccard works. |
| 2.2 | Cluster detection in Neo4j | | [ ] | 1:00 | Cypher query: find groups of posts with >90% similarity, posted within N hours, from different accounts. Write SIMILAR_TO edges. |
| 2.3 | Coordination scoring heuristics | | [ ] | 1:15 | Score each cluster: account age uniformity, text similarity %, velocity, cross-platform spread. Output a 0-100 suspicion score. |
| 2.4 | Wire Neo4j results to Streamlit | | [ ] | 1:30 | Graph visualization of the suspicious cluster. Color nodes by suspicion. Show score + breakdown. |

**Checkpoint @ 1:30:** Can click a button, see Neo4j find a suspicious cluster, display it as a graph with a suspicion score.

---

## Phase 3: Multimodal + Verification (1:30 PM - 3:00 PM)

**Goal:** Modulate, Reka, Yutori, and Fastino integrated into the pipeline.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 3.1 | Modulate integration: deepfake detection on video posts | | [ ] | 2:00 | For posts with audio/video URLs, extract audio, send to Modulate, store deepfake score on Post node. |
| 3.2 | Reka integration: video analysis on video posts | | [ ] | 2:00 | For posts with video URLs, send to Reka Vision. Get manipulation flags, extracted text. Store on Post node. |
| 3.3 | Yutori verification: dispatch Scout on flagged claims | | [ ] | 2:30 | Extract top claim from suspicious cluster. Send Yutori Scout to PolitiFact/Snopes/Reuters. Return verification result. |
| 3.4 | Fastino campaign memory: store + recall | | [ ] | 2:30 | On detection: store campaign fingerprint (key phrases, account patterns) in Fastino. On new scan: retrieve similar past campaigns. |
| 3.5 | Wire all results into Streamlit dashboard | | [ ] | 3:00 | Modulate deepfake badge, Reka visual flags, Yutori verification status, Fastino "seen before" indicator. |

**Checkpoint @ 3:00:** Full pipeline works. Click button -> text analysis -> media analysis -> verification -> memory -> dashboard shows everything.

---

## Phase 4: Polish & Demo Prep (3:00 PM - 4:00 PM)

**Goal:** Demo-ready. No new features. Only fix and polish.

| # | Task | Owner | Status | Deadline | Notes |
|---|------|-------|--------|----------|-------|
| 4.1 | Happy-path demo walkthrough (run it 3x) | ALL | [ ] | 3:15 | If it breaks, fix it. If it's slow, cache it. |
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
| 5.4 | Final demo rehearsal | ALL | [ ] | 4:30 | One more run-through while waiting. |

---

## Team Roles (Assign Before 11 AM)

| Role | Responsibilities | Suggested Skills |
|------|-----------------|------------------|
| **Graph Lead** | Neo4j schema, seed data, Cypher queries, clustering logic | Backend, databases |
| **Media Lead** | Modulate + Reka integrations, audio/video processing | API integration, media handling |
| **Verification Lead** | Yutori + Fastino + Tavily integrations, scoring heuristics | API integration, LLM prompting |
| **UI Lead** | Streamlit dashboard, graph visualization, demo script | Frontend, visualization |

Everyone helps everyone. These are primary owners, not silos.

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
