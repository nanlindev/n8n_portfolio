import os
import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
from langfuse import get_client, propagate_attributes
from langfuse.openai import AsyncOpenAI
from typing import List, Optional
import httpx

from observability import (
    build_failed_trace_output,
    build_propagate_metadata,
    build_trace_input,
    build_trace_output,
    classify_exception,
    content_hash,
    preview,
    truncate_for_llm,
)
from prompts import PROMPT_VERSION, build_analysis_prompt, prompt_hash

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "v2.0")

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

langfuse = get_client()
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "not-set")
logger.info(f"Langfuse host: {LANGFUSE_HOST}")
try:
    langfuse.auth_check()
    logger.info("Langfuse auth_check passed")
except Exception as exc:
    logger.warning(f"Langfuse auth_check failed: {exc}")

proxy_url = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
logger.info(f"Detected Proxy URL: {proxy_url}")

http_client = None
if proxy_url:
    transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
    http_client = httpx.AsyncClient(mounts={"all://": transport})
    logger.info("Proxy configured for AsyncOpenAI client.")
else:
    logger.info("No proxy configured, using direct connection.")

client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    http_client=http_client,
)

app = FastAPI()


class ContentItem(BaseModel):
    title: str
    content: str
    source_url: Optional[str] = None


class LocalizedTags(BaseModel):
    en: List[str]
    zh: List[str]


class AnalysisResult(BaseModel):
    category_key: str
    category_display: dict[str, str]
    summary: dict[str, str]
    sentiment: str
    tags: LocalizedTags
    priority: str


def _mark_generation_error(message: str) -> None:
    try:
        langfuse.update_current_generation(level="ERROR", status_message=message[:500])
    except Exception:
        logger.debug("No active Langfuse generation to mark as error", exc_info=True)


@app.post("/analyze", response_model=AnalysisResult)
async def analyze_content(item: ContentItem):
    logger.info(f"Received analysis request for URL: {item.source_url}")

    content_for_llm, truncated = truncate_for_llm(item.content)
    session_key = item.source_url or item.title

    with langfuse.start_as_current_observation(
        as_type="span",
        name="rss-article-analysis",
        input=build_trace_input(
            source_url=item.source_url,
            title=item.title,
            content=item.content,
        ),
    ) as root_span:
        with propagate_attributes(
            tags=["rss-filter"],
            version=SERVICE_VERSION,
            session_id=content_hash(session_key),
            metadata=build_propagate_metadata(
                source_url=item.source_url,
                title=item.title,
                content=item.content,
                truncated=truncated,
                prompt_version=PROMPT_VERSION,
                prompt_hash_value=prompt_hash(),
                model=DEEPSEEK_MODEL,
            ),
        ):
            try:
                prompt = build_analysis_prompt(item.title, content_for_llm)

                logger.info("Calling DeepSeek API...")
                completion = await client.chat.completions.create(
                    model=DEEPSEEK_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout=30,
                    name="deepseek-rss-analysis",
                    metadata={
                        "prompt_version": PROMPT_VERSION,
                        "prompt_hash": prompt_hash(),
                        "input_truncated": str(truncated).lower(),
                        "original_content_length": str(len(item.content or "")),
                    },
                )

                if not completion.choices:
                    raise ValueError("Empty response from LLM")

                raw = completion.choices[0].message.content

                with langfuse.start_as_current_observation(
                    as_type="span",
                    name="parse-and-validate",
                    input={"raw_json_preview": preview(raw, 500)},
                ) as parse_span:
                    result_json = json.loads(raw)
                    validated = AnalysisResult(**result_json)
                    trace_output = build_trace_output(result_json, "high")
                    parse_span.update(
                        output=trace_output,
                        metadata={"validation_status": "success"},
                    )

                category_tag = result_json.get("category_key", "unknown")
                root_span.set_trace_io(output=trace_output)
                root_span.update(metadata={"category_key": category_tag})
                logger.info("Successfully received and parsed LLM response.")
                return validated

            except json.JSONDecodeError as exc:
                logger.error("Failed to parse JSON from LLM response")
                root_span.set_trace_io(output=build_failed_trace_output("json_parse_error", "parse"))
                _mark_generation_error(str(exc))
                raise HTTPException(status_code=502, detail="Invalid JSON format from AI")

            except ValidationError as exc:
                logger.error("Failed to validate LLM response schema")
                root_span.set_trace_io(output=build_failed_trace_output("schema_validation_error", "parse"))
                _mark_generation_error(str(exc))
                raise HTTPException(status_code=502, detail="Invalid JSON format from AI")

            except HTTPException:
                raise

            except Exception as exc:
                error_type, error_stage, status_code = classify_exception(exc)
                logger.error(f"Analysis failed: {exc}")
                root_span.set_trace_io(output=build_failed_trace_output(error_type, error_stage))
                _mark_generation_error(str(exc))
                if status_code == 502:
                    raise HTTPException(status_code=502, detail=f"AI Provider Error: {exc}")
                raise HTTPException(status_code=500, detail=f"Internal Server Error: {exc}")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
