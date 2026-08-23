"""
Ontology-to-Neo4j mapping for the BRIDG-ICS schema.

This module is the single source of truth for node labels, expected
attributes, and relationship types used across the rag_graph_modelling
pipeline (preprocessing -> build_graph -> load_to_neo4j -> embeddings).
Keep it in sync with the BRIDG-ICS ontology:
https://github.com/ahmadspm/Industry-5.0--Intelligent-Threat-Analytics-KGs-and-LLMs
"""

# ==============================================
# Node labels and their identifying / display attributes
# ==============================================
NODE_SCHEMA = {
    "CVE": {"id_field": "cve_id", "attributes": ["description", "cvss_score", "published_date"]},
    "CWE": {"id_field": "cwe_id", "attributes": ["name", "description"]},
    "CWEDetection": {"id_field": "detection_id", "attributes": ["method", "description"]},
    "CWEConsequence": {"id_field": "consequence_id", "attributes": ["scope", "impact"]},
    "CWEMitigation": {"id_field": "mitigation_id", "attributes": ["phase", "description"]},
    "CWEModeOfIntroduction": {"id_field": "mode_id", "attributes": ["phase", "note"]},
    "CAPEC": {"id_field": "capec_id", "attributes": ["name", "description", "severity"]},
    "CAPECConsequence": {"id_field": "consequence_id", "attributes": ["scope", "impact"]},
    "Technique": {"id_field": "technique_id", "attributes": ["name", "description", "tactic"]},
    "Attack": {"id_field": "attack_id", "attributes": ["name", "description"]},
    "Group": {"id_field": "group_id", "attributes": ["name", "aliases"]},
    "Tactic": {"id_field": "tactic_id", "attributes": ["name", "description"]},
    "Malware": {"id_field": "malware_id", "attributes": ["name", "description"]},
    "Campaign": {"id_field": "campaign_id", "attributes": ["name", "description"]},
    "Mitigation": {"id_field": "mitigation_id", "attributes": ["name", "description"]},
    "Asset": {"id_field": "asset_id", "attributes": ["name", "asset_type", "layer"]},
    "Product": {"id_field": "product_id", "attributes": ["name", "vendor"]},
    "Target": {"id_field": "target_id", "attributes": ["name", "target_type"]},
}

# ==============================================
# Relationship triples: (start_label, relationship_type, end_label)
# Mirrors dataset/generate_benchmark.py RELATIONSHIPS so benchmark
# question generation and graph construction stay consistent.
# ==============================================
RELATIONSHIPS = [
    ("CVE", "HAS_CWE", "CWE"),
    ("CVE", "TARGETS", "Target"),
    ("CWE", "HAS_DETECTION", "CWEDetection"),
    ("CWE", "HAS_CONSEQUENCE", "CWEConsequence"),
    ("CWE", "HAS_CWE_MITIGATION", "CWEMitigation"),
    ("CWE", "HAS_MODE_OF_INTRODUCTION", "CWEModeOfIntroduction"),
    ("CWE", "HAS_CAPEC", "CAPEC"),
    ("CAPEC", "HAS_CAPEC_CONSEQUENCE", "CAPECConsequence"),
    ("CAPEC", "HAS_TECHNIQUE", "Technique"),
    ("CAPEC", "HAS_ATTACK", "Attack"),
    ("Group", "BELONG_TO", "Tactic"),
    ("Group", "USE_MALWARE", "Malware"),
    ("Group", "HAS_CAMPAIGN", "Campaign"),
    ("Group", "USE_TECHNIQUE", "Technique"),
    ("Malware", "USE_TECHNIQUE", "Technique"),
    ("Mitigation", "MITIGATES", "Technique"),
    ("Technique", "ATTACK", "Asset"),
    ("Product", "HAS_VULNERABILITY", "CVE"),
]


def id_field_for(label: str) -> str:
    """Return the identifying property name for a given node label."""
    if label not in NODE_SCHEMA:
        raise KeyError(f"Unknown node label: {label}")
    return NODE_SCHEMA[label]["id_field"]


def relationships_from(label: str):
    """List relationship triples where `label` is the start node."""
    return [r for r in RELATIONSHIPS if r[0] == label]


def relationships_to(label: str):
    """List relationship triples where `label` is the end node."""
    return [r for r in RELATIONSHIPS if r[2] == label]


def node_text(label: str, node_id: str, attributes: dict) -> str:
    """
    Build a flat text representation of a node, used both for
    embedding preparation and for LLM-facing context.
    """
    parts = [f"{label} {node_id}"]
    for key in NODE_SCHEMA.get(label, {}).get("attributes", []):
        val = attributes.get(key)
        if val:
            parts.append(f"{key}: {val}")
    return " | ".join(parts)
