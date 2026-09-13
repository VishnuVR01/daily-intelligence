from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


ALLOWED_CATEGORIES = [
    "World",
    "Geopolitics",
    "Business",
    "Markets & Economy",
    "AI & Technology",
    "Industry & Operations",
    "Supply Chain & Trade",
    "Energy",
    "Sustainability",
    "Research",
]


class EntityItem(BaseModel):
    name: str
    type: str = Field(default="organization", description="Type of entity, e.g. company, university, government, person, institution")


class ArticleAIAnalysis(BaseModel):
    primary_category: str = Field(description="Must be one of the allowed categories")
    topics: List[str] = Field(default_factory=list, description="Key topics identified in article")
    countries: List[str] = Field(default_factory=list, description="Countries referenced in article")
    entities: List[EntityItem] = Field(default_factory=list, description="Extracted entities")
    summary: str = Field(description="Concise 2-3 sentence factual summary")
    importance_score: int = Field(description="Global significance score from 0 to 100")
    relevance_score: int = Field(description="Relevance to Daily Intelligence editorial interests from 0 to 100")
    event_type: str = Field(default="general_news", description="Type of event reported")

    @field_validator("primary_category")
    @classmethod
    def validate_primary_category(cls, v: str) -> str:
        if not v:
            raise ValueError("primary_category cannot be empty")
        v_stripped = v.strip()
        matched = next((cat for cat in ALLOWED_CATEGORIES if cat.lower() == v_stripped.lower()), None)
        if not matched:
            raise ValueError(f"Category '{v}' is invalid. Must be one of: {ALLOWED_CATEGORIES}")
        return matched

    @field_validator("importance_score", "relevance_score")
    @classmethod
    def validate_score_range(cls, v: int) -> int:
        if not (0 <= v <= 100):
            raise ValueError(f"Score {v} is out of allowed range [0, 100]")
        return v
