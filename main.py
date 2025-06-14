# FILE: main.py

import time
import json
from pydantic import ValidationError
from datetime import datetime, timezone

from llm_interface import call_router, call_executor, embed_text, generate_human_reply
from email_handler import get_latest_email, parse_email_body, send_reply, archive_email
from db_manager import DatabaseManager
from scheduler import AuraScheduler
import ontology
from config import EXECUTOR_PROMPT_CONTEXT_ANALYSIS, EXECUTOR_PROMPT_FINAL_ACTION

# Maps the tool name from the LLM to the Pydantic model for the *arguments*
# This is a critical bridge between the unstructured LLM output and our structured code.
ARGUMENT_MODEL_MAP = {
    "create_task": ontology.CreateTaskArguments,
    "store_note": ontology.StoreNoteArguments,
    "create_event": ontology.CreateEventArguments,
}

def process_email(db: DatabaseManager, original_msg: dict):
    """
    Processes a single email message using a multi-step agentic chain.
    This is the core real-time logic of the application.
    """
    email_body = parse_email_body(original_msg)
    print("\n--- New Email Detected ---")
    print(f"Body: {email_body}")
    print("--------------------------")

    # The first gate: Is this something we should even process locally?
    router_result = call_router(email_body)
    
    if not router_result:
        reply_msg = "Aura had trouble understanding the request's intent."
        print("\n[Router] FAILED: Did not receive a valid response from the router model.")
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    print(f"\n[Router] Output: {router_result}")

    if router_result.get("routing_decision") != "local_processing":
        reply_msg = "Aura noted your message but routed it for cloud synthesis or determined no local action was needed."
        print(f"\n[Router] Decision: {router_result.get('routing_decision', 'unknown')}. Halting local processing.")
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    # --- AGENTIC CHAIN: STEP 1 - Context Resolution ---
    # First, we ask the LLM to simply figure out what the email is *about*.
    print("\n[Agent Step 1: Context Resolution]")
    prompt_step1 = EXECUTOR_PROMPT_CONTEXT_ANALYSIS.replace("{{user_email_body}}", email_body)
    context_tool_call = call_executor(prompt_step1, ontology.TOOLS_STEP_1_CONTEXT)
    
    if not context_tool_call or context_tool_call.get("name") != "get_or_create_context":
        reply_msg = "Aura analyzed your request but could not determine its context."
        print("[Agent Step 1] FAILED: Did not receive a valid get_or_create_context tool call.")
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    query = context_tool_call['arguments'].get('query')
    print(f"[Agent Step 1] LLM generated context query: '{query}'")
    query_embedding = embed_text(query, instruction="Embed this query to find the most relevant project or category")

    if not query_embedding:
        reply_msg = "Aura could not process the context of your request due to an embedding error."
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return
        
    similar_contexts = db.find_similar_contexts(query_embedding)
    
    if similar_contexts:
        # model_dump(mode='json') converts datetimes to ISO strings automatically.
        json_compatible_list = [c.model_dump(mode='json') for c in similar_contexts]
        context_matches_str = json.dumps(json_compatible_list)
    else:
        context_matches_str = "No existing contexts found."
    
    print(f"[Agent Step 1] Potential Contexts Found: {context_matches_str}")

    # --- AGENTIC CHAIN: STEP 2 - Final Action ---
    # Now that we have potential contexts, we ask the LLM to make a final decision and action.
    print("\n[Agent Step 2: Final Action Execution]")
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt_step2 = EXECUTOR_PROMPT_FINAL_ACTION.replace("{{user_email_body}}", email_body)\
                                               .replace("{{context_matches}}", context_matches_str)\
                                               .replace("{{current_date}}", current_date_str)

    print(f"[Agent Step 2] Sending final action prompt to LLM...")

    final_tool_call = call_executor(prompt_step2, ontology.TOOLS_STEP_2_ACTION)
    print(f"[Agent Step 2] Executor Output: {final_tool_call}")

    # Process the result and generate the technical confirmation message
    if final_tool_call:
        system_confirmation = process_final_tool_call(db, final_tool_call, router_result, query_embedding)
    else:
        system_confirmation = "Aura understood the context but could not determine a final action to take."

    print(f"\n[System] Technical Confirmation: {system_confirmation}")
    
    # Generate the final human-friendly reply based on the technical confirmation.
    if "ERROR" in system_confirmation:
        final_reply_msg = system_confirmation
    else:
        print("[System] Generating human-friendly reply...")
        final_reply_msg = generate_human_reply(email_body, system_confirmation)
    
    print("[System] Sending final reply...")
    print(f"Reply content: {final_reply_msg}")
    send_reply(original_msg, final_reply_msg)
    archive_email(original_msg['id'])
    print("\n--- Email Processing Complete ---")

def process_final_tool_call(db: DatabaseManager, tool_call: dict, router_result: dict, query_embedding: list) -> str:
    """
    Parses the final tool call from the LLM, handles context creation/selection,
    validates all data, and saves the final record to the database.
    Returns a technical confirmation message (success or error).
    """
    tool_name = tool_call.get("name")
    arguments = tool_call.get("arguments")
    
    if not tool_name or not arguments:
        return "ERROR: Malformed final tool call from Executor."

    ArgumentModel = ARGUMENT_MODEL_MAP.get(tool_name)
    if not ArgumentModel:
        return f"ERROR: Unknown tool '{tool_name}'."

    try:
        # Step 1: Validate the raw arguments from the LLM against our Pydantic schema.
        validated_args = ArgumentModel(**arguments)

        # Step 2: Determine the context_id. This is a critical decision point.
        context_id = None
        if validated_args.context_id:
            context_id = validated_args.context_id
        elif validated_args.new_context_name:
            # If the LLM wants to create a new context, do it and get the new ID.
            new_context_obj = db.create_context(name=validated_args.new_context_name, summary_embedding=query_embedding)
            context_id = new_context_obj.id
        else:
            return "ERROR: Executor failed to specify an existing context_id or a new_context_name."

        # Step 3: Fetch the definitive context object for use in the reply message.
        final_context = db.get_context_by_id(context_id)
        if not final_context:
            return f"CRITICAL ERROR: Could not find context with ID {context_id} in the database after creation/selection."
        
        # Step 4: Construct the final Pydantic data object for database insertion.
        # This ensures all data is correctly typed and structured.
        pydantic_obj = None
        if tool_name == "create_task":
            pydantic_obj = ontology.Task(
                content=validated_args.content,
                due_date=validated_args.due_date,
                permanence=router_result.get("permanence", "non-permanent"), # Use router's decision
                context_id=final_context.id
            )
        elif tool_name == "store_note":
            pydantic_obj = ontology.Note(
                content=validated_args.content,
                permanence=router_result.get("permanence", "permanent"), # Use router's decision
                context_id=final_context.id
            )
        elif tool_name == "create_event":
             pydantic_obj = ontology.Event(
                title=validated_args.title,
                start_time=validated_args.start_time,
                end_time=validated_args.end_time,
                description=validated_args.description,
                location=validated_args.location,
                context_id=final_context.id
            )

        if not pydantic_obj:
            return f"ERROR: Logic error, no final object created for tool '{tool_name}'."

        # Step 5: Add the fully validated record to the database.
        expiry_date_str = router_result.get("expiry_date")
        expiry_date_obj = datetime.fromisoformat(expiry_date_str.replace('Z', '+00:00')) if expiry_date_str else None
        
        record_type, record_id = db.add_record(pydantic_obj, expiry_date_obj)
            
        return f"CONFIRMED: {record_type} #{record_id} created successfully in Context: '{final_context.name}'."

    except ValidationError as e:
        return f"ERROR: Failed to validate arguments from LLM for '{tool_name}'. Details: {e}"
    except Exception as e:
        print(f"An unexpected error occurred in process_final_tool_call: {e}")
        return f"ERROR: Could not process and save the request. Details: {e}"

def main():
    """
    The main entry point of the Aura application.
    Initializes the database and scheduler, then enters the main email processing loop.
    """
    print("--- Aura Phase 4: Semantic Engine (Corrected) ---")
    db = DatabaseManager()
    db.create_database()

    scheduler = AuraScheduler(db)
    scheduler.start()
    
    print("\n[Core] System is live. Main loop started. Checking for emails...")
    print("[Core] Scheduler is running in the background.")
    
    try:
        while True:
            original_msg = get_latest_email()
            if original_msg:
                process_email(db, original_msg)
            else:
                # Wait before checking for new emails again to avoid spamming the API
                time.sleep(10)
    except KeyboardInterrupt:
        print("\n[Core] Shutdown signal received. Shutting down scheduler...")
        scheduler.scheduler.shutdown()
        print("[Core] System offline. Goodbye.")
    except Exception as e:
        print(f"\n[Core] A fatal error occurred: {e}")
        scheduler.scheduler.shutdown()

if __name__ == "__main__":
    main()