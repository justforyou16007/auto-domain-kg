"""Tests for the risk assessment module."""

from __future__ import annotations

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