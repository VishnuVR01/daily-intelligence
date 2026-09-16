"""
Stage 4B Entity Extraction Parser.
Parses structured entity mentions from existing ArticleAIOutput.output_json without introducing new LLM calls.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from app.models import ArticleAIOutput


@dataclass
class RawEntityMention:
    surface_name: str
    raw_type: str
    article_id: int
    context_snippet: Optional[str] = None
    source_field: str = "entities"


def extract_raw_entity_mentions(ai_output: ArticleAIOutput) -> List[RawEntityMention]:
    """
    Extracts raw entity mentions from ArticleAIOutput.output_json.
    Robust against missing, null, dictionary, list, or unexpected structures.
    """
    if not ai_output or not ai_output.article_id:
        return []

    output_json = ai_output.output_json
    if not output_json or not isinstance(output_json, dict):
        return []

    raw_mentions: List[RawEntityMention] = []

    # 1. Parse 'entities' list
    entities_data = output_json.get("entities", [])
    if isinstance(entities_data, list):
        for item in entities_data:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                raw_type = str(item.get("type", "UNKNOWN")).strip()
                context = item.get("context")
            elif isinstance(item, str):
                name = item.strip()
                raw_type = "UNKNOWN"
                context = None
            else:
                continue

            if name and len(name) > 1:
                raw_mentions.append(
                    RawEntityMention(
                        surface_name=name,
                        raw_type=raw_type,
                        article_id=ai_output.article_id,
                        context_snippet=context if isinstance(context, str) else None,
                        source_field="entities",
                    )
                )

    # 2. Parse 'countries' list if present
    countries_data = output_json.get("countries", [])
    if isinstance(countries_data, list):
        for cname in countries_data:
            if isinstance(cname, str) and cname.strip():
                name = cname.strip()
                # Avoid duplicate if already present in entities
                if not any(m.surface_name.lower() == name.lower() for m in raw_mentions):
                    raw_mentions.append(
                        RawEntityMention(
                            surface_name=name,
                            raw_type="Country",
                            article_id=ai_output.article_id,
                            context_snippet=None,
                            source_field="countries",
                        )
                    )

    return raw_mentions


def parse_entities_from_ai_output(output_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convenience helper to extract raw entity dicts from a raw output_json dictionary.
    """
    dummy_output = ArticleAIOutput(article_id=999999, output_json=output_json)
    mentions = extract_raw_entity_mentions(dummy_output)
    return [
        {
            "raw_name": m.surface_name,
            "raw_type": m.raw_type,
            "context_snippet": m.context_snippet,
            "source_field": m.source_field,
        }
        for m in mentions
    ]

