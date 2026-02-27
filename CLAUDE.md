# AWS Autonomous Agents Hackathon

Prep repo for the **Autonomous Agents Hackathon** hosted at AWS Builder Loft (Feb 27, 2026).

This is a solo project.

Hackathon page: https://autonomous-agents-hackathon.devpost.com/

## Key Constraints

- 5.5 hours of coding (11AM - 4:30PM)
- Must use **3+ sponsor tools**
- New project only (GitHub submitted)
- Teams up to 4
- Judging: Autonomy / Idea / Technical Implementation / Tool Use / Presentation (20% each)

## Current State

- **Phase 1 (Foundation):** Done — scaffold, Neo4j seeded, APIs confirmed working.
- **Phase 2 (Core Detection):** Done — 7 autonomous agents built, detection pipeline scores 75/100 on main campaign cluster, observability wired in.

### Working Sponsor Tools (5)
- Neo4j (graph DB + detection)
- Reka (media analysis)
- Tavily (claim verification)
- Pioneer/Fastino (GLiNER-2 entity extraction + text classification)
- Yutori (deep browsing verification)

### Agent Architecture (7 agents)
- `SimilarityAgent` — TF-IDF cosine, writes SIMILAR_TO edges (Neo4j)
- `ClusterAgent` — BFS connected components (Neo4j)
- `ScoringAgent` — 7-signal heuristic scoring 0-100 (Neo4j)
- `MediaAgent` — media content analysis (Reka)
- `VerificationAgent` — claim fact-checking (Tavily)
- `EntityAgent` — NER + text classification (Pioneer/GLiNER-2)
- `BrowsingAgent` — deep fact-check browsing (Yutori)

## Workflow

- **At the start of every task:** Update `tasks/timeline.md` status to `[In Progress]`
- **At the end of every task:** Update `tasks/timeline.md` status to `[Done]` or `[Blocked]` with a brief note if blocked

## Commands

```bash
# Activate venv
source .venv/bin/activate

# Seed Neo4j
python -m app.seed

# Run dashboard
streamlit run dashboard.py

# Run API server
uvicorn main:app --reload --port 8000

# Run full pipeline (CLI)
python -m app.pipeline

# Smoke test APIs
python scripts/smoke_test_apis.py
```

## Where to Find Info

- `thoughts/idea.md` — Project concept: "Disinfo Detector" coordinated inauthentic behavior detection
- `tasks/timeline.md` — Hackathon day timeline, task tracker, team roles, panic protocols
- `thoughts/sponsors/` — One file per sponsor with API details, docs links, code examples, and how we'd use each tool:
  - `yutori.md` — Web agents & Scouts ($2,500 cash prize)
  - `modulate.md` — Voice AI: transcription, deepfake, emotion ($1,750 cash)
  - `fastino.md` — Personalization & user memory ($1,750 cash/gift cards)
  - `reka.md` — Vision: video/image understanding ($1,000 cash)
  - `tavily.md` — Real-time web search API (credits only)
  - `senso.md` — Knowledge base / Context OS (credits only)
  - `neo4j.md` — Graph database & GraphRAG (credits only)
