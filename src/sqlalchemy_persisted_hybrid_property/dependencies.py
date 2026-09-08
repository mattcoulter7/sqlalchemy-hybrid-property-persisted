from __future__ import annotations

# ruff: noqa: D100,D101,D102,D103,D107
from collections import deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Mapper, RelationshipProperty

from .exceptions import DependencyAmbiguityError, DependencyConfigurationError


@dataclass(frozen=True)
class DependencyStep:
    relationship: RelationshipProperty[Any]
    reverse: bool = False


@dataclass(frozen=True)
class DependencyPath:
    steps: tuple[DependencyStep, ...]


class DependencyGraph:
    def __init__(self, edges: dict[Mapper[Any], tuple[DependencyStep, ...]]):
        self._edges = edges

    @classmethod
    def from_mappers(cls, mappers: list[Mapper[Any]] | tuple[Mapper[Any], ...]):
        edges: dict[Mapper[Any], list[DependencyStep]] = {mapper: [] for mapper in mappers}
        for mapper in mappers:
            for relationship in mapper.relationships:
                edges.setdefault(mapper, []).append(DependencyStep(relationship, reverse=False))
                has_forward_back = any(candidate.mapper is mapper for candidate in relationship.mapper.relationships)
                if not has_forward_back:
                    edges.setdefault(relationship.mapper, []).append(DependencyStep(relationship, reverse=True))
        return cls({mapper: tuple(steps) for mapper, steps in edges.items()})

    def path(self, from_mapper: Mapper[Any], to_mapper: Mapper[Any]) -> DependencyPath:
        if from_mapper is to_mapper:
            return DependencyPath(())

        queue = deque([(from_mapper, ())])
        shortest_depth: int | None = None
        paths: list[tuple[DependencyStep, ...]] = []
        seen_depth: dict[Mapper[Any], int] = {from_mapper: 0}

        while queue:
            mapper, steps = queue.popleft()
            if shortest_depth is not None and len(steps) >= shortest_depth:
                continue

            for step in self._edges.get(mapper, ()):
                next_mapper = step.relationship.parent if step.reverse else step.relationship.mapper
                next_steps = (*steps, step)
                if next_mapper is to_mapper:
                    shortest_depth = len(next_steps)
                    paths.append(next_steps)
                    continue
                if seen_depth.get(next_mapper, 10**9) < len(next_steps):
                    continue
                seen_depth[next_mapper] = len(next_steps)
                queue.append((next_mapper, next_steps))

        if not paths:
            raise DependencyConfigurationError(
                f"No relationship path from {from_mapper.class_.__name__} to {to_mapper.class_.__name__}"
            )
        if len(paths) > 1:
            raise DependencyAmbiguityError(
                f"Ambiguous dependency path from {from_mapper.class_.__name__} to {to_mapper.class_.__name__}"
            )
        return DependencyPath(paths[0])

    def validate_explicit_path(
        self, owner_mapper: Mapper[Any], path: str
    ) -> tuple[Mapper[Any], DependencyPath, str | None]:
        mapper = owner_mapper
        steps: list[DependencyStep] = []
        parts = path.split(".")
        if not parts:
            raise DependencyConfigurationError("Dependency path cannot be empty")

        column_key: str | None = None
        for index, part in enumerate(parts):
            if part not in mapper.attrs:
                raise DependencyConfigurationError(f"{mapper.class_.__name__}.{part} is missing")
            attr = mapper.attrs[part]
            if isinstance(attr, RelationshipProperty):
                steps.append(DependencyStep(attr, reverse=False))
                mapper = attr.mapper
                continue
            if index != len(parts) - 1:
                raise DependencyConfigurationError(f"{mapper.class_.__name__}.{part} is not a relationship")
            column_key = part
        changed_to_owner = tuple(
            DependencyStep(step.relationship, reverse=not step.reverse) for step in reversed(steps)
        )
        return mapper, DependencyPath(changed_to_owner), column_key


def all_configured_mappers(start: Mapper[Any]) -> tuple[Mapper[Any], ...]:
    registry = start.registry
    return tuple(inspect(mapper.class_) for mapper in registry.mappers)
