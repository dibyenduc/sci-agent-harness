import os

from langfuse import observe
from langfuse.openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.environ["BASE_URL"],
            api_key=os.environ["API_KEY"],
        )
    return _client


@observe(name="chat")
def chat(messages, tools=None, model=None):
    """Send messages (and optional tool schemas) to an OpenAI-compatible API.

    Returns the assistant message. Check .tool_calls for requested tools.
    """
    kwargs = {
        "model": model or os.environ["MODEL"],
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    resp = _get_client().chat.completions.create(**kwargs)
    return resp.choices[0].message

