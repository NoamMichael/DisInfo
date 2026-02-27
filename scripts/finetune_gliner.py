"""Fine-tune GLiNER-2 on our synthetic disinformation dataset.

Prerequisites:
    pip install gliner2

Usage:
    python scripts/finetune_gliner.py

This fine-tunes the base GLiNER-2 model on our labeled synthetic data for:
  1. Entity extraction: location, chemical, facility, government_agency, etc.
  2. Post classification: coordinated_campaign vs authentic_content vs debunking_response
  3. Manipulation intent: fabricated_claim, emotional_manipulation, urgency_tactics, etc.

The fine-tuned model is saved to models/gliner2-disinfo/ and can be loaded
for inference in the pipeline.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "gliner2-disinfo"
TRAINING_FILE = DATA_DIR / "gliner_training.jsonl"


def main():
    # Verify training data exists
    if not TRAINING_FILE.exists():
        print("Training data not found. Run prepare_training_data.py first.")
        print(f"  Expected: {TRAINING_FILE}")
        return

    with open(TRAINING_FILE) as f:
        examples = [json.loads(line) for line in f]
    print(f"Loaded {len(examples)} training examples from {TRAINING_FILE}")

    # --- Load GLiNER-2 ---
    try:
        from gliner2 import GLiNER2
        from gliner2.training.trainer import GLiNER2Trainer, TrainingConfig
    except ImportError:
        print("\ngliner2 package not installed. Install with:")
        print("  pip install gliner2")
        print("\nAlternatively, you can use the training data with the GLiNER-2 API")
        print(f"Training data ready at: {TRAINING_FILE}")
        _show_sample(examples)
        return

    print("Loading pretrained GLiNER-2 base model...")
    model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")

    # --- Configure training ---
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    config = TrainingConfig(
        output_dir=str(MODEL_DIR),
        num_epochs=15,           # Small dataset, more epochs
        batch_size=4,            # Small batches for 57 examples
        encoder_lr=1e-5,         # Base model learning rate
        task_lr=5e-4,            # Task-specific head learning rate
        eval_strategy="epoch",
        save_best=True,
        early_stopping=True,
    )

    print(f"Training config:")
    print(f"  Output: {MODEL_DIR}")
    print(f"  Epochs: {config.num_epochs}")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Encoder LR: {config.encoder_lr}")
    print(f"  Task LR: {config.task_lr}")

    # --- Train ---
    print("\nStarting fine-tuning...")
    trainer = GLiNER2Trainer(model, config)
    trainer.train(train_data=str(TRAINING_FILE))

    print(f"\nFine-tuned model saved to: {MODEL_DIR}")
    print("Load it with: GLiNER2.from_pretrained(str(MODEL_DIR))")

    # --- Quick test ---
    print("\n--- Quick inference test ---")
    test_text = "BREAKING: Government report reveals Cedar Valley water contaminated with industrial chemicals since 2024"
    entities = model.predict_entities(test_text, [
        "location", "chemical", "facility", "government_agency",
    ])
    print(f"Input: {test_text}")
    print(f"Entities: {entities}")


def _show_sample(examples):
    """Show sample training data for manual review."""
    print(f"\n--- Sample training data ({len(examples)} examples) ---\n")

    type_counts = {"coordinated_campaign": 0, "authentic_content": 0, "debunking_response": 0}
    for ex in examples:
        label = ex["output"]["classifications"][0]["true_label"][0]
        type_counts[label] = type_counts.get(label, 0) + 1

    print("Classification distribution:")
    for label, count in type_counts.items():
        print(f"  {label}: {count}")

    print("\nFirst 3 examples:")
    for ex in examples[:3]:
        print(f"\n  Input: {ex['input'][:100]}...")
        print(f"  Entities: {ex['output']['entities']}")
        print(f"  Post type: {ex['output']['classifications'][0]['true_label']}")
        print(f"  Manipulation: {ex['output']['classifications'][1]['true_label']}")


if __name__ == "__main__":
    main()
