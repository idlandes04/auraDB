# FILE: scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from db_manager import DatabaseManager
from email_handler import send_system_email
import llm_interface 
from config import SCHEDULER_INTERVAL_MINUTES, SUMMARIZATION_INTERVAL_MINUTES
import logging

logger = logging.getLogger(__name__)

class AuraScheduler:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def _check_and_send_reminders(self):
        logger.info("Running job: Check for reminders.")
        due_items = self.db.get_due_tasks_and_events()
        if not due_items:
            logger.info("No due items found.")
            return
        for item in due_items:
            try:
                if item.type == 'Task':
                    subject = f"Aura Reminder: {item.content}"
                    body = f"This is a reminder for your task:\n\n'{item.content}'\n\nThis was due at {item.due_date.strftime('%Y-%m-%d %H:%M:%S')} UTC."
                    send_system_email(subject, body)
                    self.db.mark_as_reminded('task', item.id)
                    logger.info("Sent reminder for Task ID: %d", item.id)

                elif item.type == 'Event':
                    subject = f"Aura Reminder: {item.content}"
                    body = f"This is a reminder for your event:\n\n'{item.content}'\n\nThis is scheduled for {item.due_date.strftime('%Y-%m-%d %H:%M:%S')} UTC."
                    send_system_email(subject, body)
                    self.db.mark_as_reminded('event', item.id)
                    logger.info("Sent reminder for Event ID: %d", item.id)
            except Exception as e:
                logger.error("Failed to send reminder for %s ID: %d. Error: %s", item.type, item.id, e)

    def _purge_expired_records(self):
        logger.info("Running job: Purge expired records.")
        try:
            num_deleted = self.db.delete_expired_records()
            if num_deleted > 0:
                logger.info("Purged %d expired record(s) from the database.", num_deleted)
            else:
                logger.info("No expired records to purge.")
        except Exception as e:
            logger.error("Failed during expired record purge. Error: %s", e, exc_info=True)
            
    def _run_summarization_worker(self):
        """
        Job to find contexts needing a summary, generate one, and update the DB.
        """
        logger.info("Running job: Summarization worker.")
        contexts_to_update = self.db.get_contexts_needing_summary()

        if not contexts_to_update:
            logger.info("No contexts need summarization.")
            return

        logger.info("Found %d context(s) to summarize.", len(contexts_to_update))
        for context in contexts_to_update:
            try:
                logger.info("Processing context ID: %d ('%s')", context.id, context.name)
                content_data = self.db.get_content_for_context(context.id)
                if not content_data:
                    logger.warning("Context %d has no content. Marking as stable with empty summary.", context.id)
                    self.db.update_context_summary(context.id, "No content available.", [])
                    continue
                
                new_summary = llm_interface.generate_summary_with_vertex_ai(content_data)
                if not new_summary:
                    logger.error("Failed to generate summary for context %d. Will retry next cycle.", context.id)
                    continue

                new_embedding = llm_interface.embed_text(new_summary, instruction="Embed this project summary for semantic search")
                
                self.db.update_context_summary(context.id, new_summary, new_embedding)
                logger.info("Successfully summarized and updated context ID: %d", context.id)

            except Exception as e:
                logger.error("Failed to process context ID: %d. State remains 'needs_summary' for next run. Error: %s", context.id, e, exc_info=True)

    def start(self):
        self.scheduler.add_job(
            self._check_and_send_reminders, 'interval', 
            minutes=SCHEDULER_INTERVAL_MINUTES, id='job_reminders'
        )
        self.scheduler.add_job(
            self._purge_expired_records, 'interval', 
            minutes=SCHEDULER_INTERVAL_MINUTES, id='job_purge'
        )
        self.scheduler.add_job(
            self._run_summarization_worker, 'interval', 
            minutes=SUMMARIZATION_INTERVAL_MINUTES, id='job_summarizer'
        )
        
        self.scheduler.start()
        logger.info("Scheduler started. Reminder/purge jobs run every %d mins. Summarizer job runs every %d mins.", SCHEDULER_INTERVAL_MINUTES, SUMMARIZATION_INTERVAL_MINUTES)