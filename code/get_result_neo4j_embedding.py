import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import MultiLabelBinarizer

# ================================================================
# Neo4j connection
# ================================================================
URI = "bolt://localhost:7687"
AUTH = ("", "") # adjust this part
driver = GraphDatabase.driver(URI, auth=AUTH)

# ================================================================
#  Load CSV
# ================================================================
csv_path = "incorrect_predictions_with_fallback-fine-2021.csv"
df = pd.read_csv(csv_path)

required_cols = ["Question", "Fallback_Cypher", "Answer"]
for col in required_cols:
    if col not in df.columns:
        raise ValueError(f"❌ Missing required column: {col}")

if "Fallback_Result" not in df.columns:
    df["Fallback_Result"] = None

print(f" ok Loaded {len(df)} rows from {csv_path}")

# ================================================================
# Helper: run Cypher safely
# ================================================================
def run_cypher_safely(tx, query):
    """Run a Cypher query and return results or [] if invalid."""
    try:
        result = list(tx.run(query))
        return [dict(r) for r in result] if result else []
    except Exception as e:
        # Uncomment for debugging
        # print(f" Query failed: {e}")
        return []

# ================================================================
#  Helper: extract unique CWE IDs
# ================================================================
def extract_cwe_ids(records):
    """Extract unique CWE IDs from Neo4j query results."""
    cwe_ids = set()
    for record in records:
        for key, val in record.items():
            try:
                if hasattr(val, "get") and "cwe_id" in val:
                    cwe_ids.add(val["cwe_id"].upper())
                elif isinstance(val, dict) and "cwe_id" in val:
                    cwe_ids.add(val["cwe_id"].upper())
            except Exception:
                continue
    return sorted(cwe_ids)

# ================================================================
#  Execute Fallback Cyphers
# ================================================================
predictions = []
contain_pred = []  # lenient (contains ground truth)
exact_pred = []    # strict (exact match)

with driver.session() as session:
    for idx, row in df.iterrows():
        cypher_query = row["Fallback_Cypher"]

        if not isinstance(cypher_query, str) or not cypher_query.strip():
            df.at[idx, "Fallback_Result"] = []
            predictions.append([])
            continue

        results = session.execute_read(run_cypher_safely, cypher_query)
        unique_cwe = extract_cwe_ids(results)
        df.at[idx, "Fallback_Result"] = unique_cwe
        predictions.append(unique_cwe)
        # break
        print(f" ok Processed {idx+1}/{len(df)} | CWE: {unique_cwe}")

driver.close()

# ================================================================
#  Evaluation
# ================================================================
true_labels = [[str(answer).strip().upper()] for answer in df["Answer"]]
predicted_labels = [
    [str(prediction).strip().upper() for prediction in row_predictions]
    for row_predictions in predictions
]
containment_matches = [
    truth[0] in row_predictions
    for truth, row_predictions in zip(true_labels, predicted_labels)
]
exact_matches = [
    row_predictions == truth
    for truth, row_predictions in zip(true_labels, predicted_labels)
]

all_classes = sorted({label for labels in true_labels + predicted_labels for label in labels})
mlb = MultiLabelBinarizer(classes=all_classes)
mlb.fit([all_classes])
y_true = mlb.transform(true_labels)
y_pred = mlb.transform(predicted_labels)

print("\n=== CWE prediction metrics with embedding fallback ===")
print(f"Subset accuracy       : {accuracy_score(y_true, y_pred):.4f}")
print(f"Micro precision       : {precision_score(y_true, y_pred, average='micro', zero_division=0):.4f}")
print(f"Micro recall          : {recall_score(y_true, y_pred, average='micro', zero_division=0):.4f}")
print(f"Micro F1-score        : {f1_score(y_true, y_pred, average='micro', zero_division=0):.4f}")
print(f"Macro precision       : {precision_score(y_true, y_pred, average='macro', zero_division=0):.4f}")
print(f"Macro recall          : {recall_score(y_true, y_pred, average='macro', zero_division=0):.4f}")
print(f"Macro F1-score        : {f1_score(y_true, y_pred, average='macro', zero_division=0):.4f}")
print(f"Containment accuracy  : {np.mean(containment_matches):.4f}")
print(f"Strict exact accuracy : {np.mean(exact_matches):.4f}")
print(f"Empty-result rate     : {np.mean([len(p) == 0 for p in predicted_labels]):.4f}")
print(f"Multi-result rate     : {np.mean([len(p) > 1 for p in predicted_labels]):.4f}")

# ================================================================
# 7️⃣ Save Results
# ================================================================
output_file = "fallback_rcm_fine.csv"
df.to_csv(output_file, index=False)
print(f"\n🎉 Saved results with fallback predictions to {output_file}")
