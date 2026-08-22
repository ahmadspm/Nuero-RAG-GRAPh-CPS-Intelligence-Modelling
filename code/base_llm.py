from unsloth import FastLanguageModel
from transformers import AutoTokenizer
import argparse
from pathlib import Path
import re
import pandas as pd
import unicodedata
import torch

# ==============================
# 1. Load model and tokenizer
# ==============================
tokenizer = AutoTokenizer.from_pretrained("Azzedde/llama3.1-8b-text2cypher")
model, _ = FastLanguageModel.from_pretrained("Azzedde/llama3.1-8b-text2cypher")

device = "cuda" if torch.cuda.is_available() else "cpu"

# ============================================================


def extract_all_cypher_blocks(text: str) -> list[str]:
    """
    Extract all Cypher query blocks that start with '### Cypher:'.
    Returns a list of cleaned query strings.
    """
    # Find all blocks that begin with '### Cypher:' until next '###' or end of text
    matches = re.findall(
        r"###\s*Cypher:(.*?)(?=###|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    queries = []
    for block in matches:
        # Clean and normalize whitespace
        cleaned = block.strip()
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        if cleaned:
            queries.append(cleaned)

    return queries


def clean_repeated_cypher(query_block: str) -> str:
    """
    Remove duplicate MATCH...RETURN sections inside a single block.
    Keeps OPTIONAL MATCH and overall query structure intact.
    """
    matches = re.findall(
        r"(MATCH .*?RETURN [^\n\r]*)",
        query_block,
        flags=re.IGNORECASE | re.DOTALL
    )

    unique = []
    seen = set()
    for m in matches:
        normalized = re.sub(r"\s+", " ", m.strip())
        if normalized.lower() not in seen:
            seen.add(normalized.lower())
            unique.append(normalized)
    return "\n---\n".join(unique)

def is_valid_cypher(text: str) -> bool:
    """Check if text looks like a valid Cypher query."""
    # Must start with a Cypher clause, not just contain 'match' somewhere
    return bool(re.match(r"^\s*(MATCH|OPTIONAL MATCH|WITH|CALL)\b", text.strip(), re.IGNORECASE))


# ==============================
# 2. Schema (example snippet)
# ==============================
schema = """
(:CVE {cve_id, attackComplexity, attackVector, baseScore, cvssVector,
       description, epss, exploitabilityScore, hasKEV, impactScore})
(:Product {product_id, name, type, vendor, model, domain, criticality, severity})
(:CWE {cwe_id, cwe_uri, title, description})
(:CWEDetection {detection_id, method, effectiveness, description})
(:CWEConsequence {consequence_id, impacts, note, scopes})
(:CWEMitigation {mitigation_id, name, description})
(:CWEModeOfIntroduction {introduction_id, phase, note})
(:CAPEC {capec_id, description, level})
(:CAPECConsequence {consequence_id, impact, scopes})
(:Attack {attackstep_id, attackStep, attackStepPhase, atackStepDescription, attackStepTechnique_list})
(:Technique {technique_id, name, description})
(:Tactic {tactic_id, name, description})
(:Mitigation {mitigation_id, name, description})
(:Campaign {campaign_id, name})
(:Asset {asset_id, name, description})
(:Malware {malware_id, name, description})
(:Zone {id, code, name, purpose})
(:Group {group_id, name, description})
(:Target {name})
(:CPE {id, name})
Relationships:
(:CVE)-[:HAS_CWE]->(:CWE)
(:CVE)-[:TARGETS]->(:Target)
(:CVE)-[:HAS_CPE]->(:CPE)
(:CVE)-[:SUGGESTED_TACTIC]->(:Tactic)
(:CWE)-[:HAS_DETECTION]->(:CWEDetection)
(:CWE)-[:HAS_CONSEQUENCE]->(:CWEConsequence)
(:CWE)-[:HAS_CWE_MITIGATION]->(:CWEMitigation)
(:CWE)-[:HAS_MODE_OF_INTRODUCTION]->(:CWEModeOfIntroduction)
(:CWE)-[:HAS_CAPEC]->(:CAPEC)
(:CAPEC)-[:HAS_CAPEC_CONSEQUENCE]->(:CAPECConsequence)
(:CAPEC)-[:HAS_TECHNIQUE]->(:Technique)
(:CAPEC)-[:HAS_ATTACK]->(:Attack)
(:Group)-[:BELONG_TO]->(:Tactic)
(:Group)-[:USE_MALWARE]->(:Malware)
(:Group)-[:HAS_CAMPAIGN]->(:CAMPAIGN)
(:Group)-[:USE_TECHNIQUE]->(:Technique)
(:Malware)-[:USE_TECHNIQUE]->(:Technique)
(:Mitigation)-[:MITIGATES]->(:Technique)
(:Technique)-[:ATTACK]->(:Asset)
(:Product)-[:ATTACKABLE]->(:Product)
(:Product)-[:LOCATED_IN]->(:Zone)
(:Product)-[:HAS_VULNERABILITY]->(:CVE)
(:CWE)-[:IS_CHILD_OF]->(:CWE)
(:CWE)-[:STARTS_WITH]->(:CWE)
(:CWE)-[:CAN_PRECEDE]->(:CWE)
(:CWE)-[:CAN_ALSO_BE]->(:CWE)
(:CWE)-[:IS_PEER_OF]->(:CWE)
"""


# ==============================
# 3. Instruction prompt
# ==============================
instruction = """
You are a Cypher query generation assistant.

Task:
Given a schema and a natural-language question, produce up to 3 valid Cypher queries.

Rules:

### 1. Relationship & Schema Rules
- Only use nodes and relationships defined in the schema.
- Follow the exact direction shown in the schema:
    (:A)-[:REL]->(:B) means A connects TO B.
    So: MATCH (a:A)-[:REL]->(b:B)
- NEVER reverse this direction unless the question explicitly asks for the "X of Y".
    Example:
      Schema: (:CVE)-[:HAS_CWE]->(:CWE)
      Question: "What is the CVE of CWE-200?"
       MATCH (cve:CVE)-[:HAS_CWE]->(cwe:CWE)
         WHERE toLower(cwe.cwe_id) CONTAINS toLower("cwe-200")
         RETURN cve


2. **Property & Text Matching**
   - Use `toLower(x) CONTAINS toLower("...")`.
   - Never use `=` for strings.
   - Match IDs (CVE-2021-44228, CWE-79) with CONTAINS.
   - If multiple keywords: join with `AND`.

3. Filtering rules
   - If the question explicitly mentions an ID (like CVE-2021-44228 or CWE-79), match it using:
       WHERE toLower(node.id_property) CONTAINS toLower("ID_value")
   - Only use `description` filters when the question mentions a description or descriptive text.
   - Do NOT use `description` filters for questions about IDs, names, or numeric properties.
   - If the question mention description, split long descriptions (>10 words) into maximum 4 short phrases joined by AND, using `toLower(node.description) CONTAINS toLower("...")`.
   - It is NEVER allowed to omit this WHERE clause.
   Example enforcing Rule 3 when there is description in question:
    Question: What is the CWE of the CVE with description "Linux kernel use-after-free"?
    Cypher:
    MATCH (cve:CVE)
    WHERE toLower(cve.description) CONTAINS toLower("linux kernel")
    AND toLower(cve.description) CONTAINS toLower("use-after-free")
    OPTIONAL MATCH (cve)-[:HAS_CWE]->(w:CWE)
    RETURN w

4. **MATCH Rules**
   - Never use property maps `{}`.
   - Always use plain MATCH and move filters to WHERE.
   - Example:
     MATCH (g:Group)
     WHERE toLower(g.name) CONTAINS toLower("lazarus")

5. **Return**
   - Return full nodes (e.g. RETURN cve, not cve.cve_id).
   - Use LIMIT if question specifies a number.

6. **Output**
   - Max 3 distinct queries, separated by "---".
   - Each query starts with one MATCH and ends with one RETURN.
   - After RETURN, the query should be ended.
   - Fallback if unclear:
     MATCH (n)
     WHERE any(prop IN keys(n)
               WHERE toLower(toString(n[prop])) CONTAINS toLower("keyword"))
     RETURN n
     LIMIT 5

"""

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate ontology-constrained Cypher queries for CSV questions."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV containing a Question column.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV for questions and generated Cypher queries.",
    )
    parser.add_argument(
        "--save-interval",
        type=int,
        default=15,
        help="Save progress after this many processed rows (default: 15).",
    )
    return parser.parse_args()


def generate_cypher(question: str) -> list[str]:
    cypher_prompt = f"""{instruction}

### Schema:
{schema}

### Question:
{question}

### Cypher:
"""

    inputs = tokenizer(
        cypher_prompt,
        return_tensors="pt",
        truncation=True,
        max_length=4096,
    ).to(device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            do_sample=False,
            num_beams=1,
            max_new_tokens=512,
            use_cache=True,
        )

    decoded = tokenizer.decode(output[0], skip_special_tokens=True)
    blocks = extract_all_cypher_blocks(decoded)
    return [
        clean_repeated_cypher(block)
        for block in blocks
        if isinstance(block, str) and block.strip()
    ]


def main():
    args = parse_args()
    if args.save_interval < 1:
        raise ValueError("--save-interval must be at least 1.")

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(input_path)
    if "Question" not in df.columns:
        raise ValueError("CSV must have a 'Question' column.")
    if "Generated_Cypher" not in df.columns:
        df["Generated_Cypher"] = ""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for position, (idx, row) in enumerate(df.iterrows(), start=1):
        question = row["Question"]
        if not isinstance(question, str) or not question.strip():
            df.at[idx, "Generated_Cypher"] = []
            print(f"Skipped {position}/{len(df)}: empty question")
        else:
            cypher_queries = generate_cypher(question.strip())
            df.at[idx, "Generated_Cypher"] = repr(cypher_queries)
            print(f"Processed {position}/{len(df)}")

        if position % args.save_interval == 0:
            df.to_csv(output_path, index=False)
            print(f"Progress saved to {output_path}")

    df.to_csv(output_path, index=False)
    print(f"Completed {len(df)} questions. Results saved to {output_path}")


if __name__ == "__main__":
    main()
