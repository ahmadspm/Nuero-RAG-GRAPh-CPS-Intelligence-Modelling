"""
Turns a GRICS result CSV into readable explainability examples: one
record per question with the generated Cypher, the reasoning path
(node labels touched by the Cypher), retrieved evidence, and the final
answer.

Input: a result CSV with columns
    Question, Generated_Cypher_List, Cypher_Results, Answer
(the shape produced by code/get_result_neo4j.py /
code/get_result_neo4j_embedding.py after execution against Neo4j).
`Answer` may be either the raw evidence list or, if your pipeline has
an LLM answer-synthesis step, the narrative text it produced.

Output: a JSON list of examples (see examples/sample_examples.json for
the target shape).
"""

import ast
import json
import re
import pandas as pd


def _parse_list(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except Exception:
        return []


def extract_path_labels(cypher: str) -> list:
    """
    Pull the ordered chain of node labels referenced in a Cypher MATCH
    clause, e.g. (n:CVE) -> "CVE". Excludes relationship types like
    [:HAS_CWE], which use the same `:Name` syntax but in brackets.
    """
    if not isinstance(cypher, str):
        return []
    seen = []
    for label in re.findall(r"\([a-zA-Z0-9_]*:([A-Z][A-Za-z]+)", cypher):
        if not seen or seen[-1] != label:
            seen.append(label)
    return seen


def build_example(row: dict) -> dict:
    cypher = _parse_list(row.get("Generated_Cypher_List"))
    evidence = _parse_list(row.get("Cypher_Results"))
    answer = row.get("Answer")

    return {
        "question": row.get("Question"),
        "generated_cypher": cypher,
        "reasoning_path": extract_path_labels(cypher[0]) if cypher else [],
        "retrieved_evidence": evidence,
        "answer": answer if isinstance(answer, str) and answer.strip() else evidence,
    }


def build(results_csv: str, output_path: str = "examples.json") -> None:
    df = pd.read_csv(results_csv)

    examples = [build_example(row) for _, row in df.iterrows()]

    with open(output_path, "w") as f:
        json.dump(examples, f, indent=2)
    print(f"💾 Saved {len(examples)} examples -> {output_path}")


if __name__ == "__main__":
    build(results_csv="../evaluation/cti-rcm-fine-results.csv", output_path="examples.json")
