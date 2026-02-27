// Neo4j Schema for Disinfo Detector
// Run after provisioning AuraDB instance (task P1)
// Data population happens via: python -m app.seed

// --- Constraints (uniqueness) ---
CREATE CONSTRAINT post_id IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT narrative_id IF NOT EXISTS FOR (n:Narrative) REQUIRE n.id IS UNIQUE;

// --- Node types ---
// Post: {id, text, platform, timestamp, media_url, media_type, post_type, reka_analysis, gliner_entities, gliner_classification}
// Account: {id, username, platform, created_at, follower_count, is_bot}
// Claim: {id, text, category, verification_status, verification_source}
// Narrative: {id, label, description, suspicion_score}

// --- Edge types ---
// (Post)-[:POSTED_BY]->(Account)              — who authored this post
// (Post)-[:SIMILAR_TO {score: float}]->(Post) — text similarity (computed by detector)
// (Post)-[:MENTIONS]->(Claim)                 — post references a factual claim
// (Post)-[:MENTIONS_USER]->(Account)          — post @mentions another account
// (Post)-[:PART_OF_CAMPAIGN]->(Narrative)     — post belongs to a detected campaign
// (Account)-[:FOLLOWS {since: datetime}]->(Account)  — social follow/subscribe
// (Claim)-[:PART_OF_NARRATIVE]->(Narrative)   — claim is part of a narrative
