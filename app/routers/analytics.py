from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
from datetime import datetime, timedelta
from google.cloud import bigquery
from app.database import db
from app.auth import get_user_id

router = APIRouter()

@router.get("/group/{group_id}/dashboard", response_model=Dict[str, Any])
async def get_group_dashboard(
    group_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get comprehensive dashboard for a group"""
    try:
        # Verify access
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
        
        # Get all rooms and their decisions
        room_docs = db.get_rooms_by_group(group_id)
        rooms = []
        decisions = {}
        
        for room_doc in room_docs:
            room_data = room_doc.to_dict()
            room_data['id'] = room_doc.id
            rooms.append(room_data)
            
            # Get final decision if room is locked
            if room_data.get('status') == 'locked' and 'final_decision' in room_data:
                decisions[room_data['room_type']] = room_data['final_decision']
        
        # Calculate budget breakdown
        budget_breakdown = _calculate_budget_breakdown(decisions, group_data)
        
        # Get pending decisions
        pending_decisions = [room['room_type'] for room in rooms if room.get('status') != 'locked']
        
        # Get group activity summary
        activity_summary = await _get_group_activity_summary(group_id)
        
        dashboard = {
            "group_id": group_id,
            "group_name": group_data['name'],
            "destination": group_data['destination'],
            "start_date": group_data['start_date'],
            "end_date": group_data['end_date'],
            "total_members": len(group_data.get('members', [])),
            "decisions": decisions,
            "pending_decisions": pending_decisions,
            "budget_breakdown": budget_breakdown,
            "activity_summary": activity_summary,
            "rooms": rooms,
            "created_at": group_data['created_at'],
            "updated_at": group_data['updated_at']
        }
        
        return dashboard
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dashboard: {str(e)}"
        )

def _calculate_budget_breakdown(decisions: Dict[str, Any], group_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate budget breakdown per person"""
    total_members = len(group_data.get('members', []))
    if total_members == 0:
        return {}
    
    breakdown = {
        "per_person": {},
        "total_estimated": 0,
        "currency": "INR"
    }
    
    # Calculate stay costs
    if 'stay' in decisions:
        stay_decision = decisions['stay']
        if 'price' in stay_decision:
            nights = (group_data['end_date'] - group_data['start_date']).days
            total_stay_cost = stay_decision['price'] * nights
            breakdown['per_person']['stay'] = total_stay_cost / total_members
            breakdown['total_estimated'] += total_stay_cost
    
    # Calculate travel costs
    if 'travel' in decisions:
        travel_decision = decisions['travel']
        if 'price' in travel_decision:
            total_travel_cost = travel_decision['price'] * total_members
            breakdown['per_person']['travel'] = travel_decision['price']
            breakdown['total_estimated'] += total_travel_cost
    
    # Calculate food costs (estimated)
    if 'eat' in decisions:
        eat_decision = decisions['eat']
        if 'price' in eat_decision:
            days = (group_data['end_date'] - group_data['start_date']).days
            meals_per_day = 3  # Breakfast, lunch, dinner
            total_food_cost = eat_decision['price'] * meals_per_day * days * total_members
            breakdown['per_person']['food'] = (eat_decision['price'] * meals_per_day * days)
            breakdown['total_estimated'] += total_food_cost
    
    # Calculate activities costs (estimated)
    if 'itinerary' in decisions:
        itinerary_decision = decisions['itinerary']
        if 'price' in itinerary_decision:
            total_activity_cost = itinerary_decision['price'] * total_members
            breakdown['per_person']['activities'] = itinerary_decision['price']
            breakdown['total_estimated'] += total_activity_cost
    
    breakdown['per_person']['total'] = sum(breakdown['per_person'].values())
    
    return breakdown

async def _get_group_activity_summary(group_id: str) -> Dict[str, Any]:
    """Get activity summary for the group"""
    try:
        # This would typically query BigQuery for analytics
        # For now, return a basic summary
        
        # Get all rooms
        room_docs = db.get_rooms_by_group(group_id)
        total_rooms = len(list(room_docs))
        
        # Get total suggestions across all rooms
        total_suggestions = 0
        total_votes = 0
        
        for room_doc in db.get_rooms_by_group(group_id):
            room_id = room_doc.id
            suggestion_docs = db.get_suggestions_by_room(room_id)
            total_suggestions += len(list(suggestion_docs))
            
            for suggestion_doc in db.get_suggestions_by_room(room_id):
                vote_docs = db.get_votes_by_suggestion(suggestion_doc.id)
                total_votes += len(list(vote_docs))
        
        return {
            "total_rooms": total_rooms,
            "total_suggestions": total_suggestions,
            "total_votes": total_votes,
            "active_rooms": total_rooms,  # Simplified
            "completed_rooms": 0  # Would need to check room status
        }
    except Exception as e:
        # Error getting activity summary
        return {
            "total_rooms": 0,
            "total_suggestions": 0,
            "total_votes": 0,
            "active_rooms": 0,
            "completed_rooms": 0
        }

@router.get("/group/{group_id}/export", response_model=Dict[str, Any])
async def export_group_itinerary(
    group_id: str,
    user_id: str = Depends(get_user_id)
):
    """Export group itinerary as PDF-ready data"""
    try:
        # Verify access
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
        
        # Get all decisions
        room_docs = db.get_rooms_by_group(group_id)
        decisions = {}
        
        for room_doc in room_docs:
            room_data = room_doc.to_dict()
            if room_data.get('status') == 'locked' and 'final_decision' in room_data:
                decisions[room_data['room_type']] = room_data['final_decision']
        
        # Generate itinerary data
        itinerary = {
            "group_name": group_data['name'],
            "destination": group_data['destination'],
            "start_date": group_data['start_date'],
            "end_date": group_data['end_date'],
            "members": group_data.get('members', []),
            "decisions": decisions,
            "budget_breakdown": _calculate_budget_breakdown(decisions, group_data),
            "exported_at": datetime.utcnow(),
            "exported_by": user_id
        }
        
        # Log analytics
        db.log_user_action(user_id, "itinerary_exported", {
            "group_id": group_id,
            "decisions_count": len(decisions)
        })
        
        return itinerary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting itinerary: {str(e)}"
        )

@router.get("/user/{user_id}/stats", response_model=Dict[str, Any])
async def get_user_stats(
    user_id: str = Depends(get_user_id)
):
    """Get user statistics and activity"""
    try:
        # Get user's groups
        groups = db.get_groups_collection().where('members', 'array_contains', {'id': user_id}).stream()
        user_groups = [doc.to_dict() for doc in groups]
        
        # Calculate stats
        stats = {
            "total_groups": len(user_groups),
            "active_groups": len([g for g in user_groups if g.get('status') == 'active']),
            "groups_created": len([g for g in user_groups if g.get('created_by') == user_id]),
            "total_trips_planned": len(user_groups),
            "favorite_destinations": _get_favorite_destinations(user_groups),
            "recent_activity": await _get_recent_user_activity(user_id)
        }
        
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user stats: {str(e)}"
        )

def _get_favorite_destinations(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get user's favorite destinations"""
    destinations = {}
    for group in groups:
        dest = group.get('destination', '')
        if dest:
            destinations[dest] = destinations.get(dest, 0) + 1
    
    return [{"destination": dest, "count": count} for dest, count in sorted(destinations.items(), key=lambda x: x[1], reverse=True)]

async def _get_recent_user_activity(user_id: str) -> List[Dict[str, Any]]:
    """Get recent user activity"""
    # This would typically query BigQuery for user actions
    # For now, return empty list
    return []

@router.get("/platform/stats", response_model=Dict[str, Any])
async def get_platform_stats():
    """Get platform-wide statistics"""
    try:
        # This would typically query BigQuery for platform analytics
        # For now, return basic stats from Firestore
        
        # Get total groups
        groups = db.get_groups_collection().stream()
        total_groups = len(list(groups))
        
        # Get total suggestions
        suggestions = db.get_suggestions_collection().stream()
        total_suggestions = len(list(suggestions))
        
        # Get total votes
        votes = db.get_votes_collection().stream()
        total_votes = len(list(votes))
        
        stats = {
            "total_groups": total_groups,
            "total_suggestions": total_suggestions,
            "total_votes": total_votes,
            "active_users": 0,  # Would need user tracking
            "popular_destinations": [],  # Would need analytics
            "generated_at": datetime.utcnow()
        }
        
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting platform stats: {str(e)}"
        )


