#!/usr/bin/env python3
"""Aggregate scanner reports and decide pass/fail. Standard library only.

Reads the JSON output of Semgrep, pip-audit, Trivy (fs + config), and gitleaks
from a reports directory, normalizes every finding to one shape, subtracts an
audited baseline of accepted risks, prints a summary, and exits non-zero if any
remaining finding is HIGH severity or above.

    python scripts/security_gate.py --reports reports --baseline security/baseline.json

Design note: the individual scanners never fail their own CI step. They emit
SARIF (for the GitHub Security tab) and JSON (for this gate). A scanner step that
exits non-zero would skip its SARIF upload, so findings would never reach code
scanning. Centralizing the pass/fail policy here keeps the threshold and the
accepted-risk list in one reviewable file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Iterable

RANK = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
FAIL_AT = RANK["HIGH"]


def _sev(name: str) -> str:
    name = (name or "").upper()
    aliases = {
        "ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "INFO",
        "MODERATE": "MEDIUM", "UNKNOWN": "LOW", "NEGLIGIBLE": "INFO",
    }
    name = aliases.get(name, name)
    return name if name in RANK else "LOW"


def _finding(tool, rule_id, severity, file, line, title):
    return {
        "tool": tool, "rule_id": rule_id or "", "severity": _sev(severity),
        "file": file or "", "line": line or 0, "title": (title or "")[:200],
    }


def _load(path: pathlib.Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def parse_semgrep(data) -> Iterable[dict]:
    for r in (data or {}).get("results", []):
        extra = r.get("extra", {})
        yield _finding("semgrep", r.get("check_id"),
                       extra.get("severity", "WARNING"),
                       r.get("path"), (r.get("start") or {}).get("line"),
                       extra.get("message"))


def parse_pip_audit(data) -> Iterable[dict]:
    deps = data.get("dependencies", data) if isinstance(data, dict) else data
    for dep in deps or []:
        for v in dep.get("vulns", []) or []:
            yield _finding("pip-audit", v.get("id"), "HIGH",
                           dep.get("name"), 0,
                           f"{dep.get('name')} {dep.get('version')}: {v.get('id')}")


def parse_trivy(data) -> Iterable[dict]:
    for res in (data or {}).get("Results", []) or []:
        for v in res.get("Vulnerabilities", []) or []:
            yield _finding("trivy", v.get("VulnerabilityID"), v.get("Severity"),
                           res.get("Target"), 0,
                           f"{v.get('PkgName')}: {v.get('VulnerabilityID')}")
        for m in res.get("Misconfigurations", []) or []:
            yield _finding("trivy-config", m.get("ID"), m.get("Severity"),
                           res.get("Target"),
                           (m.get("CauseMetadata") or {}).get("StartLine", 0),
                           m.get("Title"))


def parse_gitleaks(data) -> Iterable[dict]:
    # Any committed secret is treated as critical.
    for f in data or []:
        yield _finding("gitleaks", f.get("RuleID"), "CRITICAL",
                       f.get("File"), f.get("StartLine", 0),
                       f.get("Description") or "secret detected")


PARSERS = {
    "semgrep.json": parse_semgrep,
    "pip-audit.json": parse_pip_audit,
    "trivy-fs.json": parse_trivy,
    "trivy-config.json": parse_trivy,
    "gitleaks.json": parse_gitleaks,
}


def load_baseline(path: pathlib.Path) -> set[str]:
    """Return accepted rule ids, erroring on any entry missing reason/expires."""
    data = _load(path)
    if not data:
        return set()
    today = dt.date.today()
    accepted = set()
    for entry in data.get("accepted", []):
        rule = entry.get("rule_id")
        reason = entry.get("reason")
        expires = entry.get("expires")
        if not (rule and reason and expires):
            sys.exit(f"gate: baseline entry {entry!r} needs rule_id, reason, expires")
        try:
            if dt.date.fromisoformat(expires) < today:
                sys.exit(f"gate: baseline entry for {rule!r} expired on {expires}")
        except ValueError:
            sys.exit(f"gate: baseline entry for {rule!r} has bad expires {expires!r}")
        accepted.add(rule)
    return accepted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--baseline", default="security/baseline.json")
    ap.add_argument("--out", default=None, help="write summary.json here")
    ap.add_argument("--no-fail", action="store_true",
                    help="report only; always exit 0 (for baseline capture)")
    args = ap.parse_args()

    reports = pathlib.Path(args.reports)
    accepted = load_baseline(pathlib.Path(args.baseline))

    findings: list[dict] = []
    for name, parser in PARSERS.items():
        data = _load(reports / name)
        if data is not None:
            findings.extend(parser(data))

    kept = [f for f in findings if f["rule_id"] not in accepted]
    counts = {s: 0 for s in RANK}
    for f in kept:
        counts[f["severity"]] += 1
    blocking = sorted((f for f in kept if RANK[f["severity"]] >= FAIL_AT),
                      key=lambda f: -RANK[f["severity"]])

    lines = ["## Security gate", "",
             f"| Severity | {' | '.join(RANK)} |",
             "|---|" + "---|" * len(RANK),
             "| Count | " + " | ".join(str(counts[s]) for s in RANK) + " |", ""]
    if blocking:
        lines.append(f"**{len(blocking)} finding(s) at HIGH or above:**")
        for f in blocking[:25]:
            lines.append(f"- `{f['severity']}` [{f['tool']}] {f['rule_id']} "
                         f"{f['file']}:{f['line']} {f['title']}")
    else:
        lines.append("No findings at or above HIGH after baseline. Gate passes.")
    summary = "\n".join(lines)
    print(summary)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")

    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps({"counts": counts, "blocking": blocking,
                        "total": len(kept)}, indent=2), encoding="utf-8")

    if blocking and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
