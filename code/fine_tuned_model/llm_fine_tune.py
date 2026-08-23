import os
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import torch
from transformers import (
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding,
)
from datasets import load_dataset

# PEFT imports
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# Optional: Unsloth-specific loader (if you prefer & it's installed)
try:
    from unsloth import FastLanguageModel
    UNSLOTH_AVAILABLE = True
except Exception:
    UNSLOTH_AVAILABLE = False

# Optional fallback (standard HF AutoModelForCausalLM)
from transformers import AutoModelForCausalLM

# -----------------------------
# Config - edit as needed
# -----------------------------
BASE_MODEL = "Azzedde/llama3.1-8b-text2cypher"     # your base
TRAIN_FILE = "finetune_data.json"                 # JSON array of {"instruction","output"}
OUTPUT_DIR = "cypher-llama3.1-finetuned"          # where adapter + checkpoints go
MAX_LENGTH = 2048
MICRO_BATCH_SIZE = 1      # per device
GRAD_ACCUM_STEPS = 8
EPOCHS = 3
LEARNING_RATE = 2e-4
WEIGHT_DECAY = 0.0
SAVE_TOTAL_LIMIT = 3
LOGGING_STEPS = 25
SAVE_STEPS = 200
SEED = 42
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# A short system instruction you may want prepended to every prompt (optional)
SYSTEM_PROMPT = ""  # leave empty if you don't want a system prompt

# The prompt template: instruction only (user asked)
def build_prompt(instruction: str) -> str:
    # We will append the target (output) after the prompt, and mask the prompt tokens.
    # The model was previously trained with the "### Cypher:" pattern, but your dataset
    # uses instruction->output only. Use whatever you trained on. Here we use simply:
    return f"{instruction}\n\n### Cypher:\n"

# -----------------------------
# Helpers: prepare dataset
# -----------------------------
def load_json_train_dataset(train_path: str):
    # expecting a JSON file with top-level list of {"instruction": "...", "output": "..."}
    return load_dataset("json", data_files=train_path, field=None)

def tokenize_and_build_examples(examples, tokenizer):
    # examples is a dict of lists from datasets map()
    input_ids_list = []
    attention_mask_list = []
    labels_list = []

    instructions = examples["instruction"]
    outputs = examples["output"]

    for inst, out in zip(instructions, outputs):
        prompt = (SYSTEM_PROMPT + "\n" if SYSTEM_PROMPT else "") + build_prompt(inst)
        full = prompt + out

        # Tokenize with truncation/padding later by DataCollator; but to compute label masking
        tokenized_full = tokenizer(full, truncation=True, max_length=MAX_LENGTH, padding=False)
        tokenized_prompt = tokenizer(prompt, truncation=True, max_length=MAX_LENGTH, padding=False)

        input_ids = tokenized_full["input_ids"]
        attention_mask = tokenized_full["attention_mask"]

        # labels: copy input_ids, but mask prompt part (set to -100)
        labels = input_ids.copy()
        prompt_len = len(tokenized_prompt["input_ids"])
        for i in range(prompt_len):
            if i < len(labels):
                labels[i] = -100

        input_ids_list.append(input_ids)
        attention_mask_list.append(attention_mask)
        labels_list.append(labels)

    return {
        "input_ids": input_ids_list,
        "attention_mask": attention_mask_list,
        "labels": labels_list,
    }

# -----------------------------
# Main
# -----------------------------
def main():
    torch.manual_seed(SEED)

    if not os.path.exists(TRAIN_FILE):
        raise FileNotFoundError(f"Training file not found: {TRAIN_FILE}")

    # Load tokenizer
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
    # Ensure tokenizer has pad token
    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({"pad_token": "[PAD]"})

    # Load dataset
    print("Loading dataset...")
    ds = load_json_train_dataset(TRAIN_FILE)["train"]

    # Preprocess dataset to tokenized inputs/labels
    print("Tokenizing and preparing labels (this may take a while)...")
    tokenized = ds.map(
        lambda x: tokenize_and_build_examples(x, tokenizer),
        batched=True,
        remove_columns=ds.column_names,
    )

    # -------------------------
    # Load model
    # -------------------------
    print("Loading base model (may be quantized) ...")
    model = None
    if UNSLOTH_AVAILABLE:
        try:
            # Attempt to load with FastLanguageModel (unsloth). Adjust args if needed.
            model, _ = FastLanguageModel.from_pretrained(
                BASE_MODEL,
                load_in_4bit=True,     # use 4-bit if desired and supported
                dtype=torch.float16,
            )
            print("Loaded model via Unsloth FastLanguageModel.")
        except Exception as e:
            print("Unsloth load failed:", e)
            model = None

    if model is None:
        # Fallback: standard transformers AutoModelForCausalLM
        print("Falling back to AutoModelForCausalLM.from_pretrained (may be large).")
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            load_in_4bit=True if hasattr(torch, "cuda") and torch.cuda.is_available() else False,
            torch_dtype=torch.float16 if torch.cuda.is_available() else None,
            device_map="auto" if torch.cuda.is_available() else None,
        )

    # Prepare model for k-bit training (if quantized)
    try:
        model = prepare_model_for_kbit_training(model)
    except Exception:
        # prepare_model_for_kbit_training may fail or be unnecessary; ignore safely
        pass

    # -------------------------
    # Attach LoRA (PEFT)
    # -------------------------
    print("Attaching LoRA adapter via PEFT...")
    lora_config = LoraConfig(
        r=8,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"] if "llama" in BASE_MODEL.lower() else None,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # -------------------------
    # Data collator (pad on batch)
    # -------------------------
    data_collator = DataCollatorWithPadding(tokenizer, padding=True, return_tensors="pt")

    # -------------------------
    # TrainingArguments & Trainer
    # -------------------------
    total_batch = MICRO_BATCH_SIZE * (torch.cuda.device_count() if torch.cuda.is_available() else 1) * GRAD_ACCUM_STEPS
    print(f"Effective batch size = {total_batch}")

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=MICRO_BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        num_train_epochs=EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=torch.cuda.is_available(),
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        save_total_limit=SAVE_TOTAL_LIMIT,
        remove_unused_columns=False,   # IMPORTANT to avoid earlier error
        report_to="none",
        dataloader_pin_memory=True,
        run_name="cypher-finetune",
        weight_decay=WEIGHT_DECAY,
        optim="adamw_torch",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=data_collator,
    )

    # -------------------------
    # Train
    # -------------------------
    print("Starting training...")
    trainer.train()
    print("Training completed — saving adapter + model...")

    # Save the PEFT adapter and optionally full model (adapter is small)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Saved fine-tuned adapter and tokenizer to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
