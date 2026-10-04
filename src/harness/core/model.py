import json
import os
from openai import OpenAI

class OpenAICompatModel:
    def __init__(self, base_url=None, api_key=None, model=None, temperature=0.0):
        self.client = OpenAI(
            base_url=base_url or os.environ.get("BASE_URL", "http://localhost:11434/v1"),
            api_key=api_key or os.environ.get("API_KEY", "ollama"))
        self.model = model or os.environ.get("MODEL", "qwen3:8b")
        self.temperature = temperature

    def chat(self, messages, tools=None):
        kw = {"model": self.model, "messages": messages,
              "temperature": self.temperature}
        if tools:
            kw["tools"] = tools
        r = self.client.chat.completions.create(**kw)
        msg = r.choices[0].message
        calls = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__unparseable__": tc.function.arguments}
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": msg.content or "", "tool_calls": calls,
                "tokens": r.usage.total_tokens if r.usage else 0}
