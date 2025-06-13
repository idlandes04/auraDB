# FILE: main.py

import time
from pydantic import ValidationError
from datetime import datetime, timezone

from llm_interface import call_router, call_executor
from email_handler import get_latest_email, parse_email_body, send_reply, archive_email
from db_manager import DatabaseManager
from scheduler import AuraScheduler # Import the new scheduler
import ontology

TOOL_MODEL_MAP = {
    "create_task": ontology.Task,
    "store_note": ontology.Note,
    "create_event": ontology.Event
}

def process_email(db: DatabaseManager, original_msg: dict):
    """Processes a single email message."""
    email_body = parse_email_body(original_msg)
    print("\n--- New Email Detected ---")
    print(f"Body: {email_body}")
    print("--------------------------")

    print("\n[Router] Analyzing email...")
    router_result = call_router(email_body)
    print("Router Output:", router_result)

    if not router_result or router_result.get("routing_decision") != "local_processing":
        reply_msg = "Aura noted your message but has not processed it for local action (routing to cloud or unhandled)."
        print(reply_msg)
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    print("\n[Executor] Generating tool call...")
    executor_result = call_executor(email_body)
    print("Executor Output:", executor_result)
    
    reply_msg = ""
    if executor_result:
        reply_msg = process_tool_call(db, executor_result, router_result)
    else:
        reply_msg = "Aura analyzed your request but could not determine a specific action to take."

    print("\n[System] Sending final reply...")
    print("Reply content:", reply_msg)
    send_reply(original_msg, reply_msg)
    archive_email(original_msg['id'])
    print("\n--- Email Processing Complete ---")

def process_tool_call(db: DatabaseManager, tool_call: dict, router_result: dict):
    """Parses a tool call, validates it, and saves it to the database."""
    tool_name = tool_call.get("name")
    arguments = tool_call.get("arguments")
    
    if not tool_name or not arguments:
        return "ERROR: Malformed tool call from Executor."

    PydanticModel = TOOL_MODEL_MAP.get(tool_name)
    if not PydanticModel:
        return f"ERROR: Unknown tool '{tool_name}'."

    try:
        if 'created_at' not in arguments:
             arguments['created_at'] = datetime.now(timezone.utc)
        pydantic_obj = PydanticModel(**arguments)
        
        expiry_date_str = router_result.get("expiry_date")
        expiry_date_obj = None
        if expiry_date_str:
            if expiry_date_str.endswith('Z'):
                expiry_date_str = expiry_date_str[:-1] + '+00:00'
            expiry_date_obj = datetime.fromisoformat(expiry_date_str)
        
        record_type, record_id = db.add_record(pydantic_obj, expiry_date_obj)
        return f"CONFIRMED: {record_type} #{record_id} created successfully."

    except ValidationError as e:
        return f"ERROR: Failed to validate arguments for '{tool_name}'. Details: {e}"
    except Exception as e:
        return f"ERROR: Could not process and save the request. Details: {e}"

def main():
    print("--- Aura Phase 3: Proactive Agent ---")
    db = DatabaseManager()
    db.create_database()

    # --- Initialize and start the scheduler ---
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
                # Sleep to prevent constant, rapid-fire API calls when idle
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