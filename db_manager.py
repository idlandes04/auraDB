import ontology
import db_models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from config import DB_PATH
from typing import Union

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

    def add_record(self, pydantic_obj: Union[ontology.Task, ontology.Note, ontology.Event], expiry_date=None) -> db_models.Base:
        """
        Adds a record to the database based on its Pydantic type.
        Returns the created database object with its new ID.
        """
        db_record = None
        if isinstance(pydantic_obj, ontology.Task):
            db_record = db_models.Task(**pydantic_obj.dict(), expiry_date=expiry_date)
        elif isinstance(pydantic_obj, ontology.Note):
            db_record = db_models.Note(**pydantic_obj.dict(), expiry_date=expiry_date)
        elif isinstance(pydantic_obj, ontology.Event):
            db_record = db_models.Event(**pydantic_obj.dict(), expiry_date=expiry_date)
        
        if not db_record:
            raise TypeError("Unsupported Pydantic object type")

        with self.session_scope() as session:
            session.add(db_record)
            session.flush()  # To get the ID before commit
            session.refresh(db_record) # To load all default values
            print(f"Added {type(db_record).__name__} with ID: {db_record.id} to DB.")
            return db_record