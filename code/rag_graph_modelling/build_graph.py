"""
Node / edge generation.

Reads normalized per-entity CSVs (see preprocessing.py) and assembles
the graph as two JSON artifacts:

  graph_nodes.json -> {"nodes": {node_id: {"label": ..., "attributes": {...}}}}
  graph_edges.json -> [{"start": id, "type": REL_TYPE, "end": id}, ...]

graph_nodes.json follows the same shape already consumed by
code/get_similar_embedding.py (node_data["nodes"][node_id]["label"/"attributes"]),
so downstream embedding and fallback-retrieval code needs no changes.
"""

import json
import pandas as pd

from ontology_mapping import NODE_SCHEMA, RELATIONSHIPS


def build_nodes(entity_tables: dict) -> dict:
    """
    entity_tables: {"CVE": <DataFrame>, "CWE": <DataFrame>, ...}
    Returns {"nodes": {node_id: {"label": label, "attributes": {...}}}}
    """
    nodes = {}
    for label, df in entity_tables.items():
        schema = NODE_SCHEMA.get(label)
        if schema is None:
            print(f"⚠️  Unknown label '{label}', skipping node generation.")
            continue

        id_field = schema["id_field"]
        for _, row in df.iterrows():
            node_id = row[id_field]
            if not isinstance(node_id, str) or not node_id.strip():
                continue
            nodes[node_id] = {
                "label": label,
                "attributes": {k: row.get(k) for k in schema["attributes"] if k in df.columns},
            }

    print(f"✅ Built {len(nodes)} nodes across {len(entity_tables)} labels")
    return {"nodes": nodes}


def build_edges(entity_tables: dict, join_hints: dict) -> list:
    """
    join_hints: for each (start_label, rel_type, end_label) triple in
    RELATIONSHIPS, a column name in the start table holding a
    reference (single ID or comma-separated IDs) to the end node.

    Example:
        join_hints = {
            ("CVE", "HAS_CWE", "CWE"): "related_cwe",
        }
    """
    edges = []
    for start_label, rel_type, end_label in RELATIONSHIPS:
        col = join_hints.get((start_label, rel_type, end_label))
        if not col or start_label not in entity_tables:
            continue

        df = entity_tables[start_label]
        start_id_field = NODE_SCHEMA[start_label]["id_field"]
        if col not in df.columns:
            continue

        for _, row in df.iterrows():
            start_id = row[start_id_field]
            refs = row[col]
            if pd.isna(refs):
                continue
            for end_id in str(refs).split(","):
                end_id = end_id.strip()
                if not end_id:
                    continue
                edges.append({"start": start_id, "type": rel_type, "end": end_id})

    print(f"✅ Built {len(edges)} edges across {len(join_hints)} relationship types")
    return edges


def save(nodes: dict, edges: list, nodes_path: str = "graph_nodes.json", edges_path: str = "graph_edges.json") -> None:
    with open(nodes_path, "w") as f:
        json.dump(nodes, f, indent=2)
    with open(edges_path, "w") as f:
        json.dump(edges, f, indent=2)
    print(f"💾 Saved nodes -> {nodes_path}, edges -> {edges_path}")


if __name__ == "__main__":
    entity_tables = {
        "CVE": pd.read_csv("normalized/cve.csv"),
        "CWE": pd.read_csv("normalized/cwe.csv"),
        "CAPEC": pd.read_csv("normalized/capec.csv"),
        "Technique": pd.read_csv("normalized/technique.csv"),
    }

    join_hints = {
        ("CVE", "HAS_CWE", "CWE"): "related_cwe",
        ("CWE", "HAS_CAPEC", "CAPEC"): "related_capec",
        ("CAPEC", "HAS_TECHNIQUE", "Technique"): "related_technique",
    }

    nodes = build_nodes(entity_tables)
    edges = build_edges(entity_tables, join_hints)
    save(nodes, edges)
