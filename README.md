# Disinfo Detector

Autonomous agent that detects **coordinated disinformation campaigns** across social media (X, Reddit, YouTube). Built for the [Autonomous Agents Hackathon](https://autonomous-agents-hackathon.devpost.com/) at AWS Builder Loft, Feb 27 2026.

Instead of fact-checking individual claims, it identifies the *patterns* of coordinated inauthentic behavior: high-velocity posting, identical phrasing across accounts, newly-created accounts pushing a single narrative, and AI-generated media.

## Design: Two-Layer Architecture

This system is the **detection layer**, not the ingestion layer. It assumes data has already been scraped and loaded into the graph.

**Layer 1 -- Data Ingestion (above us):** Yutori Scouts scrape X/Reddit/YouTube, pull posts, account metadata, follow graphs, and dump it all into Neo4j. At the hackathon we simulate this with a pre-seeded synthetic dataset. In production, Yutori would continuously feed new nodes and edges into the graph.

**Layer 2 -- Detection Engine (us):** We take whatever is in the graph and analyze it. Source-agnostic -- doesn't matter if data came from Yutori, a custom scraper, or an API. Our job is to find structural patterns (follow cliques, mention amplification, text similarity), score them, flag suspicious media for multimodal analysis, verify claims, and remember patterns.

This separation means Yutori serves **two roles**: ingestion (Scouts feeding the graph) and verification (Scouts checking fact-check sites against flagged claims). The detection engine itself works identically whether fed live data or a seeded dataset.

## Architecture

```
         +--- Neo4j Graph ---------------------------------+
         |  Nodes: Post, Account, Claim, Narrative         |
         |  Edges: POSTED_BY, SIMILAR_TO, MENTIONS,        |
         |         PART_OF_CAMPAIGN                         |
         +-----------------------+--------------------------+
                                 |
              +------------------+------------------+
              v                  v                  v
        Text Analysis      Reka Vision       Modulate Audio
        (clustering,       (video posts ->   (audio from
        similarity,        manipulated       video posts ->
        velocity)          imagery?)         deepfake voice?)
              |                  |                  |
              +------------------+------------------+
                                 |
                                 v
                    Coordination Scorer
                    (heuristic rules on graph patterns)
                                 |
                    +------------+------------+
                    |            |            |
                    v            v            v
              Yutori Scout   Fastino      Dashboard
              (verify        (store       (Streamlit)
              claims vs.     campaign     - graph viz
              authoritative  fingerprint  - suspicion scores
              sources)       for future   - media flags
                             recall)      - verification results
```

## Sponsor Tools Used

| Tool | Role |
|------|------|
| **Neo4j** | Graph database -- accounts, posts, claims as nodes. Cypher queries detect suspicious clusters. |
| **Yutori** | Scouts verify flagged claims by navigating to PolitiFact, Snopes, Reuters. |
| **Modulate** | Deepfake voice detection on audio/video within suspicious clusters. |
| **Reka** | Video analysis -- detect manipulated imagery, extract on-screen text. |
| **Fastino** | Campaign memory -- stores disinfo fingerprints, recalls similar past campaigns. |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
```

## Seed the Database

```bash
python -m app.seed
```

Loads the synthetic dataset (`data/synthetic_posts.json`) into Neo4j:
- **30 accounts** (20 bot + 10 organic)
- **50 posts** across X, Reddit, YouTube (coordinated + organic + echo)
- **5 claims** with keyword-based linking
- **1 narrative** with 4 escalation waves
- **8 media posts** (video + audio) for deepfake detection

## Run the Dashboard

```bash
streamlit run dashboard.py
```

## Synthetic Dataset

The dataset (`data/synthetic_posts.json`) simulates a coordinated campaign pushing false claims about "Cedar Valley water contamination":

1. **Wave 1 (14:00):** 17 bot accounts flood X/Reddit/YouTube with near-identical "leaked government report" claims
2. **Wave 2 (16:00):** Escalation -- fabricated hospital crisis
3. **Wave 3 (18:00):** Conspiracy -- fake CDC whistleblower, deepfake audio "leaked phone calls"
4. **Wave 4 (20:00):** Inoculation -- "media blackout" framing to preempt debunking

Organic posts and echo posts (real users reacting) provide contrast for detection.

## Detection Signals

- **Phrasing clusters:** Posts with >90% text similarity from different accounts
- **Account age anomaly:** Cluster of accounts all created within 24 hours
- **Cross-platform echo:** Same claim on 3+ platforms within hours
- **Velocity spike:** 0 to N posts in <1 hour with uniform phrasing
- **Media flags:** AI-generated voice (Modulate) or manipulated imagery (Reka)

Output is a **suspicion score**, not a verdict.
