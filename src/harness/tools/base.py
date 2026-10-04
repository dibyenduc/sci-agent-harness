import json
import sqlite3
from dataclasses import dataclass
from typing import Callable, Literal
from pydantic import BaseModel, ValidationError

Risk = Literal["read", "draft", "write"]

@dataclass
class Ctx:
    conn: sqlite3.Connection
    tenant_id: str
    actor: str = "agent"

@dataclass
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    fn: Callable
    risk: Risk

REGISTRY: dict[str, Tool] = {}

def tool(name: str, description: str, args: type[BaseModel], risk: Risk):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, args, fn, risk)
        return fn
    return deco

def openai_schemas() -> list[dict]:
    return [{
        "type": "function",
        "function": {
            "name": t.name,
            "description": f"[{t.risk}] {t.description}",
            "parameters": t.args.model_json_schema(),
        },
    } for t in REGISTRY.values()]

def call_tool(ctx: Ctx, name: str, raw_args: dict) -> dict:
    t = REGISTRY.get(name)
    if t is None:
        return {"error": f"unknown tool: {name}", "available": sorted(REGISTRY)}
    try:
        parsed = t.args(**raw_args)
    except ValidationError as e:
        return {"error": "invalid arguments", "details": json.loads(e.json())}
    try:
        return t.fn(ctx, parsed)
    except ValueError as e:
        return {"error": str(e)}

