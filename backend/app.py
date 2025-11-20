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
from services import (
    AccommodationService,
    TransportationService,
    DiningService,
    ActivitiesService,
)

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='../dist', static_url_path='')

# Configure CORS - Allow all origins for API endpoints
# Using a more permissive configuration that works with Vercel and local development
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Allow all origins (including Vercel preview deployments)
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": False,
        "expose_headers": ["Content-Type"],
        "max_age": 3600
    }
}, 
automatic_options=True)

# Initialize BigQuery tables
try:
    bigquery_service.create_tables()
except Exception as e:
    pass

# Initialize AI Service
ai_service = None
ai_service_error = None
try:
    # Check environment variables first
    gemini_key = os.getenv('GEMINI_API_KEY')
    maps_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    print(f"\n🔍 AI Service Initialization Check:")
    print(f"   GEMINI_API_KEY: {'SET' if gemini_key else 'NOT SET'}")
    print(f"   GOOGLE_MAPS_API_KEY: {'SET' if maps_key else 'NOT SET'}")
    
    if gemini_key:
        print(f"   GEMINI_API_KEY length: {len(gemini_key)} characters")
        print(f"   GEMINI_API_KEY starts with: {gemini_key[:10]}..." if len(gemini_key) > 10 else "")
    if maps_key:
        print(f"   GOOGLE_MAPS_API_KEY length: {len(maps_key)} characters")
    
    if not gemini_key:
        ai_service_error = "GEMINI_API_KEY environment variable is not set"
        print(f"❌ {ai_service_error}")
    elif not maps_key:
        ai_service_error = "GOOGLE_MAPS_API_KEY environment variable is not set"
        print(f"❌ {ai_service_error}")
    else:
        ai_service = AIService()
        print("✅ AI Service initialized successfully")
except ValueError as e:
    ai_service_error = str(e)
    print(f"❌ AI Service initialization failed: {ai_service_error}")
except Exception as e:
    ai_service_error = str(e)
    print(f"❌ AI Service initialization failed with unexpected error: {ai_service_error}")
    import traceback
    print(f"   Traceback: {traceback.format_exc()}")

room_service_registry = {
    'accommodation': AccommodationService(ai_service=ai_service),
    'transportation': TransportationService(ai_service=ai_service),
    'dining': DiningService(ai_service=ai_service),
    'activities': ActivitiesService(ai_service=ai_service),
}


def get_room_service_by_type(room_type: str):
    service = room_service_registry.get(room_type)
    if not service:
        raise ValueError(f"Unsupported room type: {room_type}")
    return service


def get_room_service_for_room(room_id: str):
    room = firebase_service.get_room(room_id)
    if not room:
        raise ValueError("Room not found")
    service = get_room_service_by_type(room.get('room_type'))
    return service, room

@app.route('/api/groups', methods=['POST'])
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
        
        # Check if user with same email already exists in group (allow rejoin)
        user_email = data['user_email'].strip().lower()
        current_members = group.get('members', [])
        existing_user_id = None
        
        # Check all existing members to see if email matches
        for member_user_id in current_members:
            try:
                member_user = firebase_service.get_user(member_user_id)
                if member_user:
                    member_email = (member_user.get('email') or '').strip().lower()
                    if member_email == user_email:
                        # User with same email already exists - allow rejoin
                        existing_user_id = member_user_id
                        print(f"User with email {user_email} already in group. Allowing rejoin with existing user_id: {existing_user_id}")
                        break
            except Exception as e:
                # If user lookup fails, continue checking other members
                print(f"Error checking member {member_user_id}: {e}")
                continue
        
        # If user already exists, return their existing data (don't check group capacity)
        if existing_user_id:
            # Update user name in case it changed
            firebase_service.update_user(existing_user_id, {'name': data['user_name']})
            
            # Return group data with existing user info
            return jsonify({
                **group,
                'user_id': existing_user_id,
                'user_name': data['user_name'],
                'user_email': data['user_email'],
                'rejoined': True,
                'message': 'Welcome back! Rejoined successfully.'
            }), 200
        
        # User doesn't exist - check group capacity before adding new member
        total_members = group.get('total_members')
        current_count = len(current_members) if isinstance(current_members, list) else 0
        
        # If total_members is set, check if group is full
        if total_members is not None:
            if current_count >= total_members:
                return jsonify({
                    'error': f'Group is full. Maximum members ({total_members}) reached. Cannot join.'
                }), 400
        
        # Generate new user ID
        user_id = f"user_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:9]}"
        
        # Create user
        user_data = {
            'id': user_id,
            'name': data['user_name'],
            'email': data['user_email']
        }
        firebase_service.create_user(user_data)
        
        # Add user to group members
        if user_id not in current_members:
            current_members.append(user_id)
            firebase_service.update_group(group_id, {'members': current_members})
        
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
        service, _ = get_room_service_for_room(room_id)
        questions = service.create_questions(room_id)
        return jsonify(questions), 201
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/questions', methods=['GET'])
def get_room_questions(room_id):
    """Get all questions for a room"""
    try:
        service, _ = get_room_service_for_room(room_id)
        questions = service.get_questions(room_id)
        return jsonify(questions)
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/questions/trip-type', methods=['POST'])
def get_trip_type_questions(room_id):
    """Get additional questions based on trip type (one-way or return)"""
    try:
        data = request.get_json()
        trip_type = data.get('trip_type', '').lower()
        
        if trip_type not in ['one way', 'return', 'oneway', 'one-way']:
            return jsonify({'error': 'Invalid trip type. Must be "one way" or "return"'}), 400
        
        service, room = get_room_service_for_room(room_id)
        
        # Check if this is a transportation service
        if not hasattr(service, 'get_questions_for_trip_type'):
            return jsonify({'error': 'This endpoint is only available for transportation rooms'}), 400
        
        # Get group for currency and location info
        group_id = room.get('group_id')
        group = firebase_service.get_group(group_id) if group_id else {}
        currency = get_currency_from_destination(group.get('from_location', ''))
        from_location = group.get('from_location', '')
        destination = group.get('destination', '')
        
        # Normalize trip type
        normalized_trip_type = 'return' if trip_type in ['return'] else 'one way'
        
        # Get questions for the trip type
        questions = service.get_questions_for_trip_type(
            trip_type=normalized_trip_type,
            currency=currency,
            from_location=from_location,
            destination=destination
        )
        
        return jsonify(questions), 200
        
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
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
        
        service, _ = get_room_service_for_room(data['room_id'])
        answer = service.submit_answer(data['room_id'], answer_data)
        
        return jsonify(answer), 201
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/answers', methods=['GET'])
def get_room_answers(room_id):
    """Get all answers for a room"""
    try:
        service, _ = get_room_service_for_room(room_id)
        answers = service.get_answers(room_id)
        return jsonify(answers)
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/answers/<user_id>', methods=['GET'])
def get_user_answers(room_id, user_id):
    """Get answers for a specific user in a room"""
    try:
        service, _ = get_room_service_for_room(room_id)
        answers = service.get_answers(room_id, user_id=user_id)
        return jsonify(answers)
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
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

@app.route('/api/groups/<group_id>/batch-preferences', methods=['GET'])
def get_batch_preferences(group_id):
    """Batch top-preference lookup for all rooms within a group"""
    try:
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        rooms = firebase_service.get_group_rooms(group_id) or []
        total_members = group.get('total_members', 0)
        results = {}
        
        for room in rooms:
            room_id = room.get('id')
            if not room_id:
                continue
            try:
                suggestions = firebase_service.get_room_suggestions(room_id) or []
                counts_by_suggestion = {}
                for suggestion in suggestions:
                    sid = suggestion.get('id')
                    if not sid:
                        continue
                    try:
                        votes = firebase_service.get_suggestion_votes(sid) or []
                    except Exception:
                        votes = []
                    counts_by_suggestion[sid] = sum(
                        1 for vote in votes
                        if str(vote.get('vote_type', '')).lower() in ['up', 'heart', 'like']
                    )
                
                ranked = [
                    {
                        'suggestion_id': s.get('id'),
                        'name': s.get('name') or s.get('title') or 'Option',
                        'count': counts_by_suggestion.get(s.get('id'), 0)
                    }
                    for s in suggestions
                    if s.get('id')
                ]
                ranked.sort(key=lambda x: x['count'], reverse=True)
                top_k = 2 if total_members and total_members <= 5 else 3
                
                results[room_id] = {
                    'room_id': room_id,
                    'room_type': room.get('room_type'),
                    'top_preferences': ranked[:top_k],
                    'counts_by_suggestion': counts_by_suggestion,
                    'total_members': total_members
                }
            except Exception:
                results[room_id] = {
                    'room_id': room_id,
                    'room_type': room.get('room_type'),
                    'top_preferences': [],
                    'counts_by_suggestion': {},
                    'total_members': total_members
                }
        
        return jsonify(results)
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
        
        service, _ = get_room_service_for_room(room_id)
        answers = firebase_service.get_room_answers(room_id)
        
        if not ai_service:
            error_message = 'AI service not available. Please configure your API keys to generate suggestions.'
            if ai_service_error:
                error_message += f' Error: {ai_service_error}'
            return jsonify({
                'error': error_message,
                'setup_required': True,
                'details': ai_service_error if ai_service_error else 'AI service failed to initialize',
                'instructions': {
                    'gemini_api': 'Get your Gemini API key from: https://makersuite.google.com/app/apikey',
                    'maps_api': 'Get your Google Maps API key from: https://console.cloud.google.com/google/maps-apis',
                    'vercel': 'Set environment variables in Vercel Dashboard → Settings → Environment Variables',
                    'gcloud': 'Set environment variables in Google Cloud Run → Edit Service → Variables & Secrets',
                    'diagnostics': 'Check /api/diagnostics/env-check endpoint to verify environment variables'
                }
            }), 503
        
        try:
            suggestions_payload = service.generate_suggestions(room_id, answers)
        except Exception as ai_error:
            import traceback
            from google.api_core import exceptions as google_exceptions
            
            error_details = {
                'error': str(ai_error),
                'traceback': traceback.format_exc()
            }
            print(f"❌ Error generating AI suggestions: {error_details['error']}")
            print(f"Traceback: {error_details['traceback']}")
            
            error_str = str(ai_error)
            if isinstance(ai_error, google_exceptions.ServiceUnavailable) or 'ServiceUnavailable' in error_str or '503' in error_str:
                return jsonify({
                    'error': 'AI service temporarily unavailable',
                    'details': 'The Google Gemini API is currently experiencing issues. Please try again in a few moments.',
                    'retry_recommended': True,
                    'error_type': 'temporary_api_issue'
                }), 503
            
            return jsonify({
                'error': f'Failed to generate suggestions: {str(ai_error)}',
                'details': 'Please try again. If the issue persists, check your API key configuration.',
                'retry_recommended': True,
                'error_type': 'api_error'
            }), 500
        
        created_suggestions = []
        for suggestion_data in suggestions_payload:
            suggestion_data['room_id'] = room_id
            suggestion_data['created_at'] = datetime.now(UTC).isoformat()
            suggestion = firebase_service.create_suggestion(suggestion_data)
            created_suggestions.append(suggestion)
        
        return jsonify(created_suggestions), 201
        
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(UTC).isoformat(),
        'service': 'wanderly-backend'
    }), 200

@app.route('/api/diagnostics/env-check', methods=['GET'])
def check_environment_variables():
    """Diagnostic endpoint to check environment variables"""
    try:
        gemini_key = os.getenv('GEMINI_API_KEY')
        maps_key = os.getenv('GOOGLE_MAPS_API_KEY')
        
        # Check if keys exist (without revealing the actual key values)
        gemini_set = bool(gemini_key)
        maps_set = bool(maps_key)
        
        return jsonify({
            'gemini_api_key_set': gemini_set,
            'google_maps_api_key_set': maps_set,
            'gemini_key_length': len(gemini_key) if gemini_key else 0,
            'maps_key_length': len(maps_key) if maps_key else 0,
            'ai_service_initialized': ai_service is not None,
            'ai_service_error': ai_service_error,
            'environment': os.getenv('ENVIRONMENT', 'unknown'),
            'python_path': os.getenv('PATH', 'not_set')[:50] + '...' if len(os.getenv('PATH', '')) > 50 else os.getenv('PATH', 'not_set')
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/diagnostics/ai-test', methods=['GET'])
def test_ai_service():
    """Test AI service configuration"""
    try:
        if not ai_service:
            return jsonify({'error': 'AI service not initialized', 'details': ai_service_error}), 500
        
        # Try a simple AI call
        test_prompt = "Say 'hello'"
        response = ai_service.model.generate_content(test_prompt)
        
        return jsonify({
            'status': 'ok',
            'test_response': response.text,
            'gemini_configured': bool(ai_service.gemini_api_key),
            'maps_configured': bool(ai_service.maps_api_key)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

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
        service, _ = get_room_service_for_room(room_id)
        firebase_service.update_room(room_id, {
            'is_completed': True,
            'completed_at': datetime.utcnow().isoformat()
        })
        return jsonify({'message': 'Room marked as completed'})
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/status', methods=['GET'])
def get_room_status(room_id):
    """Get room completion status"""
    try:
        service, _ = get_room_service_for_room(room_id)
        status_data = service.get_room_status(room_id)
        return jsonify(status_data)
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
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
    """Save user's selected suggestions for a room - merges with existing selections from all members"""
    try:
        data = request.get_json()
        print(f"DEBUG: Received data for room {room_id}: {data}")
        
        new_selections = data.get('selections', [])
        print(f"DEBUG: New selections array: {new_selections}")
        print(f"DEBUG: New selections length: {len(new_selections)}")
        
        if not new_selections:
            print("DEBUG: No selections provided - returning 400")
            return jsonify({'error': 'No selections provided'}), 400
        
        service, _ = get_room_service_for_room(room_id)
        result = service.save_room_selections(room_id, new_selections)
        result.update({'message': 'Selections saved successfully'})
        return jsonify(result)
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
    except Exception as e:
        print(f"Error saving room selections: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/rooms/<room_id>/mark-completed', methods=['POST'])
def mark_room_completed(room_id):
    """Mark a room as completed by a specific user"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        
        if not user_email:
            return jsonify({'error': 'User email is required'}), 400
        
        service, _ = get_room_service_for_room(room_id)
        result = service.mark_room_complete(room_id, user_email)
        message = 'Room already marked as completed by this user' if result.get('already_completed') else 'Room marked as completed'
        return jsonify({
            'success': True,
            'message': message,
            'completed_count': result.get('completed_count', 0)
        })
    except ValueError as e:
        message = str(e)
        status = 404 if "not found" in message.lower() else 400
        return jsonify({'error': message}), status
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

@app.route('/api/groups/<group_id>/consolidate-preferences', methods=['POST'])
def consolidate_group_preferences(group_id):
    """Use AI to intelligently analyze all member selections and find common preferences with conflict resolution"""
    try:
        # Get group
        group = firebase_service.get_group(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        total_members = group.get('total_members', 2)
        destination = group.get('destination', 'Unknown')
        
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
        
        # Calculate optimal number of preferences per category
        def calculate_optimal_count(room_type, group_size, selection_count):
            """Calculate how many consolidated options to show"""
            # Base count by group size
            if group_size <= 3:
                base = 2
            elif group_size <= 6:
                base = 3
            else:
                base = 4
            
            # Category multipliers
            multipliers = {
                'accommodation': 1.0,  # Usually 1-2 options
                'transportation': 0.7,  # Usually 1-2 options
                'dining': 1.3,  # More variety needed
                'activities': 1.5  # Most variety needed
            }
            
            multiplier = multipliers.get(room_type, 1.0)
            optimal = max(2, min(int(base * multiplier), selection_count))
            return optimal
        
        # Use AI to find common preferences
        if ai_service and ai_service.model:
            # Prepare data for AI analysis
            prompt = f"""You are an expert travel planner analyzing group preferences to find the BEST consolidated options that work for everyone.

GROUP CONTEXT:
- Destination: {destination}
- Total Members: {total_members} people
- Travel Dates: {group.get('start_date', 'Not specified')} to {group.get('end_date', 'Not specified')}

MEMBER SELECTIONS BY CATEGORY:

"""
            
            # Add selections for each category with full details
            room_type_counts = {}
            for room_type, data in all_selections_by_room.items():
                selections = data.get('selections', [])
                if selections:
                    optimal_count = calculate_optimal_count(room_type, total_members, len(selections))
                    room_type_counts[room_type] = optimal_count
                    
                    prompt += f"""
{room_type.upper()} SELECTIONS ({len(selections)} total, select {optimal_count} best):
"""
                    for i, selection in enumerate(selections, 1):
                        name = selection.get('name') or selection.get('title') or 'N/A'
                        desc = selection.get('description', 'N/A')
                        price = selection.get('price') or selection.get('price_range', 'N/A')
                        rating = selection.get('rating', 'N/A')
                        features = selection.get('features', [])
                        highlights = selection.get('highlights', [])
                        
                        prompt += f"""
  Selection {i}: {name}
    Description: {desc[:150] if len(desc) > 150 else desc}
    Price: {price}
    Rating: {rating}/5
    Features: {', '.join(features) if features else 'N/A'}
    Highlights: {', '.join(highlights) if highlights else 'N/A'}
"""
            
            prompt += f"""

CRITICAL TASK - INTELLIGENT CONSOLIDATION:

1. **Identify Common Preferences**: Analyze all selections to find patterns, themes, and commonalities
   - Budget ranges (find overlap or compromise)
   - Location preferences (nearby areas, accessibility)
   - Activity types (adventure, cultural, spiritual, relaxation, etc.)
   - Quality expectations (ratings, amenities)

2. **Handle Conflicts Intelligently**:
   - If preferences conflict (e.g., adventurous vs spiritual), use these strategies:
     a) Find options that satisfy MULTIPLE preferences simultaneously (e.g., "mountain temple trek" = adventure + spiritual)
     b) If no overlap exists, create a BALANCED MIX that represents all preferences proportionally
     c) Prioritize options with highest consensus/vote counts
   
3. **Select Optimal Options**: Choose exactly the number specified per category:
"""
            for room_type, count in room_type_counts.items():
                prompt += f"   - {room_type}: {count} options\n"
            
            prompt += """
4. **Quality Criteria**: Prioritize options that:
   - Have good ratings (4.0+ preferred)
   - Fit within budget consensus
   - Are accessible and practical
   - Represent group consensus

Return ONLY valid JSON (no markdown, no code blocks):
{
  "consolidated_selections": {
    "accommodation": [
      {{
        "name": "Exact name from selections",
        "why_selected": "Clear explanation of why this option was chosen and how it addresses group preferences",
        "matches_preferences": ["preference1", "preference2"],
        "conflict_resolution": "How this handles conflicting preferences (if applicable)",
        "price": "price or price_range",
        "rating": 4.5
      }}
    ],
    "transportation": [...],
    "dining": [...],
    "activities": [...]
  },
  "common_preferences": {{
    "budget_range": "Consolidated budget description",
    "location_preferences": ["common location themes"],
    "activity_types": ["common activity types identified"],
    "quality_expectations": "Consolidated quality/rating expectations"
  }},
  "conflict_resolution_summary": {{
    "conflicts_identified": ["list of conflicting preferences found"],
    "resolution_strategy": "How conflicts were resolved (overlap, balanced mix, compromise)",
    "explanation": "Brief explanation of the approach"
  }},
  "recommendation": "2-3 sentence summary of the consolidated plan and why it works for the group"
}

Generate the consolidated recommendations now. Be specific and practical."""

            response = ai_service.model.generate_content(prompt)
            
            if response and response.text:
                # Parse AI response
                import json
                import re
                
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    try:
                        consolidated_data = json.loads(json_match.group())
                        # Add metadata
                        consolidated_data['ai_analyzed'] = True
                        consolidated_data['total_members'] = total_members
                        consolidated_data['destination'] = destination
                        return jsonify(consolidated_data), 200
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {e}")
                        print(f"Response text: {response.text[:500]}")
        
        # Fallback: return existing selections without AI consolidation
        fallback_data = {
            'consolidated_selections': {
                room_type: [selection.get('name', 'Selection') for selection in data['selections']]
                for room_type, data in all_selections_by_room.items()
            },
            'message': 'AI consolidation not available - showing all selections',
            'ai_analyzed': False
        }
        return jsonify(fallback_data), 200
        
    except Exception as e:
        print(f"Error consolidating preferences: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve the React frontend - catch-all route for SPA"""
    # Don't handle API routes - they should be handled by their specific routes above
    if path and path.startswith('api'):
        return jsonify({'error': 'API endpoint not found'}), 404
    
    # Try to find static directory
    static_dir = app.static_folder or '../dist'
    
    # Try multiple paths to find dist folder
    possible_paths = [
        static_dir,
        os.path.join(os.path.dirname(__file__), '..', 'dist'),
        os.path.join(os.path.dirname(__file__), 'dist'),
        'dist',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dist'))
    ]
    
    found_dir = None
    for possible_path in possible_paths:
        abs_path = os.path.abspath(possible_path) if os.path.exists(possible_path) else possible_path
        if os.path.exists(abs_path) and os.path.isdir(abs_path):
            found_dir = abs_path
            break
    
    # If static directory found, serve files
    if found_dir:
        # For root path or SPA routes, serve index.html
        if not path or path == '':
            index_path = os.path.join(found_dir, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(found_dir, 'index.html')
        
        # Try to serve requested file
        if path:
            file_path = os.path.join(found_dir, path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(found_dir, path)
            # For SPA routing, serve index.html if file doesn't exist
            index_path = os.path.join(found_dir, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(found_dir, 'index.html')
    
    # Fallback message if static files not found
    return 'Backend is running successfully! API available at /api/*', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
