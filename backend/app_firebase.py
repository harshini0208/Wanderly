from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime, UTC
import json
from utils import get_currency_from_destination, get_travel_type, get_transportation_options
from firebase_service import firebase_service
from bigquery_service import bigquery_service
from ai_service import AIService

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize BigQuery tables
try:
    bigquery_service.create_tables()
except Exception as e:
    pass

# Initialize AI Service
try:
    ai_service = AIService()
except Exception as e:
    ai_service = None

@app.route('/api/groups/', methods=['POST'])
def create_group():
    """Create a new group"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['group_name', 'destination', 'start_date', 'end_date', 'user_id', 'user_name', 'user_email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create group data
        group_data = {
            'group_name': data['group_name'],
            'destination': data['destination'],
            'from_location': data.get('from_location', ''),
            'start_date': data['start_date'],
            'end_date': data['end_date'],
            'members': [data['user_id']],
            'created_by': data['user_id'],
            'status': 'active'
        }
        
        # Create group in Firebase
        group = firebase_service.create_group(group_data)
        
        # Create user if doesn't exist
        user_data = {
            'id': data['user_id'],
            'name': data['user_name'],
            'email': data['user_email']
        }
        firebase_service.create_user(user_data)
        
        # Insert analytics data
        bigquery_service.insert_group_analytics(group)
        bigquery_service.insert_user_analytics(user_data)
        
        return jsonify(group), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/<group_id>', methods=['GET'])
def get_group(group_id):
    """Get a group by ID"""
    try:
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        return jsonify(group)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<user_id>/groups', methods=['GET'])
def get_user_groups(user_id):
    """Get all groups for a user"""
    try:
        groups = firebase_service.get_user_groups(user_id)
        return jsonify(groups)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/join', methods=['POST'])
def join_group():
    """Join an existing group using invite code (group ID)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['invite_code', 'user_name', 'user_email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        group_id = data['invite_code']  # The invite code is actually the group ID
        
        # Get the group
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Invalid invite code. Group not found.'}), 404
        
        # Generate user ID
        user_id = f"user_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:9]}"
        
        # Create user
        user_data = {
            'id': user_id,
            'name': data['user_name'],
            'email': data['user_email']
        }
        firebase_service.create_user(user_data)
        
        # Add user to group members
        if user_id not in group['members']:
            group['members'].append(user_id)
            firebase_service.update_group(group_id, {'members': group['members']})
        
        # Insert user analytics
        bigquery_service.insert_user_analytics(user_data)
        
        # Return group data with user info
        return jsonify({
            **group,
            'user_id': user_id,
            'user_name': data['user_name'],
            'user_email': data['user_email']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/<group_id>/rooms', methods=['POST'])
def create_rooms_for_group(group_id):
    """Create rooms for a group"""
    try:
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        # Define room types
        room_types = ['accommodation', 'transportation', 'activities', 'dining']
        created_rooms = []
        
        for room_type in room_types:
            room_data = {
                'group_id': group_id,
                'room_type': room_type,
                'status': 'active',
                'is_completed': False
            }
            
            room = firebase_service.create_room(room_data)
            created_rooms.append(room)
            
            # Insert room analytics
            bigquery_service.insert_room_analytics(room)
        
        return jsonify(created_rooms), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/<group_id>/rooms', methods=['GET'])
def get_group_rooms(group_id):
    """Get all rooms for a group"""
    try:
        rooms = firebase_service.get_group_rooms(group_id)
        return jsonify(rooms)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    """Get a room by ID"""
    try:
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        return jsonify(room)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/questions', methods=['POST'])
def create_questions_for_room(room_id):
    """Create questions for a room"""
    try:
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Get group to determine currency and travel type
        group = firebase_service.get_group(room['group_id'])
        destination = group['destination'] if group else 'Unknown'
        from_location = group.get('from_location', '') if group else ''
        
        # Determine currency based on room type - use from_location for all rooms
        room_type = room['room_type']
        currency = get_currency_from_destination(from_location) if from_location else '$'
            
        travel_type = get_travel_type(from_location, destination)
        transportation_options = get_transportation_options(travel_type)
        
        # Define fixed questions for each room type
        fixed_questions = {
            'accommodation': [
                {
                    'question_text': 'What is your accommodation budget range per night?',
                    'question_type': 'range',
                    'min_value': 0,
                    'max_value': 1000,
                    'step': 10,
                    'currency': currency
                },
                {
                    'question_text': 'What type of accommodation do you prefer?',
                    'question_type': 'buttons',
                    'options': ['Hotel', 'Hostel', 'Airbnb', 'Resort', 'Guesthouse', 'No preference']
                },
                {
                    'question_text': 'Any specific accommodation preferences or requirements?',
                    'question_type': 'text',
                    'placeholder': 'e.g., pet-friendly, pool, gym, near city center...'
                }
            ],
            'transportation': [
                {
                    'question_text': 'What is your transportation budget range?',
                    'question_type': 'range',
                    'min_value': 0,
                    'max_value': 2000,
                    'step': 50,
                    'currency': currency
                },
                {
                    'question_text': 'What transportation methods do you prefer?',
                    'question_type': 'buttons',
                    'options': transportation_options
                },
                {
                    'question_text': 'What is your preferred departure date?',
                    'question_type': 'date',
                    'placeholder': 'Select your departure date'
                },
                {
                    'question_text': 'What is your preferred return date? (Leave empty for one-way)',
                    'question_type': 'date',
                    'placeholder': 'Select your return date (optional)'
                },
                {
                    'question_text': 'Any specific transportation preferences?',
                    'question_type': 'text',
                    'placeholder': 'e.g., direct flights only, eco-friendly options, luxury transport...'
                }
            ],
            'activities': [
                {
                    'question_text': 'What is your activities budget range?',
                    'question_type': 'range',
                    'min_value': 0,
                    'max_value': 1500,
                    'step': 25,
                    'currency': currency
                },
                {
                    'question_text': 'What type of activities interest you?',
                    'question_type': 'buttons',
                    'options': ['Cultural', 'Adventure', 'Relaxation', 'Food & Drink', 'Nature', 'Nightlife', 'Mixed']
                },
                {
                    'question_text': 'Any specific activities or experiences you want?',
                    'question_type': 'text',
                    'placeholder': 'e.g., museum visits, hiking trails, cooking classes, local festivals...'
                }
            ],
            'dining': [
                {
                    'question_text': 'What meal type are you interested in?',
                    'question_type': 'buttons',
                    'options': ['Breakfast', 'Lunch', 'Dinner', 'Brunch', 'Snacks']
                },
                {
                    'question_text': 'What dining preferences do you have?',
                    'question_type': 'buttons',
                    'options': ['Fine dining', 'Casual restaurants', 'Street food', 'Local cuisine', 'International', 'Mixed']
                },
                {
                    'question_text': 'Any dietary restrictions or food preferences?',
                    'question_type': 'text',
                    'placeholder': 'e.g., vegetarian, halal, spicy food, seafood allergies...'
                }
            ]
        }
        
        room_type = room['room_type']
        questions_to_create = fixed_questions.get(room_type, [])
        
        created_questions = []
        for question_data in questions_to_create:
            question_data['room_id'] = room_id
            question = firebase_service.create_question(question_data)
            created_questions.append(question)
        
        return jsonify(created_questions), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/questions', methods=['GET'])
def get_room_questions(room_id):
    """Get all questions for a room"""
    try:
        questions = firebase_service.get_room_questions(room_id)
        return jsonify(questions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/answers/', methods=['POST'])
def submit_answer():
    """Submit an answer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['room_id', 'user_id', 'question_id', 'answer_value']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create answer data
        answer_data = {
            'room_id': data['room_id'],
            'user_id': data['user_id'],
            'question_id': data['question_id'],
            'answer_value': data['answer_value'],
            'answer_text': data.get('answer_text'),
            'min_value': data.get('min_value'),
            'max_value': data.get('max_value')
        }
        
        answer = firebase_service.create_answer(answer_data)
        
        # Insert analytics data
        bigquery_service.insert_answer_analytics(answer)
        
        return jsonify(answer), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/answers', methods=['GET'])
def get_room_answers(room_id):
    """Get all answers for a room"""
    try:
        answers = firebase_service.get_room_answers(room_id)
        return jsonify(answers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/answers/<user_id>', methods=['GET'])
def get_user_answers(room_id, user_id):
    """Get answers for a specific user in a room"""
    try:
        answers = firebase_service.get_user_answers(room_id, user_id)
        return jsonify(answers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions/', methods=['POST'])
def generate_suggestions():
    """Generate AI suggestions for a room"""
    try:
        data = request.get_json()
        room_id = data.get('room_id')
        
        if not room_id:
            return jsonify({'error': 'Missing room_id'}), 400
        
        # Get room and answers
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        answers = firebase_service.get_room_answers(room_id)
        
        # Get group information for context
        group_id = room.get('group_id')
        group = None
        if group_id:
            group = firebase_service.get_group(group_id)
        
        # Generate AI suggestions if AI service is available
        if ai_service and group:
            try:
                destination = group.get('destination', 'Unknown')
                room_type = room['room_type']
                
                
                # Prepare group preferences
                group_preferences = {
                    'start_date': group.get('start_date'),
                    'end_date': group.get('end_date'),
                    'group_size': group.get('group_size'),
                    'from_location': group.get('from_location', '')
                }
                
                # Generate AI suggestions
                ai_suggestions = ai_service.generate_suggestions(
                    room_type=room_type,
                    destination=destination,
                    answers=answers,
                    group_preferences=group_preferences
                )
                
                
                # Create suggestions in Firebase
                created_suggestions = []
                for suggestion_data in ai_suggestions:
                    suggestion_data['room_id'] = room_id
                    suggestion_data['created_at'] = datetime.now(UTC).isoformat()
                    suggestion = firebase_service.create_suggestion(suggestion_data)
                    created_suggestions.append(suggestion)
                
                return jsonify(created_suggestions), 201
                
            except Exception as ai_error:
                # Fall back to basic suggestions if AI fails
                pass
        else:
            if not ai_service:
                pass
            if not group:
                pass
        
        # No fallback - AI service is required
        return jsonify({
            'error': 'AI service not available. Please configure your API keys to generate suggestions.',
            'setup_required': True,
            'instructions': {
                'gemini_api': 'Get your Gemini API key from: https://makersuite.google.com/app/apikey',
                'maps_api': 'Get your Google Maps API key from: https://console.cloud.google.com/google/maps-apis',
                'env_file': 'Update your .env file with the actual API keys and restart the server'
            }
        }), 503
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/suggestions', methods=['GET'])
def get_room_suggestions(room_id):
    """Get all suggestions for a room"""
    try:
        suggestions = firebase_service.get_room_suggestions(room_id)
        return jsonify(suggestions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/votes/', methods=['POST'])
def submit_vote():
    """Submit a vote on a suggestion"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['suggestion_id', 'user_id', 'vote_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if user already voted
        existing_vote = firebase_service.get_user_vote(data['suggestion_id'], data['user_id'])
        
        if existing_vote:
            # Update existing vote
            firebase_service.update_vote(existing_vote['id'], {'vote_type': data['vote_type']})
            vote = existing_vote
            vote['vote_type'] = data['vote_type']
        else:
            # Create new vote
            vote_data = {
                'suggestion_id': data['suggestion_id'],
                'user_id': data['user_id'],
                'vote_type': data['vote_type']
            }
            vote = firebase_service.create_vote(vote_data)
        
        # Insert analytics data
        bigquery_service.insert_vote_analytics(vote)
        
        return jsonify(vote), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions/<suggestion_id>/votes', methods=['GET'])
def get_suggestion_votes(suggestion_id):
    """Get all votes for a suggestion"""
    try:
        votes = firebase_service.get_suggestion_votes(suggestion_id)
        return jsonify(votes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/lock', methods=['POST'])
def lock_room_decision(room_id):
    """Lock the final decision for a room"""
    try:
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Get the most voted suggestion
        suggestions = firebase_service.get_room_suggestions(room_id)
        best_suggestion = None
        max_votes = -1
        
        for suggestion in suggestions:
            votes = firebase_service.get_suggestion_votes(suggestion['id'])
            thumbs_up = len([v for v in votes if v['vote_type'] == 'thumbs_up'])
            if thumbs_up > max_votes:
                max_votes = thumbs_up
                best_suggestion = suggestion
        
        if best_suggestion:
            # Update room with locked decision
            firebase_service.update_room(room_id, {
                'locked_suggestion': best_suggestion,
                'is_locked': True,
                'locked_at': datetime.utcnow().isoformat()
            })
            
            return jsonify({
                'message': 'Room decision locked successfully',
                'locked_suggestion': best_suggestion
            })
        else:
            return jsonify({'error': 'No suggestions found to lock'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/voting/room/<room_id>/lock-multiple', methods=['POST'])
def lock_room_decision_multiple(room_id):
    """Lock multiple suggestions as final decisions"""
    try:
        data = request.get_json()
        suggestion_ids = data
        
        if not suggestion_ids or not isinstance(suggestion_ids, list):
            return jsonify({'error': 'Invalid suggestion IDs provided'}), 400
        
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Get the liked suggestions
        liked_suggestions = []
        for suggestion_id in suggestion_ids:
            suggestion = firebase_service.get_suggestion(suggestion_id)
            if suggestion:
                liked_suggestions.append(suggestion)
        
        if not liked_suggestions:
            return jsonify({'error': 'No valid suggestions found to lock'}), 400
        
        # Update room with locked decisions
        firebase_service.update_room(room_id, {
            'locked_suggestions': liked_suggestions,
            'is_locked': True,
            'locked_at': datetime.utcnow().isoformat()
        })
        
        return jsonify({
            'message': f'{len(liked_suggestions)} suggestions locked successfully',
            'locked_suggestions': liked_suggestions
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/complete', methods=['POST'])
def mark_room_complete(room_id):
    """Mark a room as completed"""
    try:
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Update room status
        firebase_service.update_room(room_id, {
            'is_completed': True,
            'completed_at': datetime.utcnow().isoformat()
        })
        
        return jsonify({'message': 'Room marked as completed'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/status', methods=['GET'])
def get_room_status(room_id):
    """Get room completion status"""
    try:
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        return jsonify({
            'is_completed': room.get('is_completed', False),
            'is_locked': room.get('is_locked', False),
            'completed_at': room.get('completed_at'),
            'locked_at': room.get('locked_at')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Analytics endpoints
@app.route('/api/analytics/popular-destinations', methods=['GET'])
def get_popular_destinations():
    """Get popular destinations analytics"""
    try:
        limit = request.args.get('limit', 10, type=int)
        destinations = bigquery_service.get_popular_destinations(limit)
        return jsonify(destinations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/user-engagement', methods=['GET'])
def get_user_engagement():
    """Get user engagement statistics"""
    try:
        stats = bigquery_service.get_user_engagement_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/room-completion', methods=['GET'])
def get_room_completion_analysis():
    """Get room completion analysis"""
    try:
        analysis = bigquery_service.get_room_completion_analysis()
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'firebase': 'connected',
            'bigquery': 'connected'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
