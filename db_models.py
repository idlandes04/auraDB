# FILE: db_models.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    due_date = Column(DateTime, nullable=True)
    permanence = Column(Enum("permanent", "non-permanent", name="permanence_enum"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow) # Use UTC for consistency
    completed = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False, nullable=False) # New field
    expiry_date = Column(DateTime, nullable=True)

class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow) # Use UTC for consistency
    permanence = Column(Enum("permanent", "non-permanent", name="permanence_enum"), nullable=False)
    expiry_date = Column(DateTime, nullable=True)

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow) # Use UTC for consistency
    reminder_sent = Column(Boolean, default=False, nullable=False) # New field
    expiry_date = Column(DateTime, nullable=True)