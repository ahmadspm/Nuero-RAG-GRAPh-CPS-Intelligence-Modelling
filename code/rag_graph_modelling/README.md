# RAG Graph Modelling

Scripts for building the BRIDG-ICS-shaped knowledge graph that the rest of
GRICS retrieves against. This is the missing "how do you get from raw
CVE/CWE/CAPEC/ATT&CK data to the Neo4j graph" step — everything else in
`code/` (`get_result_neo4j.py`, `get_similar_embedding.py`, ...) assumes
that graph already exists.

If you're using the pre-built BRIDG-ICS graph from
[the original repo](https://github.com/ahmadspm/Industry-5.0--Intelligent-Threat-Analytics-KGs-and-LLMs),
you don't need this pipeline. Use it when constructing a new graph, extending
the schema, or re-embedding nodes after the graph changes.

## Pipeline order

1. **`preprocessing.py`** — cleans and normalises raw source tables (CVE,
   CWE, CAPEC, Technique, ...): consistent `PREFIX-NNN` IDs, whitespace
   collapsing, deduplication. Writes tidy CSVs to `normalized/`.

2. **`ontology_mapping.py`** — the schema itself: node labels with their
   identifying/display attributes (`NODE_SCHEMA`), and the 18 relationship
   triples that define the graph shape (`RELATIONSHIPS`). This mirrors
   `dataset/generate_benchmark.py`'s relationship list so benchmark
   question generation and the graph stay in sync. Import from here rather
   than redefining labels/relationships elsewhere.

3. **`build_graph.py`** — node/edge generation. Reads the normalized CSVs
   and produces `graph_nodes.json` / `graph_edges.json`. `graph_nodes.json`
   uses the same `{"nodes": {id: {"label", "attributes"}}}` shape already
   consumed by `code/get_similar_embedding.py`, so no downstream changes
   are needed.

4. **`load_to_neo4j.py`** — graph construction. Loads the nodes/edges JSON
   into Neo4j with batched `UNWIND` + `MERGE` Cypher. Run
   `schema/bridg_ics_schema.cypher` once first to create uniqueness
   constraints and indexes.

5. **`embedding_preparation.py`** — encodes every node with
   `all-MiniLM-L6-v2` and saves `node_text_embeddings_minilm.npy` +
   `graph_nodes_updated.json`, in the exact layout
   `code/get_similar_embedding.py` expects for the embedding-fallback
   retrieval path.

## File descriptions

| File | Role |
|---|---|
| `preprocessing.py` | Raw source data → normalised per-entity CSVs |
| `ontology_mapping.py` | Node schema + relationship triples (shared by every other file here) |
| `build_graph.py` | Normalised CSVs → `graph_nodes.json` / `graph_edges.json` |
| `load_to_neo4j.py` | `graph_*.json` → live Neo4j graph |
| `embedding_preparation.py` | `graph_nodes.json` → MiniLM node embeddings for fallback retrieval |
| `schema/bridg_ics_schema.cypher` | Constraints, indexes, and example multi-hop Cypher queries |

## Notes

- `ontology_mapping.py` is the single source of truth for labels and
  relationship types — if the ontology changes, update it there and every
  other script (and `dataset/generate_benchmark.py`) picks it up.
- `build_graph.py`'s `join_hints` need to point at whatever column in your
  raw data holds the foreign-key reference for each relationship triple;
  adjust them to match your actual source tables before running.
- Update the `URI`/`AUTH` placeholders in `load_to_neo4j.py` before running,
  same convention as `get_result_neo4j.py` and `get_result_neo4j_embedding.py`.
