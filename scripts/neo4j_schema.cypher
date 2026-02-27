// Neo4j Schema for Disinfo Detector
// Run after provisioning AuraDB instance (task P1)
// Data population happens in task 1.2

// --- Constraints (uniqueness) ---
CREATE CONSTRAINT post_id IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT narrative_id IF NOT EXISTS FOR (n:Narrative) REQUIRE n.id IS UNIQUE;

// --- Node types ---
// Post: {id, text, platform, timestamp, url, media_url, media_type, deepfake_score, reka_flags}
// Account: {id, username, platform, created_at, follower_count}
// Claim: {id, text, extracted_from, verification_status, verification_source}
// Narrative: {id, label, description, suspicion_score}

// --- Edge types ---
// (Post)-[:POSTED_BY]->(Account)
// (Post)-[:SIMILAR_TO {score: float}]->(Post)
// (Post)-[:MENTIONS]->(Claim)
// (Post)-[:PART_OF_CAMPAIGN]->(Narrative)
// (Claim)-[:VERIFIED_BY {result: str, source: str}]->(Claim)  // self-ref for versioning
