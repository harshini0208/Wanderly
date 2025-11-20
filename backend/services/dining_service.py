from typing import Dict, List

from firebase_service import firebase_service as default_firebase_service

from .base_room_service import BaseRoomService


class DiningService(BaseRoomService):
    def __init__(self, firebase_service=None, ai_service=None):
        super().__init__(
            "dining",
            firebase=firebase_service or default_firebase_service,
            ai=ai_service,
        )

    def get_default_questions(self, currency: str, **kwargs) -> List[Dict]:
        return [
            {
                "question_text": "What kind of dining experiences are you most interested in during this trip?",
                "question_type": "buttons",
                "options": [
                    "Local specialties & authentic food spots",
                    "Trendy restaurants or fine dining",
                    "Hidden gems / street food experiences",
                    "Casual, budget-friendly meals",
                    "Cafés & brunch spots",
                    "Bars, pubs, or nightlife dining",
                ],
                "order": 0,
            },
            {
                "question_text": "What kind of cuisines or food styles do you want to explore?",
                "question_type": "buttons",
                "options": [
                    "Local cuisine",
                    "Asian",
                    "Mediterranean",
                    "Italian",
                    "American / Burgers",
                    "Vegetarian / Vegan",
                    "Seafood",
                    "Desserts / Coffee / Bakery",
                    "Open to anything",
                ],
                "order": 1,
            },
            {
                "question_text": "Do you have any dietary needs or food preferences?",
                "question_type": "text",
                "placeholder": 'Type your dietary needs or preferences. Type "No restrictions" if none.',
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
            room_type=room.get("room_type", "dining"),
            destination=destination,
            answers=answers,
            group_preferences=group_preferences,
        )


