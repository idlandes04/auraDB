# All settings, API keys, file paths, model IDs, and advanced prompts
import os

# --- FILE PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
DB_PATH = os.path.join(BASE_DIR, 'aura_db.sqlite')
LOG_PATH = os.path.join(BASE_DIR, 'aura_actions.log')

# --- EMAIL SETTINGS ---
# The email address Aura sends from and receives to.
AURA_EMAIL = "ethanxsteele@gmail.com" 
# Your personal email that you will send commands from.
USER_EMAIL = "idlandes04@gmail.com" 
# Full permissions: read, compose, send, and modify (archive, delete).
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# --- LLM SETTINGS ---
LMSTUDIO_API_BASE = "http://192.168.5.116:1234/v1"
LMSTUDIO_MODEL = "qwen3-14b"
LMSTUDIO_API_KEY = "lm-studio" # Not used for auth, but required by OpenAI client


# --- ROUTER PROMPT ---
ROUTER_PROMPT = '''You are a hyper-efficient, silent Triage and Routing agent. Your SOLE purpose is to analyze the user's text and classify it by following a strict thought process. You MUST use the <think> tag to reason step-by-step and then produce a single, valid JSON object as your final answer. Do not add any other conversational text.

The current date is: {{current_date}}

Here is your thought process:
<think>
1.  **Analyze the User's Goal:** What is the fundamental intent of the user's request? Is it to remember something (task/reminder), store information (note), or schedule an appointment (event)?

2.  **Determine Routing (`routing_decision`):**
    *   If the goal is simple data entry (creating a single task, note, or event), the decision is `local_processing`.
    *   If the goal requires complex reasoning, summarization across multiple items, analysis of past data, or strategic planning (e.g., "summarize my notes on Project X"), the decision is `cloud_synthesis`.

3.  **Determine Permanence (`permanence`):**
    *   Scan for keywords indicating temporary nature: "remind me," "temporary," "for now," "today," "tomorrow." If found, the permanence is `non-permanent`.
    *   A task that is actionable and has a clear completion state (e.g., "call the accountant," "buy milk") is almost always `non-permanent`.
    *   If the request is to store information, an idea, a goal, a key piece of data for a project, or anything without a clear "done" state, the permanence is `permanent`.

4.  **Calculate Expiry (`expiry_date`):**
    *   This field is ONLY for `non-permanent` items. If permanence is `permanent`, this MUST be `null`.
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


# --- EXECUTOR PROMPT ---
EXECUTOR_PROMPT = '''You are a precise and efficient AI assistant that converts user requests into structured tool calls. You MUST use the <think> tag to reason about the user's request and the available tools, then produce ONLY the JSON for the single most appropriate tool call.

The current date is: {{current_date}}

Here is your thought process:
<think>
1.  **Deconstruct the Request:** Break down the user's request into its core components. What is the action? What are the parameters (the 'what', 'when', 'where')?

2.  **Select the Best Tool:** Review the list of available tools. Which tool's `name` and `description` best matches the user's action? For "remind me," "task," or "to-do," the tool is `create_task`. For "note," "remember that," or "save this idea," the tool is `store_note`. For "schedule," "appointment," or "meeting," the tool is `create_event`.

3.  **Extract Arguments:** Go through the parameters of the selected tool and fill them in from the user's text.
    *   `content` or `title`: This is the main subject of the request (e.g., "call the accountant").
    *   `due_date` or `start_time`: Extract this explicitly using the current date as a reference. If the user says "tomorrow morning at 9am," use that exact time. If they are vague like "tomorrow," default to a reasonable time like 9:00 AM. Use the ISO 8601 format. If no time is given for a task, this can be `null`.
    *   `permanence`: Infer this from the request. A reminder is `non-permanent`. A stored fact is `permanent`.
    *   Other fields like `description`, `location`, `end_time`: Fill these if the information is present, otherwise leave them as `null`.

4.  **Construct the Final JSON:** Assemble the extracted information into a valid JSON object that matches the tool's schema. Ensure all required fields are present.
</think>

User's Request:
"{{user_email_body}}"

Now, provide your final JSON object for the tool call.
'''

# --- SCHEDULER SETTINGS ---
SCHEDULER_INTERVAL_MINUTES = 1 # Set to 1 for aggressive testing, can be increased to 5 or 15 later.
DAILY_DIGEST_TIME = "23:00" # For a future phase, but good to have the placeholder.