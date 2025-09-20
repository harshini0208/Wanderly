from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import uuid
import string
import random
from datetime import datetime

from app.models import Group, GroupCreate, GroupJoin, User
from app.database import db
from app.auth import get_user_id, get_user_email, get_user_name

router = APIRouter()

def generate_invite_code(length: int = 8) -> str:
    """Generate a random invite code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@router.post("/", response_model=dict)
async def create_group(
    group_data: GroupCreate,
    user_id: str = "demo_user_123",
    user_email: str = "demo@example.com", 
    user_name: str = "Demo User"
):
    """Create a new group"""
    try:
        # Generate unique invite code
        invite_code = generate_invite_code()
        
        # Create group data
        group_dict = {
            "name": group_data.name,
            "description": group_data.description,
            "from_location": group_data.from_location,
            "to_location": group_data.to_location,
            "total_members": group_data.total_members,
            "start_date": group_data.start_date,
            "end_date": group_data.end_date,
            "created_by": user_id,
            "members": [{
                "id": user_id,
                "name": user_name,
                "email": user_email,
                "joined_at": datetime.utcnow()
            }],
            "invite_code": invite_code,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Save to database
        group_id = db.create_group(group_dict)
        
        # Log analytics
        db.log_user_action(user_id, "group_created", {
            "group_id": group_id,
            "from_location": group_data.from_location,
            "to_location": group_data.to_location,
            "total_members": group_data.total_members
        })
        
        return {
            "group_id": group_id,
            "invite_code": invite_code,
            "message": "Group created successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating group: {str(e)}"
        )

@router.post("/join", response_model=dict)
async def join_group(
    join_data: GroupJoin,
    user_id: str = "demo_user_456",
    user_email: str = "demo2@example.com",
    user_name: str = "Demo User 2"
):
    """Join a group using invite code"""
    try:
        # Find group by invite code
        groups = db.get_groups_collection().where('invite_code', '==', join_data.invite_code).stream()
        group_docs = list(groups)
        
        if not group_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid invite code"
            )
        
        group_doc = group_docs[0]
        group_id = group_doc.id
        group_data = group_doc.to_dict()
        
        # Check if user is already a member
        existing_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this group"
            )
        
        # Add user to group
        new_member = {
            "id": user_id,
            "name": join_data.user_name,
            "email": join_data.user_email,
            "joined_at": datetime.utcnow()
        }
        
        group_data['members'].append(new_member)
        group_data['updated_at'] = datetime.utcnow()
        
        # Update group in database
        db.update_group(group_id, group_data)
        
        # Log analytics
        db.log_user_action(user_id, "group_joined", {
            "group_id": group_id,
            "invite_code": join_data.invite_code
        })
        
        return {
            "group_id": group_id,
            "message": "Successfully joined group"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error joining group: {str(e)}"
        )

@router.get("/{group_id}", response_model=Group)
async def get_group(
    group_id: str,
    user_id: str = "demo_user_123"
):
    """Get group details"""
    try:
        group_data = db.get_group(group_id)
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        # Check if user is a member
        is_member = any(member['id'] == user_id for member in group_data.get('members', []))
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not a member of this group."
            )
        
        return Group(**group_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching group: {str(e)}"
        )

@router.get("/", response_model=List[Group])
async def get_user_groups(
    user_id: str = "demo_user_123"
):
    """Get all groups for a user"""
    try:
        # Get groups where user is a member
        groups = db.get_groups_collection().where('members', 'array_contains', {'id': user_id}).stream()
        
        group_list = []
        for group_doc in groups:
            group_data = group_doc.to_dict()
            group_data['id'] = group_doc.id
            group_list.append(Group(**group_data))
        
        return group_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user groups: {str(e)}"
        )

@router.post("/{group_id}/rooms", response_model=dict)
async def create_rooms_for_group(
    group_id: str,
    user_id: str = "demo_user_123"
):
    """Create the 4 default rooms for a group"""
    try:
        # Verify user is a member
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
        
        # Create 4 rooms
        room_types = ["stay", "travel", "itinerary", "eat"]
        created_rooms = []
        
        for room_type in room_types:
            room_data = {
                "group_id": group_id,
                "room_type": room_type,
                "status": "active",  # Ensure rooms start as active
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            room_id = db.create_room(room_data)
            created_rooms.append(room_id)
        
        return {
            "message": "Rooms created successfully",
            "room_ids": created_rooms
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating rooms: {str(e)}"
        )

@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    user_id: str = "demo_user_123"
):
    """Delete a group (only by creator)"""
    try:
        group_data = db.get_group(group_id)
        if not group_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        if group_data.get('created_by') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the group creator can delete the group"
            )
        
        # Delete group and related data
        db.get_groups_collection().document(group_id).delete()
        
        # Log analytics
        db.log_user_action(user_id, "group_deleted", {
            "group_id": group_id
        })
        
        return {"message": "Group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting group: {str(e)}"
        )

