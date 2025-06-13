Aura Development Plan: V5 (Final)

This is the definitive roadmap for creating a proactive, self-maintaining, conversational cognitive partner.

Phases 0-3: The Foundation (ARCHIVED & COMPLETE)

Status: Perfected. The secure email channel, the local LLM interface, the relational database core, and the proactive scheduler form the bedrock upon which we now build.

Phase 4: The Core Semantic Engine

Objective: To imbue Aura with a deep, semantic understanding of your data. We will replace simple keyword matching with meaning-based retrieval and organization, creating an intelligent, self-organizing knowledge base.

Key Architectural Components & Tasks:

Database Schema Evolution:

Implement the Contexts table (id, name, summary, state, last_updated_utc). The state field (e.g., 'stable', 'needs_summary') will drive our asynchronous maintenance.

Add context_id as a foreign key to the tasks, notes, and events tables.

Vector Database & Advanced Embeddings:

Integrate ChromaDB.

Integrate the Qwen3-Embedding-8B model.

In llm_interface.py, create a function that uses instruction-tuned prompts for embedding (e.g., embed_text(text, instruction)).

The Semantic Resolution Engine:

Update the get_or_create_context tool to be the core of the engine.

Flow: When a new email arrives, the Executor's first step is to call this tool. The db_manager will:
a. Embed the user's query using a specific "find context" instruction.
b. Search the contexts vector collection in ChromaDB for the top 3-5 most similar existing Contexts.
c. Return this list of potential matches (including their summaries) to the Executor.

Agentic Executor Loop:

Re-architect the main.py processing loop. It will now support multi-step chains.

Flow:
a. Step 1: Call the Executor with the user's email. It will call get_or_create_context.
b. Step 2: The list of potential contexts is fed back into the Executor in a second API call. The prompt will ask: "Given these potential matches, should you use an existing one or create a new one? Then, generate the final tool call (create_task, store_note) with the correct context_id."

Go/No-Go Checkpoint: User emails, "Remember that arpeggios are a great practice technique." The agent, seeing the similarity to a "Guitar" context, correctly associates the new note with it, even though the word "guitar" was never used. The database shows the new note linked to the correct context_id.

Phase 5: The Resilient & Autonomous Maintainer

Objective: To make Aura self-sufficient and robust. It will learn to maintain its own knowledge base and operate flawlessly even if local resources are constrained.

Key Architectural Components & Tasks:

Event-Driven Summarization:

When a new note is added to a Context, its state in the database is changed to needs_summary.

A new, frequent APScheduler job (summarization_worker) runs every 15 minutes. It looks for Contexts in this state.

For each one, it bundles the content, sends it to Gemini 2.5 Flash for a quick, cheap summary, and updates the summary field and the vector embedding. The state is then set back to stable.

Compute Failover System:

In llm_interface.py, wrap the call_executor's local API call in a try...except block with a specific timeout.

If the local model fails or times out, the except block will log a warning and immediately re-route the exact same request to the Gemini 2.5 Flash API. This ensures Aura is always responsive.

Go/No-Go Checkpoint: The user adds five new notes to a project. The LM Studio server is then manually shut down. A few minutes later, the summary for that project is updated in the database. The user then sends another email, and it is processed successfully, with console logs indicating it was handled by the cloud failover.

Phase 6: The Proactive Cognitive Partner

Objective: To elevate Aura from an agent to a partner. This is where we implement the deep reasoning, conversational follow-up, and strategic insights that fulfill the core vision.

Key Architectural Components & Tasks:

The Grand Audit Nightly Job:

A daily job calls Gemini 2.5 Pro, the high-IQ model.

It orchestrates a chain of API calls, each with a specific task:
a. Contradiction Detection: "Review these pairs of notes from the 'Health' context. Do they contradict? If so, formulate a question for the user."
b. Redundancy & Culling Analysis: "Review these tasks from 5 years ago in the 'Old Projects' context. Are they still relevant? Suggest items for archival."
c. Strategic Synthesis: "Review all context summaries. Are there any surprising connections or emergent themes? Formulate three insights for the user."

The Stateful Conversation Handler:

Create a new conversations table in the database (id, thread_id, state, pending_questions).

When the Audit job generates its questions, it creates a new entry in this table and sends the daily brief email. The email's Message-ID is linked to the thread_id.

The Follow-Up Engine:
a. email_handler.py is updated to check incoming emails. If an In-Reply-To header matches an active conversation, it's routed to a special function.
b. This function retrieves the pending_questions from the DB and calls Gemini 2.5 Pro with a prompt: "Here are the questions I asked the user. Here is their reply. Convert their answers into the specific tool calls required (merge_contexts, delete_note, etc.)."
c. The system executes these tool calls.
d. A final confirmation email is sent, and the conversation state is marked resolved.

Go/No-Go Checkpoint: Aura sends its daily brief with a question: "I noticed conflicting information about your investment strategy. Do you want to remove the older note?" The user replies, "Yes, please remove the old one." Aura performs the deletion in the database and sends a final email: "CONFIRMED: The older note has been removed as requested."

Phase 7: The Command Center (UI)

Objective: Build the local FastAPI dashboard. Its design will now be context-centric, allowing you to browse your entire knowledge graph intuitively. (Functionally unchanged, but with a richer data source).

Phase 8: Packaging & Deployment

Objective: Package the entire, sophisticated application into a single, portable executable using PyInstaller. (Unchanged).

Phase 9: The "Everything" Archive

Objective: Expand Aura's data ingestion to include files, images, and documents, making it a true universal archive for your digital life. (Unchanged).

This is Aura V5. It is a complete, end-to-end blueprint for a system that is intelligent, resilient, proactive, and conversational. It directly addresses every requirement and piece of feedback you've provided, grounding your ambitious vision in a concrete, achievable engineering plan.