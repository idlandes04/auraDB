# FILE: config.py

# All settings, API keys, file paths, model IDs, and advanced prompts
import os

# --- FILE PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
DB_PATH = os.path.join(BASE_DIR, 'aura_db.sqlite')
LOG_PATH = os.path.join(BASE_DIR, 'aura_actions.log')
CHROMA_DB_PATH = os.path.join(BASE_DIR, 'aura_chroma_db')

# --- EMAIL SETTINGS ---
AURA_EMAIL = "ethanxsteele@gmail.com" 
USER_EMAIL = "idlandes04@gmail.com" 
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# --- LLM SETTINGS ---
# Local
LMSTUDIO_API_BASE = "http://192.168.5.116:1234/v1"
LMSTUDIO_MODEL = "qwen3-8b" 
QWEN3_EMBEDDING_MODEL_ID = "text-embedding-qwen3-embedding-8b"
LMSTUDIO_API_KEY = "lm-studio"
LOCAL_API_TIMEOUT_SECONDS = 45

# Cloud (Vertex AI) - Using stable model versions
VERTEX_PROJECT_ID = "firm-moonlight-462817-v2"
VERTEX_LOCATION = "us-central1"
VERTEX_MODEL_FAILOVER = "gemini-2.5-flash-preview-05-20"
VERTEX_MODEL_SUMMARIZATION = "gemini-2.5-flash-preview-05-20"

# --- ROUTER PROMPT ---
ROUTER_PROMPT = '''You are a hyper-efficient, silent Triage and Routing agent. Your SOLE purpose is to analyze the user's text and classify it by following a strict thought process. You MUST use the <think> tag to reason step-by-step and then produce a single, valid JSON object as your final answer. Do not add any other conversational text.

The current date is: {{current_date}}

<think>
1.  **Analyze the User's Goal:** What is the fundamental intent of the user's request? Is it to remember something (task/reminder), store information (note), or schedule an appointment (event)?

2.  **Determine Routing (`routing_decision`):**
    *   If the goal is simple data entry (creating a single task, note, or event), the decision is `local_processing`.
    *   If the goal requires complex reasoning, summarization across multiple items, analysis of past data, or strategic planning (e.g., "summarize my notes on Project X"), the decision is `cloud_synthesis`.

3.  **Determine Permanence (`permanence`):** This is a critical step.
    *   `permanent`: Information that is part of a larger body of knowledge. This includes ideas, facts, goals, project details (like deadlines or specifications), and general information to be stored indefinitely. A project deadline is `permanent` because the fact that the project had a deadline is important information, even after the date has passed.
    *   `non-permanent`: Information that is truly disposable and has no value after it's acted upon. This includes simple, temporary reminders like "remind me to call Mom tomorrow" or "add milk to the shopping list." These items can be safely purged after they expire.
    *   Scan for keywords, but use the subject matter as the primary guide. "Deadline for Aura V5" is project-related, so it's `permanent`. "Remind me to take out the trash" is disposable, so it's `non-permanent`.

4.  **Calculate Expiry (`expiry_date`):**
    *   This field is ONLY for `non-permanent` items. If permanence is `permanent`, this field MUST be `null`.
    *   If `non-permanent`, calculate an expiry date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
    *   Use the current date as the reference.
    *   "tomorrow morning" expires at `YYYY-MM-(DD+1)T12:00:00Z`.
    *   "in 3 days" expires at `YYYY-MM-(DD+3)T23:59:59Z`.
    *   A simple task with no specified time (e.g., "add milk to my shopping list") should expire in 7 days.
    *   Be precise. A task due at a specific time should expire a few hours after that time on the same day.
</think>

User's Text:
"{{user_email_body}}"

Now, provide your final JSON object.
'''

# --- EXECUTOR PROMPTS ---
EXECUTOR_PROMPT_CONTEXT_ANALYSIS = '''You are a Semantic Analysis Engine. Your job is to understand the user's request and determine the correct "Context" or "Project" it belongs to.

You have one tool: `get_or_create_context`.

Your thought process:
<think>
1.  Read the user's request carefully.
2.  What is the core subject? Is it about 'Health', 'Guitar', 'Work Project A', a 'Shopping List'?
3.  Formulate a concise query that captures this core subject. For "Remind me to practice my scales on the guitar", the query should be "guitar practice". For "Add milk to the list", the query should be "shopping list".
4.  Call the `get_or_create_context` tool with this `query`.
</think>

User's Request:
"{{user_email_body}}"

Now, provide ONLY the JSON for the `get_or_create_context` tool call.
'''

EXECUTOR_PROMPT_FINAL_ACTION = '''You are a precise and efficient AI assistant that converts user requests into a final, structured tool call. You have been provided with a list of potentially relevant "Contexts" (projects/categories).

The current date is: {{current_date}}

Your thought process:
<think>
1.  **Review the User's Request:** "{{user_email_body}}"
2.  **Analyze the Context Matches:** I have been given the following potential contexts: {{context_matches}}.
3.  **Make a Decision:**
    *   Is one of the provided contexts a perfect match? If yes, select its `id`.
    *   If none of the contexts are a good match, I must create a new one. The new context name should be a concise, sensible title for the user's request (e.g., "Project Phoenix", "Health & Fitness", "Guitar Practice").
4.  **Select the Final Tool:** Based on the user's request ("remind me", "note", "schedule", "what do you know about..."), choose the correct final tool: `create_task`, `store_note`, `create_event`, or `query_context`.
5.  **Extract Arguments:**
    *   Fill in all the arguments for the chosen tool (`content`, `due_date`, etc.) from the user's text.
    *   Crucially, set the `context_id` argument to the ID of the context you chose in step 3. If you are creating a new context, set `context_id` to `null` and provide the new name in `new_context_name`.
6.  **Construct Final JSON:** Assemble the final tool call based on the user's intent. All dates must be in ISO 8601 format.
</think>

User's Request:
"{{user_email_body}}"

Potential Context Matches:
{{context_matches}}

Now, provide your final JSON object for the tool call.
'''

# --- NEW PROMPT FOR PHASE 6 GROUNDWORK ---
EXECUTOR_PROMPT_QUERY = """You are an information retrieval and synthesis agent. The user is asking a question about a specific context. Your job is to call the `query_context` tool with the appropriate context ID to retrieve all relevant information.

Your thought process:
<think>
1.  **Review the User's Request:** "{{user_email_body}}"
2.  **Analyze the Context Matches:** I have been given the following potential contexts: {{context_matches}}.
3.  **Identify the Target Context:** The user's request is clearly about one of the provided contexts. I will select its `id`. If no context seems to match, I cannot answer the question.
4.  **Call the Tool:** I will call the `query_context` tool, passing the selected `context_id`.
</think>

User's Request:
"{{user_email_body}}"

Potential Context Matches:
{{context_matches}}

Now, provide your final JSON object for the `query_context` tool call.
"""


# --- REPLY GENERATOR PROMPT ---
REPLY_GENERATOR_PROMPT = '''/nothink You are Aura, a helpful AI assistant. Your job is to write a short, natural, and friendly email reply.
Your reply MUST be based on the user's original request and the action the system took.
You MUST NOT include `<think>` tags, `Your Reply:`, or any other meta-text in your output. Your output should be ONLY the text of the reply itself.

### CONTEXT ###

[USER'S ORIGINAL REQUEST]:
"{{user_request}}"

[SYSTEM ACTION CONFIRMATION]:
"{{system_confirmation}}"

### END CONTEXT ###
/nothink
'''

# --- SUMMARIZER PROMPT ---
CONTEXT_SUMMARIZER_PROMPT = """You are a meticulous and concise AI summarizer. Your task is to review a collection of notes, tasks, and events related to a single project or context. Synthesize this information into a single, dense paragraph. The summary should capture the main goals, key information, current status, and any upcoming deadlines. Do not use markdown or lists. Produce only the summary paragraph.

Here is the raw data for the context:
---
{{context_data}}
---
"""

# --- SCHEDULER SETTINGS ---
SCHEDULER_INTERVAL_MINUTES = 1
SUMMARIZATION_INTERVAL_MINUTES = 60 