from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime

from app.models import Room, Question, QuestionCreate, Answer, AnswerSubmit
from app.database import db
from app.auth import get_user_id

router = APIRouter()

@router.get("/group/{group_id}", response_model=List[Room])
async def get_group_rooms(
    group_id: str,
    user_id: str = "demo_user_123"
):
    """Get all rooms for a group"""
    try:
        # Verify user is a member of the group
        group_data = db.get_group(group_id)
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get rooms
        room_docs = db.get_rooms_by_group(group_id)
        rooms = []
        
        for room_doc in room_docs:
            room_data = room_doc.to_dict()
            room_data['id'] = room_doc.id
            rooms.append(Room(**room_data))
        
        return rooms
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching rooms: {str(e)}"
        )

@router.get("/{room_id}", response_model=Room)
async def get_room(
    room_id: str,
    user_id: str = "demo_user_123"
):
    """Get room details"""
    try:
        room_data = db.get_room(room_id)
        if not room_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        # Verify user is a member of the group
        group_data = db.get_group(room_data['group_id'])
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        room_data['id'] = room_id
        return Room(**room_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching room: {str(e)}"
        )

@router.post("/{room_id}/questions", response_model=dict)
async def create_questions_for_room(
    room_id: str,
    user_id: str = "demo_user_123"
):
    """Create default questions for a room based on room type"""
    try:
        # Get room details
        room_data = db.get_room(room_id)
        if not room_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        # Verify user is a member of the group
        group_data = db.get_group(room_data['group_id'])
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get group data for context
        group_data = db.get_group(room_data['group_id'])
        
        # Create questions based on room type
        questions = _get_default_questions(room_data['room_type'], room_id, group_data)
        created_questions = []
        
        for question_data in questions:
            question_id = db.create_question(question_data)
            created_questions.append(question_id)
        
        return {
            "message": "Questions created successfully",
            "question_ids": created_questions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating questions: {str(e)}"
        )

def _get_location_options_for_destination(group_data: dict) -> List[str]:
    """Get location options based on destination type"""
    if not group_data:
        return ["City Center", "Near Market", "Airport Area", "Historic Area"]
    
    to_location = group_data.get('to_location', '').lower()
    
    # Beach destinations
    beach_keywords = ['beach', 'coast', 'shore', 'seaside', 'ocean', 'sea', 'bay', 'gulf']
    if any(keyword in to_location for keyword in beach_keywords):
        return ["Beachside", "Beachfront", "Near Beach", "City Center", "Airport Area", "Historic Area"]
    
    # Hill station destinations
    hill_keywords = ['hill', 'mountain', 'peak', 'valley', 'hills', 'mountains', 'station']
    if any(keyword in to_location for keyword in hill_keywords):
        return ["Hill Station", "Mountain View", "Valley View", "City Center", "Near Market", "Historic Area"]
    
    # Desert destinations
    desert_keywords = ['desert', 'sand', 'dune', 'arid']
    if any(keyword in to_location for keyword in desert_keywords):
        return ["Desert View", "Oasis", "City Center", "Near Market", "Airport Area", "Historic Area"]
    
    # Forest/wildlife destinations
    forest_keywords = ['forest', 'jungle', 'wildlife', 'national park', 'reserve', 'sanctuary']
    if any(keyword in to_location for keyword in forest_keywords):
        return ["Near Forest", "Wildlife Area", "Nature View", "City Center", "Near Market", "Historic Area"]
    
    # Religious destinations
    religious_keywords = ['temple', 'church', 'mosque', 'gurudwara', 'pilgrimage', 'spiritual']
    if any(keyword in to_location for keyword in religious_keywords):
        return ["Near Temple", "Religious Area", "City Center", "Near Market", "Historic Area", "Airport Area"]
    
    # Default options for general destinations
    return ["City Center", "Near Market", "Airport Area", "Historic Area", "Business District", "Residential Area"]

def _get_default_questions(room_type: str, room_id: str, group_data: dict = None) -> List[dict]:
    """Get default questions for each room type"""
    
    if room_type == "stay":
        # Customize location options based on destination type
        location_options = _get_location_options_for_destination(group_data)
        
        return [
            {
                "room_id": room_id,
                "question_text": "What's your budget per night?",
                "question_type": "slider",
                "min_value": 0,
                "max_value": 250000,
                "step": 100,
                "required": True,
                "order": 1
            },
            {
                "room_id": room_id,
                "question_text": "What type of accommodation do you prefer?",
                "question_type": "buttons",
                "options": ["Hotel", "Hostel", "Airbnb", "Resort", "Guest House", "Homestay"],
                "required": True,
                "order": 2
            },
            {
                "room_id": room_id,
                "question_text": "Where would you like to stay?",
                "question_type": "buttons",
                "options": location_options,
                "required": True,
                "order": 3
            },
            {
                "room_id": room_id,
                "question_text": "Any specific requirements or preferences?",
                "question_type": "text",
                "required": False,
                "order": 4
            }
        ]
    
    elif room_type == "travel":
        return [
            {
                "room_id": room_id,
                "question_text": "How would you like to travel?",
                "question_type": "buttons",
                "options": ["Flight", "Train", "Bus", "Car Rental", "Mixed"],
                "required": True,
                "order": 1
            },
            {
                "room_id": room_id,
                "question_text": "What's your preferred travel time?",
                "question_type": "buttons",
                "options": ["Morning", "Afternoon", "Evening", "Night", "No Preference"],
                "required": True,
                "order": 2
            },
            {
                "room_id": room_id,
                "question_text": "What type of vehicle/service do you prefer?",
                "question_type": "buttons",
                "options": ["Sleeper Bus", "Semi-Sleeper", "AC Seater", "Non-AC", "Private Car", "Shared Taxi", "Express Train", "Local Train", "Budget Flight", "Premium Flight"],
                "required": True,
                "order": 3
            },
            {
                "room_id": room_id,
                "question_text": "Any special travel requirements?",
                "question_type": "text",
                "required": False,
                "order": 4
            }
        ]
    
    elif room_type == "itinerary":
        return [
            {
                "room_id": room_id,
                "question_text": "What activities interest you most?",
                "question_type": "buttons",
                "options": ["Adventure", "Culture & History", "Shopping", "Nightlife", "Nature", "Food & Drinks"],
                "required": True,
                "order": 1
            },
            {
                "room_id": room_id,
                "question_text": "How active do you want your trip to be?",
                "question_type": "slider",
                "min_value": 1,
                "max_value": 10,
                "step": 1,
                "required": True,
                "order": 2
            },
            {
                "room_id": room_id,
                "question_text": "How many days do you want to spend?",
                "question_type": "slider",
                "min_value": 1,
                "max_value": 14,
                "step": 1,
                "required": True,
                "order": 3
            },
            {
                "room_id": room_id,
                "question_text": "How many nights do you want to stay?",
                "question_type": "slider",
                "min_value": 1,
                "max_value": 14,
                "step": 1,
                "required": True,
                "order": 4
            },
            {
                "room_id": room_id,
                "question_text": "Any must-visit places or experiences?",
                "question_type": "text",
                "required": False,
                "order": 5
            }
        ]
    
    elif room_type == "eat":
        return [
            {
                "room_id": room_id,
                "question_text": "What type of cuisine do you prefer?",
                "question_type": "buttons",
                "options": ["Local Cuisine", "International", "Street Food", "Fine Dining", "Mixed"],
                "required": True,
                "order": 1
            },
            {
                "room_id": room_id,
                "question_text": "Any dietary restrictions?",
                "question_type": "buttons",
                "options": ["Vegetarian", "Vegan", "Non-Vegetarian", "Halal", "No Restrictions"],
                "required": True,
                "order": 2
            },
            {
                "room_id": room_id,
                "question_text": "What type of meal are you looking for?",
                "question_type": "buttons",
                "options": ["Breakfast", "Lunch", "Dinner", "Snacks/Cafes", "Any"],
                "required": True,
                "order": 3
            },
            {
                "room_id": room_id,
                "question_text": "Any specific restaurants or dishes you want to try?",
                "question_type": "text",
                "required": False,
                "order": 4
            }
        ]
    
    return []

@router.get("/{room_id}/questions", response_model=List[Question])
async def get_room_questions(
    room_id: str,
    user_id: str = "demo_user_123"
):
    """Get all questions for a room"""
    try:
        # Verify access
        room_data = db.get_room(room_id)
        if not room_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        group_data = db.get_group(room_data['group_id'])
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get questions
        question_docs = db.get_questions_by_room(room_id)
        questions = []
        
        for question_doc in question_docs:
            question_data = question_doc.to_dict()
            question_data['id'] = question_doc.id
            questions.append(Question(**question_data))
        
        return questions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching questions: {str(e)}"
        )

@router.post("/{room_id}/answers", response_model=dict)
async def submit_answer(
    room_id: str,
    answer_data: AnswerSubmit,
    user_id: str = "demo_user_123"
):
    """Submit an answer to a question"""
    try:
        # Verify access
        room_data = db.get_room(room_id)
        if not room_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        group_data = db.get_group(room_data['group_id'])
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Create answer
        answer_dict = {
            "question_id": answer_data.question_id,
            "user_id": user_id,
            "answer_value": answer_data.answer_value,
            "answer_text": answer_data.answer_text,
            "answered_at": datetime.utcnow()
        }
        
        answer_id = db.create_answer(answer_dict)
        
        # Log analytics
        db.log_user_action(user_id, "answer_submitted", {
            "room_id": room_id,
            "question_id": answer_data.question_id,
            "room_type": room_data['room_type']
        })
        
        return {
            "answer_id": answer_id,
            "message": "Answer submitted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting answer: {str(e)}"
        )

@router.get("/{room_id}/answers", response_model=List[Answer])
async def get_room_answers(
    room_id: str,
    user_id: str = "demo_user_123"
):
    """Get all answers for a room"""
    try:
        # Verify access
        room_data = db.get_room(room_id)
        if not room_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        
        group_data = db.get_group(room_data['group_id'])
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get answers
        answer_docs = db.get_answers_by_room(room_id)
        answers = []
        
        for answer_doc in answer_docs:
            answer_data = answer_doc.to_dict()
            answer_data['id'] = answer_doc.id
            answers.append(Answer(**answer_data))
        
        return answers
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching answers: {str(e)}"
        )

