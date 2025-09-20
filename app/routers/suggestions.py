from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
from datetime import datetime

from app.models import Suggestion, SuggestionRequest
from app.database import db
from app.auth import get_user_id
from app.services.ai_service import ai_service
from app.services.maps_service import maps_service

router = APIRouter()

@router.post("/generate", response_model=List[Suggestion])
async def generate_suggestions(
    request: SuggestionRequest,
    user_id: str = "demo_user_123"
):
    """Generate AI-powered suggestions for a room"""
    try:
        # Get room details
        room_data = db.get_room(request.room_id)
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
        
        # Generate AI suggestions with full group context
        group_context = {
            'from_location': group_data['from_location'],
            'to_location': group_data['to_location'],
            'start_date': group_data.get('start_date'),
            'end_date': group_data.get('end_date'),
            'group_name': group_data.get('name'),
            'group_size': len(group_data.get('members', [])),
            'preferences': request.preferences
        }
        
        ai_suggestions = ai_service.generate_suggestions(
            room_type=room_data['room_type'],
            preferences=request.preferences,
            from_location=group_data['from_location'],
            to_location=group_data['to_location'],
            group_context=group_context
        )
        
        # Enhance suggestions with Google Maps data
        enhanced_suggestions = []
        for suggestion in ai_suggestions:
            enhanced = maps_service.enhance_suggestion_with_maps_data(
                suggestion, 
                group_data['to_location']
            )
            
            # Save to database
            suggestion_dict = {
                "room_id": request.room_id,
                "title": enhanced.get('title', ''),
                "description": enhanced.get('description', ''),
                "image_url": enhanced.get('image_url'),
                "price": enhanced.get('price'),
                "currency": enhanced.get('currency', 'INR'),
                "location": enhanced.get('location', {}),
                "highlights": enhanced.get('highlights', []),
                "external_url": enhanced.get('external_url'),
                "metadata": enhanced.get('metadata', {}),
                "created_at": datetime.utcnow()
            }
            
            suggestion_id = db.create_suggestion(suggestion_dict)
            suggestion_dict['id'] = suggestion_id
            enhanced_suggestions.append(Suggestion(**suggestion_dict))
        
        # Log analytics
        db.log_user_action(user_id, "suggestions_generated", {
            "room_id": request.room_id,
            "room_type": room_data['room_type'],
            "suggestion_count": len(enhanced_suggestions)
        })
        
        return enhanced_suggestions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating suggestions: {str(e)}"
        )

@router.get("/test-suggestions")
async def test_suggestions():
    """Test endpoint to generate sample suggestions with external URLs"""
    try:
        # Generate test suggestions
        test_suggestions = [
            {
                "title": "Test Hotel",
                "description": "A test hotel for debugging",
                "price": 2000,
                "currency": "INR",
                "highlights": ["Test Feature 1", "Test Feature 2"],
                "external_url": "https://www.google.com/search?q=test+hotel",
                "location": {"address": "Test Address"},
                "metadata": {"rating": 4.0}
            },
            {
                "title": "Test Restaurant",
                "description": "A test restaurant for debugging",
                "price": 500,
                "currency": "INR",
                "highlights": ["Test Food 1", "Test Food 2"],
                "external_url": "https://www.google.com/search?q=test+restaurant",
                "location": {"address": "Test Address"},
                "metadata": {"rating": 4.2}
            }
        ]
        
        return test_suggestions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating test suggestions: {str(e)}"
        )

@router.get("/room/{room_id}", response_model=List[Suggestion])
async def get_room_suggestions(
    room_id: str,
    user_id: str = "demo_user_123"
):
    """Get all suggestions for a room"""
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
        
        # Get suggestions
        suggestion_docs = db.get_suggestions_by_room(room_id)
        suggestions = []
        
        for suggestion_doc in suggestion_docs:
            suggestion_data = suggestion_doc.to_dict()
            suggestion_data['id'] = suggestion_doc.id
            suggestions.append(Suggestion(**suggestion_data))
        
        return suggestions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching suggestions: {str(e)}"
        )

@router.get("/{suggestion_id}", response_model=Suggestion)
async def get_suggestion(
    suggestion_id: str,
    user_id: str = "demo_user_123"
):
    """Get a specific suggestion"""
    try:
        # Get suggestion
        suggestion_doc = db.get_suggestions_collection().document(suggestion_id).get()
        if not suggestion_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suggestion not found"
            )
        
        suggestion_data = suggestion_doc.to_dict()
        
        # Verify access
        room_data = db.get_room(suggestion_data['room_id'])
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
        
        suggestion_data['id'] = suggestion_id
        return Suggestion(**suggestion_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching suggestion: {str(e)}"
        )

@router.post("/{suggestion_id}/enhance", response_model=Suggestion)
async def enhance_suggestion(
    suggestion_id: str,
    user_id: str = "demo_user_123"
):
    """Enhance a suggestion with additional Google Maps data"""
    try:
        # Get suggestion
        suggestion_doc = db.get_suggestions_collection().document(suggestion_id).get()
        if not suggestion_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suggestion not found"
            )
        
        suggestion_data = suggestion_doc.to_dict()
        
        # Verify access
        room_data = db.get_room(suggestion_data['room_id'])
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
        
        # Enhance with Maps data
        enhanced = maps_service.enhance_suggestion_with_maps_data(
            suggestion_data, 
            group_data['to_location']
        )
        
        # Update suggestion in database
        db.get_suggestions_collection().document(suggestion_id).update(enhanced)
        
        # Log analytics
        db.log_user_action(user_id, "suggestion_enhanced", {
            "suggestion_id": suggestion_id,
            "room_id": suggestion_data['room_id']
        })
        
        enhanced['id'] = suggestion_id
        return Suggestion(**enhanced)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enhancing suggestion: {str(e)}"
        )

@router.get("/room/{room_id}/preferences", response_model=Dict[str, Any])
async def analyze_room_preferences(
    room_id: str,
    user_id: str = "demo_user_123"
):
    """Analyze group preferences for a room using AI"""
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
        
        # Get all answers for the room
        answer_docs = db.get_answers_by_room(room_id)
        answers = [doc.to_dict() for doc in answer_docs]
        
        # Analyze preferences using AI
        analysis = ai_service.analyze_group_preferences(answers)
        
        # Log analytics
        db.log_user_action(user_id, "preferences_analyzed", {
            "room_id": room_id,
            "room_type": room_data['room_type']
        })
        
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing preferences: {str(e)}"
        )

