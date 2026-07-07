"""Climate Knowledge Graph validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from backend.knowledge_graph.entity_models import ClimateEntity, EntityType
from backend.knowledge_graph.graph_schema import is_valid_relationship
from backend.knowledge_graph.relationship_models import GraphRelationship, RelationshipType


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class GraphValidationIssue(BaseModel):
    severity: ValidationSeverity
    message: str
    entity_id: str | None = None
    relationship_id: str | None = None
    field: str | None = None


class GraphValidationResult(BaseModel):
    valid: bool = True
    issues: list[GraphValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[GraphValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]


class GraphValidator:
    """Validates entities and relationships against CKG schema rules."""

    def validate_entity(self, entity: ClimateEntity) -> GraphValidationResult:
        issues: list[GraphValidationIssue] = []

        if not entity.name.strip():
            issues.append(GraphValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Entity name must not be empty",
                entity_id=entity.entity_id,
                field="name",
            ))

        if entity.latitude is not None and not (-90.0 <= entity.latitude <= 90.0):
            issues.append(GraphValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Latitude out of range",
                entity_id=entity.entity_id,
                field="latitude",
            ))

        if entity.entity_type == EntityType.SPECIALIZED_AGENT:
            agent_id = entity.attributes.get("agent_id") or getattr(entity, "agent_id", None)
            if not agent_id:
                issues.append(GraphValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Specialized agent entity missing agent_id",
                    entity_id=entity.entity_id,
                    field="agent_id",
                ))

        valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        return GraphValidationResult(valid=valid, issues=issues)

    def validate_relationship(
        self,
        relationship: GraphRelationship,
        source: ClimateEntity | None,
        target: ClimateEntity | None,
    ) -> GraphValidationResult:
        issues: list[GraphValidationIssue] = []

        if source is None:
            issues.append(GraphValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Source entity '{relationship.source_id}' not found",
                relationship_id=relationship.relationship_id,
            ))
        if target is None:
            issues.append(GraphValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Target entity '{relationship.target_id}' not found",
                relationship_id=relationship.relationship_id,
            ))

        if source and target:
            if relationship.source_id == relationship.target_id:
                issues.append(GraphValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="Self-referential relationships are not allowed",
                    relationship_id=relationship.relationship_id,
                ))

            if not is_valid_relationship(
                source.entity_type,
                relationship.relationship_type,
                target.entity_type,
            ):
                issues.append(GraphValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Unusual relationship: {source.entity_type.value} "
                        f"-{relationship.relationship_type.value}-> {target.entity_type.value}"
                    ),
                    relationship_id=relationship.relationship_id,
                ))

        if relationship.weight < 0:
            issues.append(GraphValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Relationship weight must be non-negative",
                relationship_id=relationship.relationship_id,
                field="weight",
            ))

        valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        return GraphValidationResult(valid=valid, issues=issues)

    def validate_graph(
        self,
        entities: list[ClimateEntity],
        relationships: list[GraphRelationship],
    ) -> GraphValidationResult:
        issues: list[GraphValidationIssue] = []
        entity_map = {e.entity_id: e for e in entities}

        for entity in entities:
            result = self.validate_entity(entity)
            issues.extend(result.issues)

        for relationship in relationships:
            result = self.validate_relationship(
                relationship,
                entity_map.get(relationship.source_id),
                entity_map.get(relationship.target_id),
            )
            issues.extend(result.issues)

        valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        return GraphValidationResult(valid=valid, issues=issues)
