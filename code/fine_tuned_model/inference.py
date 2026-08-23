"""
Inference wrapper for the fine-tuned Cypher LLM.

Loads the base model (Azzedde/llama3.1-8b-text2cypher) plus the LoRA
adapter produced by llm_fine_tune.py (see config/lora_config.json for
the training config, adapters/ for where checkpoints live) and generates
Cypher from natural-language questions.

Mirrors the prompt structure in code/base_llm.py so that base-model vs
fine-tuned outputs are directly comparable (see ../explainability_analysis).
"""

import re
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

CONFIG_PATH = "config/lora_config.json"


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def load_model(adapter_dir: str, base_model: str):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16 if torch.cuda.is_available() else None,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    model = PeftModel.from_pretrained(base, adapter_dir)
    model.eval()
    return model, tokenizer, device


def extract_cypher_blocks(text: str) -> list:
    """Same extraction logic as code/base_llm.py, kept in sync manually."""
    matches = re.findall(r"###\s*Cypher:(.*?)(?=###|$)", text, flags=re.IGNORECASE | re.DOTALL)
    return [re.sub(r"\n{2,}", "\n", m.strip()) for m in matches if m.strip()]


def generate_cypher(model, tokenizer, device, schema: str, question: str, instruction: str = "") -> list:
    prompt = f"""{instruction}

### Schema:
{schema}

### Question:
{question}

### Cypher:
"""
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096).to(device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            do_sample=False,
            num_beams=1,
            max_new_tokens=512,
            early_stopping=True,
            use_cache=True,
        )
    decoded = tokenizer.decode(output[0], skip_special_tokens=True)
    return extract_cypher_blocks(decoded)


if __name__ == "__main__":
    config = load_config()
    model, tokenizer, device = load_model(config["output_dir"], config["base_model"])

    schema = "(:CVE {cve_id, description}) (:CWE {cwe_id, description}) (:CVE)-[:HAS_CWE]->(:CWE)"
    question = "What is the CWE of CVE-2021-44228?"

    cypher_queries = generate_cypher(model, tokenizer, device, schema, question)
    print(f"Question: {question}")
    for q in cypher_queries:
        print(f"Generated Cypher:\n{q}\n")
