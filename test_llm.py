import json

from langfuse import get_client

from llm import chat

TOOLS = [{
    "type": "function",
    "function": {
        "name": "say_hello",
        "description": "Return a greeting for the given name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
}]


def say_hello(name):
    return f"Hello, {name}!"


messages = [{"role": "user", "content": "Use the say_hello tool to greet Dibyendu."}]

msg = chat(messages, TOOLS)
assert msg.tool_calls, "Model did not call the tool"

messages.append(msg.model_dump(exclude_none=True))
for call in msg.tool_calls:
    args = json.loads(call.function.arguments)
    messages.append({
        "role": "tool",
        "tool_call_id": call.id,
        "content": say_hello(**args),
    })

final = chat(messages, TOOLS)
print(final.content)

get_client().flush()

