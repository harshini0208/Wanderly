from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from app.services.room_config_service import room_config_service, RoomConfig

router = APIRouter()

@router.get("/rooms", response_model=dict)
async def get_room_configurations():
    """Get all available room configurations"""
    try:
        configs = room_config_service.get_all_room_configs()
        return {
            "room_configs": [
                {
                    "room_type": config.room_type,
                    "name": config.name,
                    "description": config.description,
                    "icon": config.icon,
                    "questions_config": config.questions_config
                }
                for config in configs
            ],
            "total_count": len(configs)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching room configurations: {str(e)}"
        )

@router.post("/rooms", response_model=dict)
async def create_custom_room_config(
    room_type: str,
    name: str,
    description: str,
    icon: str = "",
    questions_config: Dict[str, Any] = None
):
    """Create a custom room configuration"""
    try:
        config = RoomConfig(
            room_type=room_type,
            name=name,
            description=description,
            icon=icon,
            questions_config=questions_config or {}
        )
        
        room_config_service.add_room_config(config)
        
        return {
            "message": f"Room configuration '{room_type}' created successfully",
            "config": {
                "room_type": config.room_type,
                "name": config.name,
                "description": config.description,
                "icon": config.icon,
                "questions_config": config.questions_config
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating room configuration: {str(e)}"
        )

@router.put("/rooms/{room_type}", response_model=dict)
async def update_room_config(
    room_type: str,
    name: str = None,
    description: str = None,
    icon: str = None,
    questions_config: Dict[str, Any] = None
):
    """Update an existing room configuration"""
    try:
        # Check if room type exists
        existing_config = room_config_service.get_room_config(room_type)
        if not existing_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room configuration '{room_type}' not found"
            )
        
        # Update configuration
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if description is not None:
            update_data['description'] = description
        if icon is not None:
            update_data['icon'] = icon
        if questions_config is not None:
            update_data['questions_config'] = questions_config
        
        room_config_service.update_room_config(room_type, **update_data)
        
        return {
            "message": f"Room configuration '{room_type}' updated successfully",
            "updated_fields": list(update_data.keys())
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating room configuration: {str(e)}"
        )

@router.delete("/rooms/{room_type}", response_model=dict)
async def delete_room_config(room_type: str):
    """Delete a custom room configuration (only custom ones)"""
    try:
        # Prevent deletion of default room types
        default_types = ["stay", "travel", "eat", "itinerary"]
        if room_type in default_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot delete default room type '{room_type}'"
            )
        
        # Check if room type exists
        existing_config = room_config_service.get_room_config(room_type)
        if not existing_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room configuration '{room_type}' not found"
            )
        
        # Remove from configuration service
        room_config_service._room_configs.pop(room_type, None)
        
        return {
            "message": f"Room configuration '{room_type}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting room configuration: {str(e)}"
        )
