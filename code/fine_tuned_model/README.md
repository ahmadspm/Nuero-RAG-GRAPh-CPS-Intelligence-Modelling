# Fine-Tuned Model

Everything related to the fine-tuned Cypher LLM (base: `Azzedde/llama3.1-8b-text2cypher`,
adapted with LoRA to better handle paraphrased and IT/OT-specific questions).

## Contents

| Path | Role |
|---|---|
| `llm_fine_tune.py` | Training script: base model + PEFT/LoRA, saves adapter to `adapters/` |
| `config/lora_config.json` | LoRA + training hyperparameters, mirrored from `llm_fine_tune.py` so `inference.py` / `merge_adapter.py` can reuse them without re-reading the training script |
| `adapters/` | Where trained LoRA adapter checkpoints live (not committed — see `adapters/README.md`) |
| `inference.py` | Loads base model + adapter, generates Cypher for a question (same prompt structure as `code/base_llm.py`, for direct comparison) |
| `merge_adapter.py` | Merges the LoRA adapter into the base weights for a standalone deployment checkpoint |

## Workflow

1. Train: `python llm_fine_tune.py` (edit `BASE_MODEL`/`TRAIN_FILE`/`OUTPUT_DIR` at the top, or point `OUTPUT_DIR` at `adapters/`).
2. Serve: `python inference.py` — loads the adapter from `config/lora_config.json`'s `output_dir` and generates Cypher for a question.
3. (Optional) Deploy: `python merge_adapter.py` to bake the adapter into the base weights.

Outputs from either the base model (`code/base_llm.py`) or this fine-tuned
model feed into `code/get_result_neo4j*.py` for execution against Neo4j,
and can be compared side-by-side in `../explainability_analysis/`.
