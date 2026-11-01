from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ProfessionalCandidate:
    professional_id: UUID
    future_seconds: float
    first_available: datetime


class SelectionStrategy(Protocol):
    name: str

    def order(self, candidates: list[ProfessionalCandidate]) -> list[ProfessionalCandidate]: ...


class LeastFutureLoad:
    name = "LeastFutureLoad/v1"

    def order(self, candidates: list[ProfessionalCandidate]) -> list[ProfessionalCandidate]:
        return sorted(
            candidates,
            key=lambda item: (item.future_seconds, item.first_available, str(item.professional_id)),
        )
