# Explainability Analysis

Turns a GRICS run into readable explainability examples — for a given
question: the generated Cypher, the reasoning path it traces through the
graph, the retrieved evidence, and the final answer.

## Pipeline

1. Run questions through `code/base_llm.py` or
   `code/fine_tuned_model/inference.py`, then execute the generated
   Cypher via `code/get_result_neo4j.py`, producing a result CSV with
   `Question`, `Generated_Cypher_List`, `Cypher_Results`, `Answer`
   columns (the same shape already used in `code/evaluation/`). If your
   pipeline has an answer-synthesis step, `Answer` can hold the narrative
   text it produced instead of just the raw evidence list.

2. **`build_examples.py`** — reads that CSV and produces `examples.json`:
   one record per question with the Cypher, an extracted reasoning path
   (the node labels touched by the Cypher `MATCH` clause), retrieved
   evidence, and the answer.

3. **`metrics.py`** — computes Hallucination Rate, Query Violation Rate,
   and Schema Consistency Rate over `examples.json`. Hallucination Rate
   checks that every ID mentioned in the answer (parsed out of narrative
   text if needed) actually appears in the retrieved evidence. Schema
   checks reuse the node labels defined in
   `../rag_graph_modelling/ontology_mapping.py`, so metric and graph
   definitions can't drift apart.

4. **`render_report.py`** — turns `examples.json` into a readable
   Markdown report (`examples_report.md`), one section per question.

## Examples

`examples/sample_examples.json` holds two examples taken from a real
GRICS run: a multi-hop Group → Malware → Technique lookup, and a
CVE → CWE → CAPEC → Technique → Mitigation lookup with several candidate
Cypher queries. Each shows the full answer format — a structured ID list
plus the LLM-synthesized summary paragraph.
