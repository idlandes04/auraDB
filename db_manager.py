# FILE: db_manager.py

import ontology
import db_models
import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from config import DB_PATH, CHROMA_DB_PATH
from typing import Union, Tuple, List, Optional
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_url: str = f'sqlite:///{DB_PATH}'):
        # Relational DB Setup
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        
        # Vector DB Setup
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.contexts_collection = self.chroma_client.get_or_create_collection(
            name="contexts",
            metadata={"hnsw:space": "cosine"} # Using cosine similarity
        )

    def create_database(self):
        """Creates all relational database tables if they don't exist."""
        db_models.Base.metadata.create_all(self.engine)
        print("Relational database tables checked/created.")

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

    # --- Context Management (New for Phase 4) ---

    def create_context(self, name: str, summary_embedding: List[float]) -> ontology.Context:
        """Creates a new context in both relational and vector DBs."""
        with self.session_scope() as session:
            # Create in relational DB
            new_db_context = db_models.Context(name=name, summary="New context, summary pending.")
            session.add(new_db_context)
            session.flush()
            context_id = new_db_context.id
            
            # Create in vector DB
            self.contexts_collection.add(
                ids=[str(context_id)],
                embeddings=[summary_embedding],
                metadatas=[{"name": name}]
            )
            print(f"Created new context '{name}' with ID: {context_id}")
            return ontology.Context.model_validate(new_db_context)

    def find_similar_contexts(self, query_embedding: List[float], n_results: int = 3) -> List[ontology.Context]:
        """Finds the most similar contexts from the vector DB."""
        results = self.contexts_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        context_ids = [int(id) for id in results['ids'][0]]
        if not context_ids:
            return []

        with self.session_scope() as session:
            db_contexts = session.query(db_models.Context).filter(db_models.Context.id.in_(context_ids)).all()
            return [ontology.Context.model_validate(c) for c in db_contexts]

    def get_context_by_id(self, context_id: int) -> Optional[ontology.Context]:
        """Retrieves a single context by its ID."""
        with self.session_scope() as session:
            db_context = session.query(db_models.Context).filter(db_models.Context.id == context_id).first()
            if db_context:
                return ontology.Context.model_validate(db_context)
            return None

    # --- Record Management (Updated for Phase 4) ---

    def add_record(self, pydantic_obj: Union[ontology.Task, ontology.Note, ontology.Event], expiry_date: Optional[datetime] = None) -> Tuple[str, int]:
        """Adds a record to the database, ensuring it's linked to a context."""
        db_record = None
        record_data = pydantic_obj.model_dump()

        if 'context_id' not in record_data or record_data['context_id'] is None:
            raise ValueError("Cannot add a record without a valid context_id.")

        if 'created_at' in record_data and record_data['created_at'].tzinfo is None:
            record_data['created_at'] = record_data['created_at'].replace(tzinfo=timezone.utc)

        ModelClass = None
        if isinstance(pydantic_obj, ontology.Task): ModelClass = db_models.Task
        elif isinstance(pydantic_obj, ontology.Note): ModelClass = db_models.Note
        elif isinstance(pydantic_obj, ontology.Event): ModelClass = db_models.Event

        if not ModelClass:
            raise TypeError("Unsupported Pydantic object type")
            
        db_record = ModelClass(**record_data, expiry_date=expiry_date)

        with self.session_scope() as session:
            session.add(db_record)
            session.flush()
            record_id = db_record.id
            record_type = type(db_record).__name__
            print(f"Added {record_type} with ID: {record_id} to Context ID {pydantic_obj.context_id}.")

            # Mark context as needing a summary update
            session.query(db_models.Context).filter(db_models.Context.id == pydantic_obj.context_id).update({"state": "needs_summary"})

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
            for model in [db_models.Task, db_models.Note, db_models.Event]:
                query = session.query(model)
                # Check for permanence attribute before filtering
                if hasattr(model, 'permanence'):
                    query = query.filter(model.permanence == 'non-permanent', model.expiry_date <= now_utc)
                else: # Events might not have permanence but can have an expiry_date
                    query = query.filter(model.expiry_date <= now_utc)
                
                count = query.count()
                if count > 0:
                    total_deleted += count
                    query.delete(synchronize_session=False)
        return total_deleted