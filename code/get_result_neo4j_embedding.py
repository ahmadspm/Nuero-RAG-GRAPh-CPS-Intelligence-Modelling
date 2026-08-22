import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import MultiLabelBinarizer

# ================================================================
# 1️⃣ Neo4j connection
# ================================================================
URI = "bolt://localhost:7687"
AUTH = ("", "") # adjust this part
driver = GraphDatabase.driver(URI, auth=AUTH)

# ================================================================
# 2️⃣ Load CSV
# ================================================================
csv_path = "incorrect_predictions_with_fallback-fine-2021.csv"
df = pd.read_csv(csv_path)

required_cols = ["Question", "Fallback_Cypher", "Answer"]
for col in required_cols:
    if col not in df.columns:
        raise ValueError(f"❌ Missing required column: {col}")

if "Fallback_Result" not in df.columns:
    df["Fallback_Result"] = None

print(f"✅ Loaded {len(df)} rows from {csv_path}")

# ================================================================
# 3️⃣ Helper: run Cypher safely
# ================================================================
def run_cypher_safely(tx, query):
    """Run a Cypher query and return results or [] if invalid."""
    try:
        result = list(tx.run(query))
        return [dict(r) for r in result] if result else []
    except Exception as e:
        # Uncomment for debugging
        # print(f"⚠️ Query failed: {e}")
        return []

# ================================================================
# 4️⃣ Helper: extract normalized entity identifiers
# ================================================================
ENTITY_ID_PROPERTIES = {
    "CVE": ("cve_id",),
    "Product": ("product_id", "name"),
    "CWE": ("cwe_id",),
    "CWEDetection": ("detection_id", "name"),
    "CWEConsequence": ("consequence_id", "name"),
    "CWEMitigation": ("mitigation_id", "name"),
    "CWEModeOfIntroduction": ("introduction_id", "phase"),
    "CAPEC": ("capec_id",),
    "CAPECConsequence": ("consequence_id", "name"),
    "Attack": ("attackstep_id", "attackStep"),
    "Technique": ("technique_id", "name"),
    "Tactic": ("tactic_id", "name"),
    "Mitigation": ("mitigation_id", "name"),
    "Campaign": ("campaign_id", "name"),
    "Asset": ("asset_id", "name"),
    "Malware": ("malware_id", "name"),
    "Zone": ("id", "code", "name"),
    "Group": ("group_id", "name"),
    "Target": ("name",),
    "CPE": ("id", "name"),
}

FALLBACK_ID_PROPERTIES = (
    "cve_id", "cwe_id", "capec_id", "technique_id", "tactic_id",
    "mitigation_id", "malware_id", "campaign_id", "group_id",
    "product_id", "asset_id", "attackstep_id", "detection_id",
    "consequence_id", "introduction_id", "id", "code", "name",
)


def normalize_result_value(value):
    """Return stable identifiers from Neo4j nodes, mappings, lists, or scalars."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for nested in value for item in normalize_result_value(nested)]
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]

    labels = set(getattr(value, "labels", []))
    try:
        properties = dict(value.items())
    except (AttributeError, TypeError, ValueError):
        properties = value if isinstance(value, dict) else {}

    preferred_properties = []
    for label in sorted(labels):
        preferred_properties.extend(ENTITY_ID_PROPERTIES.get(label, ()))
    preferred_properties.extend(FALLBACK_ID_PROPERTIES)

    for property_name in dict.fromkeys(preferred_properties):
        property_value = properties.get(property_name)
        if property_value not in (None, ""):
            return [str(property_value)]
    return []


def extract_entity_ids(records):
    """Extract unique normalized entity identifiers from Neo4j records."""
    entity_ids = set()
    for record in records:
        for value in record.values():
            entity_ids.update(normalize_result_value(value))
    return sorted(entity_ids, key=str.casefold)

# ================================================================
# 5️⃣ Execute Fallback Cyphers
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
        entity_ids = extract_entity_ids(results)
        df.at[idx, "Fallback_Result"] = entity_ids
        predictions.append(entity_ids)
        # break
        print(f"✅ Processed {idx+1}/{len(df)} | Entity IDs: {entity_ids}")

driver.close()

# ================================================================
# 6️⃣ Evaluation
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
