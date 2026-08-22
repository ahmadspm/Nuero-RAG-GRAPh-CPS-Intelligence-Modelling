import pandas as pd
import ast
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
from sklearn.preprocessing import MultiLabelBinarizer

# === Load CSV ===
df = pd.read_csv("cti-rcm-fine-results-2021.csv")

# Convert stringified list (e.g., "['A', 'B']") to real Python list
df["Cypher_Results"] = df["Cypher_Results"].apply(
    lambda x: ast.literal_eval(x) if isinstance(x, str) else []
)

# Prepare ground-truth and predicted CWE label sets
true_labels, predicted_labels = [], []
containment_matches, exact_matches = [], []
wrong_rows = []  # collect rows with wrong or multiple predictions

for idx, row in df.iterrows():
    gt = str(row["Answer"]).strip()
    preds = [str(p).strip() for p in row["Cypher_Results"]]

    true_labels.append([gt])
    predicted_labels.append(preds)
    containment_matches.append(gt in preds)
    exact_matches.append(preds == [gt])

    # Identify incorrect, multi-result, or empty predictions
    if (gt not in preds) or (len(preds) != 1):
        wrong_rows.append({
            "Row_Index": idx,
            "Question": row.get("Question", ""),  # Include the question text
            "Answer": gt,
            "Predicted_List": preds,
            "Correct_in_Contain": gt in preds,
            "Num_Predicted": len(preds)
        })

all_classes = sorted({label for labels in true_labels + predicted_labels for label in labels})
mlb = MultiLabelBinarizer(classes=all_classes)
mlb.fit([all_classes])
y_true = mlb.transform(true_labels)
y_pred = mlb.transform(predicted_labels)

print("\n=== CWE prediction metrics ===")
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

# Export wrong predictions to CSV (now with Question column)
wrong_df = pd.DataFrame(wrong_rows)
wrong_df.to_csv("incorrect_predictions-fine.csv", index=False)

print(f"\nSaved {len(wrong_df)} incorrect/multi-result rows to 'incorrect_predictions-fine.csv'")


