from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def generate_report(repo, output_format: str, output_path: str | None = None) -> str | None:
    rows = repo.list_report_rows()
    if output_format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2)
        if output_path:
            Path(output_path).write_text(payload, encoding="utf-8")
            return output_path
        sys.stdout.write(payload + "\n")
        return None
    if output_format == "csv":
        fieldnames = ["id", "canonical_text", "question_type", "unique_post_count", "companies", "roles"]
        if output_path:
            handle = open(output_path, "w", newline="", encoding="utf-8")
        else:
            handle = sys.stdout
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
        if output_path:
            handle.close()
            return output_path
        return None
    raise ValueError(f"Unsupported format: {output_format}")
