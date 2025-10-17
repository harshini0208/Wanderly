from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict

from app.models import Vote, VoteSubmit, VoteType
from app.database import db
from app.auth import get_user_id
from app.services.ai_service import ai_service

router = APIRouter()

@router.post("/vote", response_model=dict)
async def submit_vote(
    vote_data: VoteSubmit,
    user_id: str = Depends(get_user_id)
):
    """Submit a vote for a suggestion"""
    try:
        # Get suggestion details
        suggestion_doc = db.get_suggestions_collection().document(vote_data.suggestion_id).get()
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
        
        # Check if user already voted
        existing_votes = db.get_votes_collection().where('suggestion_id', '==', vote_data.suggestion_id).where('user_id', '==', user_id).stream()
        existing_vote_docs = list(existing_votes)
        
        if existing_vote_docs:
            # Update existing vote
            vote_id = existing_vote_docs[0].id
            db.get_votes_collection().document(vote_id).update({
                'vote_type': vote_data.vote_type,
                'voted_at': datetime.utcnow()
            })
        else:
            # Create new vote
            vote_dict = {
                "suggestion_id": vote_data.suggestion_id,
                "user_id": user_id,
                "vote_type": vote_data.vote_type,
                "voted_at": datetime.utcnow()
            }
            vote_id = db.create_vote(vote_dict)
        
        # Log analytics
        db.log_user_action(user_id, "vote_submitted", {
            "suggestion_id": vote_data.suggestion_id,
            "vote_type": vote_data.vote_type,
            "room_id": suggestion_data['room_id']
        })
        
        return {
            "vote_id": vote_id if 'vote_id' not in locals() else vote_id,
            "message": "Vote submitted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting vote: {str(e)}"
        )

@router.get("/suggestion/{suggestion_id}/votes", response_model=Dict[str, Any])
async def get_suggestion_votes(
    suggestion_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get all votes for a suggestion"""
    try:
        # Get suggestion details
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
        
        # Get votes
        vote_docs = db.get_votes_by_suggestion(suggestion_id)
        votes = []
        
        for vote_doc in vote_docs:
            vote_data = vote_doc.to_dict()
            vote_data['id'] = vote_doc.id
            votes.append(Vote(**vote_data))
        
        # Calculate vote summary
        vote_summary = {
            "total_votes": len(votes),
            "up_votes": len([v for v in votes if v.vote_type == VoteType.UP]),
            "down_votes": len([v for v in votes if v.vote_type == VoteType.DOWN]),
            "neutral_votes": len([v for v in votes if v.vote_type == VoteType.NEUTRAL]),
            "user_vote": next((v.vote_type for v in votes if v.user_id == user_id), None),
            "votes": votes
        }
        
        return vote_summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching votes: {str(e)}"
        )

@router.get("/room/{room_id}/consensus", response_model=Dict[str, Any])
async def get_room_consensus(
    room_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get consensus summary for all suggestions in a room"""
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
        
        # Get all suggestions for the room
        suggestion_docs = db.get_suggestions_by_room(room_id)
        suggestions = []
        
        for suggestion_doc in suggestion_docs:
            suggestion_data = suggestion_doc.to_dict()
            suggestion_data['id'] = suggestion_doc.id
            suggestions.append(suggestion_data)
        
        # Get votes for each suggestion
        suggestion_votes = {}
        for suggestion in suggestions:
            vote_docs = db.get_votes_by_suggestion(suggestion['id'])
            votes = [doc.to_dict() for doc in vote_docs]
            
            vote_summary = {
                "total_votes": len(votes),
                "up_votes": len([v for v in votes if v['vote_type'] == VoteType.UP]),
                "down_votes": len([v for v in votes if v['vote_type'] == VoteType.DOWN]),
                "neutral_votes": len([v for v in votes if v['vote_type'] == VoteType.NEUTRAL])
            }
            
            suggestion_votes[suggestion['id']] = {
                "suggestion": suggestion,
                "votes": vote_summary
            }
        
        # Find top suggestions
        top_suggestions = sorted(
            suggestion_votes.items(),
            key=lambda x: x[1]['votes']['up_votes'] - x[1]['votes']['down_votes'],
            reverse=True
        )
        
        # Get all liked suggestions (consolidated results)
        liked_suggestions = [
            item for item in top_suggestions 
            if item[1]['votes']['up_votes'] > 0  # Only suggestions with at least one like
        ]
        
        # Generate AI consensus summary
        consensus_text = ai_service.generate_consensus_summary(suggestion_votes, suggestions)
        
        # Calculate group participation
        total_members = len(group_data.get('members', []))
        participating_members = set()
        for votes in suggestion_votes.values():
            for vote in votes['votes']:
                if 'user_id' in vote:
                    participating_members.add(vote['user_id'])
        
        participation_rate = len(participating_members) / total_members if total_members > 0 else 0
        
        consensus = {
            "room_id": room_id,
            "room_type": room_data['room_type'],
            "total_suggestions": len(suggestions),
            "participation_rate": participation_rate,
            "top_suggestions": top_suggestions[:3],  # Top 3
            "liked_suggestions": liked_suggestions,  # All liked suggestions
            "consensus_summary": consensus_text,
            "suggestion_votes": suggestion_votes,
            "group_size": total_members,
            "is_locked": room_data.get('status') == 'locked',
            "final_decision": room_data.get('final_decision')
        }
        
        return consensus
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting consensus: {str(e)}"
        )

@router.post("/room/{room_id}/lock-multiple", response_model=dict)
async def lock_room_decision_multiple(
    room_id: str,
    suggestion_ids: List[str],
    user_id: str = Depends(get_user_id)
):
    """Lock in multiple liked suggestions for a room"""
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
        
        # Allow all group members to lock suggestions
        # No restriction needed - all users can lock their choices
        
        # Get all the chosen suggestions
        liked_suggestions = []
        for suggestion_id in suggestion_ids:
            suggestion_doc = db.get_suggestions_collection().document(suggestion_id).get()
            if suggestion_doc.exists:
                suggestion_data = suggestion_doc.to_dict()
                suggestion_data['id'] = suggestion_id
                liked_suggestions.append(suggestion_data)
        
        if not liked_suggestions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid suggestions found"
            )
        
        # Update room status with all liked suggestions
        db.get_rooms_collection().document(room_id).update({
            'status': 'locked',
            'final_decision': liked_suggestions,  # Store all liked suggestions
            'locked_by': user_id,
            'locked_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        # Log analytics
        db.log_user_action(user_id, "room_locked", {
            "room_id": room_id,
            "suggestion_count": len(liked_suggestions),
            "room_type": room_data['room_type']
        })
        
        return {
            "message": f"Room locked with {len(liked_suggestions)} liked suggestions",
            "room_id": room_id,
            "liked_suggestions": liked_suggestions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error locking room: {str(e)}"
        )

@router.post("/room/{room_id}/lock", response_model=dict)
async def lock_room_decision(
    room_id: str,
    suggestion_id: str,
    user_id: str = Depends(get_user_id)
):
    """Lock in the final decision for a room"""
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
        
        # Allow all group members to lock suggestions
        # No restriction needed - all users can lock their choices
        
        # Get the chosen suggestion
        suggestion_doc = db.get_suggestions_collection().document(suggestion_id).get()
        if not suggestion_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suggestion not found"
            )
        
        suggestion_data = suggestion_doc.to_dict()
        
        # Update room status
        db.get_rooms_collection().document(room_id).update({
            'status': 'locked',
            'final_decision': suggestion_data,
            'locked_by': user_id,
            'locked_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })
        
        # Log analytics
        db.log_user_action(user_id, "room_locked", {
            "room_id": room_id,
            "suggestion_id": suggestion_id,
            "room_type": room_data['room_type']
        })
        
        return {
            "message": "Room decision locked successfully",
            "final_decision": suggestion_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error locking decision: {str(e)}"
        )

@router.get("/group/{group_id}/consolidated", response_model=Dict[str, Any])
async def get_group_consolidated_results(
    group_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get consolidated results for all rooms in a group"""
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
        
        # Get all rooms for this group
        room_docs = db.get_rooms_collection().where('group_id', '==', group_id).stream()
        rooms = []
        
        for room_doc in room_docs:
            room_data = room_doc.to_dict()
            room_data['id'] = room_doc.id
            rooms.append(room_data)
        
        # Consolidated results with proper vote aggregation
        room_results = {}
        for room in rooms:
            try:
                # Get suggestions for this room
                suggestion_docs = db.get_suggestions_by_room(room['id'])
                suggestions = []
                
                for suggestion_doc in suggestion_docs:
                    suggestion_data = suggestion_doc.to_dict()
                    suggestion_data['id'] = suggestion_doc.id
                    suggestions.append(suggestion_data)
                
                # Get votes for all suggestions in this room
                suggestion_votes = {}
                for suggestion in suggestions:
                    vote_docs = db.get_votes_by_suggestion(suggestion['id'])
                    up_votes = 0
                    down_votes = 0
                    
                    for vote_doc in vote_docs:
                        vote_data = vote_doc.to_dict()
                        if vote_data.get('vote_type') == 'up':
                            up_votes += 1
                        elif vote_data.get('vote_type') == 'down':
                            down_votes += 1
                    
                    suggestion_votes[suggestion['id']] = {
                        "up_votes": up_votes,
                        "down_votes": down_votes,
                        "total_votes": up_votes + down_votes,
                        "score": up_votes - down_votes  # Net score for ranking
                    }
                
                # Sort suggestions by score (likes - dislikes) to get top consolidated results
                liked_suggestions = []
                for suggestion in suggestions:
                    votes = suggestion_votes.get(suggestion['id'], {"up_votes": 0, "down_votes": 0, "total_votes": 0, "score": 0})
                    if votes["up_votes"] > 0:  # Only include suggestions that have been liked
                        liked_suggestions.append([
                            suggestion['id'],
                            {
                                "suggestion": suggestion,
                                "votes": votes
                            }
                        ])
                
                # Sort by score (highest first) and take top 4
                liked_suggestions.sort(key=lambda x: x[1]["votes"]["score"], reverse=True)
                top_consolidated = liked_suggestions[:4]  # Top 4 consolidated results
                
                consensus = {
                    "room_id": room['id'],
                    "room_type": room['room_type'],
                    "total_suggestions": len(suggestions),
                    "liked_suggestions": top_consolidated,
                    "is_locked": room.get('status') == 'locked',
                    "final_decision": room.get('final_decision'),
                    "total_liked": len(liked_suggestions),
                    "consolidated_count": len(top_consolidated)
                }
                
                room_results[room['id']] = {
                    "room": room,
                    "consensus": consensus
                }
            except Exception as e:
                # Error getting room data
                room_results[room['id']] = {
                    "room": room,
                    "consensus": None
                }
        
        return {
            "group_id": group_id,
            "group": group_data,
            "room_results": room_results,
            "total_rooms": len(rooms)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting consolidated results: {str(e)}"
        )

@router.post("/room/{room_id}/complete", response_model=dict)
async def mark_room_complete(
    room_id: str,
    user_id: str = Depends(get_user_id),
    user_name: str = "Demo User",
    user_email: str = "demo@example.com"
):
    """Mark a room as completed by a user"""
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
        
        # Check if user already completed this room
        completion_docs = db.get_room_completions_collection().where('room_id', '==', room_id).where('user_id', '==', user_id).stream()
        existing_completion = list(completion_docs)
        
        if existing_completion:
            return {
                "message": "Room already marked as completed by this user",
                "completion_id": existing_completion[0].id
            }
        
        # Create completion record
        completion_data = {
            "room_id": room_id,
            "group_id": room_data['group_id'],
            "user_id": user_id,
            "user_name": user_name,
            "user_email": user_email,
            "completed_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        
        completion_ref = db.get_room_completions_collection().add(completion_data)
        completion_id = completion_ref[1]  # Get the document ID from the tuple
        
        # Update room completion count
        room_completions = db.get_room_completions_collection().where('room_id', '==', room_id).stream()
        completion_count = len(list(room_completions))
        
        # Update room with completion status
        db.get_rooms_collection().document(room_id).update({
            'completion_count': completion_count,
            'updated_at': datetime.utcnow()
        })
        
        return {
            "message": "Room marked as completed",
            "completion_id": completion_id.id,
            "completion_count": completion_count,
            "total_members": len(group_data.get('members', []))
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking room complete: {str(e)}"
        )

@router.get("/room/{room_id}/status", response_model=Dict[str, Any])
async def get_room_voting_status(
    room_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get voting status and progress for a room"""
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
        
        # Get completion status
        room_completions = db.get_room_completions_collection().where('room_id', '==', room_id).stream()
        completions = [doc.to_dict() for doc in room_completions]
        completion_count = len(completions)
        total_members = len(group_data.get('members', []))
        
        # Check if current user has completed
        user_completed = any(comp['user_id'] == user_id for comp in completions)
        
        # Get all suggestions and their votes
        suggestion_docs = db.get_suggestions_by_room(room_id)
        suggestions_with_votes = []
        
        for suggestion_doc in suggestion_docs:
            suggestion_data = suggestion_doc.to_dict()
            suggestion_data['id'] = suggestion_doc.id
            
            # Get votes for this suggestion
            vote_docs = db.get_votes_by_suggestion(suggestion_data['id'])
            votes = [doc.to_dict() for doc in vote_docs]
            
            vote_summary = {
                "total_votes": len(votes),
                "up_votes": len([v for v in votes if v['vote_type'] == VoteType.UP]),
                "down_votes": len([v for v in votes if v['vote_type'] == VoteType.DOWN]),
                "neutral_votes": len([v for v in votes if v['vote_type'] == VoteType.NEUTRAL])
            }
            
            suggestions_with_votes.append({
                "suggestion": suggestion_data,
                "votes": vote_summary
            })
        
        # Calculate overall status
        total_votes = sum(s['votes']['total_votes'] for s in suggestions_with_votes)
        participation_rate = total_votes / (total_members * len(suggestions_with_votes)) if suggestions_with_votes else 0
        
        # Find most popular suggestion
        most_popular = max(suggestions_with_votes, key=lambda x: x['votes']['up_votes'] - x['votes']['down_votes']) if suggestions_with_votes else None
        
        status = {
            "room_id": room_id,
            "room_type": room_data['room_type'],
            "status": room_data.get('status', 'active'),
            "total_suggestions": len(suggestions_with_votes),
            "total_members": total_members,
            "completion_count": completion_count,
            "completion_status": f"{completion_count}/{total_members} completed",
            "user_completed": user_completed,
            "participation_rate": participation_rate,
            "most_popular": most_popular,
            "suggestions": suggestions_with_votes,
            "is_locked": room_data.get('status') == 'locked',
            "completions": completions
        }
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting voting status: {str(e)}"
        )

