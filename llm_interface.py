# FILE: llm_interface.py

import json
from openai import OpenAI
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
from pydantic import ValidationError
from config import (
    LMSTUDIO_API_BASE, LMSTUDIO_MODEL, LMSTUDIO_API_KEY, QWEN3_EMBEDDING_MODEL_ID,
    ROUTER_PROMPT, EXECUTOR_PROMPT_CONTEXT_ANALYSIS, EXECUTOR_PROMPT_FINAL_ACTION,
    REPLY_GENERATOR_PROMPT
)
import ontology

# --- JSON Schemas for LM Studio Structured Output ---
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "routing_decision": {"type": "string", "enum": ["local_processing", "cloud_synthesis"]},
        "permanence": {"type": "string", "enum": ["permanent", "non-permanent"]},
        "expiry_date": {"type": ["string", "null"], "format": "date-time"}
    },
    "required": ["routing_decision", "permanence"]
}

client = OpenAI(base_url=LMSTUDIO_API_BASE, api_key=LMSTUDIO_API_KEY)

def _safe_json_loads(content: Optional[str]) -> Dict[str, Any]:
    if not content:
        return {}
    try:
        if content.strip().startswith("```json"):
            content = content.strip()[7:-3]
        
        json_start_index = content.find('{')
        json_end_index = content.rfind('}') + 1
        if json_start_index == -1 or json_end_index == 0:
            return {}
        return json.loads(content[json_start_index:json_end_index])
    except Exception as e:
        print(f"[JSON Parse Error] Content was: '{content}'. Error: {e}")
        return {}

def _get_openai_tools(tools_list: List[Dict]) -> List[Dict]:
    """Converts our simple tool definitions into OpenAI-compatible format."""
    return [
        {"type": "function", "function": tool} for tool in tools_list
    ]

def call_router(email_body: str) -> Optional[Dict[str, Any]]:
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt = ROUTER_PROMPT.replace("{{user_email_body}}", email_body).replace("{{current_date}}", current_date_str)
    
    response_format_wrapper = {
        "type": "json_schema",
        "json_schema": {"name": "routing_schema", "schema": ROUTER_SCHEMA}
    }

    try:
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[{"role": "system", "content": prompt}],
            response_format=response_format_wrapper, # type: ignore
            max_tokens=512,
            temperature=0.5,
        )
        return _safe_json_loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Router Error] {e}")
        return None

def call_executor(prompt: str, tools: List[Dict]) -> Optional[Dict[str, Any]]:
    """A more generic executor call for our agentic chain."""
    try:
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[{"role": "system", "content": prompt}],
            tools=_get_openai_tools(tools), # type: ignore
            tool_choice="auto",
            temperature=0.5,
        )

        if response.choices[0].message and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0].function
            try:
                arguments = json.loads(tool_call.arguments)
                return {"name": tool_call.name, "arguments": arguments}
            except json.JSONDecodeError:
                print(f"[Executor JSON-Parse Error] Malformed args: {tool_call.arguments}")
                return None
        else:
            print("[Executor] Model decided not to use any tools.")
            return None

    except Exception as e:
        print(f"[Executor Error] {e}")
        return None

def embed_text(text: str, instruction: str = "Embed this text for semantic retrieval") -> Optional[List[float]]:
    """
    Generates a vector embedding for a given text using an instruction-tuned model.
    NOTE: The instruction is not directly supported by the OpenAI /v1/embeddings endpoint.
    We prepend it to the text as a common workaround for models that expect it.
    """
    try:
        # Prepending instruction to the text for models that are tuned for it.
        # This is a standard practice when the API doesn't have a separate `instruction` field.
        text_to_embed = f"{instruction}: {text}"

        response = client.embeddings.create(
            input=[text_to_embed],
            model=QWEN3_EMBEDDING_MODEL_ID
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"[Embedding Error] Could not embed text '{text[:50]}...'. Error: {e}")
        return None

def generate_human_reply(user_request: str, confirmation_message: str) -> str:
    """Takes a technical confirmation and the user's original request to generate a natural-sounding reply."""
    try:
        prompt = REPLY_GENERATOR_PROMPT.replace("{{user_request}}", user_request)\
                                       .replace("{{system_confirmation}}", confirmation_message)
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[{"role": "system", "content": prompt}],
            max_tokens=5000,
            temperature=0.8, # A little creativity is good here
        )
        # Clean up the response to ensure no extra text is included
        reply_content = response.choices[0].message.content or ""
        return reply_content.strip()
    except Exception as e:
        print(f"[Reply Generation Error] {e}")
        # Fallback to the technical message if generation fails
        return confirmation_message