import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import bigquery
from app.config import settings
import json
import os

# Initialize Firebase
def init_firebase():
    try:
        if not firebase_admin._apps:
            # Create credentials from environment variables
            cred_dict = {
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "private_key_id": settings.firebase_private_key_id,
                "private_key": settings.firebase_private_key.replace('\\n', '\n').strip('"'),
                "client_email": settings.firebase_client_email,
                "client_id": settings.firebase_client_id,
                "auth_uri": settings.firebase_auth_uri,
                "token_uri": settings.firebase_token_uri
            }
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        
        return firestore.client()
    except Exception as e:
        print(f"Firebase initialization failed: {e}")
        return None

# Initialize BigQuery
def init_bigquery():
    try:
        return bigquery.Client(project=settings.google_cloud_project_id)
    except Exception as e:
        print(f"BigQuery initialization failed: {e}")
        print("Continuing without BigQuery analytics...")
        return None

# Database collections
class Database:
    def __init__(self):
        self.db = init_firebase()
        self.bigquery_client = init_bigquery()
    
    def _serialize_datetime(self, obj):
        """Convert datetime objects to ISO format strings"""
        if isinstance(obj, dict):
            return {key: self._serialize_datetime(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime object
            return obj.isoformat()
        else:
            return obj
    
    # Groups collection
    def get_groups_collection(self):
        return self.db.collection('groups')
    
    def get_group(self, group_id: str):
        if not self.db:
            return None
        doc = self.get_groups_collection().document(group_id).get()
        if doc.exists:
            group_data = doc.to_dict()
            group_data['id'] = doc.id
            return group_data
        return None
    
    def create_group(self, group_data: dict):
        # Convert datetime objects to strings for Firestore
        serialized_data = self._serialize_datetime(group_data)
        doc_ref = self.get_groups_collection().add(serialized_data)
        return doc_ref[1].id
    
    def update_group(self, group_id: str, update_data: dict):
        self.get_groups_collection().document(group_id).update(update_data)
    
    # Rooms collection
    def get_rooms_collection(self):
        return self.db.collection('rooms')
    
    def get_room(self, room_id: str):
        doc = self.get_rooms_collection().document(room_id).get()
        if doc.exists:
            room_data = doc.to_dict()
            room_data['id'] = doc.id
            return room_data
        return None
    
    def get_rooms_by_group(self, group_id: str):
        return self.get_rooms_collection().where('group_id', '==', group_id).stream()
    
    def create_room(self, room_data: dict):
        serialized_data = self._serialize_datetime(room_data)
        doc_ref = self.get_rooms_collection().add(serialized_data)
        return doc_ref[1].id
    
    # Questions collection
    def get_questions_collection(self):
        return self.db.collection('questions')
    
    def get_questions_by_room(self, room_id: str):
        # Remove order_by to avoid index requirement for demo
        return self.get_questions_collection().where('room_id', '==', room_id).stream()
    
    def create_question(self, question_data: dict):
        serialized_data = self._serialize_datetime(question_data)
        doc_ref = self.get_questions_collection().add(serialized_data)
        return doc_ref[1].id
    
    # Answers collection
    def get_answers_collection(self):
        return self.db.collection('answers')
    
    def get_answers_by_question(self, question_id: str):
        return self.get_answers_collection().where('question_id', '==', question_id).stream()
    
    def get_answers_by_room(self, room_id: str):
        return self.get_answers_collection().where('room_id', '==', room_id).stream()
    
    def create_answer(self, answer_data: dict):
        serialized_data = self._serialize_datetime(answer_data)
        doc_ref = self.get_answers_collection().add(serialized_data)
        return doc_ref[1].id
    
    # Suggestions collection
    def get_suggestions_collection(self):
        return self.db.collection('suggestions')
    
    def get_suggestions_by_room(self, room_id: str):
        return self.get_suggestions_collection().where('room_id', '==', room_id).stream()
    
    def create_suggestion(self, suggestion_data: dict):
        serialized_data = self._serialize_datetime(suggestion_data)
        doc_ref = self.get_suggestions_collection().add(serialized_data)
        return doc_ref[1].id
    
    # Votes collection
    def get_votes_collection(self):
        return self.db.collection('votes')
    
    def get_votes_by_suggestion(self, suggestion_id: str):
        return self.get_votes_collection().where('suggestion_id', '==', suggestion_id).stream()
    
    def create_vote(self, vote_data: dict):
        serialized_data = self._serialize_datetime(vote_data)
        doc_ref = self.get_votes_collection().add(serialized_data)
        return doc_ref[1].id
    
    def create_user_completion(self, completion_data: dict):
        serialized_data = self._serialize_datetime(completion_data)
        doc_ref = self.get_user_completions_collection().add(serialized_data)
        return doc_ref[1].id
    
    def get_user_completions_collection(self):
        return self.db.collection('user_completions')
    
    # Analytics - BigQuery
    def log_user_action(self, user_id: str, action: str, metadata: dict = None):
        if not self.bigquery_client:
            print("BigQuery not available, skipping analytics logging")
            return True
            
        try:
            table_id = f"{settings.google_cloud_project_id}.{settings.bigquery_dataset_id}.user_actions"
            
            from datetime import datetime
            row = {
                "user_id": user_id,
                "action": action,
                "metadata": json.dumps(metadata) if metadata else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            errors = self.bigquery_client.insert_rows_json(table_id, [row])
            return len(errors) == 0
        except Exception as e:
            print(f"BigQuery logging error: {e}")
            return False

# Global database instance
db = Database()
