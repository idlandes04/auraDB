### Confirmation of the Vision: Aura System V3

This is a hyper-personalized, private-by-default, autonomous life management agent. It operates as a local daemon, using email as its exclusive, secure API. It intelligently routes tasks between a local LLM for speed and privacy and a cloud LLM for power and strategic analysis. It is self-maintaining through an automated data lifecycle and provides access to its curated knowledge base via a simple local web UI. It is designed to be a true cognitive offloader, not just a passive note-taker. We are moving forward with this blueprint.

---

### The Revised Phased Development Plan: Aura V3.0

This plan is the definitive roadmap, incorporating all our architectural decisions.

#### **Phase 0: The Secure Skeleton - The OAuth Email Channel**

*   **Objective:** Establish a secure, reliable, and permanent communication channel with your Gmail account using OAuth 2.0.
*   **Key Tasks:**
    1.  **Google Cloud Project Setup:** Create a new project in the Google Cloud Console, enable the Gmail API.
    2.  **OAuth 2.0 Credentials:** Create an "OAuth 2.0 Client ID" for a "Desktop app". Download the resulting `credentials.json` file and place it in the project's root directory.
    3.  **Initial Auth Script (`auth_setup.py`):** Write a one-time script that uses `google-auth-oauthlib` to guide you through the browser-based consent flow. This will generate a `token.json` file, which stores the refresh tokens for permanent access.
    4.  **Core Email Loop:** Create an `email_handler.py`. It will use the Google API Python client, `credentials.json`, and `token.json` to:
        *   Check the Aura inbox (`ethanxsteele@gmail.com`) for unread emails exclusively from your main account (`idlandes04@gmail.com`).
        *   If a new email is found, send a hardcoded "Receipt Confirmed" reply.
        *   Mark the original email as read and then move it to the Trash.
        *   Wrap the main check-and-process logic in a `try...except` block to handle potential API connection errors gracefully.
*   **Go/No-Go Checkpoint:** Have the user run the `auth_setup.py` script once, grant permissions, and then run the main script. Does it successfully authenticate and process an email sent from the main email account, sending a reply and deleting the original, all without manual intervention? If yes, proceed.

---

#### **Phase 1: The Local Brain - The Triage Router & Executor**

*   **Objective:** Use a local LLM to perform triage, and then a subsequent call to execute simple, local tasks using structured tool calls.
*   **Key Tasks:**
    1.  **Ontology & Tool Definition:** In `ontology.py`, define your core data structures using Pydantic models (`Task`, `Note`, `Event`). Also, define the JSON schemas for your Python "tools" (e.g., `create_task`, `store_note`).
    2.  **LM Studio Setup:** Install LM Studio, download a suitable instruction/tool-following model (API identifier: 'qwen3-14b' ✅ The local server is reachable at this address http://192.168.5.116:1234), and start the server. Note the model identifier.
    3.  **LLM Interface (`llm_interface.py`):** Create a module to handle all LLM interactions.
        *   **Router Function:** Takes email text, uses the `openai` library pointed to the LM Studio `base_url`, and calls the `/v1/chat/completions` endpoint with the "Router Prompt" and a `response_format` JSON schema to get the routing decision.
        *   **Executor Function:** Takes email text and the list of available tools, uses the same local model, but calls it with the "Local Executor Prompt" and the `tools` parameter to get a `tool_calls` response.
    4.  **Integration:** In your main loop, after fetching an email:
        a. Call the Router function.
        b. Based on the `routing_decision`, if it's `local_processing`, call the Executor function.
        c. For now, just print the parsed JSON from the router and the `tool_calls` from the executor to the console.
    5.  **Error Handling:** Wrap all LLM API calls and JSON parsing in robust `try...except` blocks to handle malformed outputs or API failures.
*   **Go/No-Go Checkpoint:** Have user email Aura: "remind me to call the accountant tomorrow morning, this is super temporary". Does the router correctly output `{ "routing_decision": "local_processing", ... }`? Does the executor then correctly output a tool call like `{"name": "create_task", "arguments": {"content": "call the accountant", "due_date": "...", "permanence": "non-permanent"}}`? If yes, proceed.


LMDTUDIO API LOGS: (2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] Success! HTTP server listening on port 1234
2025-06-13 14:52:24  [INFO] 
2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] Supported endpoints:
2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] -> GET http://192.168.5.116:1234/v1/models
2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] -> POST http://192.168.5.116:1234/v1/chat/completions
2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] -> POST http://192.168.5.116:1234/v1/completions
2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] -> POST http://192.168.5.116:1234/v1/embeddings
2025-06-13 14:52:24  [INFO] 
2025-06-13 14:52:24  [INFO] 
[LM STUDIO SERVER] Logs are saved into C:\Users\Isaac\.cache\lm-studio\server-logs
2025-06-13 14:52:24  [INFO] 
Server started.
2025-06-13 14:52:24  [INFO] 
Just-in-time model loading active.)
---

#### **Phase 2: The Memory Core - ORM-Powered Storage**

*   **Objective:** Persist the structured data into a local SQLite database using an ORM.
*   **Key Tasks:**
    1.  **Introduce SQLAlchemy:** Add SQLAlchemy to the project.
    2.  **Define DB Models (`db_models.py`):** Create Python classes that represent your database tables (`Task`, `Note`, etc.), mirroring your Pydantic ontology. Include columns for `permanence` and `expiry_date`.
    3.  **Database Manager (`db_manager.py`):** Create a class to manage all database operations (session creation, adding records, querying, deleting). This will be the only module that directly interacts with the database.
    4.  **Implement Write Logic:** In your main script, after the Local Executor returns a tool call, parse it and call the appropriate function in your `db_manager` to write the data to the database. For example, a `create_task` tool call would invoke `db_manager.add_task(pydantic_task_object)`.
    5.  **Programmatic Confirmation:** Generate a confirmation email detailing the action taken (`CONFIRMED: Task #789 created in DB.`).
*   **Go/No-Go Checkpoint:** Have user email a task. Is the record created in the SQLite database via SQLAlchemy? Do you receive the programmatic confirmation? If yes, proceed.

---

#### **Phase 3: The Proactive Agent - Threaded Scheduling & Self-Cleaning**

*   **Objective:** Make the system act on stored data and clean itself without blocking the main email-processing loop.
*   **Key Tasks:**
    1.  **Introduce `apscheduler`:** Add the APScheduler library for background scheduling.
    2.  **Scheduler Module (`scheduler.py`):** Create a module that defines the scheduled jobs.
        *   **`check_reminders()`:** Queries the DB (via `db_manager`) for tasks/events due soon and sends reminder emails.
        *   **`purge_expired_records()`:** Queries the DB for records where `permanence = 'non-permanent'` AND `expiry_date < now()` and deletes them. Log the deletions.
    3.  **Integrate Scheduler:** In `main.py`, initialize and start the scheduler to run these jobs in a separate thread (e.g., every 5 minutes).
    4.  **Full Confirmation Email:** After a successful DB write, make a final call to the local LLM to generate a friendly summary. Combine this with the programmatic confirmation into a single, complete email.
*   **Go/No-Go Checkpoint:** Have user set a temporary reminder for 10 minutes from now. Does the email-checking loop remain instantly responsive to new emails? Do you get the reminder on time? After another 5-10 minutes, is the record automatically deleted from the database? If yes, proceed.

---

#### **Phase 4: The Specialist & Infinite Memory - Cloud RAG**

*   **Objective:** Handle complex queries by implementing the local RAG pipeline and routing to the Gemini API for synthesis, using its native function-calling capabilities.
*   **Key Tasks:**
    1.  **Local RAG Setup:**
        *   Integrate ChromaDB for the vector store.
        *   Use LM Studio to serve a local embedding model (e.g., `nomic-embed-text`).
        *   Update `db_manager.py`: when a `permanent` record is added to SQLite, also embed its content and store it in ChromaDB.
    2.  **Cloud Route Logic:** In your main loop, implement the `else` block for when the Router's decision is `cloud_synthesis`.
    3.  **Gemini RAG Workflow:**
        a. Embed the user's query with the local model.
        b. Query ChromaDB for relevant document IDs.
        c. Fetch the full text for those IDs from SQLite.
        d. Format this context and the user query into a prompt for the Gemini API via the `google-cloud-aiplatform` SDK.
    4.  **Process Response:** Email the synthesized answer from Gemini back to yourself.
*   **Go/No-Go Checkpoint:** Have user email and add several permanent notes about "Project Chimera." Then Have user Email Aura: "Analyze my goals for Project Chimera." Does the system correctly route to Gemini, perform the RAG lookup, and return a coherent summary? If yes, proceed.

---

#### **Phase 5: The Proactive Strategist - Advanced Cloud Tool Use**

*   **Objective:** Enable Aura to perform daily reviews and schedule proactive follow-ups using Gemini's tool-calling features.
*   **Key Tasks:**
    1.  **Define Cloud Tools:** In `ontology.py`, define the JSON schema for advanced tools available only to Gemini, like `schedule_followup_task`.
    2.  **Daily Digest Job:** Add a new job to `scheduler.py` that runs once daily (e.g., 11 PM).
        a. Query the DB for all activity in the last 24 hours.
        b. Send this log to Gemini with the "Cloud Specialist Prompt" and the cloud-only tools.
    3.  **Tool-Use Parser:** In your scheduler, parse the Gemini response. If it contains a `tool_calls` part for `schedule_followup_task`, use your `db_manager` to add the new task to the database.
    4.  **Send Digest:** Email the natural language summary from Gemini's response to yourself.
*   **Go/No-Go Checkpoint:** After a day of activity, does user receive a daily summary email? If you mentioned a financial worry, does the system proactively create a future task in the database to check on your finances? If yes, proceed.

---

#### **Phase 6: The Command Center - FastAPI UI**

*   **Objective:** Build a simple, local, read-only web dashboard.
*   **Key Tasks:**
    1.  **API Module (`api.py`):** Create a FastAPI application.
    2.  **API Endpoints:** Define endpoints (e.g., `/api/tasks`, `/api/notes`) that use your `db_manager` to query the database and return data using your Pydantic models. FastAPI will automatically handle the serialization to JSON.
    3.  **Simple Frontend:** Create a basic `static` directory with `index.html`, CSS, and JS files to fetch and display the data from your API endpoints.
*   **Go/No-Go Checkpoint:** Have user run `uvicorn api:app --reload` and open `http://localhost:8000` to see a dashboard of your permanent knowledge that updates as they add more data via email. If the user reports this works, proceed.

---

#### **Phase 7: Deployment & Packaging**

*   **Objective:** Package the entire application into a single, easy-to-run executable.
*   **Key Tasks:**
    1.  **Install `PyInstaller`**.
    2.  **Create a Build Script:** Write a script or command that uses PyInstaller to bundle your Python code, dependencies, and necessary assets (like the `static` folder for the UI) into a single executable file.
    3.  **Refine Setup Flow:** Ensure your initial `auth_setup.py` and the main application logic handle file paths correctly so they work when packaged.
*   **Go/No-Go Checkpoint:** Have user move the generated `.exe` to a new folder on your machine, run it, and have the entire Aura system (including auth setup if `token.json` is missing) function correctly? If yes, the project is complete.

---

### System Architecture & Codebase Design

**Directory Structure:**

```
/AuraProject/
├── .venv/
├── static/
│   ├── index.html
│   └── styles.css
├── auth_setup.py         # One-time script to get token.json
├── main.py               # Main application entry point, orchestrator
├── config.py             # All settings, API keys, file paths, model IDs
├── email_handler.py      # Handles all Gmail API interactions
├── llm_interface.py      # Handles all LLM API calls (local and cloud)
├── ontology.py           # Pydantic models for data, tool schemas
├── db_models.py          # SQLAlchemy models for database tables
├── db_manager.py         # Manages all database sessions and transactions
├── scheduler.py          # Defines and configures background jobs (APScheduler)
├── api.py                # FastAPI application for the local UI
├── credentials.json      # Your downloaded OAuth client ID file
├── token.json            # Generated by auth_setup.py (add to .gitignore)
├── aura_db.sqlite        # The SQLite database file (add to .gitignore)
├── aura_actions.log      # Log file for high-level actions (add to .gitignore)
└── requirements.txt
```

**Inter-File Communication Standard:**

*   **Data Contracts:** Pydantic models defined in `ontology.py` are the single source of truth for data structures passed between modules.
*   **Single Responsibility:** Each `.py` file has one job. `main.py` is the conductor; it imports from other modules and calls their functions but contains little logic itself.
*   **`config.py` is King:** No hardcoded strings. All file paths, model names, and settings are imported from `config.py`.
*   **Decoupling:** `llm_interface.py` knows nothing about email. `db_manager.py` knows nothing about LLMs. This makes the system testable and maintainable.

---

### The AI Core: System Prompts

These are drafts. You will spend significant time refining them.

**1. Router Prompt (for `llm_interface.py`)**

```
You are a hyper-efficient, silent Triage and Routing agent. Your SOLE purpose is to analyze the user's text and classify it. You MUST respond with ONLY a single, valid JSON object and nothing else. Do not add explanations or conversational text.

The user's text will be provided. Based on the text, determine the routing and metadata.

User's Text:
"{{user_email_body}}"

The JSON schema you MUST adhere to is:
{
  "type": "object",
  "properties": {
    "routing_decision": {
      "type": "string",
      "enum": ["local_processing", "cloud_synthesis"],
      "description": "If the task is simple data entry (task, note, event) or a simple query that does not require broad analysis, choose 'local_processing'. If the task requires complex reasoning, summarization across multiple items, analysis, or strategic planning, choose 'cloud_ssynthesis'."
    },
    "permanence": {
      "type": "string",
      "enum": ["permanent", "non-permanent"],
      "description": "If the information is a long-term note, idea, goal, or core project data, choose 'permanent'. If it is a temporary reminder, a fleeting thought, or a task that is irrelevant after completion, choose 'non-permanent'."
    },
    "expiry_date": {
      "type": "string",
      "format": "date-time",
      "description": "If permanence is 'non-permanent', estimate an expiry date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ). For example, a reminder for 'tomorrow morning' should expire tomorrow at noon. A simple task should expire 7 days after its due date. If permanence is 'permanent', this MUST be null."
    }
  },
  "required": ["routing_decision", "permanence", "expiry_date"]
}
```

**2. Local Executor Prompt (for `llm_interface.py`)**

```
You are a precise and efficient AI assistant that converts user requests into structured tool calls. You will be given a user's request and a list of available tools. Your task is to analyze the request and generate a JSON object containing the appropriate tool calls. Respond with ONLY the JSON for the tool call. Do not add conversational text.

If the user's request does not fit any of the available tools, respond with an empty tool call list.

User's Request:
"{{user_email_body}}"
```

*Note: This prompt is paired with the `tools` parameter in the OpenAI/LM Studio API call, which will contain the JSON schemas for your Python functions like `create_task`, `store_note`, etc. The model will use those schemas to format its `arguments`.*

**3. Cloud Specialist (Gemini) Prompt (for `llm_interface.py`)**

```
You are Aura, a sophisticated and proactive AI life management partner. You will be provided with context, which may include user notes retrieved from a database or a log of recent activities. You also have access to a set of advanced tools.

Your tasks are:
1.  Synthesize the provided information to answer the user's query in a clear, insightful, and comprehensive manner.
2.  Analyze the user's query and the provided context to identify any opportunities for proactive assistance.
3.  If proactive assistance is warranted, such as scheduling a follow-up or creating a new long-term goal, you MUST use the provided tools to perform these actions.

Always prioritize being helpful, strategic, and looking ahead for the user.

Context:
"{{rag_context_or_daily_log}}"

User's Query:
"{{user_query}}"
```

*Note: Like the local executor, this prompt is paired with the `tools` parameter in the Gemini API call, but with the advanced tools like `schedule_followup_task`.*

---

### Setup & Prerequisites

**1. `requirements.txt`**

```
# Google API for Email
google-api-python-client
google-auth-oauthlib
google-auth-httplib2

# LLM Interaction
openai # For LM Studio's OpenAI-compatible server
google-cloud-aiplatform # For Vertex AI Gemini API

# Database
SQLAlchemy
ChromaDB

# Background Jobs
APScheduler

# Web UI
fastapi
uvicorn

# Packaging
PyInstaller

# Data validation (implicitly used by FastAPI, good to have explicit)
pydantic
```

**2. Your Setup**
    # --- FILE PATHS ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
    TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
    DB_PATH = os.path.join(BASE_DIR, 'aura_db.sqlite')
    LOG_PATH = os.path.join(BASE_DIR, 'aura_actions.log')

    # --- EMAIL SETTINGS ---
    AURA_EMAIL = "ethanxsteele@gmail.com"
    USER_EMAIL = "idlandes04@gmail.com"
    GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.modify'] # Read, send, delete

    # --- LLM SETTINGS ---
    # Local LLM (LM Studio)
    LMSTUDIO_API_BASE = "http://localhost:1234/v1"
    LOCAL_MODEL_ID = "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF" # Replace with your loaded model
    LOCAL_EMBEDDING_MODEL_ID = "nomic-ai/nomic-embed-text-v1.5-GGUF" # Replace if different

    # Cloud LLM (Gemini)
    GCP_PROJECT_ID = "aura-life-agent" # Replace with your GCP project ID
    GCP_LOCATION = "us-central1" # Or your preferred region
    GEMINI_MODEL_ID = "gemini-1.5-flash-001"

    # --- SCHEDULER SETTINGS ---
    SCHEDULER_INTERVAL_MINUTES = 5
    DAILY_DIGEST_TIME = "23:00" # 11 PM
    ```
6.  **First Run:** Execute `python auth_setup.py`. The browser will open. USer will log in to the `ethanxsteele@gmail.com` account and grant permissions. A `token.json` file should be created.
7.  **Launch Aura:** Execute `python main.py`. The system is now live.

This blueprint is comprehensive and sets you up for success. The path is clear. Take it one phase at a time, and you will build this system.