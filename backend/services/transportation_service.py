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
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": 2,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "one_way",
            },
            # Return trip - departure section (all questions grouped together)
            {
                "question_text": "What transportation methods do you prefer for departing?",
                "question_type": "dropdown",
                "options": options,
                "order": 2,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            {
                "question_text": "What is your preferred departure date?",
                "question_type": "date",
                "placeholder": "Select your departure date",
                "order": 3,
                "section": "departure",
                "trip_leg": "departure",
                "visibility_condition": "return_departure",
            },
            # Return trip - return section (all questions grouped together)
            {
                "question_text": "What transportation methods do you prefer for returning?",
                "question_type": "dropdown",
                "options": options,
                "order": 4,
                "section": "return",
                "trip_leg": "return",
                "visibility_condition": "return_return",
            },
            {
                "question_text": "What is your preferred return date?",
                "question_type": "date",
                "placeholder": "Select your return date",
                "order": 5,
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
            # First, get all questions to look up sections
            questions = self.get_questions(room_id)
            question_sections = {}
            for q in questions:
                qid = q.get('id')
                if qid:
                    question_sections[qid] = (q.get('section') or '').lower()
            
            general_answers = []
            departure_specific = []
            return_specific = []

            for answer in answers:
                # First check answer's own section/trip_leg
                section = (answer.get("section") or answer.get("trip_leg") or "").lower()
                
                # If not found, look up the question's section
                if not section:
                    question_id = answer.get("question_id")
                    if question_id and question_id in question_sections:
                        section = question_sections[question_id]
                
                # Enrich the answer with the section for later use (even if it was already set)
                enriched_answer = {**answer, "section": section} if section else answer
                
                # Categorize the enriched answer
                if section == "return":
                    return_specific.append(enriched_answer)
                elif section == "departure":
                    departure_specific.append(enriched_answer)
                else:
                    general_answers.append(enriched_answer)
            
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
                "trip_leg": "return",  # Mark this as a return trip
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
            value = answer.get("answer_value")

            # Check if this looks like a trip type question
            is_trip_question = (
                "trip" in key or "trip" in qid or "trip" in text or
                key == "trip_type" or qid == "trip_type" or
                "type" in key and "trip" in key or
                "type" in qid and "trip" in qid
            )

            # Also check if the answer value itself indicates return/one-way
            # (in case question metadata is missing)
            if isinstance(value, list):
                value_str = value[0] if value else ""
            elif isinstance(value, dict):
                value_str = value.get("value") or ""
            else:
                value_str = str(value) if value else ""
            
            cleaned = value_str.strip().lower() if isinstance(value_str, str) else str(value_str).lower()
            
            # If it's a trip type question OR the value contains return/one-way keywords
            if is_trip_question or "return" in cleaned or "one" in cleaned or "one-way" in cleaned:
                if "return" in cleaned:
                    return "return"
                if "one" in cleaned or "one-way" in cleaned:
                    return "one way"
        
        return "one way"

