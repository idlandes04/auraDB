# FILE: llm_interface.py

import json
from openai import OpenAI
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
import ontology

import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part

from config import (
    LMSTUDIO_API_BASE, LMSTUDIO_MODEL, LMSTUDIO_API_KEY, QWEN3_EMBEDDING_MODEL_ID,
    ROUTER_PROMPT, EXECUTOR_PROMPT_CONTEXT_ANALYSIS, EXECUTOR_PROMPT_FINAL_ACTION,
    REPLY_GENERATOR_PROMPT, CONTEXT_SUMMARIZER_PROMPT,
    VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_MODEL_FAILOVER, VERTEX_MODEL_SUMMARIZATION,
    LOCAL_API_TIMEOUT_SECONDS
)

# JSON Schema for Router
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "routing_decision": {"type": "string", "enum": ["local_processing", "cloud_synthesis"]},
        "permanence": {"type": "string", "enum": ["permanent", "non-permanent"]},
        "expiry_date": {"type": "string", "format": "date-time"}
    },
    "required": ["routing_decision", "permanence"]
}
ROUTER_TOOL_VERTEX = Tool(function_declarations=[
    FunctionDeclaration(name="routing_decision_tool", description="Makes a routing and permanence decision based on user email.", parameters=ROUTER_SCHEMA)
])

# Client Initialization
local_client = OpenAI(base_url=LMSTUDIO_API_BASE, api_key=LMSTUDIO_API_KEY, timeout=LOCAL_API_TIMEOUT_SECONDS)

try:
    vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
    vertex_model_failover = GenerativeModel(VERTEX_MODEL_FAILOVER)
    vertex_model_summarization = GenerativeModel(VERTEX_MODEL_SUMMARIZATION)
    print("[Vertex AI] Initialized successfully.")
except Exception as e:
    print(f"[Vertex AI] CRITICAL: Failed to initialize Vertex AI SDK. Cloud features will be disabled. Error: {e}")
    vertex_model_failover = None
    vertex_model_summarization = None

def _safe_json_loads(content: Optional[str]) -> Dict[str, Any]:
    if not content: return {}
    try:
        if content.strip().startswith("```json"): content = content.strip()[7:-3]
        json_start_index = content.find('{')
        json_end_index = content.rfind('}') + 1
        if json_start_index == -1 or json_end_index == 0: return {}
        return json.loads(content[json_start_index:json_end_index])
    except Exception as e:
        print(f"[JSON Parse Error] Content was: '{content}'. Error: {e}")
        return {}

def _get_openai_tools(tools_list: List[Dict]) -> List[Dict]:
    return [{"type": "function", "function": tool} for tool in tools_list]

def _convert_raw_tools_to_vertex(tools_list: List[Dict]) -> List[Tool]:
    """
    FIXED: Correctly converts Aura's internal tool format (from ontology.py)
    to the Vertex AI SDK's Tool format.
    """
    declarations = [
        FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"]
        ) for t in tools_list
    ]
    return [Tool(function_declarations=declarations)] if declarations else []

# --- Failover Functions with Diagnostic Logging ---

def _call_vertex_ai_router(prompt: str) -> Optional[Dict[str, Any]]:
    if not vertex_model_failover:
        print("[Vertex AI] Router failover called, but model is not initialized.")
        return None
    print("[Vertex AI] Executing router failover call...")
    try:
        response = vertex_model_failover.generate_content(prompt, tools=[ROUTER_TOOL_VERTEX])
        print(f"[Vertex AI Raw Response - Router] {response}")
        if not response.candidates or not response.candidates[0].content.parts:
            print("[Vertex AI Router Failover] Model returned no candidates or parts.")
            return None
        
        part = response.candidates[0].content.parts[0]
        if not hasattr(part, 'function_call') or not part.function_call.name:
            print("[Vertex AI Router Failover] Model returned no valid function call.")
            return None

        fc = part.function_call
        return dict(fc.args)
    except Exception as e:
        print(f"[Vertex AI Router Failover Error] {e}")
        return None

def _call_vertex_ai_executor(prompt: str, tools: List[Dict]) -> Optional[Dict[str, Any]]:
    if not vertex_model_failover:
        print("[Vertex AI] Executor failover called, but model is not initialized.")
        return None
    print("[Vertex AI] Executing executor failover call...")
    try:
        vertex_tools = _convert_raw_tools_to_vertex(tools)
        response = vertex_model_failover.generate_content(prompt, tools=vertex_tools)
        print(f"[Vertex AI Raw Response - Executor] {response}")
        
        if not response.candidates or not response.candidates[0].content.parts:
            print("[Vertex AI Executor Failover] Model returned no candidates or parts.")
            return None

        part = response.candidates[0].content.parts[0]
        if not hasattr(part, 'function_call') or not part.function_call.name:
            text_response = part.text if hasattr(part, 'text') else 'No text content.'
            print(f"[Vertex AI Executor Failover] Model returned a text response instead of a function call: '{text_response}'")
            return None

        fc = part.function_call
        return {"name": fc.name, "arguments": dict(fc.args)}
    except Exception as e:
        print(f"[Vertex AI Executor Failover Error] {e}")
        return None

# --- Primary Functions with Hardened Failover ---

def call_router(email_body: str) -> Optional[Dict[str, Any]]:
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt = ROUTER_PROMPT.replace("{{user_email_body}}", email_body).replace("{{current_date}}", current_date_str)
    response_format_wrapper = {"type": "json_schema", "json_schema": {"name": "routing_schema", "schema": ROUTER_SCHEMA}}
    try:
        print("[Router] Attempting local call...")
        response = local_client.chat.completions.create(
            model=LMSTUDIO_MODEL, messages=[{"role": "system", "content": prompt}],
            response_format=response_format_wrapper, max_tokens=512, temperature=0.5, # type: ignore
        )
        result = _safe_json_loads(response.choices[0].message.content)
        if result: return result
    except Exception as e:
        print(f"[Router Error] Local call failed: {e}. Failing over to cloud.")
    return _call_vertex_ai_router(prompt)

def embed_text(text: str, instruction: str = "Embed this text for semantic retrieval") -> List[float]:
    """
    Generates an embedding for the given text using the local model.
    ARCHITECTURAL CHANGE: Failover to a cloud embedding model has been REMOVED.
    This is to guarantee that all vectors in the semantic database have the same
    dimensions and origin, preventing data corruption. If this function fails,
    the calling process must handle the exception as it's a critical error.
    """
    text_to_embed = f"{instruction}: {text}"
    try:
        print("[Embedding] Attempting local call...")
        response = local_client.embeddings.create(input=[text_to_embed], model=QWEN3_EMBEDDING_MODEL_ID)
        embedding = response.data[0].embedding
        if embedding and isinstance(embedding, list):
            return embedding
        raise ValueError("Local embedding model returned an invalid or empty embedding.")
    except Exception as e:
        print(f"[Embedding Error] CRITICAL: Local embedding call failed. This is a fatal error for semantic operations.")
        raise e

def call_executor(prompt: str, tools: List[Dict]) -> Optional[Dict[str, Any]]:
    try:
        print(f"[Executor] Attempting local call with model: {LMSTUDIO_MODEL}")
        response = local_client.chat.completions.create(
            model=LMSTUDIO_MODEL, messages=[{"role": "system", "content": prompt}],
            tools=_get_openai_tools(tools), tool_choice="auto", temperature=0.5,
        )
        if response.choices[0].message and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0].function
            arguments = json.loads(tool_call.arguments)
            print("[Executor] Local call successful.")
            return {"name": tool_call.name, "arguments": arguments}
    except Exception as e:
        print(f"[Executor Error] Local model failed: {e}. Failing over to cloud.")
    return _call_vertex_ai_executor(prompt, tools)

def generate_human_reply(user_request: str, confirmation_message: str) -> str:
    prompt = REPLY_GENERATOR_PROMPT.replace("{{user_request}}", user_request).replace("{{system_confirmation}}", confirmation_message)
    try:
        print("[Reply Gen] Attempting local call...")
        response = local_client.chat.completions.create(
            model=LMSTUDIO_MODEL, messages=[{"role": "system", "content": prompt}], max_tokens=500, temperature=0.8,
        )
        reply_content = response.choices[0].message.content or ""
        if "<think>" in reply_content: reply_content = reply_content.split("</think>")[-1]
        return reply_content.strip()
    except Exception as e:
        print(f"[Reply Gen Error] Local call failed: {e}. Failing over to cloud.")
    try:
        if not vertex_model_failover: raise Exception("Vertex AI model not initialized.")
        print("[Reply Gen] Executing failover call...")
        response = vertex_model_failover.generate_content(prompt)
        print(f"[Vertex AI Raw Response - Reply Gen] {response}")
        return response.text.strip()
    except Exception as e_cloud:
        print(f"[Reply Gen Error] Cloud failover also failed: {e_cloud}")
        return confirmation_message

def generate_summary_with_vertex_ai(context_data: str) -> Optional[str]:
    if not vertex_model_summarization:
        print("[Vertex AI] Summarizer called, but model is not initialized. Aborting.")
        return None
    try:
        prompt = CONTEXT_SUMMARIZER_PROMPT.replace("{{context_data}}", context_data)
        response = vertex_model_summarization.generate_content(prompt)
        print(f"[Vertex AI Raw Response - Summarizer] {response}")
        return response.text
    except Exception as e:
        print(f"[Vertex AI Summarizer Error] {e}")
        return None