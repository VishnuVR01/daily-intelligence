from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ingestion.rss import FeedItem


class CollectionStatus(str, Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    SKIPPED_INACTIVE = "SKIPPED_INACTIVE"
    SKIPPED_UNSUPPORTED = "SKIPPED_UNSUPPORTED"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"


@dataclass
class CollectorResult:
    status: CollectionStatus
    items: list[FeedItem] = field(default_factory=list)
    error_message: str | None = None
