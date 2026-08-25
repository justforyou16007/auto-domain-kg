"""Audit report generation and adversarial traceability module.

Implements Issue #14 (audit report output) and Issue #15 (adversarial
effectiveness with traceability across multiple rounds).

The audit report captures the full audit state for one adversarial round:
which rubrics were applied, per-audit-skill results, an overall pass/fail
under STRICT semantics (any error-level issue blocks the round), issue
counts by severity, and the worker fixes recorded for traceability.

A persistent ``AuditHistory`` (JSONL) lets the adversarial loop trace any
issue across rounds — when it was first found, how the worker fixed it, and
whether it reappeared — and produce a convergence summary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_domain_kg.audit_rubrics import RubricsConfig

# The 5 audit skills a report aggregates.
AUDIT_SKILLS: tuple[str, ...] = (
    "schema_audit",
    "graph_structure_audit",
    "graphrag_validation",
    "evidence_audit",
    "task_relevance_audit",
)

# History is persisted as one JSON object per line.
_HISTORY_FILENAME = "audit_history.jsonl"


@dataclass
class AuditReport:
    """Full audit report for one adversarial round."""

    round_number: int
    timestamp: str
    rubrics_used: list[dict[str, Any]]
    sub_reports: dict[str, dict[str, Any]]
    overall_passed: bool
    total_issues: int
    errors: int
    warnings: int
    worker_fixes: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a plain dict (for JSON)."""
        return {
            "round_number": self.round_number,
            "timestamp": self.timestamp,
            "rubrics_used": self.rubrics_used,
            "sub_reports": self.sub_reports,
            "overall_passed": self.overall_passed,
            "total_issues": self.total_issues,
            "errors": self.errors,
            "warnings": self.warnings,
            "worker_fixes": self.worker_fixes,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditReport":
        """Reconstruct an AuditReport from a plain dict."""
        return cls(
            round_number=int(data["round_number"]),
            timestamp=str(data["timestamp"]),
            rubrics_used=list(data.get("rubrics_used", [])),
            sub_reports=dict(data.get("sub_reports", {})),
            overall_passed=bool(data["overall_passed"]),
            total_issues=int(data.get("total_issues", 0)),
            errors=int(data.get("errors", 0)),
            warnings=int(data.get("warnings", 0)),
            worker_fixes=list(data.get("worker_fixes", [])),
            summary=str(data.get("summary", "")),
        )


class AuditReportGenerator:
    """Generate, render, and persist audit reports."""

    def generate_report(
        self,
        round_number: int,
        sub_reports: dict[str, dict[str, Any]],
        rubrics_config: RubricsConfig,
        worker_fixes: list[dict[str, Any]] | None = None,
    ) -> AuditReport:
        """Build an AuditReport from raw sub-audit results.

        Under STRICT auditing the round passes only when *every* sub-audit
        passes and no error-level issue exists.

        Args:
            round_number: Which adversarial round this is (1, 2, ...).
            sub_reports: Per-audit-skill result dicts.
            rubrics_config: The rubrics applied this round.
            worker_fixes: What the worker changed this round (traceability).

        Returns:
            A populated AuditReport.
        """
        rubrics_used = [
            {
                "name": r.name,
                "strictness_level": r.strictness_level,
                "custom_config": dict(r.custom_thresholds),
                "enabled": r.enabled,
            }
            for r in rubrics_config.get_enabled_rubrics()
        ]

        total_issues = 0
        errors = 0
        warnings = 0
        any_sub_failed = False

        for skill in AUDIT_SKILLS:
            sub = sub_reports.get(skill, {})
            passed = bool(sub.get("passed", True))
            if not passed:
                any_sub_failed = True
            for issue in sub.get("issues", []) or []:
                total_issues += 1
                sev = str(issue.get("severity", "")).lower()
                if sev == "error":
                    errors += 1
                elif sev == "warning":
                    warnings += 1

        # STRICT: any error-level issue blocks the round, regardless of the
        # per-skill "passed" flag. A sub-audit that failed also blocks.
        overall_passed = (errors == 0) and not any_sub_failed

        timestamp = datetime.now(timezone.utc).isoformat()
        summary = self._build_summary(
            round_number, overall_passed, total_issues, errors, warnings
        )

        return AuditReport(
            round_number=round_number,
            timestamp=timestamp,
            rubrics_used=rubrics_used,
            sub_reports=dict(sub_reports),
            overall_passed=overall_passed,
            total_issues=total_issues,
            errors=errors,
            warnings=warnings,
            worker_fixes=list(worker_fixes or []),
            summary=summary,
        )

    # ── Rendering ────────────────────────────────────────────────────────

    def render_markdown(self, report: AuditReport) -> str:
        """Render the full audit report as detailed markdown.

        Covers all audit characteristics: schema completeness stats, graph
        connectivity metrics, evidence source counts, GraphRAG question
        results, task relevance coverage, issue breakdown by
        severity/category, and worker fix traceability.
        """
        lines: list[str] = []
        status = "PASSED" if report.overall_passed else "FAILED"
        lines.append(f"# Audit Report — Round {report.round_number}")
        lines.append("")
        lines.append(f"- **Timestamp**: `{report.timestamp}`")
        lines.append(f"- **Overall**: {status}")
        lines.append(f"- **Total issues**: {report.total_issues}")
        lines.append(f"- **Errors**: {report.errors}")
        lines.append(f"- **Warnings**: {report.warnings}")
        lines.append("")
        lines.append("## Rubrics Applied")
        lines.append("")
        lines.append("| Rubric | Strictness | Enabled | Thresholds |")
        lines.append("|--------|------------|---------|------------|")
        for r in report.rubrics_used:
            th = ", ".join(f"{k}={v}" for k, v in r["custom_config"].items())
            lines.append(
                f"| {r['name']} | {r['strictness_level']} | "
                f"{'yes' if r.get('enabled', True) else 'no'} | {th} |"
            )
        lines.append("")

        lines.append(self._render_schema(report))
        lines.append(self._render_graph_structure(report))
        lines.append(self._render_graphrag(report))
        lines.append(self._render_evidence(report))
        lines.append(self._render_task_relevance(report))
        lines.append(self._render_issues(report))
        lines.append(self._render_worker_fixes(report))

        lines.append("## Summary")
        lines.append("")
        lines.append(report.summary)
        lines.append("")
        return "\n".join(lines)

    def render_json(self, report: AuditReport) -> str:
        """Render the report as a JSON string."""
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    # ── Persistence ──────────────────────────────────────────────────────

    def save_report(
        self, report: AuditReport, output_dir: str = "reports/audits/"
    ) -> str:
        """Save both .md and .json files, returning the base path.

        Files are written to ``<output_dir>/round_<N>/audit_report`` with
        ``.md`` and ``.json`` extensions.

        Args:
            report: The report to save.
            output_dir: Base output directory.

        Returns:
            The base path (without extension) of the saved files.
        """
        out = Path(output_dir) / f"round_{report.round_number}"
        out.mkdir(parents=True, exist_ok=True)
        base = out / "audit_report"
        base.with_suffix(".md").write_text(
            self.render_markdown(report), encoding="utf-8"
        )
        base.with_suffix(".json").write_text(
            self.render_json(report), encoding="utf-8"
        )
        return str(base)

    # ── Internal renderers ───────────────────────────────────────────────

    def _build_summary(
        self, round_number: int, passed: bool, total: int, errors: int,
        warnings: int,
    ) -> str:
        verdict = "passed" if passed else "did not pass"
        return (
            f"Round {round_number} {verdict} the strict audit. "
            f"Found {total} issue(s): {errors} error(s), "
            f"{warnings} warning(s). "
            f"STRICT policy: any error-level issue blocks the round."
        )

    def _render_schema(self, report: AuditReport) -> str:
        sub = report.sub_reports.get("schema_audit", {})
        s = sub.get("summary", {}) or {}
        lines = [
            "## Schema Audit",
            "",
            f"- Passed: {sub.get('passed', 'n/a')}",
            f"- Total entity types: {s.get('total_entity_types', 'n/a')}",
            f"- Missing entity types: {s.get('missing_entity_types', 'n/a')}",
            f"- Undefined relationships: "
            f"{s.get('undefined_relationships', 'n/a')}",
        ]
        lines.append("")
        return "\n".join(lines)

    def _render_graph_structure(self, report: AuditReport) -> str:
        sub = report.sub_reports.get("graph_structure_audit", {})
        s = sub.get("summary", {}) or {}
        avg = s.get("avg_relationships_per_entity", "n/a")
        lines = [
            "## Graph Structure Audit (Connectivity Metrics)",
            "",
            f"- Passed: {sub.get('passed', 'n/a')}",
            f"- Total entities: {s.get('total_entities', 'n/a')}",
            f"- Orphan entities: {s.get('orphan_entities', 'n/a')}",
            f"- Avg relationships per entity: {avg}",
        ]
        lines.append("")
        return "\n".join(lines)

    def _render_graphrag(self, report: AuditReport) -> str:
        sub = report.sub_reports.get("graphrag_validation", {})
        s = sub.get("summary", {}) or {}
        questions = sub.get("questions", []) or []
        lines = [
            "## GraphRAG Validation (Question Results)",
            "",
            f"- Passed: {sub.get('passed', 'n/a')}",
            f"- Total questions: {s.get('total_questions', 'n/a')}",
            f"- Answerable: {s.get('answerable', 'n/a')}",
            f"- Unanswerable: {s.get('unanswerable', 'n/a')}",
            "",
        ]
        if questions:
            lines.append("| Question | Answerable | Precision | Results |")
            lines.append("|----------|------------|-----------|---------|")
            for q in questions:
                lines.append(
                    f"| {q.get('question', '')} | "
                    f"{q.get('answerable', '')} | "
                    f"{q.get('precision', '')} | "
                    f"{q.get('result_count', '')} |"
                )
            lines.append("")
        return "\n".join(lines)

    def _render_evidence(self, report: AuditReport) -> str:
        sub = report.sub_reports.get("evidence_audit", {})
        s = sub.get("summary", {}) or {}
        lines = [
            "## Evidence Audit (Source Counts)",
            "",
            f"- Passed: {sub.get('passed', 'n/a')}",
            f"- Entities audited: "
            f"{s.get('total_entities_audited', 'n/a')}",
            f"- Single-source entities: "
            f"{s.get('single_source_entities', 'n/a')}",
            f"- Conflicting evidence: "
            f"{s.get('conflicting_evidence', 'n/a')}",
            "",
        ]
        return "\n".join(lines)

    def _render_task_relevance(self, report: AuditReport) -> str:
        sub = report.sub_reports.get("task_relevance_audit", {})
        s = sub.get("summary", {}) or {}
        total = s.get("total_concerns", 0) or 0
        fully = s.get("fully_covered", 0) or 0
        ratio = (fully / total) if total else 0.0
        lines = [
            "## Task Relevance Audit (Coverage)",
            "",
            f"- Passed: {sub.get('passed', 'n/a')}",
            f"- Total concerns: {total}",
            f"- Fully covered: {fully}",
            f"- Partially covered: "
            f"{s.get('partially_covered', 'n/a')}",
            f"- Not covered: {s.get('not_covered', 'n/a')}",
            f"- Fully-covered ratio: {ratio:.2f}",
        ]
        lines.append("")
        return "\n".join(lines)

    def _render_issues(self, report: AuditReport) -> str:
        lines = ["## Issue Breakdown", ""]
        lines.append(
            f"- Errors: {report.errors}  | Warnings: {report.warnings}  "
            f"| Total: {report.total_issues}"
        )
        lines.append("")
        # Group by severity then category.
        by_severity: dict[str, list[dict[str, Any]]] = {}
        for skill in AUDIT_SKILLS:
            sub = report.sub_reports.get(skill, {})
            for issue in sub.get("issues", []) or []:
                sev = str(issue.get("severity", "info")).lower()
                issue = dict(issue)
                issue.setdefault("audit_skill", skill)
                by_severity.setdefault(sev, []).append(issue)

        if by_severity:
            lines.append("| Severity | Audit | Category | Issue ID | Description |")
            lines.append("|----------|-------|----------|----------|-------------|")
            for sev in ("error", "warning", "info"):
                for issue in by_severity.get(sev, []):
                    iid = issue.get("id", issue.get("issue_id", ""))
                    lines.append(
                        f"| {sev} | {issue.get('audit_skill', '')} | "
                        f"{issue.get('category', '')} | {iid} | "
                        f"{issue.get('description', '')} |"
                    )
            lines.append("")
        return "\n".join(lines)

    def _render_worker_fixes(self, report: AuditReport) -> str:
        lines = ["## Worker Fixes (Traceability)", ""]
        if not report.worker_fixes:
            lines.append("_No worker fixes recorded for this round._")
            lines.append("")
            return "\n".join(lines)
        lines.append(
            "| Fix | Issue IDs Addressed | Files Modified |"
        )
        lines.append("|-----|----------------------|----------------|")
        for fix in report.worker_fixes:
            ids = ", ".join(fix.get("issue_ids_addressed", []) or [])
            files = ", ".join(fix.get("files_modified", []) or [])
            desc = fix.get("fix_description", "")
            lines.append(f"| {desc} | {ids} | {files} |")
        lines.append("")
        return "\n".join(lines)


class AuditHistory:
    """Persistent adversarial-round history for traceability.

    History is persisted as JSONL in ``<history_dir>/audit_history.jsonl``,
    one AuditReport per line. Reloading the same directory reconstructs the
    full round history.
    """

    def __init__(self, history_dir: str = "reports/audits/") -> None:
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.history_dir / _HISTORY_FILENAME
        self._rounds: list[AuditReport] = []
        self._load()

    def _load(self) -> None:
        """Load existing rounds from the JSONL file."""
        self._rounds = []
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                self._rounds.append(AuditReport.from_dict(data))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        self._rounds.sort(key=lambda r: r.round_number)

    def add_round(self, report: AuditReport) -> None:
        """Append a round report to history (dedup by round number)."""
        # Replace an existing entry for the same round number if present.
        self._rounds = [
            r for r in self._rounds if r.round_number != report.round_number
        ]
        self._rounds.append(report)
        self._rounds.sort(key=lambda r: r.round_number)
        self._persist()

    def _persist(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            for r in self._rounds:
                f.write(
                    json.dumps(r.to_dict(), ensure_ascii=False) + "\n"
                )

    def get_round(self, round_number: int) -> AuditReport | None:
        """Return the report for a specific round, or None."""
        for r in self._rounds:
            if r.round_number == round_number:
                return r
        return None

    def get_all_rounds(self) -> list[AuditReport]:
        """Return all rounds sorted by round number."""
        return list(self._rounds)

    def get_issue_trace(self, issue_id: str) -> list[dict[str, Any]]:
        """Trace a specific issue across rounds.

        Each trace entry records the round number, the action taken
        (``found`` when the issue appears, ``fixed`` when a worker fix in
        that round addressed it, ``reappeared`` when it reappears after a
        prior fix), the audit skill, and the issue description.

        Args:
            issue_id: The issue identifier to trace.

        Returns:
            A chronologically ordered list of trace entries.
        """
        trace: list[dict[str, Any]] = []
        seen_fixed = False
        for report in self._rounds:
            # Was the issue present this round?
            found_skill: str | None = None
            found_desc = ""
            for skill in AUDIT_SKILLS:
                sub = report.sub_reports.get(skill, {})
                for issue in sub.get("issues", []) or []:
                    iid = str(
                        issue.get("id", issue.get("issue_id", ""))
                    )
                    if iid == issue_id:
                        found_skill = skill
                        found_desc = issue.get("description", "")
                        break
                if found_skill:
                    break

            # Did a worker fix address it this round?
            fixed_this_round = False
            for fix in report.worker_fixes:
                addressed = [str(x) for x in fix.get("issue_ids_addressed", [])]
                if issue_id in addressed:
                    fixed_this_round = True
                    trace.append({
                        "round_number": report.round_number,
                        "action": "fixed",
                        "audit_skill": found_skill or "",
                        "description": fix.get("fix_description", ""),
                        "files_modified": fix.get("files_modified", []),
                    })
                    seen_fixed = True
                    break

            if found_skill and not fixed_this_round:
                action = "reappeared" if seen_fixed else "found"
                trace.append({
                    "round_number": report.round_number,
                    "action": action,
                    "audit_skill": found_skill,
                    "description": found_desc,
                })

        return trace

    def get_summary(self) -> dict[str, Any]:
        """Produce a convergence summary across all rounds.

        Returns:
            Dict with total_rounds, issues_resolved, issues_recurring,
            and a convergence_trend (per-round error counts).
        """
        if not self._rounds:
            return {
                "total_rounds": 0,
                "issues_resolved": 0,
                "issues_recurring": 0,
                "convergence_trend": [],
            }

        convergence_trend: list[dict[str, Any]] = []
        for r in self._rounds:
            convergence_trend.append({
                "round": r.round_number,
                "errors": r.errors,
                "warnings": r.warnings,
                "passed": r.overall_passed,
            })

        # Collect every distinct issue id and the rounds it appeared in.
        issue_rounds: dict[str, list[int]] = {}
        for report in self._rounds:
            for skill in AUDIT_SKILLS:
                sub = report.sub_reports.get(skill, {})
                for issue in sub.get("issues", []) or []:
                    iid = str(
                        issue.get("id", issue.get("issue_id", ""))
                    )
                    if iid:
                        issue_rounds.setdefault(iid, []).append(
                            report.round_number
                        )

        last_round = self._rounds[-1].round_number
        issues_resolved = 0
        issues_recurring = 0
        for iid, rounds in issue_rounds.items():
            found_rounds = sorted(set(rounds))
            # Resolved: found in some round but absent from the final round.
            if found_rounds and last_round not in found_rounds:
                issues_resolved += 1
            # Recurring: found, then absent in an intermediate round, then
            # found again later (came back after disappearing).
            if len(found_rounds) >= 2:
                lo, hi = found_rounds[0], found_rounds[-1]
                present = set(found_rounds)
                gap = any(r not in present for r in range(lo + 1, hi))
                if gap:
                    issues_recurring += 1

        return {
            "total_rounds": len(self._rounds),
            "issues_resolved": issues_resolved,
            "issues_recurring": issues_recurring,
            "convergence_trend": convergence_trend,
        }


# Re-exported for convenience / external typing.
__all__ = [
    "AuditReport",
    "AuditReportGenerator",
    "AuditHistory",
    "AUDIT_SKILLS",
]
