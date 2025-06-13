# FILE: db_manager.py

import ontology
import db_models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from config import DB_PATH
from typing import Union, Tuple, List, Optional
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_url: str = f'sqlite:///{DB_PATH}'):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_database(self):
        """Creates all database tables if they don't exist."""
        db_models.Base.metadata.create_all(self.engine)
        print("Database tables checked/created.")

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_record(self, pydantic_obj: Union[ontology.Task, ontology.Note, ontology.Event], expiry_date: Optional[datetime] = None) -> Tuple[str, int]:
        """
        Adds a record to the database and returns its type and new ID.
        """
        db_record = None
        record_data = pydantic_obj.model_dump()

        if 'created_at' in record_data and record_data['created_at'].tzinfo is None:
            record_data['created_at'] = record_data['created_at'].replace(tzinfo=timezone.utc)

        if isinstance(pydantic_obj, ontology.Task):
            db_record = db_models.Task(**record_data, expiry_date=expiry_date)
        elif isinstance(pydantic_obj, ontology.Note):
            db_record = db_models.Note(**record_data, expiry_date=expiry_date)
        elif isinstance(pydantic_obj, ontology.Event):
            db_record = db_models.Event(**record_data, expiry_date=expiry_date)
        
        if not db_record:
            raise TypeError("Unsupported Pydantic object type")

        with self.session_scope() as session:
            session.add(db_record)
            session.flush()
            record_id = db_record.id
            record_type = type(db_record).__name__
            print(f"Added {record_type} with ID: {record_id} to DB.")

        return record_type, record_id

    def get_due_tasks_and_events(self) -> List[ontology.DueItem]:
        """
        Fetches all due tasks/events and returns them as simple DueItem objects.
        """
        now_utc = datetime.now(timezone.utc)
        due_items_to_return = []
        
        with self.session_scope() as session:
            due_tasks = session.query(db_models.Task).filter(
                db_models.Task.due_date <= now_utc,
                db_models.Task.reminder_sent == False,
                db_models.Task.completed == False
            ).all()

            for task in due_tasks:
                due_items_to_return.append(
                    ontology.DueItem(id=task.id, type="Task", content=task.content, due_date=task.due_date)
                )

            due_events = session.query(db_models.Event).filter(
                db_models.Event.start_time <= now_utc,
                db_models.Event.reminder_sent == False
            ).all()

            for event in due_events:
                 due_items_to_return.append(
                    ontology.DueItem(id=event.id, type="Event", content=event.title, due_date=event.start_time)
                )
            
        return due_items_to_return

    def mark_as_reminded(self, record_type: str, record_id: int):
        """Marks a specific task or event as having had its reminder sent."""
        model_class = None
        if record_type.lower() == 'task':
            model_class = db_models.Task
        elif record_type.lower() == 'event':
            model_class = db_models.Event
        else:
            return

        with self.session_scope() as session:
            session.query(model_class).filter(model_class.id == record_id).update({"reminder_sent": True})
            print(f"Marked {record_type} ID {record_id} as reminder_sent=True.")

    def delete_expired_records(self) -> int:
        """
        Deletes all records marked as non-permanent whose expiry_date has passed.
        Returns the number of records deleted.
        """
        now_utc = datetime.now(timezone.utc)
        total_deleted = 0
        with self.session_scope() as session:
            expired_tasks = session.query(db_models.Task).filter(
                db_models.Task.permanence == 'non-permanent',
                db_models.Task.expiry_date <= now_utc
            )
            total_deleted += expired_tasks.count()
            expired_tasks.delete(synchronize_session=False)

            expired_notes = session.query(db_models.Note).filter(
                db_models.Note.permanence == 'non-permanent',
                db_models.Note.expiry_date <= now_utc
            )
            total_deleted += expired_notes.count()
            expired_notes.delete(synchronize_session=False)

            # Events are rarely non-permanent, but we handle it just in case
            expired_events = session.query(db_models.Event).filter(
                db_models.Event.expiry_date <= now_utc
            )
            total_deleted += expired_events.count()
            expired_events.delete(synchronize_session=False)
            
        return total_deleted