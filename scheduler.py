# FILE: scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from db_manager import DatabaseManager
from email_handler import send_system_email
from config import SCHEDULER_INTERVAL_MINUTES
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AuraScheduler:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def _check_and_send_reminders(self):
        """
        Job to check for due tasks and events and send email reminders.
        """
        logging.info("[Scheduler] Running job: Check for reminders.")
        
        due_items = self.db.get_due_tasks_and_events()

        if not due_items:
            logging.info("[Scheduler] No due items found.")
            return

        for item in due_items:
            try:
                if item.type == 'Task':
                    subject = f"Aura Reminder: {item.content}"
                    body = f"This is a reminder for your task:\n\n'{item.content}'\n\nThis was due at {item.due_date.strftime('%Y-%m-%d %H:%M:%S')} UTC."
                    send_system_email(subject, body)
                    self.db.mark_as_reminded('task', item.id)
                    logging.info(f"[Scheduler] Sent reminder for Task ID: {item.id}")

                elif item.type == 'Event':
                    subject = f"Aura Reminder: {item.content}" # item.content now holds the title
                    body = f"This is a reminder for your event:\n\n'{item.content}'\n\nThis is scheduled for {item.due_date.strftime('%Y-%m-%d %H:%M:%S')} UTC."
                    send_system_email(subject, body)
                    self.db.mark_as_reminded('event', item.id)
                    logging.info(f"[Scheduler] Sent reminder for Event ID: {item.id}")
            except Exception as e:
                logging.error(f"[Scheduler] Failed to send reminder for {item.type} ID: {item.id}. Error: {e}")

    def _purge_expired_records(self):
        """
        Job to delete non-permanent records that have passed their expiry date.
        """
        logging.info("[Scheduler] Running job: Purge expired records.")
        num_deleted = self.db.delete_expired_records()
        if num_deleted > 0:
            logging.info(f"[Scheduler] Purged {num_deleted} expired record(s) from the database.")
        else:
            logging.info("[Scheduler] No expired records to purge.")

    def start(self):
        """
        Adds jobs to the scheduler and starts it.
        """
        self.scheduler.add_job(
            self._check_and_send_reminders,
            'interval',
            minutes=SCHEDULER_INTERVAL_MINUTES,
            id='job_reminders'
        )
        self.scheduler.add_job(
            self._purge_expired_records,
            'interval',
            minutes=SCHEDULER_INTERVAL_MINUTES,
            id='job_purge'
        )
        
        self.scheduler.start()
        logging.info(f"[Scheduler] Started. Jobs will run every {SCHEDULER_INTERVAL_MINUTES} minutes.")