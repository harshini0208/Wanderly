# Room configuration system
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RoomConfig:
    """Configuration for a room type"""
    room_type: str
    name: str
    description: str
    icon: str = ""
    questions_config: Dict[str, Any] = None

class RoomConfigurationService:
    """Service to manage room configurations"""
    
    def __init__(self):
        self._room_configs = self._load_default_configs()
    
    def _load_default_configs(self) -> Dict[str, RoomConfig]:
        """Load default room configurations"""
        return {
            "stay": RoomConfig(
                room_type="stay",
                name="Plan Stay",
                description="Find the perfect accommodation",
                icon="hotel",
                questions_config={
                    "accommodation_type": ["Hotel", "Resort", "Hostel", "Homestay", "Any"],
                    "budget": ["Budget", "Mid-range", "Luxury", "Any"],
                    "amenities": ["WiFi", "Pool", "Gym", "Parking", "Breakfast"]
                }
            ),
            "travel": RoomConfig(
                room_type="travel", 
                name="Plan Travel",
                description="Book your transportation",
                icon="plane",
                questions_config={
                    "travel_type": ["Flight", "Train", "Bus", "Car Rental", "Mixed"],
                    "vehicle_type": ["Budget Flight", "Premium Flight", "Express Train", "Local Train", "Sleeper Bus", "Semi-Sleeper", "AC Seater", "Non-AC", "Private Car", "Shared Taxi"],
                    "travel_time": ["Morning", "Afternoon", "Evening", "Night", "No Preference"]
                }
            ),
            "eat": RoomConfig(
                room_type="eat",
                name="Plan Eat", 
                description="Discover local cuisine",
                icon="utensils",
                questions_config={
                    "meal_type": ["Breakfast", "Lunch", "Dinner", "Snacks/Cafes", "Any"],
                    "cuisine_type": ["Local", "International", "Vegetarian", "Non-Vegetarian", "Any"],
                    "dining_preference": ["Fine Dining", "Casual", "Street Food", "Cafes", "Any"]
                }
            ),
            "itinerary": RoomConfig(
                room_type="itinerary",
                name="Plan Activities",
                description="Plan activities and attractions", 
                icon="calendar",
                questions_config={
                    "activity_type": ["Sightseeing", "Adventure", "Cultural", "Relaxation", "Mixed"],
                    "duration": ["Half Day", "Full Day", "Multiple Days", "Any"],
                    "group_size_preference": ["Small Group", "Large Group", "Private", "Any"]
                }
            )
        }
    
    def get_room_config(self, room_type: str) -> RoomConfig:
        """Get configuration for a specific room type"""
        return self._room_configs.get(room_type)
    
    def get_all_room_configs(self) -> List[RoomConfig]:
        """Get all available room configurations"""
        return list(self._room_configs.values())
    
    def get_room_types(self) -> List[str]:
        """Get all available room types"""
        return list(self._room_configs.keys())
    
    def add_room_config(self, config: RoomConfig) -> None:
        """Add a new room configuration"""
        self._room_configs[config.room_type] = config
    
    def update_room_config(self, room_type: str, **kwargs) -> None:
        """Update an existing room configuration"""
        if room_type in self._room_configs:
            config = self._room_configs[room_type]
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
    
    def create_rooms_for_group(self, group_id: str, room_types: List[str] = None) -> List[str]:
        """Create rooms for a group based on configuration"""
        if room_types is None:
            room_types = self.get_room_types()
        
        created_rooms = []
        for room_type in room_types:
            config = self.get_room_config(room_type)
            if config:
                room_data = {
                    "group_id": group_id,
                    "room_type": config.room_type,
                    "name": config.name,
                    "description": config.description,
                    "icon": config.icon,
                    "questions_config": config.questions_config,
                    "status": "active",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                # This would call the database service
                # room_id = db.create_room(room_data)
                # created_rooms.append(room_id)
                created_rooms.append(f"room_{room_type}_{group_id}")
        
        return created_rooms

# Global instance
room_config_service = RoomConfigurationService()
