import hashlib

PROMPT_VERSION = "rss-analysis-v1.0.0"

_PROMPT_TEMPLATE = """You are an intelligent bilingual content analyst. Analyze the following content:

Title: {title}
Content: {content}

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
}}"""


def build_analysis_prompt(title: str, content: str) -> str:
    return _PROMPT_TEMPLATE.format(title=title, content=content)


def prompt_hash() -> str:
    return hashlib.sha256(_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
