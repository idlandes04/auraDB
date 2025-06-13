from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# --- Core Data Structures ---
class Task(BaseModel):
    content: str
    due_date: Optional[datetime] = None
    permanence: Literal["permanent", "non-permanent"] = "non-permanent"
    created_at: Optional[datetime] = None
    completed: bool = False

class Note(BaseModel):
    content: str
    created_at: Optional[datetime] = None
    permanence: Literal["permanent", "non-permanent"] = "permanent"

class Event(BaseModel):
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None

# --- Tool Schemas ---
class CreateTaskArguments(BaseModel):
    content: str
    due_date: Optional[datetime] = None
    permanence: Literal["permanent", "non-permanent"] = "non-permanent"

class StoreNoteArguments(BaseModel):
    content: str
    permanence: Literal["permanent", "non-permanent"] = "permanent"

class CreateEventArguments(BaseModel):
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None

# Tool definitions for LLM function-calling
TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task/reminder for the user.",
        "parameters": CreateTaskArguments.schema(),
    },
    {
        "name": "store_note",
        "description": "Store a note for the user.",
        "parameters": StoreNoteArguments.schema(),
    },
    {
        "name": "create_event",
        "description": "Create a calendar event for the user.",
        "parameters": CreateEventArguments.schema(),
    },
]
