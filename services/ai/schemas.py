from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


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
    is_relevant: bool = Field(description="True if article is strategically relevant to Daily Intelligence scope, false if out of scope")
    primary_category: Optional[str] = Field(default=None, description="Allowed category if is_relevant=true, null if is_relevant=false")
    rejection_reason: Optional[str] = Field(default=None, description="Concise reason why article is out of scope if is_relevant=false, null if is_relevant=true")
    topics: List[str] = Field(default_factory=list, description="Key topics identified in article")
    countries: List[str] = Field(default_factory=list, description="Countries referenced in article")
    entities: List[EntityItem] = Field(default_factory=list, description="Extracted entities")
    summary: str = Field(default="", description="Concise 2-3 sentence factual summary")
    importance_score: int = Field(default=0, description="Global significance score from 0 to 100")
    relevance_score: int = Field(default=0, description="Relevance to Daily Intelligence editorial interests from 0 to 100")
    event_type: str = Field(default="general_news", description="Type of event reported")

    @field_validator("importance_score", "relevance_score")
    @classmethod
    def validate_score_range(cls, v: int) -> int:
        if not (0 <= v <= 100):
            raise ValueError(f"Score {v} is out of allowed range [0, 100]")
        return v

    @model_validator(mode="after")
    def validate_relevance_and_category(self) -> "ArticleAIAnalysis":
        if self.is_relevant:
            if not self.primary_category or not self.primary_category.strip():
                raise ValueError("primary_category is required when is_relevant is true")
            v_stripped = self.primary_category.strip()
            matched = next((cat for cat in ALLOWED_CATEGORIES if cat.lower() == v_stripped.lower()), None)
            if not matched:
                raise ValueError(f"Category '{self.primary_category}' is invalid. Must be one of: {ALLOWED_CATEGORIES}")
            self.primary_category = matched
            self.rejection_reason = None
        else:
            self.primary_category = None
            if not self.rejection_reason or not self.rejection_reason.strip():
                self.rejection_reason = "Article content is outside Daily Intelligence editorial scope"
            else:
                self.rejection_reason = self.rejection_reason.strip()
        return self
