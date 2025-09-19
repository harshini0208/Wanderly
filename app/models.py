from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class RoomType(str, Enum):
    STAY = "stay"
    TRAVEL = "travel"
    ITINERARY = "itinerary"
    EAT = "eat"

class VoteType(str, Enum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"

class GroupStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class User(BaseModel):
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    joined_at: datetime = Field(default_factory=datetime.utcnow)

class Group(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    destination: str
    start_date: datetime
    end_date: datetime
    created_by: str
    members: List[User] = []
    invite_code: str
    status: GroupStatus = GroupStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Room(BaseModel):
    id: str
    group_id: str
    room_type: RoomType
    status: str = "active"  # active, completed, locked
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Question(BaseModel):
    id: str
    room_id: str
    question_text: str
    question_type: str  # slider, buttons, text, map_selector
    options: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    required: bool = True
    order: int

class Answer(BaseModel):
    id: str
    question_id: str
    user_id: str
    answer_value: Any
    answer_text: Optional[str] = None
    answered_at: datetime = Field(default_factory=datetime.utcnow)

class Suggestion(BaseModel):
    id: str
    room_id: str
    title: str
    description: str
    image_url: Optional[str] = None
    price: Optional[float] = None
    currency: str = "INR"
    location: Optional[Dict[str, Any]] = None
    highlights: List[str] = []
    external_url: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Vote(BaseModel):
    id: str
    suggestion_id: str
    user_id: str
    vote_type: VoteType
    voted_at: datetime = Field(default_factory=datetime.utcnow)

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    destination: str
    start_date: datetime
    end_date: datetime

class GroupJoin(BaseModel):
    invite_code: str
    user_name: str
    user_email: str

class QuestionCreate(BaseModel):
    question_text: str
    question_type: str
    options: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    required: bool = True
    order: int

class AnswerSubmit(BaseModel):
    question_id: str
    answer_value: Any
    answer_text: Optional[str] = None

class VoteSubmit(BaseModel):
    suggestion_id: str
    vote_type: VoteType

class SuggestionRequest(BaseModel):
    room_id: str
    preferences: Dict[str, Any]

class TripDashboard(BaseModel):
    group_id: str
    stay_decision: Optional[Dict[str, Any]] = None
    travel_decision: Optional[Dict[str, Any]] = None
    itinerary_decision: Optional[Dict[str, Any]] = None
    eat_decision: Optional[Dict[str, Any]] = None
    budget_breakdown: Optional[Dict[str, Any]] = None
    pending_decisions: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


