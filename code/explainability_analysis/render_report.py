"""
Renders the examples from build_examples.py into a human-readable
Markdown report: one section per question with its Cypher, reasoning
path, retrieved evidence, and answer.
"""

import json


def render_example(ex: dict, index: int) -> str:
    cypher_block = "\n---\n".join(ex["generated_cypher"]) or "—"
    path = " → ".join(ex["reasoning_path"]) or "—"
    evidence = ", ".join(str(e) for e in ex["retrieved_evidence"]) or "—"
    answer = ex["answer"] if isinstance(ex["answer"], str) else ", ".join(str(a) for a in ex["answer"])

    return f"""
## Example {index}: {ex['question']}

**Reasoning path:** {path}

**Generated Cypher**
```cypher
{cypher_block}
```

**Retrieved evidence:** {evidence}

**Answer**

{answer}
"""


def render(examples_path: str = "examples.json", output_path: str = "examples_report.md") -> None:
    with open(examples_path) as f:
        examples = json.load(f)

    sections = [render_example(ex, i + 1) for i, ex in enumerate(examples)]
    report = "# GRICS Explainability Examples\n" + "\n---\n".join(sections)

    with open(output_path, "w") as f:
        f.write(report)
    print(f"💾 Saved report -> {output_path}")


if __name__ == "__main__":
    render()
