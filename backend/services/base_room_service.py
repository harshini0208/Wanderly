from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Dict, List, Tuple, Optional, Any

from firebase_service import firebase_service
from ai_service import AIService
from bigquery_service import bigquery_service
from utils import get_currency_from_destination, get_travel_type, get_transportation_options


class BaseRoomService(ABC):
    """Shared helpers for room-specific services."""

    def __init__(
        self,
        room_type: str,
        firebase=firebase_service,
        ai: Optional[AIService] = None,
    ) -> None:
        self.room_type = room_type
        self.firebase_service = firebase
        self.ai_service = ai

    # --------------------------------------------------------------------- #
    # Core fetch/validation helpers
    # --------------------------------------------------------------------- #
    def get_room(self, room_id: str) -> Dict:
        room = self.firebase_service.get_room(room_id)
        if not room:
            raise ValueError("Room not found")
        return room

    def get_group(self, group_id: str) -> Dict:
        group = self.firebase_service.get_group(group_id)
        if not group:
            raise ValueError("Group not found")
        return group

    def validate_room_and_group(self, room_id: str) -> Tuple[Dict, Dict]:
        room = self.get_room(room_id)
        group_id = room.get("group_id")
        if not group_id:
            raise ValueError("Room missing group reference")
        group = self.get_group(group_id)
        return room, group

    # --------------------------------------------------------------------- #
    # Question management
    # --------------------------------------------------------------------- #
    def create_questions(self, room_id: str) -> List[Dict]:
        room, group = self.validate_room_and_group(room_id)
        currency = self._resolve_currency(group)
        from_location = group.get("from_location", "")
        destination = group.get("destination", "")

        default_questions = self.get_default_questions(
            currency=currency,
            from_location=from_location,
            destination=destination,
            group=group,
        )

        created_questions: List[Dict] = []
        for index, question_data in enumerate(default_questions):
            payload = {
                **question_data,
                "room_id": room_id,
                "order": question_data.get("order", index),
            }
            created_questions.append(self.firebase_service.create_question(payload))

        created_questions.sort(key=lambda q: q.get("order", 999))
        return created_questions

    def get_questions(self, room_id: str) -> List[Dict]:
        room = self.get_room(room_id)
        questions = self.firebase_service.get_room_questions(room_id) or []
        questions.sort(key=lambda q: q.get("order", 999))
        return self._filter_room_questions(room, questions)

    # --------------------------------------------------------------------- #
    # Answers
    # --------------------------------------------------------------------- #
    def submit_answer(self, room_id: str, answer_data: Dict[str, Any]) -> Dict:
        if not {"room_id", "user_id", "question_id", "answer_value"} <= answer_data.keys():
            raise ValueError("Missing required answer fields")

        answer = self.firebase_service.create_answer(answer_data)
        bigquery_service.insert_answer_analytics(answer)
        return answer

    def get_answers(self, room_id: str, user_id: Optional[str] = None) -> List[Dict]:
        if user_id:
            return self.firebase_service.get_user_answers(room_id, user_id)
        return self.firebase_service.get_room_answers(room_id)

    # --------------------------------------------------------------------- #
    # Room progress helpers
    # --------------------------------------------------------------------- #
    def save_room_selections(self, room_id: str, selections: List[Dict]) -> Dict:
        if not selections:
            raise ValueError("No selections provided")

        room = self.get_room(room_id)
        existing = room.get("user_selections", []) or []
        previous_count = len(existing)
        added_count = len(selections)

        existing_by_id = {sel.get("id") or sel.get("suggestion_id"): sel for sel in existing if sel.get("id") or sel.get("suggestion_id")}
        existing_by_name = {
            (sel.get("name") or sel.get("title") or "").strip().lower(): sel
            for sel in existing if not sel.get("id") and not sel.get("suggestion_id")
        }

        merged = existing.copy()
        for new_sel in selections:
            new_id = new_sel.get("id") or new_sel.get("suggestion_id")
            new_name = (new_sel.get("name") or new_sel.get("title") or "").strip().lower()

            if new_id and new_id in existing_by_id:
                merged = [s for s in merged if (s.get("id") != new_id and s.get("suggestion_id") != new_id)]
                merged.append(new_sel)
                existing_by_id[new_id] = new_sel
                continue

            if not new_id and new_name and new_name in existing_by_name:
                continue

            if new_id:
                existing_by_id[new_id] = new_sel
            elif new_name:
                existing_by_name[new_name] = new_sel
            merged.append(new_sel)

        self.firebase_service.update_room(room_id, {
            "user_selections": merged,
            "last_updated": datetime.now(UTC).isoformat(),
        })
        return {
            "success": True,
            "selections_count": len(merged),
            "previous_count": previous_count,
            "added_count": added_count,
        }

    def mark_room_complete(self, room_id: str, user_email: str) -> Dict:
        if not user_email:
            raise ValueError("User email is required")

        room = self.get_room(room_id)
        completed = room.get("completed_by") or []
        already_completed = user_email in completed
        if not already_completed:
            completed.append(user_email)
            self.firebase_service.update_room(room_id, {"completed_by": completed})
    
        return {
            "success": True,
            "completed_count": len(completed),
            "already_completed": already_completed,
        }

    def get_room_status(self, room_id: str) -> Dict:
        room = self.get_room(room_id)
        return {
            "is_completed": room.get("is_completed", False),
            "is_locked": room.get("is_locked", False),
            "completed_at": room.get("completed_at"),
            "locked_at": room.get("locked_at"),
            "completion_status": room.get("completion_status"),
            "completions": room.get("completed_by", []),
        }

    # --------------------------------------------------------------------- #
    # Travel helpers for transportation service reuse
    # --------------------------------------------------------------------- #
    def get_travel_type(self, from_location: str, destination: str) -> str:
        return get_travel_type(from_location, destination)

    def get_transportation_options(self, travel_type: str) -> List[str]:
        return get_transportation_options(travel_type)

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _resolve_currency(self, group: Dict) -> str:
        from_location = group.get("from_location", "")
        if not from_location:
            return "$"
        try:
            return get_currency_from_destination(from_location)
        except Exception:
            return "$"

    def _filter_room_questions(self, room: Dict, questions: List[Dict]) -> List[Dict]:
        if room.get("room_type") != "dining":
            return questions
        filtered = []
        seen = set()
        for question in questions:
            text = (question.get("question_text") or "").strip().lower()
            if "must-do" in text:
                continue
            if text in seen:
                continue
            seen.add(text)
            filtered.append(question)
        return filtered

    # --------------------------------------------------------------------- #
    # Abstract API
    # --------------------------------------------------------------------- #
    @abstractmethod
    def get_default_questions(self, currency: str, **kwargs) -> List[Dict]:
        raise NotImplementedError

    @abstractmethod
    def generate_suggestions(self, room_id: str, answers: List[Dict]) -> List[Dict]:
        raise NotImplementedError

