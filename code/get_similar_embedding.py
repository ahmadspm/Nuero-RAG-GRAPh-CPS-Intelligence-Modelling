import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


def parse_args():
    parser = argparse.ArgumentParser(
        description="Retrieve confidence-aware graph anchors for failed Cypher questions."
    )
    parser.add_argument("--input", default="incorrect_predictions-fine.csv")
    parser.add_argument("--output", default="fallback_incorrect-fine-2021.csv")
    parser.add_argument(
        "--embeddings",
        default="code_and_file_part1llm/node_text_embeddings_minilm.npy",
    )
    parser.add_argument(
        "--nodes",
        default="code_and_file_part1llm/graph_nodes_updated.json",
    )
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.50,
        help="Minimum top-1 cosine similarity required to accept an anchor.",
    )
    return parser.parse_args()


def find_similar_nodes(query, embeddings, nodes, node_info, model, top_k=5):
    """Return the top-k graph nodes ranked by cosine similarity."""
    if not isinstance(query, str) or not query.strip():
        return []

    query_vector = model.encode([query], show_progress_bar=False)[0].reshape(1, -1)
    similarities = cosine_similarity(query_vector, embeddings)[0]
    candidate_count = min(top_k, len(nodes))
    ranked_indices = np.argsort(similarities)[::-1][:candidate_count]

    candidates = []
    for index in ranked_indices:
        node_id = nodes[int(index)]
        info = node_info.get(node_id, {})
        attributes = info.get("attributes", {})
        description = attributes.get("description") or attributes.get("title", "")
        candidates.append(
            {
                "node_id": node_id,
                "label": info.get("label", "Unknown"),
                "score": round(float(similarities[index]), 6),
                "description": description[:300],
            }
        )
    return candidates


def main():
    args = parse_args()
    if args.top_k < 1:
        raise ValueError("--top-k must be at least 1.")
    if not -1.0 <= args.min_similarity <= 1.0:
        raise ValueError("--min-similarity must be between -1 and 1.")

    input_path = Path(args.input)
    output_path = Path(args.output)
    embeddings_path = Path(args.embeddings)
    nodes_path = Path(args.nodes)
    for required_path in (input_path, embeddings_path, nodes_path):
        if not required_path.is_file():
            raise FileNotFoundError(f"Required file not found: {required_path}")

    embeddings = np.load(embeddings_path)
    with nodes_path.open("r", encoding="utf-8") as stream:
        node_data = json.load(stream)

    nodes = list(node_data["nodes"].keys())
    node_info = node_data["nodes"]
    if len(nodes) != len(embeddings):
        raise ValueError(
            "Embedding and node counts differ: "
            f"{len(embeddings)} embeddings for {len(nodes)} nodes."
        )

    from sentence_transformers import SentenceTransformer
    from tqdm import tqdm

    print(f"Loaded {len(nodes):,} graph nodes and embeddings shaped {embeddings.shape}.")
    model = SentenceTransformer(args.model)
    df = pd.read_csv(input_path)
    if "Question" not in df.columns:
        raise ValueError("Input CSV must contain a 'Question' column.")

    accepted_anchors = []
    candidate_lists = []
    top_scores = []
    statuses = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Finding graph anchors"):
        candidates = find_similar_nodes(
            row.get("Question", ""),
            embeddings,
            nodes,
            node_info,
            model,
            top_k=args.top_k,
        )
        top_score = candidates[0]["score"] if candidates else None
        accepted = top_score is not None and top_score >= args.min_similarity

        accepted_anchors.append(candidates[0]["node_id"] if accepted else None)
        candidate_lists.append(json.dumps(candidates, ensure_ascii=False))
        top_scores.append(top_score)
        statuses.append("accepted" if accepted else "low_confidence")

    df["embed_result"] = accepted_anchors
    df["embed_candidates"] = candidate_lists
    df["embedding_top_score"] = top_scores
    df["embedding_status"] = statuses

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    accepted_count = statuses.count("accepted")
    print(f"Saved embedding results to {output_path}.")
    print(
        f"Accepted {accepted_count}/{len(df)} anchors at similarity >= "
        f"{args.min_similarity:.3f}; {len(df) - accepted_count} require review."
    )


if __name__ == "__main__":
    main()
