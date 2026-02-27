"""Convert synthetic_posts.json into GLiNER-2 fine-tuning JSONL format.

Output format (per line):
{
  "input": "post text",
  "output": {
    "entities": {
      "organization": ["CDC", "EPA"],
      "location": ["Cedar Valley"],
      ...
    },
    "classifications": [{
      "task": "post_type",
      "labels": ["coordinated_campaign", "authentic_content", "debunking_response"],
      "true_label": ["coordinated_campaign"]
    }, {
      "task": "manipulation_intent",
      "labels": ["fabricated_claim", "emotional_manipulation", "authority_impersonation",
                  "urgency_tactics", "conspiracy_framing", "media_criticism", "none"],
      "true_label": ["fabricated_claim"]
    }]
  }
}

Usage:
    python scripts/prepare_training_data.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_FILE = DATA_DIR / "synthetic_posts.json"
OUTPUT_FILE = DATA_DIR / "gliner_training.jsonl"

# --- Classification mappings ---

POST_TYPE_MAP = {
    "coordinated": "coordinated_campaign",
    "organic": "authentic_content",
    "echo": "debunking_response",
}

POST_TYPE_LABELS = list(POST_TYPE_MAP.values())

MANIPULATION_LABELS = [
    "fabricated_claim",
    "emotional_manipulation",
    "authority_impersonation",
    "urgency_tactics",
    "conspiracy_framing",
    "media_criticism",
    "none",
]

# --- Entity extraction labels ---
# We manually annotate entities based on known ground truth in the synthetic data.

ENTITY_RULES = {
    # Organizations / agencies
    "CDC": "government_agency",
    "EPA": "government_agency",
    "Scouting America": "organization",
    "Pentagon": "government_agency",
    # Locations
    "Cedar Valley": "location",
    "Cupertino": "location",
    "California": "location",
    "San Francisco": "location",
    "Springfield": "location",
    # Substances
    "industrial chemicals": "chemical",
    # Facilities
    "Cedar Valley water treatment facility": "facility",
    "Cedar Valley water treatment plant": "facility",
    "Cedar Valley water plant": "facility",
    # Media / platforms
    "Snopes": "media_outlet",
    "PolitiFact": "media_outlet",
    # Health
    "chemical exposure": "health_condition",
    "water contamination": "health_issue",
}

# Longer phrases first so they match before substrings
SORTED_ENTITIES = sorted(ENTITY_RULES.keys(), key=len, reverse=True)


def extract_entities_from_text(text: str) -> dict[str, list[str]]:
    """Simple rule-based entity extraction using known ground truth."""
    found: dict[str, list[str]] = {}
    text_lower = text.lower()
    seen = set()

    for phrase in SORTED_ENTITIES:
        if phrase.lower() in text_lower and phrase not in seen:
            label = ENTITY_RULES[phrase]
            found.setdefault(label, []).append(phrase)
            seen.add(phrase)

    return found


def determine_manipulation_intent(post: dict) -> list[str]:
    """Determine manipulation intent labels from post content and type."""
    text = post["text"].lower()
    post_type = post["post_type"]
    intents = []

    if post_type == "organic":
        return ["none"]
    if post_type == "echo":
        return ["none"]

    # Coordinated posts — classify manipulation tactics
    if any(w in text for w in ["exposed", "leaked", "reveals", "report shows", "report confirms"]):
        intents.append("fabricated_claim")
    if any(w in text for w in ["overwhelmed", "flooding hospitals", "poisoned", "sick", "crisis"]):
        intents.append("emotional_manipulation")
    if any(w in text for w in ["cdc insider", "whistleblower", "leaked phone call", "confesses"]):
        intents.append("authority_impersonation")
    if any(w in text for w in ["share before", "before they delete", "before they censor",
                                "before it gets taken down", "go viral", "spread the word"]):
        intents.append("urgency_tactics")
    if any(w in text for w in ["deliberate", "lab rats", "testing on", "population testing",
                                "tuskegee", "on purpose"]):
        intents.append("conspiracy_framing")
    if any(w in text for w in ["media blackout", "mainstream media", "media silence",
                                "msm complicit", "media is silent"]):
        intents.append("media_criticism")

    return intents if intents else ["fabricated_claim"]


def convert_post(post: dict) -> dict:
    """Convert a single post to GLiNER-2 training format."""
    text = post["text"]
    post_type = post["post_type"]

    # Entities
    entities = extract_entities_from_text(text)

    # Classifications
    classifications = [
        {
            "task": "post_type",
            "labels": POST_TYPE_LABELS,
            "true_label": [POST_TYPE_MAP[post_type]],
        },
        {
            "task": "manipulation_intent",
            "labels": MANIPULATION_LABELS,
            "true_label": determine_manipulation_intent(post),
            "multi_label": True,
        },
    ]

    return {
        "input": text,
        "output": {
            "entities": entities,
            "classifications": classifications,
        },
    }


def main():
    with open(INPUT_FILE) as f:
        data = json.load(f)

    posts = data["posts"]
    training_examples = [convert_post(p) for p in posts]

    with open(OUTPUT_FILE, "w") as f:
        for example in training_examples:
            f.write(json.dumps(example) + "\n")

    # Stats
    types = {}
    for p in posts:
        types[p["post_type"]] = types.get(p["post_type"], 0) + 1

    entity_counts = {}
    for ex in training_examples:
        for label, ents in ex["output"]["entities"].items():
            entity_counts[label] = entity_counts.get(label, 0) + len(ents)

    print(f"Wrote {len(training_examples)} training examples to {OUTPUT_FILE}")
    print(f"\nPost type distribution:")
    for pt, count in sorted(types.items()):
        print(f"  {pt}: {count} -> {POST_TYPE_MAP[pt]}")
    print(f"\nEntity counts across all examples:")
    for label, count in sorted(entity_counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")
    print(f"\nSample (first coordinated post):")
    for ex in training_examples:
        if ex["output"]["classifications"][0]["true_label"] == ["coordinated_campaign"]:
            print(json.dumps(ex, indent=2)[:500])
            break


if __name__ == "__main__":
    main()
