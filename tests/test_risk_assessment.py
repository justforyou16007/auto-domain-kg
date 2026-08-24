"""Tests for the risk assessment module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from auto_domain_kg.risk_assessment import RiskAssessment, RiskLevel, RiskSubgraph


@pytest.fixture
def mock_neo4j():
    """Create a mock Neo4jClient."""
    client = AsyncMock()
    client.get_entity_node = AsyncMock(
        return_value={
            "name": "Test Corp",
            "risk_level": "NONE",
            "risk_reason": "",
            "risk_evidence_urls": [],
        }
    )
    client.update_entity_node = AsyncMock()
    client.multi_hop_subgraph = AsyncMock(
        return_value=[
            {
                "path": {
                    "segments": [
                        {
                            "start": {
                                "elementId": "entity-1",
                                "name": "Test Corp",
                            },
                            "end": {
                                "elementId": "entity-2",
                                "name": "Supplier A",
                            },
                            "relationship": {
                                "elementId": "rel-1",
                                "type": "SUPPLIES",
                            },
                        }
                    ]
                }
            }
        ]
    )
    client.get_entity_relationships = AsyncMock(
        return_value=[
            {
                "source": {"name": "Test Corp"},
                "relationship": {"type": "SUPPLIES"},
                "target": {"name": "Supplier A"},
            }
        ]
    )
    return client


@pytest.fixture
def risk_assessment(mock_neo4j):
    """Create a RiskAssessment with mocked Neo4j."""
    return RiskAssessment(neo4j_client=mock_neo4j)


@pytest.mark.asyncio
async def test_add_risk_field(risk_assessment, mock_neo4j):
    """Test adding a risk field to an entity."""
    await risk_assessment.add_risk_field(
        entity_id="entity-1",
        risk_level=RiskLevel.HIGH,
        reason="Entity is sole supplier of critical component.",
        evidence_urls=["https://example.com/news/1"],
    )
    mock_neo4j.update_entity_node.assert_called_once()
    call_args = mock_neo4j.update_entity_node.call_args[0]
    assert call_args[0] == "entity-1"
    properties = call_args[1]
    assert properties["risk_level"] == "HIGH"
    assert "sole supplier" in properties["risk_reason"]
    assert properties["risk_evidence_urls"] == ["https://example.com/news/1"]


@pytest.mark.asyncio
async def test_get_risk_field(risk_assessment, mock_neo4j):
    """Test getting a risk field from an entity."""
    risk_field = await risk_assessment.get_risk_field(entity_id="entity-1")
    assert risk_field is not None
    assert risk_field.level == RiskLevel.NONE
    assert risk_field.reason == ""


@pytest.mark.asyncio
async def test_get_risk_field_nonexistent(risk_assessment, mock_neo4j):
    """Test getting risk field for nonexistent entity."""
    mock_neo4j.get_entity_node = AsyncMock(return_value=None)
    risk_field = await risk_assessment.get_risk_field(entity_id="nonexistent")
    assert risk_field is None


@pytest.mark.asyncio
async def test_update_risk_after_news_scan(risk_assessment, mock_neo4j):
    """Test triggering risk reassessment after news scan."""
    await risk_assessment.update_risk_after_news_scan(entity_id="entity-1")
    mock_neo4j.update_entity_node.assert_called_once()
    call_args = mock_neo4j.update_entity_node.call_args[0]
    properties = call_args[1]
    assert properties["risk_needs_reassessment"] is True


@pytest.mark.asyncio
async def test_get_risk_subgraph(risk_assessment, mock_neo4j):
    """Test getting risk subgraph for agent traversal."""
    subgraph = await risk_assessment.get_risk_subgraph(
        entity_id="entity-1",
        hops=2,
        rel_types=["SUPPLIES"],
    )
    assert isinstance(subgraph, RiskSubgraph)
    assert subgraph.center_entity is not None
    assert len(subgraph.neighbors) >= 0
    assert subgraph.hops == 2
    mock_neo4j.multi_hop_subgraph.assert_called_once_with(
        start_entity_id="entity-1",
        hops=2,
        rel_types=["SUPPLIES"],
    )


@pytest.mark.asyncio
async def test_assess_risk_propagation(risk_assessment, mock_neo4j):
    """Test risk propagation assessment."""
    result = await risk_assessment.assess_risk_propagation(
        entity_id="entity-1",
        concern_entity_ids=["entity-2"],
        hops=3,
        rel_types=["SUPPLIES"],
    )
    assert "subgraph" in result
    assert "paths_to_concern" in result
    assert "alternative_paths" in result
    assert result["subgraph"]["center_entity"] is not None


def test_risk_level_enum():
    """Test risk level enum values."""
    assert RiskLevel.NONE.value == "NONE"
    assert RiskLevel.LOW.value == "LOW"
    assert RiskLevel.MEDIUM.value == "MEDIUM"
    assert RiskLevel.HIGH.value == "HIGH"
    assert RiskLevel.CRITICAL.value == "CRITICAL"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for new 6-step pipeline methods
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_evidence_store():
    """Create a mock EvidenceStore."""
    store = MagicMock()
    store.save_evidence_batch = MagicMock()
    store.save_evidence = MagicMock()
    return store


@pytest.fixture
def mock_graph_ops():
    """Create a mock GraphOps."""
    ops = AsyncMock()
    ops.vector_search = AsyncMock(return_value=[
        {
            "node": {"elementId": "entity-1", "name": "Test Corp"},
            "score": 0.95,
        },
        {
            "node": {"elementId": "entity-3", "name": "Supplier B"},
            "score": 0.72,
        },
    ])
    ops.multi_hop_subgraph = AsyncMock(return_value=[
        {
            "path": {
                "segments": [
                    {
                        "start": {"elementId": "entity-1", "name": "Test Corp"},
                        "end": {"elementId": "entity-2", "name": "Supplier A"},
                        "relationship": {"elementId": "rel-1", "type": "SUPPLIES"},
                    }
                ]
            }
        }
    ])
    return ops


@pytest.fixture
def risk_assessment_with_mocks(mock_neo4j, mock_graph_ops, mock_evidence_store):
    """Create a RiskAssessment with mocked Neo4j, GraphOps, and EvidenceStore."""
    return RiskAssessment(
        neo4j_client=mock_neo4j,
        graph_ops=mock_graph_ops,
        evidence_store=mock_evidence_store,
    )


@pytest.mark.asyncio
async def test_extract_events_from_news(risk_assessment_with_mocks):
    """Test event extraction from news items."""
    news_items = [
        {
            "title": "Factory Fire at Supplier A",
            "url": "https://example.com/news/factory-fire",
            "content": "A major fire broke out at Supplier A's factory.",
            "published_date": "2026-08-24",
            "source": "NewsWire",
        }
    ]
    events = await risk_assessment_with_mocks.extract_events_from_news(news_items)
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == ""
    assert event["description"] == ""
    assert event["entities_mentioned"] == []
    assert event["severity_hint"] == ""
    assert event["source_news_id"] == "https://example.com/news/factory-fire"
    assert event["source_news_title"] == "Factory Fire at Supplier A"


@pytest.mark.asyncio
async def test_associate_evidence(risk_assessment_with_mocks, mock_evidence_store):
    """Test associating evidence fragments from news to events."""
    event = {
        "event_type": "factory_fire",
        "description": "A major fire broke out at Supplier A's factory",
        "source_news_id": "https://example.com/news/factory-fire",
        "source_news_url": "https://example.com/news/factory-fire",
    }
    news_item = {
        "title": "Factory Fire at Supplier A",
        "url": "https://example.com/news/factory-fire",
        "content": "A major fire broke out at Supplier A's factory early this morning. Firefighters responded quickly and contained the blaze. Production has been halted indefinitely.",
    }

    records = await risk_assessment_with_mocks.associate_evidence(event, news_item)
    assert len(records) > 0
    assert records[0].source_url == "https://example.com/news/factory-fire"
    assert records[0].source_title == "Factory Fire at Supplier A"
    assert "fire" in records[0].text_slice.lower()
    assert "evidence_records" in event
    mock_evidence_store.save_evidence_batch.assert_called_once()


@pytest.mark.asyncio
async def test_graphrag_event_search(risk_assessment_with_mocks, mock_graph_ops):
    """Test GraphRAG event-to-node search."""
    results = await risk_assessment_with_mocks.graphrag_event_search(
        event_description="A major fire broke out at Supplier A's factory",
        top_k=10,
    )
    assert len(results) == 2
    assert results[0]["node"]["name"] == "Test Corp"
    assert results[0]["score"] == 0.95
    assert "subgraph" in results[0]
    mock_graph_ops.vector_search.assert_called_once_with(
        query_text="A major fire broke out at Supplier A's factory",
        top_k=10,
    )


@pytest.mark.asyncio
async def test_graphrag_event_search_no_graph_ops(mock_neo4j):
    """Test GraphRAG search returns empty when no GraphOps provided."""
    ra = RiskAssessment(neo4j_client=mock_neo4j)
    results = await ra.graphrag_event_search(
        event_description="Some event",
        top_k=10,
    )
    assert results == []


@pytest.mark.asyncio
async def test_trace_dag_impact(risk_assessment_with_mocks, mock_neo4j):
    """Test DAG impact tracing."""
    mock_neo4j.execute_custom_query = AsyncMock(return_value=[
        {
            "path": {
                "segments": [
                    {
                        "start": {"elementId": "entity-1", "name": "Test Corp"},
                        "end": {"elementId": "entity-2", "name": "Supplier A"},
                    },
                    {
                        "start": {"elementId": "entity-2", "name": "Supplier A"},
                        "end": {"elementId": "entity-4", "name": "Sub-supplier X"},
                    },
                ]
            }
        }
    ])

    result = await risk_assessment_with_mocks.trace_dag_impact(
        affected_node_ids=["entity-1", "entity-3"],
        max_hops=5,
    )
    assert "propagation_paths" in result
    assert "downstream_nodes" in result
    assert "impact_map" in result
    assert len(result["propagation_paths"]) > 0
    assert len(result["downstream_nodes"]) > 0
    mock_neo4j.execute_custom_query.assert_called()


@pytest.mark.asyncio
async def test_generate_report(tmp_path, risk_assessment_with_mocks):
    """Test report generation from template."""
    # Create a template file
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "test_domain_report_template.md"
    template_path.write_text(
        "# {{domain}} Risk Report\n\nDate: {{date}}\n\n## Events\n{{events_summary}}\n\n## Risk\n{{risk_assessment}}",
        encoding="utf-8",
    )

    output_path = tmp_path / "reports" / "2026-08-24_test_risk_report.md"
    context = {
        "date": "2026-08-24",
        "domain": "test",
        "events_summary": "- Factory fire at Supplier A",
        "affected_nodes": "None",
        "impact_paths": "None",
        "risk_assessment": "HIGH",
        "evidence": "Text snippet...",
        "mitigation_suggestions": "Review alternatives.",
    }

    result = await risk_assessment_with_mocks.generate_report(
        template_path=str(template_path),
        output_path=str(output_path),
        context=context,
    )
    assert result == str(output_path)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "test" in content
    assert "2026-08-24" in content
    assert "Factory fire" in content
    assert "HIGH" in content


@pytest.mark.asyncio
async def test_run_full_analysis(risk_assessment_with_mocks, mock_neo4j, mock_graph_ops, tmp_path):
    """Test the full 6-step analysis pipeline."""
    # Create a template file
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "default_domain_report_template.md"
    template_path.write_text(
        "# {{domain}}\nDate: {{date}}\n## Events\n{{events_summary}}\n## Nodes\n{{affected_nodes}}\n## Risk\n{{risk_assessment}}",
        encoding="utf-8",
    )

    # Override template path for the test
    ra = risk_assessment_with_mocks

    news_items = [
        {
            "title": "Factory Fire at Supplier A",
            "url": "https://example.com/news/factory-fire",
            "content": "A major fire broke out at Supplier A's factory early this morning. Production has been halted indefinitely.",
            "published_date": "2026-08-24",
            "source": "NewsWire",
        }
    ]

    mock_neo4j.execute_custom_query = AsyncMock(return_value=[
        {
            "path": {
                "segments": [
                    {
                        "start": {"elementId": "entity-1", "name": "Test Corp"},
                        "end": {"elementId": "entity-2", "name": "Supplier A"},
                    }
                ]
            }
        }
    ])

    report_path = await ra.run_full_analysis(
        news_items=news_items,
        domain="test_domain",
        template_path=str(template_path),
    )
    assert report_path is not None
    assert "test_domain" in report_path
    assert "risk_report" in report_path
    # The report should be in the reports/ dir
    assert Path(report_path).exists()


@pytest.mark.asyncio
async def test_derive_risk_level(risk_assessment_with_mocks):
    """Test the _derive_risk_level method."""
    # Test NONE
    level = risk_assessment_with_mocks._derive_risk_level(
        {}, {"downstream_nodes": []}
    )
    assert "NONE" in level

    # Test LOW
    level = risk_assessment_with_mocks._derive_risk_level(
        {"a": {"node": {}}}, {"downstream_nodes": ["x"]}
    )
    assert "LOW" in level

    # Test MEDIUM
    level = risk_assessment_with_mocks._derive_risk_level(
        {"a": {"node": {}}, "b": {"node": {}}},
        {"downstream_nodes": ["x", "y", "z"]},
    )
    assert "MEDIUM" in level

    # Test HIGH
    level = risk_assessment_with_mocks._derive_risk_level(
        {"a": {}, "b": {}, "c": {}, "d": {}},
        {"downstream_nodes": ["x", "y", "z", "w", "v", "u"]},
    )
    assert "HIGH" in level

    # Test CRITICAL
    level = risk_assessment_with_mocks._derive_risk_level(
        {"a": {}, "b": {}, "c": {}, "d": {}, "e": {}, "f": {}},
        {"downstream_nodes": ["x", "y", "z", "w", "v", "u", "t", "s", "r", "q", "p"]},
    )
    assert "CRITICAL" in level