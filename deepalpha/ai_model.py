# -*- coding: utf-8 -*-
"""
X 实时情报系统 - AI 模型接口
================================================
统一的大模型调用接口，支持多种后端：
  - OpenAI API (GPT-4, GPT-3.5)
  - 本地模型 (Ollama, LM Studio)
  - 其他兼容 API

使用方式：
  from deepalpha.ai_model import AIModel
  
  ai = AIModel()  # 自动检测可用后端
  response = ai.chat("分析这段文本...")
"""

import os
import json
import logging
import requests
from typing import Optional, List, Dict, Any


class AIModel:
    """统一的 AI 模型接口"""

    def __init__(self, backend: str = "auto", model: str = None, api_key: str = None, base_url: str = None):
        """
        初始化 AI 模型

        Args:
            backend: 后端类型 "openai" | "ollama" | "lmstudio" | "auto"
            model: 模型名称
            api_key: API 密钥（OpenAI 需要）
            base_url: 自定义 API 地址
        """
        self.backend = backend
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url

        if backend == "auto":
            self.backend = self._detect_backend()

        if not self.model:
            self.model = self._get_default_model()

        if not self.base_url:
            self.base_url = self._get_default_url()

        self.conversation_history: List[Dict] = []

    def _detect_backend(self) -> str:
        """自动检测可用的后端"""
        if self.api_key:
            return "openai"

        ollama_url = "http://localhost:11434"
        try:
            resp = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                return "ollama"
        except:
            pass

        lmstudio_url = "http://localhost:1234"
        try:
            resp = requests.get(f"{lmstudio_url}/v1/models", timeout=2)
            if resp.status_code == 200:
                return "lmstudio"
        except:
            pass

        return "openai"

    def _get_default_model(self) -> str:
        """获取默认模型"""
        defaults = {
            "openai": "gpt-4o-mini",
            "ollama": "llama3",
            "lmstudio": "local-model",
        }
        return defaults.get(self.backend, "gpt-4o-mini")

    def _get_default_url(self) -> str:
        """获取默认 API 地址"""
        urls = {
            "openai": "https://api.openai.com/v1",
            "ollama": "http://localhost:11434",
            "lmstudio": "http://localhost:1234/v1",
        }
        return urls.get(self.backend, "https://api.openai.com/v1")

    def chat(self, message: str, system_prompt: str = None, temperature: float = 0.7,
             max_tokens: int = 2000, json_mode: bool = False) -> str:
        """
        发送聊天请求

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            json_mode: 是否返回 JSON 格式

        Returns:
            模型响应文本
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": message})

        if self.backend == "ollama":
            return self._chat_ollama(messages, temperature, max_tokens, json_mode)
        else:
            return self._chat_openai(messages, temperature, max_tokens, json_mode)

    def _chat_openai(self, messages: List[Dict], temperature: float,
                     max_tokens: int, json_mode: bool) -> str:
        """OpenAI 兼容 API 调用"""
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            return f"AI 调用失败: {str(e)}"

    def _chat_ollama(self, messages: List[Dict], temperature: float,
                     max_tokens: int, json_mode: bool) -> str:
        """Ollama API 调用"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except requests.exceptions.RequestException as e:
            return f"AI 调用失败: {str(e)}"

    def chat_json(self, message: str, system_prompt: str = None,
                  temperature: float = 0.7, max_tokens: int = 2000) -> Dict:
        """
        发送聊天请求并返回 JSON

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            解析后的 JSON 字典
        """
        response = self.chat(
            message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True
        )

        try:
            if response.startswith("AI 调用失败"):
                return {"error": response}
            return json.loads(response)
        except json.JSONDecodeError:
            return {"error": f"JSON 解析失败: {response[:200]}"}

    def add_to_history(self, role: str, content: str):
        """添加消息到历史记录"""
        self.conversation_history.append({"role": role, "content": content})

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []

    def is_available(self) -> bool:
        """检查模型是否可用"""
        try:
            response = self.chat("Hi", max_tokens=10)
            return not response.startswith("AI 调用失败")
        except:
            return False


_system_prompt_decision = """你是一个金融市场情报分析专家。用户会问你各种问题，你需要分析问题并输出结构化的抓取决策。

你的任务是：
1. 识别问题涉及的核心资产（oil/gold/fx/crypto/equity/macro/geopolitics/general）
2. 判断当前市场阶段（supply_risk/demand_risk/policy_risk/war_risk/dollar_risk/risk_sentiment）
3. 识别用户意图（direction/magnitude/timing/event_risk/general）
4. 判断紧急程度（critical/high/normal）
5. 推荐最相关的 Twitter 账号（最多5个）
6. 生成搜索关键词（最多5个事件短语）
7. 生成 X 搜索语句（最多2条）

请以 JSON 格式输出，格式如下：
{
    "asset": "资产类型",
    "current_regime": "市场阶段",
    "user_intent": "用户意图",
    "urgency": "紧急程度",
    "top_accounts": ["@账号1", "@账号2", ...],
    "top_event_phrases": ["关键词1", "关键词2", ...],
    "crawl_tasks": ["搜索语句1", "搜索语句2"],
    "why_this_route": "决策理由"
}

注意：
- 对于一般性问题（如"今天天气怎么样"），asset 设为 "general"，返回空列表
- 对于金融/市场相关问题，给出具体的抓取建议
- 账号推荐优先级：官方机构 > 通讯社 > 一线记者 > 分析师
"""

_system_prompt_clean = """你是一个金融情报清洗专家。你会收到一条推文，需要判断其情报价值。

请分析并输出 JSON：
{
    "is_relevant": true/false,
    "relevance_score": 0-10,
    "is_duplicate": true/false,
    "source_credibility": 1-10,
    "timeliness": 0-1,
    "is_noise": true/false,
    "noise_reason": "噪音原因（如果是噪音）",
    "is_hearsay": true/false,
    "hearsay_indicator": "二手转述标记词",
    "market_signals": ["信号1", "信号2"],
    "direction": "bullish/bearish/neutral",
    "impact_level": 1-5,
    "key_entities": ["实体1", "实体2"],
    "summary": "一句话摘要",
    "final_verdict": "actionable/noteworthy/low_value/discard",
    "final_score": 0-10
}

判断标准：
- actionable: 高价值可行动情报（≥7分）
- noteworthy: 值得关注（5-7分）
- low_value: 低价值（3-5分）
- discard: 应丢弃（<3分或噪音）
"""


def ai_decide(query: str, ai: AIModel = None) -> dict:
    """
    使用 AI 进行前置决策

    Args:
        query: 用户问题
        ai: AI 模型实例

    Returns:
        决策结果字典
    """
    if ai is None:
        ai = AIModel()

    result = ai.chat_json(
        query,
        system_prompt=_system_prompt_decision,
        temperature=0.3
    )

    if "error" in result:
        logging.error("AI decision failed, falling back to local router: %s", result["error"])
        from deepalpha.intel_router_v2 import decide
        return decide(query).to_dict()

    required_fields = ["asset", "current_regime", "top_accounts", "top_event_phrases", "crawl_tasks"]
    for field in required_fields:
        if field not in result:
            result[field] = [] if field in ["top_accounts", "top_event_phrases", "crawl_tasks"] else "unknown"

    return result


def ai_clean_tweet(tweet: dict, ai: AIModel = None) -> dict:
    """
    使用 AI 清洗单条推文

    Args:
        tweet: 推文字典
        ai: AI 模型实例

    Returns:
        清洗结果字典
    """
    if ai is None:
        ai = AIModel()

    content = tweet.get("content", "")
    handle = tweet.get("handle", "")
    verified = tweet.get("verified", False)

    prompt = f"""分析这条推文：

作者: {handle}
认证: {"是" if verified else "否"}
内容: {content}

请判断其情报价值。"""

    result = ai.chat_json(
        prompt,
        system_prompt=_system_prompt_clean,
        temperature=0.2
    )

    if "error" in result:
        logging.error("AI clean failed, using heuristic fallback: %s", result["error"])
        result = {
            "is_relevant": True,
            "relevance_score": 5,
            "final_verdict": "noteworthy",
            "final_score": 5,
        }

    return result


def ai_batch_clean(tweets: List[dict], ai: AIModel = None, batch_size: int = 5) -> List[dict]:
    """
    批量 AI 清洗推文

    Args:
        tweets: 推文列表
        ai: AI 模型实例
        batch_size: 批处理大小

    Returns:
        清洗后的推文列表
    """
    if ai is None:
        ai = AIModel()

    results = []

    for i in range(0, len(tweets), batch_size):
        batch = tweets[i:i + batch_size]

        batch_prompt = "分析以下推文的情报价值，以 JSON 数组格式返回：\n\n"
        for j, tweet in enumerate(batch):
            batch_prompt += f"[{j}] @{tweet.get('handle', 'unknown')}: {tweet.get('content', '')[:200]}\n\n"

        batch_prompt += "\n返回格式: [{...}, {...}, ...]"

        try:
            response = ai.chat(
                batch_prompt,
                system_prompt=_system_prompt_clean,
                temperature=0.2,
                json_mode=True
            )

            batch_results = json.loads(response)
            if isinstance(batch_results, list):
                results.extend(batch_results)
            else:
                for tweet in batch:
                    results.append(ai_clean_tweet(tweet, ai))
        except:
            for tweet in batch:
                results.append(ai_clean_tweet(tweet, ai))

    return results


if __name__ == "__main__":
    print("AI 模型接口测试")
    print("=" * 60)

    ai = AIModel()
    print(f"检测到后端: {ai.backend}")
    print(f"使用模型: {ai.model}")
    print(f"API 地址: {ai.base_url}")
    print(f"可用性: {'✓' if ai.is_available() else '✗'}")
    print()

    test_query = "油价会涨吗？"
    print(f"测试问题: {test_query}")
    print("-" * 40)

    result = ai_decide(test_query, ai)
    print(json.dumps(result, ensure_ascii=False, indent=2))
