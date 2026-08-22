import ast
import pandas as pd
from neo4j import GraphDatabase

# ==============================================
# Neo4j connection
# ==============================================
URI = "bolt://localhost:7687"
AUTH = ("", "") # adjust this part
driver = GraphDatabase.driver(URI, auth=AUTH)

# ==============================================
# Load CSV
# ==============================================
csv_path = "cti-rcm-cypher-fine-2-2021.csv"
df = pd.read_csv(csv_path)

# Ensure required columns exist
if "Cypher_Results" not in df.columns:
    df["Cypher_Results"] = None
if "num_query" not in df.columns:
    df["num_query"] = None

# ==============================================
# Helper: run Cypher safely (no print)
# ==============================================
def run_cypher_safely(tx, query):
    """Run a Cypher query and return results or [] if invalid."""
    try:
        result = list(tx.run(query))
        return [dict(r) for r in result] if result else []
    except Exception:
        return []  # silently ignore invalid or failed queries

# ==============================================
# Helper: extract normalized entity identifiers
# ==============================================
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

# ==============================================
# Main loop
# ==============================================
for idx, row in df.iterrows():
    cypher_str = row["Generated_Cypher_List"]

    if not isinstance(cypher_str, str) or not cypher_str.strip():
        df.at[idx, "Cypher_Results"] = []
        df.at[idx, "num_query"] = []
        continue

    try:
        cypher_list = ast.literal_eval(cypher_str)
    except Exception:
        df.at[idx, "Cypher_Results"] = []
        df.at[idx, "num_query"] = []
        continue

    if not isinstance(cypher_list, list):
        cypher_list = [cypher_list]

    all_records = []
    successful_queries = []

    with driver.session() as session:
        for i, query in enumerate(cypher_list, start=1):
            if not isinstance(query, str) or not query.strip():
                continue
            try:
                results = session.execute_read(run_cypher_safely, query)
            except Exception:
                continue
            if results:
                all_records.extend(results)
                successful_queries.append(i)
                break
    

    # Extract normalized IDs for any supported BRIDG-ICS entity type
    entity_ids = extract_entity_ids(all_records)

    df.at[idx, "Cypher_Results"] = entity_ids
    df.at[idx, "num_query"] = successful_queries

    print(f"✅ Processed {idx + 1}/{len(df)} | Entity IDs: {entity_ids} | Queries: {successful_queries}")

    # Save progress every 10 rows
    if (idx + 1) % 10 == 0:
        df.to_csv(csv_path, index=False)

# ==============================================
# Final save
# ==============================================
output_file = "cti-rcm-fine-results-2021.csv"
df.to_csv(output_file, index=False)
print(f"\n🎉 All done! Results saved to {output_file}")

driver.close()
