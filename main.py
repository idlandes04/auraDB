# Main application entry point for Aura Phase 1
# Orchestrates: fetches email, routes, executes, prints/logs results

from llm_interface import call_router, call_executor
from email_handler import get_latest_email_body

def main():
    print("--- Aura Phase 1: Local Brain Test ---")
    print("Checking for new email...")
    email_body = get_latest_email_body()

    if not email_body:
        print("No new email to process. Exiting.")
        return

    print("\n--- Email Body ---")
    print(email_body)
    print("--------------------")


    print("\n[Router] Analyzing email...")
    router_result = call_router(email_body)
    print("Router Output:", router_result)

    if not router_result or router_result.get("routing_decision") != "local_processing":
        print("[Router] Not routed for local processing. Exiting.")
        return

    print("\n[Executor] Generating tool call...")
    executor_result = call_executor(email_body)
    print("Executor Output:", executor_result)
    print("\nPhase 1 test complete. If output matches expectations, proceed to next phase.")

if __name__ == "__main__":
    main()