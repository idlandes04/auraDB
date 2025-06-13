import json
from openai import OpenAI
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from pydantic import ValidationError
from config import LMSTUDIO_API_BASE, LMSTUDIO_MODEL, LMSTUDIO_API_KEY, ROUTER_PROMPT, EXECUTOR_PROMPT
from ontology import TOOLS, CreateTaskArguments, StoreNoteArguments, CreateEventArguments

# ... (rest of file is identical to your provided file, no changes needed yet)
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
    "required": ["routing_decision", "permanence"] # expiry_date is not always required
}


client = OpenAI(base_url=LMSTUDIO_API_BASE, api_key=LMSTUDIO_API_KEY)

def _safe_json_loads(content: Optional[str]) -> Dict[str, Any]:
    if not content:
        return {}
    try:
        # The model sometimes wraps the JSON in markdown backticks
        if content.strip().startswith("```json"):
            content = content.strip()[7:-3]
        
        json_start_index = content.find('{')
        if json_start_index == -1:
            return {}
        # Find the matching closing brace
        json_end_index = content.rfind('}') + 1
        return json.loads(content[json_start_index:json_end_index])
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
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt = ROUTER_PROMPT.replace("{{user_email_body}}", email_body).replace("{{current_date}}", current_date_str)

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
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt = EXECUTOR_PROMPT.replace("{{user_email_body}}", email_body).replace("{{current_date}}", current_date_str)
    try:
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[
                {"role": "system", "content": prompt}
            ],
            tools=_get_openai_tools(),
            tool_choice="auto",
            temperature=0.0,
        )

        if response.choices[0].message and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0].function
            try:
                arguments = json.loads(tool_call.arguments)
            except json.JSONDecodeError:
                print(f"[Executor JSON-Parse Error] Malformed arguments: {tool_call.arguments}")
                return None
            
            return {
                "name": tool_call.name,
                "arguments": arguments
            }
        else:
            print("[Executor] Model decided not to use any tools or returned an empty response.")
            return None

    except Exception as e:
        print(f"[Executor Error] {e}")
        return None