import pandas as pd
import ast
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import MultiLabelBinarizer

# === Load both CSVs ===
main_df = pd.read_csv("cti-rcm-fine-results-2021.csv")
fallback_df = pd.read_csv("fallback_rcm_fine.csv")

# --- Safely parse stringified lists ---
def safe_parse(x):
    if isinstance(x, str):
        try:
            return ast.literal_eval(x)
        except:
            return []
    return x if isinstance(x, list) else []

main_df["Cypher_Results"] = main_df["Cypher_Results"].apply(safe_parse)
fallback_df["Fallback_Result"] = fallback_df["Fallback_Result"].apply(safe_parse)

# --- Extract only relevant columns ---
final_df = main_df[["Answer", "Cypher_Results"]].copy()

# --- Replace predictions based on Row_Index ---
if "Row_Index" not in fallback_df.columns:
    raise ValueError("❌ 'Row_Index' column not found in fallback_results_with_metrics.csv")

replaced_rows = 0
for _, row in fallback_df.iterrows():
    i = int(row["Row_Index"])
    if i in final_df.index:
        final_df.at[i, "Cypher_Results"] = row["Fallback_Result"]
        replaced_rows += 1

print(f"✅ Replaced {replaced_rows} rows with fallback results.\n")

# === Prepare ground-truth and predicted CWE label sets ===
true_labels, predicted_labels = [], []
containment_matches, exact_matches = [], []

for _, row in final_df.iterrows():
    gt = str(row["Answer"]).strip().upper()
    preds = [str(p).strip().upper() for p in row["Cypher_Results"]]

    true_labels.append([gt])
    predicted_labels.append(preds)
    containment_matches.append(gt in preds)
    exact_matches.append(preds == [gt])

all_classes = sorted({label for labels in true_labels + predicted_labels for label in labels})
mlb = MultiLabelBinarizer(classes=all_classes)
mlb.fit([all_classes])
y_true = mlb.transform(true_labels)
y_pred = mlb.transform(predicted_labels)

print("=== CWE prediction metrics with embedding fallback ===")
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
