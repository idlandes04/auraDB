from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    due_date = Column(DateTime, nullable=True)
    permanence = Column(Enum("permanent", "non-permanent", name="permanence_enum"), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    completed = Column(Boolean, default=False)
    expiry_date = Column(DateTime, nullable=True) # For future self-cleaning

class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    permanence = Column(Enum("permanent", "non-permanent", name="permanence_enum"), nullable=False)
    expiry_date = Column(DateTime, nullable=True) # For future self-cleaning

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    expiry_date = Column(DateTime, nullable=True) # For future self-cleaning