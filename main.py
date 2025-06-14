# FILE: main.py

import time
import json
import logging
from pydantic import ValidationError
from datetime import datetime, timezone

from logging_config import setup_logging
from llm_interface import call_router, call_executor, embed_text, generate_human_reply
from email_handler import get_latest_email, parse_email_body, send_reply, archive_email
from db_manager import DatabaseManager
from scheduler import AuraScheduler
import ontology
from config import EXECUTOR_PROMPT_CONTEXT_ANALYSIS, EXECUTOR_PROMPT_FINAL_ACTION

# --- Setup standardized logging ---
setup_logging()
logger = logging.getLogger(__name__)

ARGUMENT_MODEL_MAP = {
    "create_task": ontology.CreateTaskArguments,
    "store_note": ontology.StoreNoteArguments,
    "create_event": ontology.CreateEventArguments,
    "query_context": ontology.QueryContextArguments,
}

def process_email(db: DatabaseManager, original_msg: dict):
    email_body = parse_email_body(original_msg)
    logger.info("--- New Email Detected --- Body: %s", email_body)

    router_result = call_router(email_body)
    
    if not router_result:
        reply_msg = "Aura had trouble understanding the request's intent. The system may be operating on cloud failover or experiencing a connection issue."
        logger.error("ROUTER FAILED: Did not receive a valid response from the router model.")
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    logger.info("Router Output: %s", router_result)

    if router_result.get("routing_decision") != "local_processing":
        reply_msg = "Aura noted your message but routed it for cloud synthesis or determined no local action was needed."
        logger.info("Router Decision: %s. Halting local processing.", router_result.get('routing_decision', 'unknown'))
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    logger.info("Agent Step 1: Context Resolution")
    prompt_step1 = EXECUTOR_PROMPT_CONTEXT_ANALYSIS.replace("{{user_email_body}}", email_body)
    context_tool_call = call_executor(prompt_step1, ontology.TOOLS_STEP_1_CONTEXT)
    
    if not context_tool_call or context_tool_call.get("name") != "get_or_create_context":
        reply_msg = "Aura analyzed your request but could not determine its context."
        logger.error("AGENT_STEP_1 FAILED: Did not receive a valid get_or_create_context tool call. Response: %s", context_tool_call)
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return

    query = context_tool_call['arguments'].get('query')
    logger.info("Agent Step 1: LLM generated context query: '%s'", query)
    
    try:
        query_embedding = embed_text(query, instruction="Embed this query to find the most relevant project or category")
    except Exception as e:
        logger.critical("EMBEDDING FAILED: Fatal error for this request. Error: %s", e)
        reply_msg = "Aura could not process the context of your request due to a critical embedding system error."
        send_reply(original_msg, reply_msg)
        archive_email(original_msg['id'])
        return
        
    similar_contexts = db.find_similar_contexts(query_embedding)
    context_matches_str = json.dumps([c.model_dump(mode='json') for c in similar_contexts]) if similar_contexts else "No existing contexts found."
    logger.info("Agent Step 1: Potential Contexts Found: %s", context_matches_str)

    logger.info("Agent Step 2: Final Action Execution")
    current_date_str = datetime.now(timezone.utc).isoformat()
    prompt_step2 = EXECUTOR_PROMPT_FINAL_ACTION.replace("{{user_email_body}}", email_body)\
                                               .replace("{{context_matches}}", context_matches_str)\
                                               .replace("{{current_date}}", current_date_str)

    final_tool_call = call_executor(prompt_step2, ontology.TOOLS_STEP_2_ACTION)
    logger.info("Agent Step 2: Executor Output: %s", final_tool_call)

    if final_tool_call:
        system_confirmation = process_final_tool_call(db, final_tool_call, router_result, query_embedding)
    else:
        system_confirmation = "Aura understood the context but could not determine a final action to take."

    logger.info("System Technical Confirmation: %s", system_confirmation)
    
    if "ERROR" in system_confirmation:
        final_reply_msg = system_confirmation
    else:
        logger.info("Generating human-friendly reply...")
        final_reply_msg = generate_human_reply(email_body, system_confirmation)
    
    logger.info("Sending final reply: %s", final_reply_msg)
    send_reply(original_msg, final_reply_msg)
    archive_email(original_msg['id'])
    logger.info("--- Email Processing Complete ---")

def process_final_tool_call(db: DatabaseManager, tool_call: dict, router_result: dict, query_embedding: list) -> str:
    tool_name = tool_call.get("name")
    arguments = tool_call.get("arguments")
    
    if not tool_name or not arguments: return "ERROR: Malformed final tool call from Executor."
    ArgumentModel = ARGUMENT_MODEL_MAP.get(tool_name)
    if not ArgumentModel: return f"ERROR: Unknown tool '{tool_name}'."

    try:
        validated_args = ArgumentModel(**arguments)
        
        if tool_name == "query_context":
            context_data = db.get_full_context_data(validated_args.context_id)
            context_obj = db.get_context_by_id(validated_args.context_id)
            return f"QUERY RESULT for Context '{context_obj.name}':\n---\n{context_data}\n---"

        context_id = None
        if hasattr(validated_args, 'context_id') and validated_args.context_id:
            context_id = validated_args.context_id
        elif hasattr(validated_args, 'new_context_name') and validated_args.new_context_name:
            if not query_embedding: return "ERROR: Cannot create new context without a valid query embedding."
            new_context_obj = db.create_context(name=validated_args.new_context_name, summary_embedding=query_embedding)
            context_id = new_context_obj.id
        else:
            return "ERROR: Executor failed to specify an existing context_id or a new_context_name."

        final_context = db.get_context_by_id(context_id)
        if not final_context: return f"CRITICAL ERROR: Could not find context with ID {context_id} in DB."
        
        pydantic_obj = None
        if tool_name == "create_task":
            pydantic_obj = ontology.Task(
                content=validated_args.content, due_date=validated_args.due_date,
                permanence=router_result.get("permanence", "non-permanent"), context_id=final_context.id
            )
        elif tool_name == "store_note":
            pydantic_obj = ontology.Note(
                content=validated_args.content, permanence=router_result.get("permanence", "permanent"),
                context_id=final_context.id
            )
        elif tool_name == "create_event":
             pydantic_obj = ontology.Event(
                title=validated_args.title, start_time=validated_args.start_time, end_time=validated_args.end_time,
                description=validated_args.description, location=validated_args.location, context_id=final_context.id
            )

        if not pydantic_obj: return f"ERROR: Logic error, no final object created for tool '{tool_name}'."
        
        expiry_date_str = router_result.get("expiry_date")
        expiry_date_obj = datetime.fromisoformat(expiry_date_str.replace('Z', '+00:00')) if expiry_date_str else None
        
        record_type, record_id = db.add_record(pydantic_obj, expiry_date_obj)
        return f"CONFIRMED: {record_type} #{record_id} created successfully in Context: '{final_context.name}'."

    except ValidationError as e:
        return f"ERROR: Failed to validate arguments from LLM for '{tool_name}'. Details: {e}"
    except Exception as e:
        logger.error("An unexpected error occurred in process_final_tool_call: %s", e, exc_info=True)
        return f"ERROR: Could not process and save the request. Details: {e}"

def main():
    logger.info("--- Aura Phase 5: Resilient Maintainer (Finalized) ---")
    db = DatabaseManager()
    db.create_database()

    scheduler = AuraScheduler(db)
    scheduler.start()
    
    logger.info("Core system is live. Main loop started. Checking for emails...")
    logger.info("Scheduler is running in the background. Use Ctrl+C to shut down.")
    
    try:
        while True:
            original_msg = get_latest_email()
            if original_msg:
                process_email(db, original_msg)
            else:
                time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Shutting down scheduler...")
        scheduler.scheduler.shutdown()
        logger.info("System offline. Goodbye.")
    except Exception as e:
        logger.critical("A fatal error occurred in the main loop: %s", e, exc_info=True)
        scheduler.scheduler.shutdown()

if __name__ == "__main__":
    main()