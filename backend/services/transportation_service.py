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

        base_order = 4

        return [
            {
                "question_text": "What type of trip?",
                "question_type": "buttons",
                "options": ["One Way", "Return"],
                "order": 1,
                "section": "general",
                "question_key": "trip_type",
            },
            # Departure budget - show for both one-way and return, but in departure section
            {
                "question_text": "What is your departure transportation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 2000,
                "step": 50,
                "currency": currency,
                "order": base_order - 2,  # Show before other departure questions
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "departure_budget_show",  # Show for both one-way and return
                "question_key": "departure_budget",
            },
            # Return budget - show only for return trips, in return section
            {
                "question_text": "What is your return transportation budget range?",
                "question_type": "range",
                "min_value": 0,
                "max_value": 2000,
                "step": 50,
                "currency": currency,
                "order": base_order + 5,  # Show before other return questions
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
                "question_key": "return_budget",
            },
            # One-way only questions (departure leg)
            {
                "question_text": "What transportation methods do you prefer?",
                "question_type": "dropdown",
                "options": options,
                "order": base_order,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
            },
            {
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": base_order + 1,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
            },
            {
                "question_text": "Any specific transportation preferences?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": base_order + 2,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
            },
            # Return trip - departure leg questions
            {
                "question_text": "What transportation methods do you prefer for departing?",
                "question_type": "dropdown",
                "options": options,
                "order": base_order + 3,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            {
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": base_order + 4,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            {
                "question_text": "Any specific transportation preferences for travelling while departing?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": base_order + 5,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            # Return trip - return leg questions
            {
                "question_text": "What transportation methods do you prefer for returning?",
                "question_type": "dropdown",
                "options": options,
                "order": base_order + 6,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
            },
            {
                "question_text": "What is your preferred return date?",
                "question_type": "date",
                "placeholder": "Select your return date",
                "order": base_order + 7,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
            },
            {
                "question_text": "Any specific transportation preferences for travelling while returning?",
                "question_type": "text",
                "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                "order": base_order + 8,
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

        # Check if this is a return trip
        trip_type_answer = next(
            (
                a
                for a in answers
                if a.get("question_key") == "trip_type"
                or "trip" in (str(a.get("question_text", "")).lower())
                or "type" in (str(a.get("question_text", "")).lower())
            ),
            None,
        )
        trip_type = (trip_type_answer.get("answer_value", "") if trip_type_answer else "one way").lower()

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

