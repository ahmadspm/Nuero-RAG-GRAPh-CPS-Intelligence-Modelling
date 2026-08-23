"""
Preprocessing / normalisation for raw CTI source data (CVE, CWE, CAPEC,
MITRE ATT&CK dumps, or the CTI-BENCH tsv files under dataset/Cti_bench).

Output is a set of tidy per-entity CSVs with normalised ID formatting,
ready for ontology mapping in build_graph.py.
"""

import re
import pandas as pd

# ==============================================
# ID normalisation
# ==============================================
def normalize_id(raw_id: str, prefix: str) -> str:
    """
    Normalise an entity ID to the canonical `PREFIX-NNN` form
    used across the BRIDG-ICS graph (e.g. CWE-79, CAPEC-66).
    """
    if not isinstance(raw_id, str):
        return ""
    match = re.search(r"(\d+)", raw_id)
    if not match:
        return raw_id.strip().upper()
    return f"{prefix.upper()}-{match.group(1)}"


def clean_text(value) -> str:
    """Collapse whitespace and strip a free-text field."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


# ==============================================
# Per-entity normalisation
# ==============================================
def normalize_cve(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cve_id"] = df["cve_id"].apply(lambda x: normalize_id(x, "CVE"))
    df["description"] = df.get("description", "").apply(clean_text)
    df = df.drop_duplicates(subset="cve_id")
    return df


def normalize_cwe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cwe_id"] = df["cwe_id"].apply(lambda x: normalize_id(x, "CWE"))
    df["name"] = df.get("name", "").apply(clean_text)
    df["description"] = df.get("description", "").apply(clean_text)
    df = df.drop_duplicates(subset="cwe_id")
    return df


def normalize_capec(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["capec_id"] = df["capec_id"].apply(lambda x: normalize_id(x, "CAPEC"))
    df["name"] = df.get("name", "").apply(clean_text)
    df["description"] = df.get("description", "").apply(clean_text)
    df = df.drop_duplicates(subset="capec_id")
    return df


def normalize_technique(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["technique_id"] = df["technique_id"].str.strip().str.upper()
    df["name"] = df.get("name", "").apply(clean_text)
    df["description"] = df.get("description", "").apply(clean_text)
    df = df.drop_duplicates(subset="technique_id")
    return df


NORMALIZERS = {
    "CVE": normalize_cve,
    "CWE": normalize_cwe,
    "CAPEC": normalize_capec,
    "Technique": normalize_technique,
}


def run(input_paths: dict, output_dir: str = "normalized") -> None:
    """
    input_paths: {"CVE": "raw/cve.csv", "CWE": "raw/cwe.csv", ...}
    Writes normalized/<label>.csv for each entity type provided.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    for label, path in input_paths.items():
        normalizer = NORMALIZERS.get(label)
        if normalizer is None:
            print(f"⚠️  No normalizer registered for '{label}', skipping.")
            continue

        df = pd.read_csv(path)
        normalized = normalizer(df)
        out_path = f"{output_dir}/{label.lower()}.csv"
        normalized.to_csv(out_path, index=False)
        print(f"✅ Normalized {len(normalized)} {label} rows -> {out_path}")


if __name__ == "__main__":
    run({
        "CVE": "raw/cve.csv",
        "CWE": "raw/cwe.csv",
        "CAPEC": "raw/capec.csv",
        "Technique": "raw/technique.csv",
    })
