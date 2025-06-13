import json
from openai import OpenAI
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from config import LMSTUDIO_API_BASE, LMSTUDIO_MODEL, LMSTUDIO_API_KEY, ROUTER_PROMPT, EXECUTOR_PROMPT
from ontology import TOOLS

# --- JSON Schemas for LM Studio Structured Output ---
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "routing_decision": {
            "type": "string",
            "enum": ["local_processing", "cloud_synthesis"],
        },
        "permanence": {
            "type": "string",
            "enum": ["permanent", "non-permanent"],
        },
        "expiry_date": {
            "type": "string",
            "format": "date-time",
        }
    },
    "required": ["routing_decision", "permanence", "expiry_date"]
}


client = OpenAI(base_url=LMSTUDIO_API_BASE, api_key=LMSTUDIO_API_KEY)

def _safe_json_loads(content):
    if not content:
        return {}
    try:
        if isinstance(content, str):
            json_start_index = content.find('{')
            if json_start_index == -1:
                return {}
            return json.loads(content[json_start_index:])
        return content
    except Exception as e:
        print(f"[JSON Parse Error] Content was: '{content}'. Error: {e}")
        return {}

def _get_openai_tools():
    tools = []
    for tool in TOOLS:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
        })
    return tools

def call_router(email_body: str) -> Optional[Dict[str, Any]]:
    # **FIX:** Inject the current date into the prompt for context-aware responses.
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt = ROUTER_PROMPT.replace("{{user_email_body}}", email_body)
    prompt = prompt.replace("{{current_date}}", current_date_str)

    # Wrap the schema in the required nested structure from the API docs.
    response_format_wrapper = {
        "type": "json_schema",
        "json_schema": {
            "name": "routing_schema",
            "schema": ROUTER_SCHEMA
        }
    }

    try:
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[{"role": "system", "content": prompt}],
            response_format=response_format_wrapper, # type: ignore
            max_tokens=256,
            temperature=0.0,
        )
        content = response.choices[0].message.content
        return _safe_json_loads(content)
    except Exception as e:
        print(f"[Router Error] {e}")
        return None

def call_executor(email_body: str) -> Optional[Dict[str, Any]]:
    prompt = EXECUTOR_PROMPT.replace("{{user_email_body}}", email_body)
    try:
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise and efficient AI assistant that converts user requests into structured tool calls. Respond with ONLY the JSON for the tool call."},
                {"role": "user", "content": prompt}
            ],
            tools=_get_openai_tools(),
            tool_choice="auto",
            temperature=0.0,
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0].function
            # The arguments are returned as a string, so we need to load them into a dict
            arguments = json.loads(tool_call.arguments)
            return {
                "name": tool_call.name,
                "arguments": arguments
            }
        else:
            print("[Executor] Model decided not to use any tools.")
            return None

    except Exception as e:
        print(f"[Executor Error] {e}")
        return None