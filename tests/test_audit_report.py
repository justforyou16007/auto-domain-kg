"""Acceptance tests for Issues #14 and #15: audit report output and
adversarial traceability.

Tests AuditReport, AuditReportGenerator (markdown/json rendering), and
AuditHistory (add round, get round, issue trace, summary).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_domain_kg.audit_report import (
    AuditHistory,
    AuditReport,
    AuditReportGenerator,
)
from auto_domain_kg.audit_rubrics import RubricsConfig


def _sample_sub_reports(*, passed: bool = False) -> dict[str, dict]:
    """Build a representative sub_reports dict matching the 5 audit skills."""
    return {
        "schema_audit": {
            "passed": passed,
            "issues": [
                {
                    "id": "ISS-001",
                    "severity": "error",
                    "category": "completeness",
                    "description": "Missing entity type",
                    "location": "Supplier",
                    "suggestion": "Add Supplier type",
                }
            ],
            "summary": {
                "total_entity_types": 4,
                "missing_entity_types": 1,
                "undefined_relationships": 0,
                "errors": 1,
                "warnings": 0,
            },
        },
        "graph_structure_audit": {
            "passed": True,
            "issues": [],
            "summary": {
                "total_entities": 10,
                "orphan_entities": 0,
                "avg_relationships_per_entity": 2.1,
            },
        },
        "graphrag_validation": {
            "passed": True,
            "questions": [
                {
                    "question": "Who supplies X?",
                    "answerable": True,
                    "precision": "high",
                    "result_count": 3,
                }
            ],
            "summary": {
                "total_questions": 1,
                "answerable": 1,
                "unanswerable": 0,
            },
        },
        "evidence_audit": {
            "passed": True,
            "issues": [],
            "summary": {
                "total_entities_audited": 10,
                "single_source_entities": 0,
                "conflicting_evidence": 0,
            },
        },
        "task_relevance_audit": {
            "passed": True,
            "issues": [],
            "summary": {
                "total_concerns": 3,
                "fully_covered": 3,
                "partially_covered": 0,
                "not_covered": 0,
            },
        },
    }


class TestAuditReportDataclass:
    def test_fields_present(self) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        report = gen.generate_report(
            round_number=1,
            sub_reports=_sample_sub_reports(),
            rubrics_config=rubrics,
        )
        assert isinstance(report, AuditReport)
        assert report.round_number == 1
        assert isinstance(report.timestamp, str) and len(report.timestamp) > 0
        assert isinstance(report.rubrics_used, list) and len(report.rubrics_used) == 5
        assert "schema_audit" in report.sub_reports
        # Error present -> overall not passed (STRICT).
        assert report.overall_passed is False
        assert report.errors == 1
        assert report.total_issues >= 1
        assert report.worker_fixes == []
        assert isinstance(report.summary, str) and len(report.summary) > 0

    def test_rubrics_used_carry_config(self) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        report = gen.generate_report(
            round_number=1,
            sub_reports=_sample_sub_reports(),
            rubrics_config=rubrics,
        )
        for r in report.rubrics_used:
            assert "name" in r
            assert "strictness_level" in r
            assert "custom_config" in r

    def test_overall_passed_when_no_errors(self) -> None:
        sub = _sample_sub_reports()
        # Clear the only error.
        sub["schema_audit"]["passed"] = True
        sub["schema_audit"]["issues"] = []
        sub["schema_audit"]["summary"]["errors"] = 0
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        report = gen.generate_report(1, sub, rubrics)
        assert report.overall_passed is True
        assert report.errors == 0


class TestAuditReportGeneratorMarkdown:
    def test_render_markdown_contains_audit_characteristics(self) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        report = gen.generate_report(
            round_number=2,
            sub_reports=_sample_sub_reports(),
            rubrics_config=rubrics,
            worker_fixes=[
                {
                    "fix_description": "Added Supplier entity type",
                    "issue_ids_addressed": ["ISS-001"],
                    "files_modified": ["tmp/schema_definition.json"],
                }
            ],
        )
        md = gen.render_markdown(report)
        assert "# Audit Report" in md
        assert "Round 2" in md or "round 2" in md.lower()
        # Schema completeness stats.
        assert "Schema" in md
        # Graph connectivity metrics.
        assert "orphan" in md.lower() or "connectivity" in md.lower()
        # Evidence source counts.
        assert "evidence" in md.lower()
        # GraphRAG question results.
        assert "GraphRAG" in md
        # Task relevance coverage.
        assert "relevance" in md.lower() or "concern" in md.lower()
        # Issue breakdown.
        assert "error" in md.lower()
        # Worker fix traceability.
        assert "Worker" in md or "worker" in md
        assert "ISS-001" in md
        assert "Added Supplier entity type" in md

    def test_render_json_is_valid_json(self) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        report = gen.generate_report(1, _sample_sub_reports(), rubrics)
        text = gen.render_json(report)
        data = json.loads(text)
        assert data["round_number"] == 1
        assert "sub_reports" in data
        assert data["overall_passed"] is False


class TestAuditReportGeneratorSave:
    def test_save_report_creates_md_and_json(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        report = gen.generate_report(1, _sample_sub_reports(), rubrics)
        base = gen.save_report(report, output_dir=str(tmp_path))
        md_path = Path(f"{base}.md")
        json_path = Path(f"{base}.json")
        assert md_path.is_file()
        assert json_path.is_file()
        # JSON file is valid.
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["round_number"] == 1


class TestAuditHistory:
    def test_add_and_get_round(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        hist = AuditHistory(history_dir=str(tmp_path))
        report = gen.generate_report(1, _sample_sub_reports(), rubrics)
        hist.add_round(report)
        got = hist.get_round(1)
        assert got is not None
        assert got.round_number == 1
        assert hist.get_round(99) is None

    def test_get_all_rounds_sorted(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        hist = AuditHistory(history_dir=str(tmp_path))
        for rnd in (3, 1, 2):
            hist.add_round(
                gen.generate_report(rnd, _sample_sub_reports(), rubrics)
            )
        all_rounds = hist.get_all_rounds()
        assert [r.round_number for r in all_rounds] == [1, 2, 3]

    def test_persisted_as_jsonl(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        hist = AuditHistory(history_dir=str(tmp_path))
        hist.add_round(gen.generate_report(1, _sample_sub_reports(), rubrics))
        jsonl = tmp_path / "audit_history.jsonl"
        assert jsonl.is_file()
        lines = [
            ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["round_number"] == 1

    def test_issue_trace_across_rounds(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        hist = AuditHistory(history_dir=str(tmp_path))

        # Round 1: issue ISS-001 found (error).
        r1 = gen.generate_report(1, _sample_sub_reports(), rubrics)
        hist.add_round(r1)

        # Round 2: worker fixed ISS-001, no longer present.
        sub2 = _sample_sub_reports()
        sub2["schema_audit"]["passed"] = True
        sub2["schema_audit"]["issues"] = []
        sub2["schema_audit"]["summary"]["errors"] = 0
        r2 = gen.generate_report(
            2,
            sub2,
            rubrics,
            worker_fixes=[
                {
                    "fix_description": "Added Supplier type",
                    "issue_ids_addressed": ["ISS-001"],
                    "files_modified": ["tmp/schema_definition.json"],
                }
            ],
        )
        hist.add_round(r2)

        trace = hist.get_issue_trace("ISS-001")
        # Issue should appear at least once in the trace.
        assert len(trace) >= 1
        # First entry: found in round 1.
        assert trace[0]["round_number"] == 1
        # There should be a record that it was fixed.
        fixed_entries = [t for t in trace if t.get("action") == "fixed"]
        assert len(fixed_entries) >= 1
        assert fixed_entries[0]["round_number"] == 2

    def test_get_summary(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        hist = AuditHistory(history_dir=str(tmp_path))

        r1 = gen.generate_report(1, _sample_sub_reports(), rubrics)
        hist.add_round(r1)

        sub2 = _sample_sub_reports()
        sub2["schema_audit"]["passed"] = True
        sub2["schema_audit"]["issues"] = []
        sub2["schema_audit"]["summary"]["errors"] = 0
        r2 = gen.generate_report(2, sub2, rubrics)
        hist.add_round(r2)

        summary = hist.get_summary()
        assert summary["total_rounds"] == 2
        # Issue ISS-001 resolved.
        assert summary["issues_resolved"] >= 1
        # Convergence trend present.
        assert "convergence_trend" in summary

    def test_history_roundtrip_after_reload(self, tmp_path: Path) -> None:
        rubrics = RubricsConfig.load_default()
        gen = AuditReportGenerator()
        hist = AuditHistory(history_dir=str(tmp_path))
        hist.add_round(gen.generate_report(1, _sample_sub_reports(), rubrics))
        hist.add_round(gen.generate_report(2, _sample_sub_reports(), rubrics))

        # New history instance reading the same dir.
        hist2 = AuditHistory(history_dir=str(tmp_path))
        rounds = hist2.get_all_rounds()
        assert [r.round_number for r in rounds] == [1, 2]
