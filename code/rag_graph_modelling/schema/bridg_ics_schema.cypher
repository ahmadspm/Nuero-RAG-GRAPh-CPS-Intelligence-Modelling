// BRIDG-ICS schema: uniqueness constraints and indexes.
// Run once against a fresh Neo4j database before load_to_neo4j.py.

CREATE CONSTRAINT cve_id IF NOT EXISTS FOR (n:CVE) REQUIRE n.cve_id IS UNIQUE;
CREATE CONSTRAINT cwe_id IF NOT EXISTS FOR (n:CWE) REQUIRE n.cwe_id IS UNIQUE;
CREATE CONSTRAINT cwe_detection_id IF NOT EXISTS FOR (n:CWEDetection) REQUIRE n.detection_id IS UNIQUE;
CREATE CONSTRAINT cwe_consequence_id IF NOT EXISTS FOR (n:CWEConsequence) REQUIRE n.consequence_id IS UNIQUE;
CREATE CONSTRAINT cwe_mitigation_id IF NOT EXISTS FOR (n:CWEMitigation) REQUIRE n.mitigation_id IS UNIQUE;
CREATE CONSTRAINT cwe_moi_id IF NOT EXISTS FOR (n:CWEModeOfIntroduction) REQUIRE n.mode_id IS UNIQUE;
CREATE CONSTRAINT capec_id IF NOT EXISTS FOR (n:CAPEC) REQUIRE n.capec_id IS UNIQUE;
CREATE CONSTRAINT capec_consequence_id IF NOT EXISTS FOR (n:CAPECConsequence) REQUIRE n.consequence_id IS UNIQUE;
CREATE CONSTRAINT technique_id IF NOT EXISTS FOR (n:Technique) REQUIRE n.technique_id IS UNIQUE;
CREATE CONSTRAINT attack_id IF NOT EXISTS FOR (n:Attack) REQUIRE n.attack_id IS UNIQUE;
CREATE CONSTRAINT group_id IF NOT EXISTS FOR (n:Group) REQUIRE n.group_id IS UNIQUE;
CREATE CONSTRAINT tactic_id IF NOT EXISTS FOR (n:Tactic) REQUIRE n.tactic_id IS UNIQUE;
CREATE CONSTRAINT malware_id IF NOT EXISTS FOR (n:Malware) REQUIRE n.malware_id IS UNIQUE;
CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (n:Campaign) REQUIRE n.campaign_id IS UNIQUE;
CREATE CONSTRAINT mitigation_id IF NOT EXISTS FOR (n:Mitigation) REQUIRE n.mitigation_id IS UNIQUE;
CREATE CONSTRAINT asset_id IF NOT EXISTS FOR (n:Asset) REQUIRE n.asset_id IS UNIQUE;
CREATE CONSTRAINT product_id IF NOT EXISTS FOR (n:Product) REQUIRE n.product_id IS UNIQUE;
CREATE CONSTRAINT target_id IF NOT EXISTS FOR (n:Target) REQUIRE n.target_id IS UNIQUE;

// ==============================================
// Example relationship creation (see ontology_mapping.RELATIONSHIPS
// for the full list of 18 triples; load_to_neo4j.py generates these
// programmatically from graph_edges.json).
// ==============================================
// MATCH (c:CVE {cve_id: $cve_id}), (w:CWE {cwe_id: $cwe_id})
// MERGE (c)-[:HAS_CWE]->(w);
//
// MATCH (w:CWE {cwe_id: $cwe_id}), (a:CAPEC {capec_id: $capec_id})
// MERGE (w)-[:HAS_CAPEC]->(a);
//
// MATCH (a:CAPEC {capec_id: $capec_id}), (t:Technique {technique_id: $technique_id})
// MERGE (a)-[:HAS_TECHNIQUE]->(t);

// ==============================================
// Example lookup queries used by the retrieval pipeline
// ==============================================
// // Multi-hop: CVE -> CWE -> CAPEC -> Technique
// MATCH (c:CVE {cve_id: $cve_id})-[:HAS_CWE]->(:CWE)-[:HAS_CAPEC]->(:CAPEC)-[:HAS_TECHNIQUE]->(t:Technique)
// RETURN DISTINCT t.technique_id, t.name;
//
// // Mitigations for a technique used by a threat group
// MATCH (g:Group {group_id: $group_id})-[:USE_TECHNIQUE]->(t:Technique)<-[:MITIGATES]-(m:Mitigation)
// RETURN t.technique_id, m.name;
