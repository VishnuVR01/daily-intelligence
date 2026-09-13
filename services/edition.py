from dataclasses import dataclass
from datetime import date


@dataclass
class DailyEdition:
    edition_date: date
    title: str


def edition_title(for_date: date) -> str:
    return f"Daily Intelligence Brief — {for_date:%A, %d %B %Y}"
