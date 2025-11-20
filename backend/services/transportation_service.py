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
                "question_text": "What type of trip?",
                "question_type": "buttons",
                "options": ["One Way", "Return"],
                "order": 1,
            },
        ]
    
    def get_questions_for_trip_type(self, trip_type: str, currency: str, from_location: str = "", destination: str = "") -> List[Dict]:
        """Get questions based on trip type (one-way or return)"""
        travel_type = self.get_travel_type(from_location, destination)
        options = self.get_transportation_options(travel_type) or ["Flight", "Bus", "Train"]
        
        questions = []
        base_order = 2
        
        if trip_type.lower() == "one way":
            # One-way trip questions
            questions = [
                {
                    "question_text": "What transportation methods do you prefer?",
                    "question_type": "dropdown",
                    "options": options,
                    "order": base_order,
                },
                {
                    "question_text": "What is your preferred departure date?",
                    "question_type": "date",
                    "placeholder": "Select your departure date",
                    "order": base_order + 1,
                },
                {
                    "question_text": "Any specific transportation preferences?",
                    "question_type": "text",
                    "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                    "order": base_order + 2,
                },
            ]
        elif trip_type.lower() == "return":
            # Return trip questions - departure section
            questions = [
                {
                    "question_text": "What transportation methods do you prefer?",
                    "question_type": "dropdown",
                    "options": options,
                    "order": base_order,
                    "section": "departure",
                },
                {
                    "question_text": "What is your preferred departure date?",
                    "question_type": "date",
                    "placeholder": "Select your departure date",
                    "order": base_order + 1,
                    "section": "departure",
                },
                {
                    "question_text": "Any specific transportation preferences for travelling while departing?",
                    "question_type": "text",
                    "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                    "order": base_order + 2,
                    "section": "departure",
                },
                # Return section
                {
                    "question_text": "What transportation methods do you prefer?",
                    "question_type": "dropdown",
                    "options": options,
                    "order": base_order + 3,
                    "section": "return",
                },
                {
                    "question_text": "What is your preferred return date?",
                    "question_type": "date",
                    "placeholder": "Select your return date",
                    "order": base_order + 4,
                    "section": "return",
                },
                {
                    "question_text": "Any specific transportation preferences for travelling while returning?",
                    "question_type": "text",
                    "placeholder": "e.g., direct flights only, eco-friendly options, luxury transport...",
                    "order": base_order + 5,
                    "section": "return",
                },
            ]
        
        return questions

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
            (a for a in answers if "trip" in a.get("question_text", "").lower() or "type" in a.get("question_text", "").lower()),
            None
        )
        trip_type = trip_type_answer.get("answer_value", "").lower() if trip_type_answer else "one way"

        if trip_type == "return":
            # Generate suggestions for both departure and return
            departure_answers = []
            return_answers = []
            
            # Separate answers by section
            for answer in answers:
                section = answer.get("section", "")
                if section == "return":
                    return_answers.append(answer)
                else:
                    # Include non-sectioned answers and departure answers
                    if section != "return":
                        departure_answers.append(answer)
            
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

