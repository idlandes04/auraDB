# All settings, API keys, file paths, model IDs

LMSTUDIO_API_BASE = "http://192.168.5.116:1234/v1"  # Updated to match LM Studio server address
LMSTUDIO_MODEL = "qwen3-14b"  # Updated to match the actual model identifier
LMSTUDIO_API_KEY = "lm-studio"  # Not used for auth, but required by OpenAI client

ROUTER_PROMPT = '''You are a hyper-efficient, silent Triage and Routing agent. Your SOLE purpose is to analyze the user's text and classify it based on the rules provided. You MUST respond with ONLY a single, valid JSON object and nothing else. Do not add explanations or conversational text.

The current date is: {{current_date}}

User's Text:
"{{user_email_body}}"

Analyze the text and determine the routing and metadata based on the following JSON schema. Pay close attention to the descriptions for each field.

The JSON schema you MUST adhere to is:
{
  "type": "object",
  "properties": {
    "routing_decision": {
      "type": "string",
      "enum": ["local_processing", "cloud_synthesis"],
      "description": "Choose 'local_processing' for simple data entry like creating a task, note, or event. Choose 'cloud_synthesis' for complex reasoning, analysis, or summarization of multiple items."
    },
    "permanence": {
      "type": "string",
      "enum": ["permanent", "non-permanent"],
      "description": "Choose 'non-permanent' for temporary reminders, fleeting thoughts, or tasks that are irrelevant after completion (e.g., if the user says 'temporary', 'for now', 'reminder'). Choose 'permanent' for long-term knowledge, goals, or core project data."
    },
    "expiry_date": {
      "type": "string",
      "format": "date-time",
      "description": "If permanence is 'non-permanent', estimate an expiry date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ) based on the current date and the user's request. For example, a reminder for 'tomorrow morning' should expire tomorrow at noon. A simple task should expire 7 days after its due date. If permanence is 'permanent', this field MUST be null."
    }
  },
  "required": ["routing_decision", "permanence", "expiry_date"]
}
'''

EXECUTOR_PROMPT = '''You are a precise and efficient AI assistant that converts user requests into structured tool calls. You will be given a user's request and a list of available tools. Your task is to analyze the request and generate a JSON object containing the appropriate tool calls. Respond with ONLY the JSON for the tool call. Do not add conversational text.

If the user's request does not fit any of the available tools, respond with an empty tool call list.

User's Request:
"{{user_email_body}}"
'''