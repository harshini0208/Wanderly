import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
from datetime import datetime
import json

class FirebaseService:
    def __init__(self):
        """Initialize Firebase connection"""
        if not firebase_admin._apps:
            # Initialize Firebase Admin SDK
            cred = credentials.Certificate('firebase_service_account.json')
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'lexical-theory-471417-q3.appspot.com'
            })
        
        self.db = firestore.client()
        self.bucket = storage.bucket()
    
    # Groups Collection
    def create_group(self, group_data):
        """Create a new group in Firestore"""
        doc_ref = self.db.collection('groups').document()
        group_data['id'] = doc_ref.id
        group_data['created_at'] = datetime.utcnow().isoformat()
        group_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.set(group_data)
        return group_data
    
    def get_group(self, group_id):
        """Get a group by ID"""
        doc_ref = self.db.collection('groups').document(group_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def get_user_groups(self, user_id):
        """Get all groups for a user"""
        groups_ref = self.db.collection('groups')
        query = groups_ref.where('members', 'array_contains', user_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def update_group(self, group_id, update_data):
        """Update a group"""
        doc_ref = self.db.collection('groups').document(group_id)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.update(update_data)
        return True
    
    # Users Collection
    def create_user(self, user_data):
        """Create a new user"""
        doc_ref = self.db.collection('users').document(user_data['id'])
        user_data['created_at'] = datetime.utcnow().isoformat()
        user_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.set(user_data)
        return user_data
    
    def get_user(self, user_id):
        """Get a user by ID"""
        doc_ref = self.db.collection('users').document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def update_user(self, user_id, update_data):
        """Update a user"""
        doc_ref = self.db.collection('users').document(user_id)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.update(update_data)
        return True
    
    # Rooms Collection
    def create_room(self, room_data):
        """Create a new room"""
        doc_ref = self.db.collection('rooms').document()
        room_data['id'] = doc_ref.id
        room_data['created_at'] = datetime.utcnow().isoformat()
        room_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.set(room_data)
        return room_data
    
    def get_room(self, room_id):
        """Get a room by ID"""
        doc_ref = self.db.collection('rooms').document(room_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def get_group_rooms(self, group_id):
        """Get all rooms for a group"""
        rooms_ref = self.db.collection('rooms')
        query = rooms_ref.where('group_id', '==', group_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def update_room(self, room_id, update_data):
        """Update a room"""
        doc_ref = self.db.collection('rooms').document(room_id)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.update(update_data)
        return True
    
    # Questions Collection
    def create_question(self, question_data):
        """Create a new question"""
        doc_ref = self.db.collection('questions').document()
        question_data['id'] = doc_ref.id
        question_data['created_at'] = datetime.utcnow().isoformat()
        doc_ref.set(question_data)
        return question_data
    
    def get_room_questions(self, room_id):
        """Get all questions for a room"""
        questions_ref = self.db.collection('questions')
        query = questions_ref.where('room_id', '==', room_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    # Answers Collection
    def create_answer(self, answer_data):
        """Create a new answer"""
        doc_ref = self.db.collection('answers').document()
        answer_data['id'] = doc_ref.id
        answer_data['created_at'] = datetime.utcnow().isoformat()
        doc_ref.set(answer_data)
        return answer_data
    
    def get_room_answers(self, room_id):
        """Get all answers for a room"""
        answers_ref = self.db.collection('answers')
        query = answers_ref.where('room_id', '==', room_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_user_answers(self, room_id, user_id):
        """Get answers for a specific user in a room"""
        answers_ref = self.db.collection('answers')
        query = answers_ref.where('room_id', '==', room_id).where('user_id', '==', user_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def update_answer(self, answer_id, update_data):
        """Update an answer"""
        doc_ref = self.db.collection('answers').document(answer_id)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.update(update_data)
        return True
    
    # Suggestions Collection
    def create_suggestion(self, suggestion_data):
        """Create a new suggestion"""
        doc_ref = self.db.collection('suggestions').document()
        suggestion_data['id'] = doc_ref.id
        suggestion_data['created_at'] = datetime.utcnow().isoformat()
        doc_ref.set(suggestion_data)
        return suggestion_data
    
    def get_room_suggestions(self, room_id):
        """Get all suggestions for a room"""
        suggestions_ref = self.db.collection('suggestions')
        query = suggestions_ref.where('room_id', '==', room_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_suggestion(self, suggestion_id):
        """Get a specific suggestion by ID"""
        doc_ref = self.db.collection('suggestions').document(suggestion_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    # Votes Collection
    def create_vote(self, vote_data):
        """Create a new vote"""
        doc_ref = self.db.collection('votes').document()
        vote_data['id'] = doc_ref.id
        vote_data['created_at'] = datetime.utcnow().isoformat()
        doc_ref.set(vote_data)
        return vote_data
    
    def get_suggestion_votes(self, suggestion_id):
        """Get all votes for a suggestion"""
        votes_ref = self.db.collection('votes')
        query = votes_ref.where('suggestion_id', '==', suggestion_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_user_vote(self, suggestion_id, user_id):
        """Get a user's vote for a suggestion"""
        votes_ref = self.db.collection('votes')
        query = votes_ref.where('suggestion_id', '==', suggestion_id).where('user_id', '==', user_id)
        docs = query.stream()
        votes = [doc.to_dict() for doc in docs]
        return votes[0] if votes else None
    
    def update_vote(self, vote_id, update_data):
        """Update a vote"""
        doc_ref = self.db.collection('votes').document(vote_id)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.update(update_data)
        return True
    
    # Room Completions Collection
    def create_room_completion(self, completion_data):
        """Create a room completion record"""
        doc_ref = self.db.collection('room_completions').document()
        completion_data['id'] = doc_ref.id
        completion_data['created_at'] = datetime.utcnow().isoformat()
        doc_ref.set(completion_data)
        return completion_data
    
    def get_room_completion(self, room_id):
        """Get room completion status"""
        completions_ref = self.db.collection('room_completions')
        query = completions_ref.where('room_id', '==', room_id)
        docs = query.stream()
        completions = [doc.to_dict() for doc in docs]
        return completions[0] if completions else None
    
    def update_room_completion(self, completion_id, update_data):
        """Update room completion"""
        doc_ref = self.db.collection('room_completions').document(completion_id)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        doc_ref.update(update_data)
        return True

# Global Firebase service instance
firebase_service = FirebaseService()
