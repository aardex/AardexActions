"""Write a metadata-only GitHub job summary for one SARIF report.

No message, code snippet, location, path or secret value is copied into the summary.
"""

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path


def summarize(path: Path, label: str) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != "2.1.0" or not isinstance(data.get("runs"), list):
        raise ValueError("Expected a SARIF 2.1.0 document with a runs array")
    counts = Counter()
    for run in data["runs"]:
        for result in run.get("results", []):
            counts[result.get("ruleId") or "(unknown)"] += 1
    lines = [f"### {label}", "", f"**{sum(counts.values())} results** across {len(counts)} rules.", "",
             "| Rule ID | Results |", "| --- | ---: |"]
    for rule_id, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        # Treat scanner-provided IDs as untrusted: no Markdown/HTML injection.
        safe_id = re.sub(r"[^A-Za-z0-9_.:/-]", "_", str(rule_id))[:120]
        lines.append(f"| {safe_id} | {count} |")
    lines += ["", "Download the private SARIF artifact for details. Findings are not yet qualified.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("label")
    args = parser.parse_args()
    text = summarize(args.path, args.label)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
        output.write(text + "\n")


if __name__ == "__main__":
    main()
