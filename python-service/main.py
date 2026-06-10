import os
import json
import logging
# import asyncpg # 如果暂时没用可以注释掉，避免无关报错
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from openai import AsyncOpenAI
from typing import List, Optional
import httpx  # 确保导入 httpx

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# 获取 API Key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# --- 关键修复：创建异步 HTTP 客户端并配置代理 ---
proxy_url = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
logger.info(f"Detected Proxy URL: {proxy_url}")

http_client = None
if proxy_url:
    # 必须使用 AsyncHTTPTransport 和 AsyncClient
    transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
    http_client = httpx.AsyncClient(mounts={"all://": transport})
    logger.info("Proxy configured for AsyncOpenAI client.")
else:
    logger.info("No proxy configured, using direct connection.")
# 初始化 OpenAI 客户端
client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    http_client=http_client # 传入异步客户端
)

app = FastAPI()

class ContentItem(BaseModel):
    title: str
    content: str
    source_url: Optional[str] = None

# 定义多语言输出结构
class LocalizedTags(BaseModel):
    en: List[str]
    zh: List[str]

class AnalysisResult(BaseModel):
    # 分类：保持英文键值以便程序处理，但可以提供显示名称
    category_key: str  # e.g., "tech_news", "competitor"
    category_display: dict[str, str] # {"en": "Tech News", "zh": "科技新闻"}
    summary: dict[str, str] # {"en": "...", "zh": "..."}
    # 情感：保持英文标准值
    sentiment: str # "Positive", "Negative", "Neutral"
    # 标签：双语列表
    tags: LocalizedTags
    # 优先级：保持英文标准值
    priority: str # "high", "medium", "low"

@app.post("/analyze", response_model=AnalysisResult)

async def analyze_content(item: ContentItem):
    logger.info(f"Received analysis request for URL: {item.source_url}")
    """
    使用 DeepSeek LLM 对单条内容进行清洗、分类和摘要
    """
    try:
        prompt = f"""
        You are an intelligent bilingual content analyst. Analyze the following content:
        
        Title: {item.title}
        Content: {item.content}
        
        Please provide the analysis in BOTH English and Chinese where applicable.
        
        Requirements:
        1. Category: 
           - Key: One of ['tech_news', 'competitor', 'lead', 'general']
           - Display Name: Provide both English and Chinese names.
        2. Summary: 
           - Provide a concise 2-sentence summary in BOTH English and Chinese.
        3. Sentiment: One of ['Positive', 'Negative', 'Neutral'] (English only).
        4. Tags: 
           - Provide 3-5 relevant keywords in BOTH English and Chinese lists.
        5. Priority: One of ['high', 'medium', 'low'] (English only).
           - 'high' if it contains specific company names, urgent tech trends, or high-value leads.
        
        Output ONLY valid JSON format matching this exact structure:
        {{
            "category_key": "tech_news",
            "category_display": {{
                "en": "Tech News",
                "zh": "科技新闻"
            }},
            "summary": {{
                "en": "Short English summary...",
                "zh": "简短的中文摘要..."
            }},
            "sentiment": "Positive",
            "tags": {{
                "en": ["AI", "LLM"],
                "zh": ["人工智能", "大模型"]
            }},
            "priority": "high"
        }}
        """
        
        logger.info("Calling DeepSeek API...")
        completion = await client.chat.completions.create(
            model=DEEPSEEK_MODEL, # 使用 DeepSeek 的标准聊天模型
            messages=[
                        {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
            temperature=0.1, # 低温度以保证输出格式稳定
            response_format={"type": "json_object"}, # DeepSeek 支持 JSON 模式
            timeout=30
        )
        
        if not completion.choices:
            raise ValueError("Empty response from LLM")

        result_json = json.loads(completion.choices[0].message.content)

        logger.info("Successfully received and parsed LLM response.")

        return AnalysisResult(**result_json)

    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from LLM response")
        raise HTTPException(status_code=502, detail="Invalid JSON format from AI")
    
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        # 区分是 API 错误还是其他错误
        if "status_code" in dir(e):
             raise HTTPException(status_code=502, detail=f"AI Provider Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "healthy"}