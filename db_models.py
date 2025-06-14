# FILE: db_models.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Context(Base):
    __tablename__ = 'contexts'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    summary = Column(String, nullable=True)
    state = Column(Enum("stable", "needs_summary", name="context_state_enum"), default="stable", nullable=False)
    last_updated_utc = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    due_date = Column(DateTime, nullable=True)
    permanence = Column(Enum("permanent", "non-permanent", name="permanence_enum"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False, nullable=False)
    expiry_date = Column(DateTime, nullable=True)
    
    context_id = Column(Integer, ForeignKey('contexts.id'), nullable=False)
    context_rel = relationship("Context") # FIX: Renamed from 'context' to avoid conflicts

class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    permanence = Column(Enum("permanent", "non-permanent", name="permanence_enum"), nullable=False)
    expiry_date = Column(DateTime, nullable=True)

    context_id = Column(Integer, ForeignKey('contexts.id'), nullable=False)
    context_rel = relationship("Context") # FIX: Renamed from 'context' to avoid conflicts

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reminder_sent = Column(Boolean, default=False, nullable=False)
    expiry_date = Column(DateTime, nullable=True)

    context_id = Column(Integer, ForeignKey('contexts.id'), nullable=False)
    context_rel = relationship("Context") # FIX: Renamed from 'context' to avoid conflicts