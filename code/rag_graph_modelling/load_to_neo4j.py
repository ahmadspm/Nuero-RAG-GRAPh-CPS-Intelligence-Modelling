"""
Graph construction script: loads graph_nodes.json / graph_edges.json
(produced by build_graph.py) into a running Neo4j instance.

Uses UNWIND + MERGE batches for reasonable performance on graphs with
tens of thousands of nodes/edges. Run schema/bridg_ics_schema.cypher
once beforehand to create uniqueness constraints and indexes.
"""

import json
from neo4j import GraphDatabase

from ontology_mapping import id_field_for

# ==============================================
# Neo4j connection
# ==============================================
URI = "bolt://localhost:7687"
AUTH = ("", "")  # adjust this part
BATCH_SIZE = 500


def load_nodes(driver, nodes: dict) -> None:
    by_label = {}
    for node_id, data in nodes.items():
        by_label.setdefault(data["label"], []).append({"id": node_id, **data["attributes"]})

    with driver.session() as session:
        for label, rows in by_label.items():
            id_field = id_field_for(label)
            query = f"""
            UNWIND $rows AS row
            MERGE (n:{label} {{{id_field}: row.id}})
            SET n += row
            """
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                session.run(query, rows=batch)
            print(f"✅ Loaded {len(rows)} :{label} nodes")


def load_edges(driver, edges: list, nodes: dict) -> None:
    by_type = {}
    for edge in edges:
        by_type.setdefault(edge["type"], []).append(edge)

    with driver.session() as session:
        for rel_type, rows in by_type.items():
            skipped = 0
            valid_rows = []
            for row in rows:
                start_label = nodes.get(row["start"], {}).get("label")
                end_label = nodes.get(row["end"], {}).get("label")
                if not start_label or not end_label:
                    skipped += 1
                    continue
                valid_rows.append({
                    "start_id": row["start"],
                    "end_id": row["end"],
                    "start_field": id_field_for(start_label),
                    "end_field": id_field_for(end_label),
                    "start_label": start_label,
                    "end_label": end_label,
                })

            for (start_label, start_field, end_label, end_field), group in _group_by_labels(valid_rows):
                query = f"""
                UNWIND $rows AS row
                MATCH (a:{start_label} {{{start_field}: row.start_id}})
                MATCH (b:{end_label} {{{end_field}: row.end_id}})
                MERGE (a)-[:{rel_type}]->(b)
                """
                for i in range(0, len(group), BATCH_SIZE):
                    batch = group[i:i + BATCH_SIZE]
                    session.run(query, rows=batch)

            print(f"✅ Loaded {len(valid_rows)} :{rel_type} edges ({skipped} skipped, missing endpoint)")


def _group_by_labels(rows):
    """Group edge rows by (start_label, start_field, end_label, end_field)."""
    groups = {}
    for row in rows:
        key = (row["start_label"], row["start_field"], row["end_label"], row["end_field"])
        groups.setdefault(key, []).append(row)
    return groups.items()


if __name__ == "__main__":
    with open("graph_nodes.json") as f:
        nodes = json.load(f)["nodes"]
    with open("graph_edges.json") as f:
        edges = json.load(f)

    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        load_nodes(driver, nodes)
        load_edges(driver, edges, nodes)
    finally:
        driver.close()

    print("\n🎉 Graph construction complete.")
