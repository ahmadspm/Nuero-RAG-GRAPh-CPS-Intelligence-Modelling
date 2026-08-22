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
# Helper: extract unique CWE IDs
# ==============================================
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
    

    # Extract unique CWE IDs
    unique_cwe_ids = extract_cwe_ids(all_records)

    df.at[idx, "Cypher_Results"] = unique_cwe_ids
    df.at[idx, "num_query"] = successful_queries

    print(f"✅ Processed {idx + 1}/{len(df)} | CWE IDs: {unique_cwe_ids} | Queries: {successful_queries}")

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
