# Disinfo Detector

Autonomous agent system that detects **coordinated disinformation campaigns** across social media (X, Reddit, YouTube). Built for the [Autonomous Agents Hackathon](https://autonomous-agents-hackathon.devpost.com/) at AWS Builder Loft, Feb 27 2026.

Instead of fact-checking individual claims, it identifies the *patterns* of coordinated inauthentic behavior: high-velocity posting, identical phrasing across accounts, newly-created accounts pushing a single narrative, and AI-generated media.

## Architecture

Six autonomous agents orchestrate the full detection pipeline:

```
  ┌─────────────────────────────────────────────────────────────┐
  │                     Neo4j Graph                             │
  │  Nodes: Post, Account, Claim, Narrative                    │
  │  Edges: POSTED_BY, SIMILAR_TO, MENTIONS, FOLLOWS,          │
  │         PART_OF_CAMPAIGN, MENTIONS_USER                     │
  └───────────────────────┬─────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
  SimilarityAgent   ClusterAgent    ScoringAgent
  (TF-IDF cosine,   (BFS connected  (7-signal
   writes            components)     heuristic
   SIMILAR_TO                        scoring
   edges)                            0-100)
          │               │               │
          └───────────────┼───────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    MediaAgent     VerificationAgent  BrowsingAgent
    (Reka Vision   (Tavily web        (Yutori Scout
     analysis)      search)            fact-check
                                       browsing)
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                ┌─────────────────┐
                │   Dashboard     │
                │   (Streamlit)   │
                │   + Observ-     │
                │     ability     │
                └─────────────────┘
```

### Agent Descriptions

| Agent | What It Does | Sponsor Tool |
|-------|-------------|-------------|
| **SimilarityAgent** | Computes pairwise TF-IDF cosine similarity on post text. Writes `SIMILAR_TO` edges for pairs above threshold. | Neo4j |
| **ClusterAgent** | Finds connected components in the similarity graph via BFS. Groups related posts into clusters. | Neo4j |
| **ScoringAgent** | Scores each cluster on 7 coordination signals: text similarity, account age spread, posting velocity, cross-platform spread, cluster size, follower counts, media presence. Outputs 0-100 suspicion score. | Neo4j |
| **MediaAgent** | Analyzes video/audio posts for sensationalism, manipulation tactics, and disinformation red flags. | Reka |
| **VerificationAgent** | Fact-checks extracted claims via web search. Classifies as debunked/confirmed/unverified. | Tavily |
| **BrowsingAgent** | Dispatches a browsing agent to fact-check sites (Snopes, PolitiFact) for deep claim verification. | Yutori |

### Pipeline Flow

1. **Agents 1-3** run sequentially: similarity → clustering → scoring (Neo4j)
2. **Agents 4+5** run in parallel: media analysis (Reka) + claim verification (Tavily)
3. **Agent 6** runs last: deep verification (Yutori) on the top flagged claim

## Sponsor Tools Used

| Tool | Role | Status |
|------|------|--------|
| **Neo4j** | Graph database — accounts, posts, claims as nodes. Cypher queries detect suspicious clusters. | Working |
| **Reka** | Media content analysis — flags sensationalized/manipulated video and audio posts. | Working |
| **Tavily** | Web search — fact-checks extracted claims against news sources. | Working |
| **Yutori** | Browsing agent — navigates to Snopes/PolitiFact to deep-verify flagged claims. | Working |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
```

## Seed the Database

```bash
python -m app.seed
```

Loads the synthetic dataset (`data/synthetic_posts.json`) into Neo4j:
- **30 accounts** (20 bot + 10 organic)
- **57 posts** across X, Reddit, YouTube (coordinated + organic + echo)
- **5 claims** with keyword-based linking
- **1 narrative** with 4 escalation waves
- **8 media posts** (video + audio)
- **198 FOLLOWS edges** (bot follow cliques + camouflage follows)
- **26 MENTIONS_USER edges** (amplification patterns)

## Run

### Dashboard (primary)
```bash
streamlit run dashboard.py
```

### API Server
```bash
uvicorn main:app --reload --port 8000
```

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/graph/stats` | Neo4j node counts |
| POST | `/detect` | Run detection agents (1-3) only |
| POST | `/pipeline` | Run full 6-agent pipeline |
| GET | `/logs` | Pipeline event log (filter by `?stage=` or `?kind=`) |
| GET | `/logs/summary` | Observability summary: timings, API calls, errors |

## Synthetic Dataset

The dataset (`data/synthetic_posts.json`) simulates a coordinated campaign pushing false claims about "Cedar Valley water contamination":

1. **Wave 1 (14:00):** 17 bot accounts flood X/Reddit/YouTube with near-identical "leaked government report" claims
2. **Wave 2 (16:00):** Escalation — fabricated hospital crisis
3. **Wave 3 (18:00):** Conspiracy — fake CDC whistleblower, deepfake audio "leaked phone calls"
4. **Wave 4 (20:00):** Inoculation — "media blackout" framing to preempt debunking

Organic posts and echo posts (real users reacting) provide contrast for detection.

## Detection Signals

The ScoringAgent evaluates 7 heuristic signals per cluster:

| Signal | Max Points | What It Measures |
|--------|-----------|-----------------|
| Text similarity | 30 | Average pairwise TF-IDF cosine within cluster |
| Account age spread | 20 | All accounts created within 24-48h = suspicious |
| Posting velocity | 15 | Posts per hour within the cluster window |
| Cross-platform spread | 15 | Same narrative across X, Reddit, YouTube |
| Cluster size | 10 | Number of unique accounts in cluster |
| Low follower counts | 5 | New/low-follower accounts = bot signal |
| Media presence | 5 | Video/audio posts amplify suspicion |

Output is a **suspicion score (0-100)**, not a verdict.

## Observability

Built-in pipeline observability tracks:
- Per-agent stage timings
- Individual API call latency and status
- Error counts and details
- Full event log with timestamps

Visible in the Streamlit dashboard and via `/logs` and `/logs/summary` API endpoints.

## Project Structure

```
app/
  agents/           # 6 autonomous agents
    base.py         # Agent base class with observability
    similarity_agent.py
    cluster_agent.py
    scoring_agent.py
    media_agent.py
    verification_agent.py
    browsing_agent.py
  api/              # Sponsor API clients
    tavily_client.py
    reka_client.py
    yutori_client.py
    modulate_client.py
    fastino_client.py
  config.py         # .env loading
  neo4j_client.py   # Neo4j driver wrapper
  observe.py        # Pipeline observability
  pipeline.py       # Agent orchestration
  detector.py       # Backward-compat wrapper
  seed.py           # Neo4j data loader
data/
  synthetic_posts.json   # 30 accounts, 57 posts, 5 claims
scripts/
  neo4j_schema.cypher    # Graph schema
  smoke_test_apis.py     # API smoke tests
dashboard.py        # Streamlit frontend
main.py             # FastAPI backend
```
