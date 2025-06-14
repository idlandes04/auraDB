# FILE: db_manager.py

import ontology
import db_models
import chromadb
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from config import DB_PATH, CHROMA_DB_PATH
from typing import Union, Tuple, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_url: str = f'sqlite:///{DB_PATH}'):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.contexts_collection = self.chroma_client.get_or_create_collection(name="contexts", metadata={"hnsw:space": "cosine"})

    def create_database(self):
        db_models.Base.metadata.create_all(self.engine)
        logger.info("Relational database tables checked/created.")

    @contextmanager
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- Context Management ---

    def create_context(self, name: str, summary_embedding: List[float]) -> ontology.Context:
        with self.session_scope() as session:
            new_db_context = db_models.Context(name=name, summary="New context, summary pending.", state="needs_summary")
            session.add(new_db_context)
            session.flush()
            context_id = new_db_context.id
            self.contexts_collection.add(ids=[str(context_id)], embeddings=[summary_embedding], metadatas=[{"name": name}])
            logger.info("Created new context '%s' with ID: %d", name, context_id)
            return ontology.Context.model_validate(new_db_context)

    def find_similar_contexts(self, query_embedding: List[float], n_results: int = 3) -> List[ontology.Context]:
        if not query_embedding: return []
        results = self.contexts_collection.query(query_embeddings=[query_embedding], n_results=n_results)
        context_ids = [int(id) for id in results['ids'][0]]
        if not context_ids: return []
        with self.session_scope() as session:
            db_contexts = session.query(db_models.Context).filter(db_models.Context.id.in_(context_ids)).all()
            return [ontology.Context.model_validate(c) for c in db_contexts]

    def get_context_by_id(self, context_id: int) -> Optional[ontology.Context]:
        with self.session_scope() as session:
            db_context = session.query(db_models.Context).filter(db_models.Context.id == context_id).first()
            return ontology.Context.model_validate(db_context) if db_context else None

    def get_contexts_needing_summary(self) -> List[ontology.Context]:
        with self.session_scope() as session:
            db_contexts = session.query(db_models.Context).filter(db_models.Context.state == 'needs_summary').all()
            return [ontology.Context.model_validate(c) for c in db_contexts]

    def get_content_for_context(self, context_id: int) -> str:
        content_parts = []
        with self.session_scope() as session:
            tasks = session.query(db_models.Task).filter(db_models.Task.context_id == context_id).order_by(db_models.Task.created_at.desc()).all()
            for t in tasks: content_parts.append(f"Task: {t.content} (Due: {t.due_date.strftime('%Y-%m-%d') if t.due_date else 'N/A'})")
            notes = session.query(db_models.Note).filter(db_models.Note.context_id == context_id).order_by(db_models.Note.created_at.desc()).all()
            for n in notes: content_parts.append(f"Note: {n.content}")
            events = session.query(db_models.Event).filter(db_models.Event.context_id == context_id).order_by(db_models.Event.start_time.desc()).all()
            for e in events: content_parts.append(f"Event: {e.title} (Starts: {e.start_time.strftime('%Y-%m-%d %H:%M')}) - {e.description or ''}")
        return "\n".join(content_parts)

    def update_context_summary(self, context_id: int, new_summary: str, new_embedding: List[float]):
        with self.session_scope() as session:
            session.query(db_models.Context).filter(db_models.Context.id == context_id).update({
                "summary": new_summary,
                "state": "stable",
                "last_updated_utc": datetime.utcnow()
            })
        if new_embedding:
            self.contexts_collection.upsert(ids=[str(context_id)], embeddings=[new_embedding], metadatas=[{"name": "Context summary updated"}])
        logger.info("Updated summary for Context ID: %d", context_id)

    def get_full_context_data(self, context_id: int) -> str:
        return self.get_content_for_context(context_id)

    # --- Record Management ---

    def add_record(self, pydantic_obj: Union[ontology.Task, ontology.Note, ontology.Event], expiry_date: Optional[datetime] = None) -> Tuple[str, int]:
        db_record = None
        record_data = pydantic_obj.model_dump()
        
        if 'context_id' not in record_data or record_data['context_id'] is None:
            raise ValueError("Cannot add a record without a valid context_id.")
        
        if 'created_at' in record_data and record_data['created_at'].tzinfo is None:
            record_data['created_at'] = record_data['created_at'].replace(tzinfo=timezone.utc)
            
        ModelClass = None
        if isinstance(pydantic_obj, ontology.Task):
            ModelClass = db_models.Task
        elif isinstance(pydantic_obj, ontology.Note):
            ModelClass = db_models.Note
        elif isinstance(pydantic_obj, ontology.Event):
            ModelClass = db_models.Event
            
        if not ModelClass:
            raise TypeError(f"Unsupported Pydantic object type: {type(pydantic_obj)}")
            
        db_record = ModelClass(**record_data, expiry_date=expiry_date)
        
        with self.session_scope() as session:
            session.add(db_record)
            session.flush()
            record_id = db_record.id
            record_type = type(db_record).__name__
            logger.info("Added %s with ID: %d to Context ID %d.", record_type, record_id, pydantic_obj.context_id)
            session.query(db_models.Context).filter(db_models.Context.id == pydantic_obj.context_id).update({"state": "needs_summary"})
        
        return record_type, record_id

    def get_due_tasks_and_events(self) -> List[ontology.DueItem]:
        now_utc = datetime.now(timezone.utc)
        due_items_to_return = []
        with self.session_scope() as session:
            due_tasks = session.query(db_models.Task).filter(db_models.Task.due_date <= now_utc, db_models.Task.reminder_sent == False, db_models.Task.completed == False).all()
            for task in due_tasks: due_items_to_return.append(ontology.DueItem(id=task.id, type="Task", content=task.content, due_date=task.due_date))
            due_events = session.query(db_models.Event).filter(db_models.Event.start_time <= now_utc, db_models.Event.reminder_sent == False).all()
            for event in due_events: due_items_to_return.append(ontology.DueItem(id=event.id, type="Event", content=event.title, due_date=event.start_time))
        return due_items_to_return

    def mark_as_reminded(self, record_type: str, record_id: int):
        model_class = None
        if record_type.lower() == 'task': model_class = db_models.Task
        elif record_type.lower() == 'event': model_class = db_models.Event
        else: return
        with self.session_scope() as session:
            session.query(model_class).filter(model_class.id == record_id).update({"reminder_sent": True})
            logger.info("Marked %s ID %d as reminder_sent=True.", record_type, record_id)

    def delete_expired_records(self) -> int:
        now_utc = datetime.now(timezone.utc)
        total_deleted = 0
        with self.session_scope() as session:
            for model in [db_models.Task, db_models.Note, db_models.Event]:
                query = session.query(model)
                if hasattr(model, 'permanence'):
                    query = query.filter(model.permanence == 'non-permanent', model.expiry_date <= now_utc)
                else: 
                    query = query.filter(model.expiry_date <= now_utc)
                
                # Use a subquery to get IDs to delete for compatibility across DB backends
                ids_to_delete = [item.id for item in query.with_entities(model.id).all()]
                if ids_to_delete:
                    count = len(ids_to_delete)
                    session.query(model).filter(model.id.in_(ids_to_delete)).delete(synchronize_session=False)
                    logger.info("Purged %d expired records of type %s.", count, model.__name__)
                    total_deleted += count
        return total_deleted