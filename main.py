import time
from pydantic import ValidationError
from datetime import datetime
from llm_interface import call_router, call_executor
from email_handler import get_latest_email, parse_email_body, send_reply, archive_email
from db_manager import DatabaseManager
import ontology

# Mapping tool names to their Pydantic argument models
TOOL_MODEL_MAP = {
    "create_task": ontology.Task,
    "store_note": ontology.Note,
    "create_event": ontology.Event
}

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
        # Validate and create the Pydantic object from arguments
        pydantic_obj = PydanticModel(**arguments)
        
        # Convert the expiry_date string from the router to a datetime object
        expiry_date_str = router_result.get("expiry_date")
        expiry_date_obj = None
        if expiry_date_str:
            # The 'Z' at the end for Zulu/UTC is handled by fromisoformat in Python 3.11+
            # For broader compatibility, we explicitly handle it.
            if expiry_date_str.endswith('Z'):
                expiry_date_str = expiry_date_str[:-1] + '+00:00'
            expiry_date_obj = datetime.fromisoformat(expiry_date_str)
        
        # Call the database manager and unpack the returned simple tuple
        record_type, record_id = db.add_record(pydantic_obj, expiry_date_obj)
        
        # Build the confirmation message from the simple data
        return f"CONFIRMED: {record_type} #{record_id} created successfully."

    except ValidationError as e:
        return f"ERROR: Failed to validate arguments for '{tool_name}'. Details: {e}"
    except Exception as e:
        return f"ERROR: Could not process and save the request. Details: {e}"

def main():
    print("--- Aura Phase 2: Memory Core ---")
    db = DatabaseManager()
    db.create_database()

    print("Checking for new email...")
    original_msg = get_latest_email()

    if not original_msg:
        print("No new email to process. Exiting.")
        return

    email_body = parse_email_body(original_msg)
    print("\n--- Email Body ---")
    print(email_body)
    print("--------------------")

    print("\n[Router] Analyzing email...")
    router_result = call_router(email_body)
    print("Router Output:", router_result)

    if not router_result or router_result.get("routing_decision") != "local_processing":
        reply_msg = "Aura received your message but has not processed it for local action."
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
    
    print("\n--- Cycle Complete ---")

if __name__ == "__main__":
    main()