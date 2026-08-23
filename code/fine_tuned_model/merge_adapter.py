"""
Merges a trained LoRA adapter into the base model weights, producing a
single standalone checkpoint for deployment (no PEFT dependency needed
at serving time).
"""

import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

CONFIG_PATH = "config/lora_config.json"


def merge(adapter_dir: str, base_model: str, output_dir: str) -> None:
    print(f"Loading base model {base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16 if torch.cuda.is_available() else None,
    )

    print(f"Loading adapter from {adapter_dir}...")
    model = PeftModel.from_pretrained(base, adapter_dir)

    print("Merging adapter into base weights...")
    merged = model.merge_and_unload()

    merged.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Saved merged model to {output_dir}")


if __name__ == "__main__":
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    merge(
        adapter_dir=config["output_dir"],
        base_model=config["base_model"],
        output_dir=f"{config['output_dir']}-merged",
    )
