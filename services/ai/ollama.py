import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.config import get_settings
from services.ai.schemas import ALLOWED_CATEGORIES, ArticleAIAnalysis

logger = logging.getLogger("services.ai.ollama")


@dataclass
class OllamaAnalysisResult:
    analysis: Optional[ArticleAIAnalysis] = None
    raw_output: Optional[Dict[str, Any]] = None
    status: str = "success"  # "success", "failed", "invalid_json", "unavailable", "timeout"
    processing_ms: int = 0
    error_message: Optional[str] = None
    done_reason: Optional[str] = None
    eval_count: Optional[int] = None


SYSTEM_PROMPT_TEMPLATE = """You are an expert editorial intelligence analyst for Daily Intelligence Newspaper.
Your task is to analyze the supplied article and output a structured JSON analysis.

CRITICAL INSTRUCTIONS:
1. Analyze ONLY the supplied article content. Do not invent facts, entities, or countries.
2. Preserve uncertainty where information is incomplete or unclear.
3. Choose EXACTLY ONE primary_category from this allowed list:
   - World
   - Geopolitics
   - Business
   - Markets & Economy
   - AI & Technology
   - Industry & Operations
   - Supply Chain & Trade
   - Energy
   - Sustainability
   - Research

4. Provide a factual summary of maximum 2-3 concise sentences.
5. Provide an importance_score (0-100 integer) according to this rubric:
   - 0-20: minor / niche
   - 21-40: useful but limited significance
   - 41-60: material sector or national development
   - 61-80: major company / industry / economic / geopolitical event
   - 81-100: major international development

6. Provide a relevance_score (0-100 integer) measuring relevance to Daily Intelligence editorial interests (global news, macroeconomics, tech, energy, supply chain, geopolitics, industrial operations).

7. Output ONLY a valid JSON object matching this schema structure:
{
  "primary_category": "string (one of allowed categories)",
  "topics": ["string"],
  "countries": ["string"],
  "entities": [{"name": "string", "type": "string"}],
  "summary": "string (2-3 concise factual sentences)",
  "importance_score": int (0-100),
  "relevance_score": int (0-100),
  "event_type": "string"
}

Return the JSON object immediately. Do not include explanations, markdown, commentary, or reasoning.
"""


class OllamaService:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        prompt_version: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model or "qwen3.5:4b"
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds or 120
        self.prompt_version = prompt_version or settings.ai_prompt_version or "v1"

    def check_health(self) -> bool:
        """Returns True if local Ollama API server is reachable."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception as exc:
            logger.warning(f"Ollama health check failed: {exc}")
            return False

    def check_model_available(self, model_name: Optional[str] = None) -> bool:
        """Returns True if the target model is installed in Ollama."""
        target_model = model_name or self.model
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Check exact or prefix match (e.g. qwen3.5:4b vs qwen3.5:4b-latest)
                    return any(m == target_model or m.startswith(f"{target_model}:") for m in models)
            return False
        except Exception as exc:
            logger.warning(f"Ollama model check failed for '{target_model}': {exc}")
            return False

    def prepare_article_prompt(self, article_data: Dict[str, Any]) -> str:
        """Constructs safe user prompt with text truncation to ~3,000 chars."""
        headline = article_data.get("title", "").strip()
        source_name = article_data.get("source_name", "Unknown Source")
        source_family = article_data.get("source_family", "news")
        pub_time = article_data.get("published_at") or article_data.get("collected_at") or "Unknown"

        # Prefer extracted_text if available and valid (> 50 chars), else raw_summary
        extracted = article_data.get("extracted_text") or ""
        raw_summary = article_data.get("raw_summary") or ""

        content_text = extracted if len(extracted.strip()) > 50 else raw_summary

        # Truncate content text safely to ~3,000 chars (~600-750 words)
        if len(content_text) > 3000:
            content_text = content_text[:3000] + "\n...[truncated for AI processing]"

        prompt = f"""ARTICLE FOR ANALYSIS:
Headline: {headline}
Source: {source_name} (Family: {source_family})
Published: {pub_time}

CONTENT:
{content_text}
"""
        return prompt

    def analyze_article(
        self, article_data: Dict[str, Any], model_override: Optional[str] = None
    ) -> OllamaAnalysisResult:
        """
        Sends article analysis request to Ollama and validates response against ArticleAIAnalysis.
        Safe failure isolation: returns OllamaAnalysisResult with status and error message instead of raising.
        """
        start_time = time.time()
        target_model = model_override or self.model
        art_id = article_data.get("id", "Unknown")
        logger.info(f"Sending request to Ollama for article ID {art_id} ({article_data.get('title', '')[:30]}...)...")

        user_prompt = self.prepare_article_prompt(article_data)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": "{"},
        ]

        payload = {
            "model": target_model,
            "messages": messages,
            "format": ArticleAIAnalysis.model_json_schema(),
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 1024,
                "think": False,
            },
        }

        try:
            url = f"{self.base_url}/api/chat"
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                processing_ms = int((time.time() - start_time) * 1000)
                if response.status != 200:
                    return OllamaAnalysisResult(
                        status="failed",
                        processing_ms=processing_ms,
                        error_message=f"HTTP {response.status} from Ollama API",
                    )

                res_data = json.loads(response.read().decode("utf-8"))
                done = res_data.get("done", True)
                done_reason = res_data.get("done_reason", "unknown")
                prompt_eval_count = res_data.get("prompt_eval_count", 0)
                eval_count = res_data.get("eval_count", 0)
                total_duration = res_data.get("total_duration", 0)

                msg_obj = res_data.get("message", {})
                raw_content = msg_obj.get("content", "").strip()
                thinking_content = msg_obj.get("thinking") or res_data.get("thinking") or ""

                # Check for explicit empty output or done_reason == "length" truncation failure
                if done_reason == "length" or not raw_content:
                    logger.warning(
                        f"Ollama generation failure for article {art_id}: "
                        f"HTTP status={response.status}, done={done}, done_reason='{done_reason}', "
                        f"prompt_eval_count={prompt_eval_count}, eval_count={eval_count}, "
                        f"content_len={len(raw_content)}, thinking_len={len(thinking_content)}, "
                        f"total_duration={total_duration}"
                    )
                    err_msg = (
                        f"Ollama generation ended with done_reason='{done_reason}' and empty content"
                        if not raw_content
                        else f"Ollama output truncated by token length limit (done_reason='{done_reason}')"
                    )
                    return OllamaAnalysisResult(
                        status="failed",
                        processing_ms=processing_ms,
                        error_message=err_msg,
                        done_reason=done_reason,
                        eval_count=eval_count,
                    )

                # Clean markdown backticks if returned (e.g. ```json ... ```)
                cleaned_content = raw_content
                if cleaned_content.startswith("```"):
                    lines = cleaned_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    cleaned_content = "\n".join(lines).strip()

                if not cleaned_content.startswith("{"):
                    cleaned_content = "{" + cleaned_content

                try:
                    analysis = ArticleAIAnalysis.model_validate_json(cleaned_content)
                    raw_dict = json.loads(cleaned_content)
                    return OllamaAnalysisResult(
                        analysis=analysis,
                        raw_output=raw_dict,
                        status="success",
                        processing_ms=processing_ms,
                        done_reason=done_reason,
                        eval_count=eval_count,
                    )
                except Exception as val_err:
                    top_keys = list(res_data.keys())
                    logger.warning(
                        f"Ollama parsing failed for article {art_id}: "
                        f"done_reason='{done_reason}', HTTP status={response.status}, "
                        f"top_level_keys={top_keys}, content_len={len(raw_content)}, "
                        f"thinking_len={len(thinking_content)}"
                    )
                    try:
                        raw_dict = json.loads(cleaned_content)
                        return OllamaAnalysisResult(
                            raw_output=raw_dict,
                            status="invalid_json",
                            processing_ms=processing_ms,
                            error_message=f"Schema validation error: {val_err}",
                            done_reason=done_reason,
                            eval_count=eval_count,
                        )
                    except Exception as json_err:
                        return OllamaAnalysisResult(
                            status="invalid_json",
                            processing_ms=processing_ms,
                            error_message=f"Invalid JSON content (done_reason='{done_reason}', content_len={len(raw_content)}, thinking_len={len(thinking_content)}): {json_err}",
                            done_reason=done_reason,
                            eval_count=eval_count,
                        )

        except urllib.error.URLError as url_err:
            processing_ms = int((time.time() - start_time) * 1000)
            if "timed out" in str(url_err).lower():
                return OllamaAnalysisResult(
                    status="timeout",
                    processing_ms=processing_ms,
                    error_message=f"Request timed out after {self.timeout_seconds}s",
                )
            return OllamaAnalysisResult(
                status="unavailable",
                processing_ms=processing_ms,
                error_message=f"Ollama API unavailable: {url_err}",
            )
        except Exception as exc:
            processing_ms = int((time.time() - start_time) * 1000)
            return OllamaAnalysisResult(
                status="failed",
                processing_ms=processing_ms,
                error_message=f"Unexpected error: {exc}",
            )
