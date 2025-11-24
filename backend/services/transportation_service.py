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
                "question_text": "What type of trip?",
                "question_type": "buttons",
                "options": ["One Way", "Return"],
                "order": 1,
                "section": "general",
                "question_key": "trip_type",
            },
            # One-way questions
            {
                "question_text": "What is your departure transportation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 2000,
                "step": 50,
                "currency": currency,
                "order": 2,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
                "question_key": "departure_budget",
            },
            {
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": 3,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
            },
            {
                "question_text": "Any specific transportation preferences?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": 4,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
            },
            # Return trip - departure section (all questions grouped together)
            {
                "question_text": "What is your departure transportation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 2000,
                "step": 50,
                "currency": currency,
                "order": 2,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
                "question_key": "departure_budget",
            },
            {
                "question_text": "What transportation methods do you prefer for departing?",
                "question_type": "dropdown",
                "options": options,
                "order": 3,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            {
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": 4,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            {
                "question_text": "Any specific transportation preferences for travelling while departing?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": 5,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            # Return trip - return section (all questions grouped together)
            {
                "question_text": "What is your return transportation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 2000,
                "step": 50,
                "currency": currency,
                "order": 6,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
                "question_key": "return_budget",
            },
            {
                "question_text": "What transportation methods do you prefer for returning?",
                "question_type": "dropdown",
                "options": options,
                "order": 7,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
            },
            {
                "question_text": "What is your preferred return date?",
                "question_type": "date",
                "placeholder": "Select your return date",
                "order": 8,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
            },
            {
                "question_text": "Any specific transportation preferences for travelling while returning?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": 9,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
            },
        ]

    def generate_suggestions(self, room_id: str, answers: List[Dict]) -> List[Dict]:
        room, group = self.validate_room_and_group(room_id)
        if not self.ai_service:
            raise RuntimeError("AI service unavailable")

        destination = group.get("destination", "Unknown")
        from_location = group.get("from_location", "")
        group_preferences = {
            "start_date": group.get("start_date"),
            "end_date": group.get("end_date"),
            "group_size": group.get("group_size"),
            "from_location": from_location,
        }

        trip_type = self._determine_trip_type(answers)

        if trip_type == "return":
            # Separate answers into general, departure, and return buckets
            general_answers = []
            departure_specific = []
            return_specific = []

            for answer in answers:
                section = (answer.get("section") or answer.get("trip_leg") or "").lower()
                if section == "return":
                    return_specific.append(answer)
                elif section == "departure":
                    departure_specific.append(answer)
                else:
                    general_answers.append(answer)
            
            departure_answers = general_answers + departure_specific
            return_answers = general_answers + return_specific
            
            # Generate departure suggestions
            departure_suggestions = self.ai_service.generate_suggestions(
                room_type="transportation",
                destination=destination,
                answers=departure_answers,
                group_preferences=group_preferences,
            )
            
            # Mark departure suggestions
            for suggestion in departure_suggestions:
                suggestion["trip_leg"] = "departure"
                suggestion["leg_type"] = "departure"
            
            # Generate return suggestions (swap from_location and destination)
            return_group_preferences = {
                **group_preferences,
                "from_location": destination,  # Return trip starts from destination
            }
            # For return, we need to swap the locations in the answers
            return_suggestions = self.ai_service.generate_suggestions(
                room_type="transportation",
                destination=from_location,  # Return goes back to origin
                answers=return_answers,
                group_preferences=return_group_preferences,
            )
            
            # Mark return suggestions
            for suggestion in return_suggestions:
                suggestion["trip_leg"] = "return"
                suggestion["leg_type"] = "return"
            
            # Combine both sets of suggestions
            return departure_suggestions + return_suggestions
        else:
            # One-way trip - generate suggestions normally
            suggestions = self.ai_service.generate_suggestions(
                room_type=room.get("room_type", "transportation"),
                destination=destination,
                answers=answers,
                group_preferences=group_preferences,
            )
            # Mark as departure for consistency
            for suggestion in suggestions:
                suggestion["trip_leg"] = "departure"
                suggestion["leg_type"] = "departure"
            
            return suggestions

    def _determine_trip_type(self, answers: List[Dict]) -> str:
        """Infer whether the user asked for a return trip from the answers."""
        for answer in answers or []:
            key = (answer.get("question_key") or "").lower()
            qid = (answer.get("question_id") or "").lower()
            text = (answer.get("question_text") or "").lower()

            if "trip" in key or "trip" in qid or "trip" in text:
                value = answer.get("answer_value")
                if isinstance(value, list):
                    value = value[0] if value else ""
                if isinstance(value, dict):
                    value = value.get("value") or ""
                if isinstance(value, str):
                    cleaned = value.strip().lower()
                else:
                    cleaned = str(value).lower()
                if "return" in cleaned:
                    return "return"
                if "one" in cleaned:
                    return "one way"
        return "one way"

