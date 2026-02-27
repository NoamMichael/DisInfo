"""EmotionAgent — Computes per-post emotional intensity / manipulation score (0-100).

Measures how emotionally charged or manipulative content is using text signals:
- Sentiment word ratio (positive/negative emotional vocabulary)
- CAPS ratio (shouting)
- Punctuation intensity (!!!, ???)
- Loaded/manipulative vocabulary (fear, outrage, conspiracy terms)
- Urgency markers (BREAKING, URGENT, SHARE THIS)
- Absolutist language (NEVER, ALWAYS, EVERYONE, NOBODY)

This is the Emotion axis — orthogonal to Suspicion (behavioral coordination)
and Trust (account credibility).
"""

import re
import math
from app.agents.base import Agent
from app.neo4j_client import run_query, run_write

# ── Lexicons ──────────────────────────────────────────────────────────

_FEAR_ANGER_WORDS = frozenset(
    "afraid alarmed anger angry attack awful ban banned catastrophe chaos "
    "collapsing conspiracy corrupt cover-up crisis critical danger dangerous "
    "deadly death destroy destroying destruction devastating disaster doom "
    "dread emergency epidemic evil exposed extremist fail failing fatal fear "
    "fired forced fraud frightening genocide harm harmful hate hateful "
    "hoax horrific horror hostile illegal infiltrate invasion kill killing "
    "lethal lies lied liar lying manipulation mass murder nightmare outrage "
    "outraged panic pedophile persecution poison poisoned propaganda purge "
    "radical regime riot sabotage scandal secret shame shocking sinister "
    "slaughter stolen suppress surveillance terror terrorism terrorize "
    "threat threatening toxic tragedy treachery treason tyranny unsafe "
    "uprising vandalism victim violence violent war warning weapon "
    "weaponized witch-hunt".split()
)

_URGENCY_PHRASES = [
    "breaking", "breaking news", "just in", "urgent", "developing",
    "share this", "spread the word", "wake up", "open your eyes",
    "they don't want you to know", "exposed", "leaked", "bombshell",
    "this is huge", "read this before", "going viral", "must watch",
    "must read", "happening now", "alert", "warning",
]

_ABSOLUTIST_WORDS = frozenset(
    "always never everyone nobody everything nothing everywhere nowhere "
    "all none every no-one totally completely absolutely entirely "
    "impossible certain definitely undeniable proven fact guaranteed "
    "worst best ultimate pure total".split()
)

_POSITIVE_EMOTIONAL = frozenset(
    "amazing awesome beautiful best brilliant celebrate celebration "
    "champion fantastic freedom glory glorious great greatest hero "
    "heroic incredible inspire inspiring magnificent outstanding "
    "patriot patriotic perfect powerful proud remarkable saved "
    "spectacular stunning success triumph victorious victory wonderful".split()
)

_NEGATIVE_EMOTIONAL = frozenset(
    "abysmal appalling despicable disgrace disgusting dreadful failure "
    "garbage gutter horrible idiotic incompetent inferior loser miserable "
    "pathetic pitiful repulsive revolting ridiculous rubbish shameful "
    "stupid terrible trash useless weak worthless wretched".split()
)


def _word_set(text: str) -> list[str]:
    """Lowercase words from text."""
    return re.findall(r"[a-z']+", text.lower())


def _caps_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are uppercase."""
    alpha = [c for c in text if c.isalpha()]
    if len(alpha) < 5:
        return 0.0
    return sum(1 for c in alpha if c.isupper()) / len(alpha)


def _punctuation_intensity(text: str) -> float:
    """Score based on exclamation and question mark density."""
    if len(text) < 5:
        return 0.0
    bangs = text.count("!")
    questions = text.count("?")
    # Repeated punctuation (!! or ??) is stronger signal
    repeated = len(re.findall(r"[!?]{2,}", text))
    raw = (bangs + questions) / len(text) * 50 + repeated * 0.15
    return min(1.0, raw)


def _loaded_vocab_score(words: list[str]) -> float:
    """Fraction of words that are fear/anger/outrage vocabulary."""
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _FEAR_ANGER_WORDS)
    # Sigmoid-ish: 2 hits in a 20-word text = moderate, 5+ = high
    ratio = hits / len(words)
    return min(1.0, ratio * 8.0)


def _urgency_score(text_lower: str) -> float:
    """Presence of urgency/viral markers."""
    hits = sum(1 for phrase in _URGENCY_PHRASES if phrase in text_lower)
    return min(1.0, hits * 0.35)


def _absolutism_score(words: list[str]) -> float:
    """Presence of absolutist / superlative language."""
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _ABSOLUTIST_WORDS)
    return min(1.0, hits * 0.25)


def _sentiment_extremity(words: list[str]) -> float:
    """How emotionally extreme the vocabulary is (positive OR negative)."""
    if not words:
        return 0.0
    pos = sum(1 for w in words if w in _POSITIVE_EMOTIONAL)
    neg = sum(1 for w in words if w in _NEGATIVE_EMOTIONAL)
    total = pos + neg
    ratio = total / len(words)
    return min(1.0, ratio * 10.0)


def compute_emotion_score(text: str) -> dict:
    """Compute emotion/manipulation intensity for a single text.

    Returns dict with overall score (0-100) and per-signal breakdown.
    """
    words = _word_set(text)
    text_lower = text.lower()

    caps = _caps_ratio(text)
    punctuation = _punctuation_intensity(text)
    loaded = _loaded_vocab_score(words)
    urgency = _urgency_score(text_lower)
    absolutism = _absolutism_score(words)
    sentiment = _sentiment_extremity(words)

    # Weighted combination (weights sum to 1.0)
    raw = (
        loaded * 0.30          # Fear/anger vocabulary is strongest signal
        + sentiment * 0.20     # Extreme positive/negative emotional words
        + urgency * 0.15       # Urgency/viral language
        + caps * 0.15          # ALL CAPS shouting
        + punctuation * 0.10   # !!! and ??? density
        + absolutism * 0.10    # NEVER, ALWAYS, EVERYONE
    )

    score = int(round(min(100, max(0, raw * 100))))

    return {
        "score": score,
        "breakdown": {
            "loaded_vocab": round(loaded, 3),
            "sentiment_extremity": round(sentiment, 3),
            "urgency": round(urgency, 3),
            "caps_ratio": round(caps, 3),
            "punctuation": round(punctuation, 3),
            "absolutism": round(absolutism, 3),
        },
    }


class EmotionAgent(Agent):
    name = "EmotionAgent"

    def execute(self, **kwargs):
        posts = run_query("""
            MATCH (p:Post)-[:POSTED_BY]->(a:Account)
            RETURN p.id AS id, p.text AS text, a.username AS username,
                   p.platform AS platform
        """)
        self.log(f"Scoring emotion/manipulation on {len(posts)} posts")

        results = {}
        for post in posts:
            em = compute_emotion_score(post["text"])

            # Write to Neo4j
            run_write(
                """
                MATCH (p:Post {id: $id})
                SET p.emotion_score = $score
                """,
                {"id": post["id"], "score": em["score"]},
            )

            results[post["id"]] = {
                "post_text": post["text"],
                "username": post["username"],
                "platform": post["platform"],
                "emotion_score": em["score"],
                "breakdown": em["breakdown"],
                "status": "analyzed",
            }

        # Log top emotional posts
        by_score = sorted(results.values(), key=lambda r: r["emotion_score"], reverse=True)
        for r in by_score[:5]:
            self.log(
                f"  emotion={r['emotion_score']:3d} @{r['username']}: "
                f"{r['post_text'][:60]}..."
            )

        return results

    def summary(self) -> str:
        if not self.result:
            return "no posts analyzed"
        scores = [r["emotion_score"] for r in self.result.values()]
        avg = sum(scores) / len(scores) if scores else 0
        high = len([s for s in scores if s >= 50])
        return f"{len(scores)} posts scored (avg emotion: {avg:.0f}, {high} high-emotion)"
