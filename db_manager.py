import ontology
import db_models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from config import DB_PATH
from typing import Union, Tuple
from datetime import datetime

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

    def add_record(self, pydantic_obj: Union[ontology.Task, ontology.Note, ontology.Event], expiry_date: datetime = None) -> Tuple[str, int]:
        """
        Adds a record to the database and returns its type and new ID.
        """
        db_record = None
        # Pydantic's .dict() is now deprecated in v2, .model_dump() is the new standard
        # but since we are on v1 lets stick with .dict()
        record_data = pydantic_obj.dict()

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
            session.flush()  # To get the ID before commit
            
            # Get the necessary info before the session closes
            record_id = db_record.id
            record_type = type(db_record).__name__
            print(f"Added {record_type} with ID: {record_id} to DB.")

        # Return simple, detached data, not the stateful object
        return record_type, record_id