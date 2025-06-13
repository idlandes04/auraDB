# ontology.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# --- Core Data Structures ---
# These are the Pydantic models used for data validation and transfer between modules.

class Task(BaseModel):
    content: str
    due_date: Optional[datetime] = None
    permanence: Literal["permanent", "non-permanent"] = "non-permanent"
    created_at: datetime = Field(default_factory=datetime.now) # Ensure this is always set
    completed: bool = False

class Note(BaseModel):
    content: str
    created_at: datetime = Field(default_factory=datetime.now) # Ensure this is always set
    permanence: Literal["permanent", "non-permanent"] = "permanent"

class Event(BaseModel):
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now) # Ensure this is always set

# --- Tool Schemas for LLM ---
# (The rest of the file is unchanged)
class CreateTaskArguments(BaseModel):
    content: str = Field(..., description="The content or description of the task.")
    due_date: Optional[datetime] = Field(None, description="The date and time the task is due. Should be in ISO 8601 format.")
    permanence: Literal["permanent", "non-permanent"] = Field("non-permanent", description="Is the task a temporary reminder or a long-term goal?")

class StoreNoteArguments(BaseModel):
    content: str = Field(..., description="The full content of the note to be stored.")
    permanence: Literal["permanent", "non-permanent"] = Field("permanent", description="Is this a permanent piece of information or a fleeting thought?")

class CreateEventArguments(BaseModel):
    title: str = Field(..., description="The title of the calendar event.")
    start_time: datetime = Field(..., description="The start date and time of the event in ISO 8601 format.")
    end_time: Optional[datetime] = Field(None, description="The end date and time of the event in ISO 8601 format.")
    description: Optional[str] = Field(None, description="A detailed description of the event.")
    location: Optional[str] = Field(None, description="The physical location or meeting link for the event.")

# --- New Data Transfer Object ---
class DueItem(BaseModel):
    """A simple, inert data structure for passing reminder info."""
    id: int
    type: Literal["Task", "Event"]
    content: str # Will hold task content or event title
    due_date: datetime

# Tool definitions for LLM function-calling
TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task, to-do item, or reminder for the user. Use for actionable items.",
        "parameters": CreateTaskArguments.schema(),
    },
    {
        "name": "store_note",
        "description": "Store a piece of information, an idea, a fact, or a memory for the user. Use for non-actionable information.",
        "parameters": StoreNoteArguments.schema(),
    },
    {
        "name": "create_event",
        "description": "Create a calendar event, appointment, or meeting for the user. Use for items with a specific start and end time.",
        "parameters": CreateEventArguments.schema(),
    },
]