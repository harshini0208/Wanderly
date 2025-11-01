from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime, UTC
import json
import threading
from utils import get_currency_from_destination, get_travel_type, get_transportation_options
from firebase_service import firebase_service
from booking_service import booking_service
from bigquery_service import bigquery_service
from ai_service import AIService

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='../dist', static_url_path='')

# Configure CORS
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

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
            'total_members': data.get('total_members', 2),  # Include total_members from frontend
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
        
        # Insert analytics data in the background to cut API latency
        def _insert_analytics_async(created_group, created_user):
            try:
                bigquery_service.insert_group_analytics(created_group)
            except Exception:
                pass
            try:
                bigquery_service.insert_user_analytics(created_user)
            except Exception:
                pass

        threading.Thread(target=_insert_analytics_async, args=(group, user_data), daemon=True).start()
        
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

@app.route('/api/groups/<group_id>/members', methods=['GET'])
def get_group_members(group_id):
    """Get all members of a group with their details"""
    try:
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        members = group.get('members', [])
        member_details = []
        
        for user_id in members:
            user = firebase_service.get_user(user_id)
            if user:
                member_details.append({
                    'id': user.get('id'),
                    'name': user.get('name', 'Unknown'),
                    'email': user.get('email', 'Unknown')
                })
            else:
                # If user not found, still include with ID
                member_details.append({
                    'id': user_id,
                    'name': 'Unknown',
                    'email': 'Unknown'
                })
        
        return jsonify({
            'members': member_details,
            'total_count': len(member_details)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/places/autocomplete', methods=['GET'])
def get_places_autocomplete():
    """Get place autocomplete suggestions from Google Places API"""
    try:
        import os
        import requests
        
        query = request.args.get('input', '')
        if not query or len(query) < 2:
            return jsonify({'predictions': []})
        
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            return jsonify({'error': 'Google Maps API key not configured'}), 500
        
        # Call Google Places Autocomplete API
        autocomplete_url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json'
        params = {
            'input': query,
            'key': api_key,
            'types': '(cities)'  # Focus on cities/locations
        }
        
        response = requests.get(autocomplete_url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'OK':
                predictions = []
                for prediction in data.get('predictions', []):
                    predictions.append({
                        'description': prediction.get('description', ''),
                        'place_id': prediction.get('place_id', ''),
                        'main_text': prediction.get('structured_formatting', {}).get('main_text', ''),
                        'secondary_text': prediction.get('structured_formatting', {}).get('secondary_text', '')
                    })
                return jsonify({'predictions': predictions})
            else:
                # If API returns error status, return empty results
                return jsonify({'predictions': []})
        else:
            return jsonify({'error': 'Failed to fetch autocomplete suggestions'}), 500
            
    except Exception as e:
        print(f"Error in places autocomplete: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/<group_id>', methods=['PUT'])
def update_group(group_id):
    """Update group details"""
    try:
        data = request.get_json()
        
        # Validate that at least one field is provided
        if not data:
            return jsonify({'error': 'No update data provided'}), 400
        
        # Get existing group
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        # Update only provided fields (preserve votes and room data)
        update_data = {}
        
        if 'name' in data:
            update_data['name'] = data['name']
        if 'from_location' in data:
            update_data['from_location'] = data['from_location']
        if 'destination' in data:
            update_data['destination'] = data['destination']
        if 'start_date' in data:
            update_data['start_date'] = data['start_date']
        if 'end_date' in data:
            update_data['end_date'] = data['end_date']
        if 'total_members' in data:
            update_data['total_members'] = data['total_members']
        
        # Add last updated timestamp
        update_data['last_updated'] = datetime.now(UTC).isoformat()
        
        # Update group in Firebase
        firebase_service.update_group(group_id, update_data)
        
        return jsonify({
            'success': True,
            'message': 'Group updated successfully',
            'updated_fields': list(update_data.keys())
        })
        
    except Exception as e:
        print(f"Error updating group: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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
        
        # Trim whitespace from invite code (group ID)
        group_id = str(data['invite_code']).strip() if data['invite_code'] else ''
        
        if not group_id:
            return jsonify({'error': 'Invalid invite code. Please enter a valid group code.'}), 400
        
        # Get the group
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({
                'error': f'Invalid invite code. Group not found.',
                'hint': 'Please check the invite code and ensure it matches exactly (including case).'
            }), 404
        
        # Check if group has a member limit set
        total_members = group.get('total_members')
        current_members = group.get('members', [])
        current_count = len(current_members) if isinstance(current_members, list) else 0
        
        # If total_members is set, check if group is full
        if total_members is not None:
            if current_count >= total_members:
                return jsonify({
                    'error': f'Group is full. Maximum members ({total_members}) reached. Cannot join.'
                }), 400
        
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
                    'question_text': 'What kind of dining experiences are you most interested in during this trip?',
                    'question_type': 'buttons',
                    'options': ['Local specialties & authentic food spots', 'Trendy restaurants or fine dining', 'Hidden gems / street food experiences', 'Casual, budget-friendly meals', 'Cafés & brunch spots', 'Bars, pubs, or nightlife dining']
                },
                {
                    'question_text': 'What kind of cuisines or food styles do you want to explore?',
                    'question_type': 'buttons',
                    'options': ['Local cuisine', 'Asian', 'Mediterranean', 'Italian', 'American / Burgers', 'Vegetarian / Vegan', 'Seafood', 'Desserts / Coffee / Bakery', 'Open to anything']
                },
                {
                    'question_text': 'Do you have any dietary needs or food preferences?',
                    'question_type': 'text',
                    'placeholder': 'Type your dietary needs or preferences. Type "No restrictions" if none.'
                }
            ]
        }
        
        room_type = room['room_type']
        questions_to_create = fixed_questions.get(room_type, [])
        
        # For dining room, delete old format questions first
        if room_type == 'dining':
            existing_questions = firebase_service.get_room_questions(room_id)
            old_format_questions = [q for q in existing_questions if 
                q.get('question_text') in [
                    'What meal type are you interested in?',
                    'What dining preferences do you have?',
                    'Any dietary restrictions or food preferences?',
                    'Are there any "must-do" food experiences for this group?'
                ]]
            if old_format_questions:
                # Delete old format questions
                for old_q in old_format_questions:
                    try:
                        firebase_service.db.collection('questions').document(old_q.get('id')).delete()
                    except Exception:
                        pass
        
        created_questions = []
        for index, question_data in enumerate(questions_to_create):
            question_data['room_id'] = room_id
            question_data['order'] = index  # Add order field to ensure consistent ordering
            question = firebase_service.create_question(question_data)
            created_questions.append(question)
        
        # Sort by order before returning
        created_questions.sort(key=lambda q: q.get('order', 999))
        return jsonify(created_questions), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/questions', methods=['GET'])
def get_room_questions(room_id):
    """Get all questions for a room"""
    try:
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        questions = firebase_service.get_room_questions(room_id)
        
        # For dining room, filter out old format questions
        if room.get('room_type') == 'dining':
            old_format_texts = [
                'What meal type are you interested in?',
                'What dining preferences do you have?',
                'Any dietary restrictions or food preferences?',
                'Are there any "must-do" food experiences for this group?'
            ]
            questions = [q for q in questions if q.get('question_text') not in old_format_texts]
        
        # STRICT deduplication: Remove duplicates by question_text first, then by ID
        seen_texts = set()
        seen_ids = set()
        unique_questions = []
        for q in questions:
            text = (q.get('question_text') or '').strip().lower()
            q_id = q.get('id') or ''
            
            # Skip if we've seen this text or ID before
            if text in seen_texts or (q_id and q_id in seen_ids):
                continue
            
            seen_texts.add(text)
            if q_id:
                seen_ids.add(q_id)
            unique_questions.append(q)
        
        questions = unique_questions
        
        # Sort by order field (default to 999 if order is missing for backwards compatibility)
        questions.sort(key=lambda q: q.get('order', 999))
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

@app.route('/api/rooms/<room_id>/top-preferences', methods=['GET'])
def get_room_top_preferences(room_id):
    """Compute top preferences for a room based on HEART/UP votes on suggestions.
    No AI used. Returns:
      {
        room_id,
        room_type,
        top_preferences: [ { suggestion_id, name, count } ],
        counts_by_suggestion: { suggestion_id: count },
        total_members
      }
    """
    try:
        # Fetch room and group for sizing logic
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        group_id = room.get('group_id')
        group = firebase_service.get_group(group_id) if group_id else None
        total_members = group.get('total_members', 0) if group else 0

        # Get all suggestions for the room
        suggestions = firebase_service.get_room_suggestions(room_id) or []

        # Count HEART/UP votes per suggestion
        counts_by_suggestion = {}
        for s in suggestions:
            sid = s.get('id')
            if not sid:
                continue
            try:
                votes = firebase_service.get_suggestion_votes(sid) or []
            except Exception:
                votes = []
            count_up = sum(1 for v in votes if str(v.get('vote_type')).lower() in ['up', 'heart', 'like'])
            counts_by_suggestion[sid] = count_up

        # Build ranked list
        ranked = []
        for s in suggestions:
            sid = s.get('id')
            if not sid:
                continue
            ranked.append({
                'suggestion_id': sid,
                'name': s.get('name') or s.get('title') or 'Option',
                'count': counts_by_suggestion.get(sid, 0)
            })

        ranked.sort(key=lambda x: x['count'], reverse=True)

        # Determine how many to show: small groups top 2, larger groups top 3
        top_k = 2 if total_members and total_members <= 5 else 3
        top_preferences = ranked[:top_k]

        return jsonify({
            'room_id': room_id,
            'room_type': room.get('room_type'),
            'top_preferences': top_preferences,
            'counts_by_suggestion': counts_by_suggestion,
            'total_members': total_members
        })
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
                
                print(f"\n🎯 API GENERATE SUGGESTIONS:")
                print(f"   Room Type: {room_type}")
                print(f"   Destination from group: '{destination}'")
                print(f"   Group data: {group}")
                
                # Prepare group preferences
                group_preferences = {
                    'start_date': group.get('start_date'),
                    'end_date': group.get('end_date'),
                    'group_size': group.get('group_size'),
                    'from_location': group.get('from_location', '')
                }
                
                # Generate AI suggestions
                print(f"   Calling ai_service.generate_suggestions(room_type='{room_type}', destination='{destination}')")
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
                
                # Standardized response format: always return array directly
                # Frontend expects: Array<Suggestion>
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

@app.route('/api/destinations/<destination>/fun-facts', methods=['GET'])
def get_destination_fun_facts(destination):
    """Get fun facts about a destination using AI"""
    try:
        if not ai_service:
            # Return some generic fun facts if AI service is unavailable
            return jsonify({
                'destination': destination,
                'facts': [
                    f"{destination} is a beautiful destination with rich culture and history.",
                    f"Travelers love exploring the local cuisine and hidden gems in {destination}.",
                    f"{destination} offers unique experiences that create lasting memories."
                ]
            })
        
        # Use AI to generate fun facts
        prompt = f"""Generate 5 interesting, fun, and engaging facts about {destination}. 
Make them:
- Interesting and surprising
- Travel-focused and useful for tourists
- Positive and exciting
- Concise (one sentence each)
- Unique to {destination}

Return ONLY a JSON array of facts, no additional text:
["fact 1", "fact 2", "fact 3", "fact 4", "fact 5"]"""

        try:
            response = ai_service.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            # Parse JSON response
            import json
            facts = json.loads(response_text)
            
            if isinstance(facts, list) and len(facts) > 0:
                return jsonify({
                    'destination': destination,
                    'facts': facts[:5]  # Limit to 5 facts
                })
        except Exception as ai_error:
            print(f"AI error generating fun facts: {ai_error}")
        
        # Fallback facts if AI fails
        return jsonify({
            'destination': destination,
            'facts': [
                f"{destination} is known for its unique culture and welcoming locals.",
                f"Many travelers discover hidden gems and amazing experiences in {destination}.",
                f"{destination} offers diverse attractions that cater to all types of travelers.",
                f"The local cuisine in {destination} is a must-try for food enthusiasts.",
                f"{destination} has beautiful landscapes and scenic spots perfect for memories."
            ]
        })
        
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

@app.route('/api/groups/<group_id>/update-total-members', methods=['POST'])
def update_group_total_members(group_id):
    """Update an existing group with total_members field"""
    try:
        data = request.get_json()
        total_members = data.get('total_members')
        
        if not total_members:
            return jsonify({'error': 'total_members is required'}), 400
        
        # Get the group
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        # Update the group with total_members
        firebase_service.update_group(group_id, {'total_members': total_members})
        
        return jsonify({
            'success': True,
            'message': 'Group total_members updated successfully',
            'total_members': total_members
        })
        
    except Exception as e:
        print(f"Error updating group total_members: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/flights/search', methods=['POST'])
def search_flights():
    """Search for flights using AI service"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['origin', 'destination', 'departure_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        origin = data['origin']
        destination = data['destination']
        departure_date = data['departure_date']
        return_date = data.get('return_date')
        passengers = data.get('passengers', 1)
        class_type = data.get('class_type', 'Economy')
        
        # Search flights using AI service
        flight_results = ai_service.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            class_type=class_type
        )
        
        return jsonify(flight_results)
        
    except Exception as e:
        print(f"Error searching flights: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/rooms/<room_id>/save-selections', methods=['POST'])
def save_room_selections(room_id):
    """Save user's selected suggestions for a room"""
    try:
        data = request.get_json()
        print(f"DEBUG: Received data for room {room_id}: {data}")
        
        selections = data.get('selections', [])
        print(f"DEBUG: Selections array: {selections}")
        print(f"DEBUG: Selections length: {len(selections)}")
        
        if not selections:
            print("DEBUG: No selections provided - returning 400")
            return jsonify({'error': 'No selections provided'}), 400
        
        # Get the room
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Save selections to room
        firebase_service.update_room(room_id, {
            'user_selections': selections,
            'last_updated': datetime.now(UTC).isoformat()
        })
        
        return jsonify({
            'success': True,
            'message': 'Selections saved successfully',
            'selections_count': len(selections)
        })
        
    except Exception as e:
        print(f"Error saving room selections: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/rooms/<room_id>/mark-completed', methods=['POST'])
def mark_room_completed(room_id):
    """Mark a room as completed by a specific user"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        
        if not user_email:
            return jsonify({'error': 'User email is required'}), 400
        
        # Get the room
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Initialize completed_by array if it doesn't exist
        if 'completed_by' not in room:
            room['completed_by'] = []
        
        # Add user email to completed_by if not already present
        if user_email not in room['completed_by']:
            room['completed_by'].append(user_email)
            
            # Update the room in Firebase
            firebase_service.update_room(room_id, {'completed_by': room['completed_by']})
            
            return jsonify({
                'success': True,
                'message': 'Room marked as completed',
                'completed_count': len(room['completed_by'])
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Room already marked as completed by this user',
                'completed_count': len(room['completed_by'])
            })
            
    except Exception as e:
        print(f"Error marking room as completed: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/rooms/<room_id>/clear-data', methods=['POST'])
def clear_room_data(room_id):
    """Clear all voting and suggestion data for a room"""
    try:
        # Get the room
        room = firebase_service.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Clear all answers, suggestions, and votes for this room
        update_data = {
            'answers': [],
            'user_selections': [],
            'completed_by': [],
            'last_updated': datetime.now(UTC).isoformat()
        }
        
        firebase_service.update_room(room_id, update_data)
        
        # Also delete any suggestions associated with this room from the suggestions collection
        # (This would need additional Firebase queries, but for now we'll just reset room state)
        
        return jsonify({
            'success': True,
            'message': 'Room data cleared successfully'
        })
        
    except Exception as e:
        print(f"Error clearing room data: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Booking endpoints
@app.route('/api/bookings/', methods=['POST'])
def create_booking():
    """Create a new booking for selected trip options"""
    try:
        data = request.get_json()
        
        required_fields = ['group_id', 'user_id', 'selections']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Prepare booking data
        booking_data = {
            'group_id': data['group_id'],
            'user_id': data['user_id'],
            'selections': data['selections'],
            'total_amount': data.get('total_amount', 0),
            'currency': data.get('currency', '₹'),
            'booking_status': 'pending',
            'trip_dates': data.get('trip_dates', {}),
            'customer_details': data.get('customer_details', {})
        }
        
        result = booking_service.create_booking(booking_data)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/user/<user_id>', methods=['GET'])
def get_user_bookings(user_id):
    """Get all bookings for a user"""
    try:
        bookings = booking_service.get_user_bookings(user_id)
        return jsonify(bookings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/group/<group_id>', methods=['GET'])
def get_group_bookings(group_id):
    """Get all bookings for a group"""
    try:
        bookings = booking_service.get_group_bookings(group_id)
        return jsonify(bookings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/<booking_id>/status', methods=['PUT'])
def update_booking_status(booking_id):
    """Update booking status"""
    try:
        data = request.get_json()
        status = data.get('status')
        payment_status = data.get('payment_status')
        
        result = booking_service.update_booking_status(booking_id, status, payment_status)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/')
def index():
    return 'Backend is running successfully!'
    
@app.route('/api/groups/<group_id>/consolidate-preferences', methods=['POST'])
def consolidate_group_preferences(group_id):
    """Use AI to analyze all member selections and find common preferences"""
    try:
        # Get group
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        # Get all rooms
        rooms = firebase_service.get_group_rooms(group_id)
        
        # Collect all selections from all members for all rooms
        all_selections_by_room = {}
        
        for room in rooms:
            selections = room.get('user_selections', [])
            if selections:
                # Get the original suggestions to analyze preferences
                room_suggestions = firebase_service.get_room_suggestions(room['id'])
                
                # Analyze preferences from selected suggestions
                all_selections_by_room[room['room_type']] = {
                    'selections': selections,
                    'suggestions': room_suggestions,
                    'room_type': room['room_type']
                }
        
        if not all_selections_by_room:
            return jsonify({'error': 'No selections found to consolidate'}), 400
        
        # Use AI to find common preferences
        if ai_service and ai_service.model:
            # Prepare data for AI analysis
            prompt = f"""Analyze all member selections from a travel planning group and identify the most suitable consolidated options that match common preferences.

GROUP INFO:
- Destination: {group.get('destination', 'Unknown')}
- Members: {group.get('total_members', 2)} people

MEMBER SELECTIONS BY CATEGORY:

"""
            
            # Add selections for each category
            for room_type, data in all_selections_by_room.items():
                selections = data.get('selections', [])
                if selections:
                    prompt += f"""
{room_type.upper()} SELECTIONS:
"""
                    for i, selection in enumerate(selections, 1):
                        selection_str = f"""
  Selection {i}:
    Name: {selection.get('name', selection.get('title', 'N/A'))}
    Description: {selection.get('description', 'N/A')[:100]}
    Price: {selection.get('price', selection.get('price_range', 'N/A'))}
    Rating: {selection.get('rating', 'N/A')}
"""
                        prompt += selection_str
            
            prompt += """
TASK:
1. Analyze all selections to identify COMMON PREFERENCES across members
2. Consider: price range, location preferences, features, quality (rating), type
3. Select the BEST OPTIONS that match these common preferences
4. Limit to 3-5 most suitable options per category (not all selections)

Return JSON format:
{
  "consolidated_selections": {
    "room_type": [
      {
        "name": "Option name",
        "why_selected": "Reason based on common preferences",
        "matches_preferences": ["preference1", "preference2"],
        "price": 1000,
        "rating": 4.5
      }
    ]
  },
  "common_preferences": {
    "budget_range": "description",
    "location_preferences": ["list"],
    "quality_expectations": "description"
  },
  "recommendation": "Brief summary of the consolidated plan"
}

Generate the consolidated recommendations now."""

            response = ai_service.model.generate_content(prompt)
            
            if response and response.text:
                # Parse AI response
                import json
                import re
                
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    consolidated_data = json.loads(json_match.group())
                    return jsonify(consolidated_data), 200
        
        # Fallback: return existing selections without AI consolidation
        fallback_data = {
            'consolidated_selections': {
                room_type: [selection.get('name', 'Selection') for selection in data['selections']]
                for room_type, data in all_selections_by_room.items()
            },
            'message': 'AI consolidation not available - showing all selections'
        }
        return jsonify(fallback_data), 200
        
    except Exception as e:
        print(f"Error consolidating preferences: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve the React frontend"""
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
