from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Any

from domain.event.direction import Direction


@dataclass
class AggregatedGroup:
    event_type: str
    asset: Optional[str]
    events: list[Any]
    direction: Direction
    avg_strength: float
    source_count: int
    source_diversity: float

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def unique_sources(self) -> set[str]:
        sources = set()
        for e in self.events:
            if hasattr(e, 'sources'):
                sources.update(e.sources)
            elif isinstance(e, dict) and 'sources' in e:
                sources.update(e['sources'])
        return sources


class EventAggregator:
    def __init__(self, min_events: int = 1):
        self.min_events = min_events

    def aggregate(self, events: list[Any]) -> list[AggregatedGroup]:
        grouped: dict[tuple[str, Optional[str]], list[Any]] = defaultdict(list)

        for event in events:
            event_type = event.event_type if hasattr(event, 'event_type') else event.get('event_type') if isinstance(event, dict) else None
            asset = event.asset if hasattr(event, 'asset') else event.get('asset') if isinstance(event, dict) else None
            if event_type is None:
                continue
            key = (event_type, asset)
            grouped[key].append(event)

        results = []
        for (event_type, asset), event_list in grouped.items():
            if len(event_list) < self.min_events:
                continue

            group = self._create_group(event_type, asset, event_list)
            if group:
                results.append(group)

        return results

    def _create_group(
        self,
        event_type: str,
        asset: Optional[str],
        events: list[Any]
    ) -> Optional[AggregatedGroup]:
        if not events:
            return None

        directions = []
        for e in events:
            if hasattr(e, 'direction'):
                d = e.direction
            elif isinstance(e, dict):
                d = e.get('direction', 'neutral')
            else:
                d = 'neutral'
            if isinstance(d, str):
                d = Direction(d)
            directions.append(d)

        direction = self._resolve_direction(directions)

        strengths = []
        for e in events:
            if hasattr(e, 'strength'):
                strengths.append(e.strength)
            elif isinstance(e, dict):
                strengths.append(e.get('strength', 0.5))
            else:
                strengths.append(0.5)
        avg_strength = sum(strengths) / len(strengths)

        sources = set()
        for e in events:
            if hasattr(e, 'sources'):
                sources.update(e.sources)
            elif isinstance(e, dict) and 'sources' in e:
                sources.update(e['sources'])
        source_count = len(sources)
        source_diversity = min(source_count / 4, 1.0)

        return AggregatedGroup(
            event_type=event_type,
            asset=asset,
            events=events,
            direction=direction,
            avg_strength=avg_strength,
            source_count=source_count,
            source_diversity=source_diversity,
        )

    def _resolve_direction(self, directions: list[Direction]) -> Direction:
        bullish = directions.count(Direction.BULLISH)
        bearish = directions.count(Direction.BEARISH)

        if bullish > bearish:
            return Direction.BULLISH
        elif bearish > bullish:
            return Direction.BEARISH
        return Direction.NEUTRAL

    def resolve_conflict(self, groups: list[AggregatedGroup]) -> AggregatedGroup | None:
        if not groups:
            return None

        direction_scores: dict[Direction, float] = {
            Direction.BULLISH: 0.0,
            Direction.BEARISH: 0.0,
            Direction.NEUTRAL: 0.0,
        }

        for group in groups:
            direction_scores[group.direction] += group.avg_strength * group.event_count

        dominant = max(direction_scores, key=direction_scores.get)

        filtered = [g for g in groups if g.direction == dominant]
        if not filtered:
            return None

        return self._merge_groups(filtered, dominant)

    def _merge_groups(self, groups: list[AggregatedGroup], direction: Direction) -> AggregatedGroup:
        all_events = []
        for g in groups:
            all_events.extend(g.events)

        assets = set(g.asset for g in groups if g.asset)
        event_types = set(g.event_type for g in groups)

        total_strength = sum(g.avg_strength * g.event_count for g in groups)
        total_count = sum(g.event_count for g in groups)
        avg_strength = total_strength / total_count if total_count > 0 else 0.5

        all_sources = set()
        for g in groups:
            all_sources.update(g.unique_sources)

        return AggregatedGroup(
            event_type=", ".join(sorted(event_types)),
            asset=", ".join(sorted(assets)) if assets else None,
            events=all_events,
            direction=direction,
            avg_strength=avg_strength,
            source_count=len(all_sources),
            source_diversity=min(len(all_sources) / 4, 1.0),
        )
