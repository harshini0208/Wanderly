from typing import Dict, List

from firebase_service import firebase_service as default_firebase_service

from .base_room_service import BaseRoomService


class AccommodationService(BaseRoomService):
    def __init__(self, firebase_service=None, ai_service=None):
        super().__init__(
            "accommodation",
            firebase=firebase_service or default_firebase_service,
            ai=ai_service,
        )

    def get_default_questions(self, currency: str, **kwargs) -> List[Dict]:
        return [
            {
                "question_text": "What is your accommodation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 1000,
                "step": 10,
                "currency": currency,
                "order": 0,
            },
            {
                "question_text": "What type of accommodation do you prefer?",
                "question_type": "buttons",
                "options": ["Hotel", "Hostel", "Airbnb", "Resort", "Guesthouse", "No preference"],
                "order": 1,
            },
            {
                "question_text": "Any specific accommodation preferences or requirements?",
                "question_type": "text",
                "placeholder": "e.g., pet-friendly, pool, gym, near city center...",
                "order": 2,
            },
        ]

    def generate_suggestions(self, room_id: str, answers: List[Dict]) -> List[Dict]:
        room, group = self.validate_room_and_group(room_id)
        if not self.ai_service:
            raise RuntimeError("AI service unavailable")

        destination = group.get("destination", "Unknown")
        group_preferences = {
            "start_date": group.get("start_date"),
            "end_date": group.get("end_date"),
            "group_size": group.get("group_size"),
            "from_location": group.get("from_location", ""),
        }

        return self.ai_service.generate_suggestions(
            room_type=room.get("room_type", "accommodation"),
            destination=destination,
            answers=answers,
            group_preferences=group_preferences,
        )

