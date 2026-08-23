"""
Embedding preparation for the fallback retrieval mechanism.

Encodes every node in graph_nodes.json with MiniLM-L6-v2 and saves the
embedding matrix alongside the node list, in the exact layout expected
by code/get_similar_embedding.py:

  node_text_embeddings_minilm.npy  -> float32 array, shape (num_nodes, dim)
  graph_nodes_updated.json         -> {"nodes": {node_id: {label, attributes}}}
                                       (row order matches the embedding matrix)
"""

import json
import numpy as np
from sentence_transformers import SentenceTransformer

from ontology_mapping import node_text

MODEL_NAME = "all-MiniLM-L6-v2"


def prepare_embeddings(nodes_path: str = "graph_nodes.json",
                        embeddings_out: str = "node_text_embeddings_minilm.npy",
                        nodes_out: str = "graph_nodes_updated.json") -> None:
    with open(nodes_path) as f:
        graph = json.load(f)
    nodes = graph["nodes"]

    print(f"🧠 Loading {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    node_ids = list(nodes.keys())
    texts = [node_text(nodes[nid]["label"], nid, nodes[nid]["attributes"]) for nid in node_ids]

    print(f"🔍 Encoding {len(texts)} nodes...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    np.save(embeddings_out, embeddings.astype(np.float32))
    with open(nodes_out, "w") as f:
        json.dump({"nodes": nodes}, f, indent=2)

    print(f"💾 Saved embeddings -> {embeddings_out} (shape {embeddings.shape})")
    print(f"💾 Saved node metadata -> {nodes_out}")


if __name__ == "__main__":
    prepare_embeddings()
