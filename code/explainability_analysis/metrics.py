"""
Explainability metrics

  - Hallucination Rate (HR)     — fraction of examples whose answer mentions
                                   an ID not present in the retrieved evidence
  - Query Violation Rate (QVR)  — fraction of generated Cypher violating basic syntax rules
  - Schema Consistency Rate (SCR) — fraction of generated Cypher using only known node labels

Operates on the examples list produced by build_examples.py.
"""

import os
import re
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag_graph_modelling"))
from ontology_mapping import NODE_SCHEMA  # noqa: E402

KNOWN_LABELS = set(NODE_SCHEMA.keys())

ID_PATTERN = re.compile(
    r"\bCVE-\d{4}-\d+\b|\bCWE-\d+\b|\bCAPEC-\d+\b|\bT\d{4}(?:\.\d{3})?\b|\bM\d{4}\b|\b[0-9a-f]{8,}\b",
    re.IGNORECASE,
)


def is_syntactically_valid(cypher: str) -> bool:
    """Same starting-clause rule enforced in code/base_llm.py's generation prompt."""
    if not isinstance(cypher, str) or not cypher.strip():
        return False
    starts_ok = bool(re.match(r"^\s*(MATCH|OPTIONAL MATCH|WITH|CALL)\b", cypher.strip(), re.IGNORECASE))
    has_return = "RETURN" in cypher.upper()
    return starts_ok and has_return


def uses_known_schema(cypher: str) -> bool:
    """Check only node labels, e.g. (n:CVE) — not relationship types like [:HAS_CWE]."""
    labels = re.findall(r"\([a-zA-Z0-9_]*:([A-Z][A-Za-z]+)", cypher)
    return all(label in KNOWN_LABELS for label in labels) if labels else True


def extract_mentioned_ids(answer) -> set:
    """IDs referenced in the final answer, whether it's a narrative string or a raw list."""
    if isinstance(answer, str):
        return {m.upper() for m in ID_PATTERN.findall(answer)}
    if isinstance(answer, list):
        return {str(a).upper() for a in answer}
    return set()


def hallucination_rate(examples: list) -> float:
    """
    Flags an example when the answer mentions an ID that isn't grounded
    in the retrieved evidence. IDs already present in the question
    (the subject being asked about, e.g. the CVE in "mitigations for
    CVE-X") are excluded — restating the subject isn't a hallucination.
    """
    flagged = 0
    for ex in examples:
        mentioned = extract_mentioned_ids(ex["answer"])
        allowed = {str(e).upper() for e in ex["retrieved_evidence"]}
        allowed |= extract_mentioned_ids(ex.get("question", ""))
        if mentioned and not mentioned.issubset(allowed):
            flagged += 1
    return flagged / len(examples) if examples else 0.0


def query_violation_rate(examples: list) -> float:
    violations, total = 0, 0
    for ex in examples:
        for cypher in ex["generated_cypher"]:
            total += 1
            if not is_syntactically_valid(cypher):
                violations += 1
    return violations / total if total else 0.0


def schema_consistency_rate(examples: list) -> float:
    consistent, total = 0, 0
    for ex in examples:
        for cypher in ex["generated_cypher"]:
            total += 1
            if uses_known_schema(cypher):
                consistent += 1
    return consistent / total if total else 0.0


def summarize(examples_path: str = "examples.json") -> dict:
    with open(examples_path) as f:
        examples = json.load(f)

    return {
        "hallucination_rate": hallucination_rate(examples),
        "query_violation_rate": query_violation_rate(examples),
        "schema_consistency_rate": schema_consistency_rate(examples),
    }


if __name__ == "__main__":
    for metric, value in summarize().items():
        print(f"{metric}: {value:.4f}")
