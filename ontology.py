# ontology.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime

# --- Core Data Structures ---

class Context(BaseModel):
    model_config = ConfigDict(from_attributes=True) # FIX: Allow creation from SQLAlchemy objects

    id: int
    name: str
    summary: Optional[str] = None
    state: Literal['stable', 'needs_summary'] = 'stable'
    last_updated_utc: datetime

class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True) # FIX: Allow creation from SQLAlchemy objects

    content: str
    due_date: Optional[datetime] = None
    permanence: Literal["permanent", "non-permanent"] = "non-permanent"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed: bool = False
    context_id: int

class Note(BaseModel):
    model_config = ConfigDict(from_attributes=True) # FIX: Allow creation from SQLAlchemy objects

    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    permanence: Literal["permanent", "non-permanent"] = "permanent"
    context_id: int

class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True) # FIX: Allow creation from SQLAlchemy objects

    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context_id: int

# --- Tool Schemas for LLM ---

class GetOrCreateContextArguments(BaseModel):
    query: str = Field(..., description="A concise search query representing the core subject of the user's request. E.g., 'guitar practice', 'Project X updates'.")

class CreateTaskArguments(BaseModel):
    content: str = Field(..., description="The content or description of the task.")
    due_date: Optional[datetime] = Field(None, description="The date and time the task is due. Should be in ISO 8601 format.")
    permanence: Optional[Literal["permanent", "non-permanent"]] = Field(None, description="Is the task a temporary reminder or a long-term goal?")
    context_id: Optional[int] = Field(None, description="The ID of the existing context to associate this task with.")
    new_context_name: Optional[str] = Field(None, description="If no existing context matches, provide a new, concise name for a context to be created.")

class StoreNoteArguments(BaseModel):
    content: str = Field(..., description="The full content of the note to be stored.")
    permanence: Optional[Literal["permanent", "non-permanent"]] = Field(None, description="Is this a permanent piece of information or a fleeting thought?")
    context_id: Optional[int] = Field(None, description="The ID of the existing context to associate this note with.")
    new_context_name: Optional[str] = Field(None, description="If no existing context matches, provide a new, concise name for a context to be created.")

class CreateEventArguments(BaseModel):
    title: str = Field(..., description="The title of the calendar event.")
    start_time: datetime = Field(..., description="The start date and time of the event in ISO 8601 format.")
    end_time: Optional[datetime] = Field(None, description="The end date and time of the event in ISO 8601 format.")
    description: Optional[str] = Field(None, description="A detailed description of the event.")
    location: Optional[str] = Field(None, description="The physical location or meeting link for the event.")
    context_id: Optional[int] = Field(None, description="The ID of the existing context to associate this event with.")
    new_context_name: Optional[str] = Field(None, description="If no existing context matches, provide a new, concise name for a context to be created.")

# --- New Data Transfer Object ---
class DueItem(BaseModel):
    id: int
    type: Literal["Task", "Event"]
    content: str
    due_date: datetime

# --- Tool definitions for LLM function-calling ---
# Note: These are now split logically. The first tool is for Step 1, the rest for Step 2.
TOOLS_STEP_1_CONTEXT = [
    {
        "name": "get_or_create_context",
        "description": "Searches for an existing context (project/category) or determines a name for a new one based on a query.",
        "parameters": GetOrCreateContextArguments.model_json_schema(),
    }
]

TOOLS_STEP_2_ACTION = [
    {
        "name": "create_task",
        "description": "Create a new task, to-do item, or reminder for the user. Use for actionable items.",
        "parameters": CreateTaskArguments.model_json_schema(),
    },
    {
        "name": "store_note",
        "description": "Store a piece of information, an idea, a fact, or a memory for the user. Use for non-actionable information.",
        "parameters": StoreNoteArguments.model_json_schema(),
    },
    {
        "name": "create_event",
        "description": "Create a calendar event, appointment, or meeting for the user. Use for items with a specific start and end time.",
        "parameters": CreateEventArguments.model_json_schema(),
    },
]