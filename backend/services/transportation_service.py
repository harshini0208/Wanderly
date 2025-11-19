from typing import Dict, List

from firebase_service import firebase_service as default_firebase_service

from .base_room_service import BaseRoomService


class TransportationService(BaseRoomService):
    def __init__(self, firebase_service=None, ai_service=None):
        super().__init__(
            "transportation",
            firebase=firebase_service or default_firebase_service,
            ai=ai_service,
        )

    def get_default_questions(
        self,
        currency: str,
        from_location: str = "",
        destination: str = "",
        **kwargs,
    ) -> List[Dict]:
        travel_type = self.get_travel_type(from_location, destination)
        options = self.get_transportation_options(travel_type) or ["Flight", "Bus", "Train"]

        return [
            {
                "question_text": "What is your transportation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 2000,
                "step": 50,
                "currency": currency,
                "order": 0,
            },
            {
                "question_text": "What transportation methods do you prefer?",
                "question_type": "dropdown",
                "options": options,
                "order": 1,
            },
            {
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": 2,
            },
            {
                "question_text": "What is your preferred return date? (Leave empty for one-way)",
                "question_type": "date",
                "placeholder": "Select your return date (optional)",
                "order": 3,
            },
            {
                "question_text": "Any specific transportation preferences?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": 4,
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
            room_type=room.get("room_type", "transportation"),
            destination=destination,
            answers=answers,
            group_preferences=group_preferences,
        )

