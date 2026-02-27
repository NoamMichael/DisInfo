# Disinfo Detector

Autonomous agent system that detects **coordinated disinformation campaigns** across social media (X, Reddit, YouTube). Built for the [Autonomous Agents Hackathon](https://autonomous-agents-hackathon.devpost.com/) at AWS Builder Loft, Feb 27 2026.

Instead of fact-checking individual claims, it identifies the *patterns* of coordinated inauthentic behavior: high-velocity posting, identical phrasing across accounts, newly-created accounts pushing a single narrative, and AI-generated media.

## Architecture

### Two-Layer Pipeline: Source → Detect

The system has two layers. **Layer 1** uses sponsor tools to source real social media content from the live web. **Layer 2** feeds that content into the autonomous detection pipeline.

#### Layer 1: Real-Time Data Sourcing

We use **Tavily** and **Yutori** to ingest real posts from X, YouTube, and news outlets — zero synthetic data.

| Step | Tool | What Happens |
|------|------|-------------|
| **Search** | **Tavily** | Runs dozens of targeted web searches (`site:x.com`, news topics) to discover real X/Twitter posts, news articles, and YouTube videos about the topic under investigation. Each query returns up to 10 results with post text, URL, and metadata. |
| **Browse** | **Yutori** | Deploys autonomous browsing agents to navigate X.com search pages and YouTube directly. Yutori's Navigator agent scrolls through results, extracts post text, handles, timestamps, and media URLs from the live DOM — content that search APIs can't reach. |
| **Deduplicate** | Script | Raw results from both tools are deduplicated by URL and text hash. Unique posts are converted into dataset entries (accounts + posts) and written to `data/realtime_data.json`. |
| **Seed** | **Neo4j** | The dataset is loaded into a Neo4j graph: `Account`, `Post`, `Claim`, and `Narrative` nodes with `POSTED_BY`, `MENTIONS`, `FOLLOWS`, and other relationship edges. |

The sourcing script (`scripts/fetch_x_posts.py`) runs Tavily and Yutori in parallel, deduplicates against the existing dataset, and appends only truly new posts — so it can be run repeatedly to grow the dataset.

#### Layer 2: Autonomous Detection

Nine autonomous agents orchestrate the detection pipeline:

```
  ┌──────────────┐    ┌──────────────┐
  │   Tavily     │    │   Yutori     │
  │  Web Search  │    │  Web Browse  │
  │  (X, news)   │    │  (X, YT)    │
  └──────┬───────┘    └──────┬───────┘
         └────────┬──────────┘
                  ▼
         ┌────────────────┐
         │  Dedup + Build │──► data/realtime_data.json
         └────────┬───────┘
                  ▼
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
    MediaAgent     VerificationAgent  EntityAgent
    (Reka Vision   (Tavily web        (Pioneer/GLiNER-2
     analysis)      search)            NER + text
                                       classification)
                          │
                          ▼
                   BrowsingAgent
                   (Yutori Scout
                    fact-check
                    browsing)
                          │
                          ▼
                    MemoryAgent
                    (Campaign
                     fingerprinting
                     + recall)
                          │
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
| **EntityAgent** | Extracts named entities (orgs, people, locations, chemicals) and classifies posts (disinformation, conspiracy, news, opinion) using GLiNER-2. | Pioneer |
| **BrowsingAgent** | Dispatches a browsing agent to fact-check sites (Snopes, PolitiFact) for deep claim verification. | Yutori |
| **MemoryAgent** | Builds campaign fingerprints (keywords, timing, platform spread) and stores them in Neo4j for cross-session recall. | Neo4j |

### Pipeline Flow

1. **Agents 1-4** run sequentially: similarity → clustering → account trust → scoring (Neo4j)
2. **Agents 5-7** run in parallel: media analysis (Reka) + claim verification (Tavily) + entity extraction (Pioneer)
3. **Agent 8** runs: deep verification (Yutori) on the top flagged claim
4. **Agent 9** runs: campaign fingerprinting and recall (Neo4j)

## Sponsor Tools Used (5)

Every sponsor tool serves **dual roles** — sourcing data *and* analyzing it:

| Tool | Data Sourcing Role | Detection Role |
|------|-------------------|---------------|
| **Tavily** | Searches the live web for real X posts, news articles, and YouTube videos about the topic under investigation. Dozens of parallel queries with `site:x.com` filters to maximize unique posts. | Fact-checks extracted claims against news sources. Classifies as debunked/confirmed/unverified. |
| **Yutori** | Deploys autonomous browsing agents to navigate X.com and YouTube, extracting post text, handles, timestamps, and media URLs from the live DOM. | Deep-verifies flagged claims by browsing fact-check sites (Snopes, PolitiFact, Reuters). |
| **Neo4j** | Stores the full social graph — accounts, posts, claims, narratives as nodes with relationship edges (`POSTED_BY`, `SIMILAR_TO`, `FOLLOWS`, `MENTIONS`). | Powers similarity detection, cluster analysis, account trust scoring, and campaign fingerprint recall via Cypher queries. |
| **Reka** | — | Analyzes video/audio posts for sensationalism, manipulation tactics, and disinformation red flags. |
| **Pioneer (Fastino)** | — | GLiNER-2 entity extraction (orgs, people, locations) and text classification (disinformation, conspiracy, news, opinion). |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
```

## Source Data & Seed the Database

```bash
# 1. Build base dataset (hand-verified real posts)
python -m scripts.build_real_dataset

# 2. Fetch 100+ more real posts via Tavily + Yutori
python -m scripts.fetch_x_posts

# 3. Load into Neo4j
python -m app.seed
```

The dataset (`data/realtime_data.json`) contains **100% real content** sourced from live platforms:
- **244 accounts** (all real — zero synthetic)
- **265 posts** across X, YouTube, and web (all organic)
- **4 claims** with keyword-based linking
- **1 narrative** tracking the story arc
- **9 media posts** (video + images)
- **47 FOLLOWS edges**

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
| POST | `/pipeline` | Run full 7-agent pipeline |
| GET | `/logs` | Pipeline event log (filter by `?stage=` or `?kind=`) |
| GET | `/logs/summary` | Observability summary: timings, API calls, errors |

## Dataset: Real-World Case Study

The dataset tracks real coverage of the **Pentagon / Scouting America policy change** story (Feb 27, 2026) — Pete Hegseth's announcement that Scouting America would end DEI initiatives and adopt biological sex requirements to maintain Pentagon support.

Sources:
- **X/Twitter** — 228 real posts from journalists, officials, commentators, and public reaction (sourced via Tavily search + Yutori browsing)
- **YouTube** — 5 real news videos from USA TODAY, NewsNation, ABC7, CBS News (sourced via Yutori)
- **Web articles** — 32 real news articles from CNN, AP, WaPo, NPR, Military.com, etc. (sourced via Tavily)

The pipeline analyzes this real-world content to detect coordination patterns, verify claims, extract entities, and flag potential disinformation — all without any synthetic data.

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
  agents/              # 9 autonomous agents
    base.py            # Agent base class with observability
    similarity_agent.py
    cluster_agent.py
    account_trust_agent.py
    scoring_agent.py
    media_agent.py
    verification_agent.py
    entity_agent.py
    browsing_agent.py
    memory_agent.py
  api/                 # Sponsor API clients
    tavily_client.py   # Tavily web search (sourcing + verification)
    yutori_client.py   # Yutori browsing agent (sourcing + deep verify)
    reka_client.py     # Reka vision (media analysis)
    fastino_client.py  # Pioneer/GLiNER-2 (entity extraction)
  config.py            # .env loading
  neo4j_client.py      # Neo4j driver wrapper
  observe.py           # Pipeline observability
  pipeline.py          # Agent orchestration
  detector.py          # Backward-compat wrapper
  seed.py              # Neo4j data loader
data/
  realtime_data.json       # 244 accounts, 265 posts (100% real)
  sourced_x_posts.json     # Raw Tavily/Yutori fetch results
scripts/
  fetch_x_posts.py         # Live data sourcing (Tavily + Yutori)
  build_real_dataset.py    # Base dataset from hand-verified posts
  source_realtime_urls.py  # URL sourcing utility
  neo4j_schema.cypher      # Graph schema
  smoke_test_apis.py       # API smoke tests
dashboard.py           # Streamlit frontend
main.py                # FastAPI backend
```
