from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime, UTC, timedelta
import json
import threading
from pathlib import Path
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
from weather_service import WeatherService

# Load environment variables - explicitly from backend/.env to avoid conflicts with root .env
backend_dir = Path(__file__).parent
env_path = backend_dir / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✅ Loaded .env from: {env_path}")
else:
    # Fallback to root .env if backend/.env doesn't exist
    root_env = backend_dir.parent / '.env'
    if root_env.exists():
        load_dotenv(dotenv_path=root_env)
        print(f"⚠️  Loaded .env from root: {root_env} (backend/.env not found)")
    else:
        load_dotenv()  # Default behavior
        print("⚠️  Using default load_dotenv() - no .env file found")

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

weather_service = WeatherService()


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


@app.route('/api/ai/status', methods=['GET'])
def get_ai_status():
    """Expose current AI provider configuration for frontend UI badges."""
    # Use lazy getter to avoid blocking on startup
    vertex_enabled = bool(ai_service and ai_service._get_vertex_client() is not None)
    status = {
        'gemini_configured': bool(os.getenv('GEMINI_API_KEY')),
        'maps_configured': bool(os.getenv('GOOGLE_MAPS_API_KEY')),
        'vertex_enabled': vertex_enabled,
        'vertex_project': os.getenv('VERTEX_PROJECT_ID'),
        'vertex_location': os.getenv('VERTEX_LOCATION', 'us-central1') if vertex_enabled else None,
        'provider_message': 'Vertex AI is powering dining & activities suggestions'
        if vertex_enabled else 'Using Gemini direct API fallback for dining & activities',
        'timestamp': datetime.now(UTC).isoformat()
    }
    return jsonify(status)

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
        
        # Calculate number of nights if not provided
        number_of_nights = data.get('number_of_nights')
        if not number_of_nights:
            # Calculate from dates if not provided
            try:
                from datetime import datetime
                start = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
                diff = (end - start).days
                number_of_nights = max(1, diff)
            except:
                number_of_nights = 1
        
        # Create group data
        group_data = {
            'group_name': data['group_name'],
            'destination': data['destination'],
            'from_location': data.get('from_location', ''),
            'start_date': data['start_date'],
            'end_date': data['end_date'],
            'number_of_nights': number_of_nights,
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


@app.route('/api/itinerary/weather', methods=['GET'])
def get_itinerary_weather():
    """Return daily weather data for a destination between start and end dates."""
    try:
        location = request.args.get('location') or request.args.get('destination')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not location or not start_date or not end_date:
            return jsonify({'error': 'Missing required query parameters: location, start_date, end_date'}), 400

        # Normalize date formats - accept multiple formats and convert to YYYY-MM-DD
        def normalize_date(date_str):
            """Convert various date formats to YYYY-MM-DD"""
            if not date_str:
                return None
            
            # Try different date formats
            date_formats = [
                '%Y-%m-%d',           # 2024-12-02
                '%m/%d/%Y',           # 12/02/2024
                '%d/%m/%Y',           # 02/12/2024
                '%Y-%m-%dT%H:%M:%S',  # ISO format with time
                '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with microseconds
                '%Y-%m-%dT%H:%M:%SZ',     # ISO format UTC
            ]
            
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(date_str.split('T')[0], fmt.split('T')[0])
                    return dt.strftime('%Y-%m-%d')
                except (ValueError, AttributeError):
                    continue
            
            # If all formats fail, try parsing as Date object (JavaScript format)
            try:
                # Handle JavaScript Date string format
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d')
            except:
                pass
            
            return None

        normalized_start = normalize_date(start_date)
        normalized_end = normalize_date(end_date)
        
        if not normalized_start or not normalized_end:
            return jsonify({'error': f'Invalid date format. Received: start_date={start_date}, end_date={end_date}. Please use YYYY-MM-DD format.'}), 400

        try:
            start = datetime.strptime(normalized_start, '%Y-%m-%d')
            end = datetime.strptime(normalized_end, '%Y-%m-%d')
        except ValueError as e:
            return jsonify({'error': f'Date parsing error: {str(e)}'}), 400

        if end < start:
            start, end = end, start

        day_count = (end - start).days + 1
        max_supported_days = 30  # Reasonable upper bound to avoid runaway loops
        if day_count > max_supported_days:
            day_count = max_supported_days

        itinerary_weather = []
        for offset in range(day_count):
            current_date = start + timedelta(days=offset)
            date_str = current_date.strftime('%Y-%m-%d')
            weather = weather_service.get_weather_for_location(location, date_str)
            weather['date'] = weather.get('date') or date_str
            weather['formatted_date'] = current_date.strftime('%a, %b %d')
            if 'icon' not in weather or not weather['icon']:
                weather['icon'] = weather_service.get_weather_icon(weather.get('condition', '') or weather.get('description', ''))
            weather['is_bad_weather'] = weather_service.is_bad_weather(weather)
            itinerary_weather.append(weather)

        return jsonify({
            'location': location,
            'start_date': start_date,
            'end_date': end_date,
            'days': itinerary_weather
        })

    except Exception as e:
        print(f"Error fetching itinerary weather: {e}")
        return jsonify({'error': 'Failed to fetch itinerary weather'}), 500

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
        
        # Deduplicate suggestions by place_id and name (case-insensitive)
        seen_place_ids = set()
        seen_names = set()
        unique_suggestions = []
        
        for suggestion in suggestions:
            place_id = suggestion.get('place_id')
            name = suggestion.get('name', '').strip().lower()
            
            # Use place_id as primary deduplication key (most reliable)
            if place_id:
                if place_id not in seen_place_ids:
                    seen_place_ids.add(place_id)
                    unique_suggestions.append(suggestion)
                else:
                    continue
            # Fallback to name if no place_id (case-insensitive)
            elif name:
                if name not in seen_names:
                    seen_names.add(name)
                    unique_suggestions.append(suggestion)
                else:
                    continue
            else:
                # If no place_id or name, include it (shouldn't happen, but be safe)
                unique_suggestions.append(suggestion)
        
        return jsonify(unique_suggestions)
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
    """Use AI to intelligently analyze all member selections and find common preferences with conflict resolution
    
    Optional query parameter: room_type - if provided, only consolidate that specific room type
    """
    try:
        # Get optional room_type parameter to consolidate only a specific room
        room_type_filter = request.args.get('room_type') or request.get_json(silent=True) or {}
        if isinstance(room_type_filter, dict):
            room_type_filter = room_type_filter.get('room_type')
        
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
        user_info_map = {}  # Map user emails to user names
        
        # Get group members to map emails to names
        try:
            group_members = group.get('members', [])
            for member in group_members:
                if isinstance(member, dict):
                    email = member.get('email', '')
                    name = member.get('name', email.split('@')[0] if email else 'Unknown')
                    user_info_map[email] = name
                elif isinstance(member, str):
                    # If member is just an email string
                    user_info_map[member] = member.split('@')[0]
        except Exception as e:
            print(f"Error getting user info: {e}")
        
        for room in rooms:
            # CRITICAL: If room_type_filter is specified, only process that room type
            if room_type_filter and room.get('room_type') != room_type_filter:
                continue
            
            selections = room.get('user_selections', [])
            completed_by = room.get('completed_by', [])
            
            # CRITICAL: Only consolidate if 2+ users have made decisions
            if len(completed_by) < 2:
                # Skip consolidation for this room - not enough users yet
                print(f"⚠️ Skipping {room.get('room_type')} - only {len(completed_by)} user(s) completed (need 2+)")
                continue
            
            print(f"✅ Processing {room.get('room_type')} - {len(completed_by)} users completed")
            
            if selections:
                # Get the original suggestions to analyze preferences
                room_suggestions = firebase_service.get_room_suggestions(room['id'])
                
                # Map selections to users who selected them
                # Since we can't directly track which user selected which item,
                # we'll use the completed_by list and distribute selections
                # For now, we'll note which users have completed this room
                user_names = [user_info_map.get(email, email.split('@')[0] if email else 'Unknown') 
                             for email in completed_by]
                
                # CRITICAL: Get actual user preferences/answers for this room
                # This ensures consolidation considers the original preferences, not just selections
                user_preferences = {}
                for user_email in completed_by:
                    try:
                        # Get user ID from email (try to find in members)
                        user_id = None
                        for member in group.get('members', []):
                            if isinstance(member, dict) and member.get('email') == user_email:
                                user_id = member.get('id') or user_email
                                break
                            elif isinstance(member, str) and member == user_email:
                                user_id = user_email
                                break
                        
                        if not user_id:
                            user_id = user_email
                        
                        # Fetch user's answers/preferences for this room
                        answers = firebase_service.get_user_answers(room['id'], user_id)
                        if answers:
                            user_name = user_info_map.get(user_email, user_email.split('@')[0])
                            user_preferences[user_name] = answers
                    except Exception as e:
                        print(f"Error fetching preferences for {user_email}: {e}")
                        continue
                
                # Analyze preferences from selected suggestions
                all_selections_by_room[room['room_type']] = {
                    'selections': selections,
                    'suggestions': room_suggestions,
                    'room_type': room['room_type'],
                    'completed_by_users': user_names,
                    'completed_by_emails': completed_by,
                    'user_count': len(completed_by),
                    'user_preferences': user_preferences  # Add actual preferences
                }
        
        if not all_selections_by_room:
            # Check if any rooms have selections but not enough users
            has_single_user_selections = any(
                len(room.get('completed_by', [])) == 1 
                for room in rooms 
                if room.get('user_selections')
            )
            
            # If filtering by room_type, check if that specific room has insufficient users
            if room_type_filter:
                filtered_room = next((r for r in rooms if r.get('room_type') == room_type_filter), None)
                if filtered_room:
                    completed_count = len(filtered_room.get('completed_by', []))
                    if completed_count < 2:
                        return jsonify({
                            'error': 'Not enough users have made decisions yet',
                            'message': f'Consolidation for {room_type_filter} requires at least 2 members to complete selections',
                            'ai_analyzed': False,
                            'room_type': room_type_filter,
                            'completed_count': completed_count
                        }), 200  # Return 200 but with ai_analyzed: false
            
            if has_single_user_selections:
                return jsonify({
                    'error': 'Not enough users have made decisions yet',
                    'message': 'Consolidation requires at least 2 members to complete selections',
                    'ai_analyzed': False
                }), 200  # Return 200 but with ai_analyzed: false
            
            return jsonify({'error': 'No selections found to consolidate'}), 400
        
        # Calculate optimal number of preferences per category
        def calculate_optimal_count(room_type, group_size, selection_count):
            """Calculate how many consolidated options to show"""
            # Base count by group size - increased to show more options
            if group_size <= 3:
                base = 4  # Show at least 4 options for small groups
            elif group_size <= 6:
                base = 5  # Show at least 5 options for medium groups
            else:
                base = 6  # Show at least 6 options for large groups
            
            # Category multipliers - adjusted to show more variety
            multipliers = {
                'accommodation': 1.2,  # Show 4-6 options
                'transportation': 1.0,  # Show 4-6 options (can have multiple legs)
                'dining': 1.5,  # Show 6-9 options (more variety needed)
                'activities': 1.8  # Show 7-10 options (most variety needed)
            }
            
            multiplier = multipliers.get(room_type, 1.2)
            # Calculate optimal count, but don't cap too strictly
            # Show at least 4 options, up to 80% of available selections (or minimum of 4-6)
            calculated = int(base * multiplier)
            # Use at least 4, but show more if there are more selections available
            # Cap at 80% of selections to ensure we're consolidating, not just showing everything
            optimal = max(4, min(calculated, max(4, int(selection_count * 0.8))))
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
            # CRITICAL: If room_type_filter is provided, only process that room type
            room_type_counts = {}
            for room_type, data in all_selections_by_room.items():
                # If filtering by room type, skip other room types
                if room_type_filter and room_type != room_type_filter:
                    continue
                    
                selections = data.get('selections', [])
                completed_by_users = data.get('completed_by_users', [])
                user_count = data.get('user_count', len(completed_by_users))
                
                if selections:
                    optimal_count = calculate_optimal_count(room_type, total_members, len(selections))
                    room_type_counts[room_type] = optimal_count
                    
                    user_list = ', '.join(completed_by_users) if completed_by_users else 'Group members'
                    user_preferences = data.get('user_preferences', {})
                    
                    prompt += f"""
{room_type.upper()} - MEMBER PREFERENCES AND SELECTIONS:

Members who completed: {user_list}

ACTUAL USER PREFERENCES (from their form answers - THIS IS THE PRIMARY BASIS FOR CONSOLIDATION):
"""
                    # Add actual preferences from user answers
                    for user_name, answers in user_preferences.items():
                        if answers and isinstance(answers, list) and len(answers) > 0:
                            prompt += f"\n{user_name}'s Preferences:\n"
                            for answer in answers:
                                question_text = answer.get('question_text', answer.get('question_id', 'Unknown'))
                                answer_value = answer.get('answer_value', 'N/A')
                                if isinstance(answer_value, dict):
                                    if 'min_value' in answer_value and 'max_value' in answer_value:
                                        answer_value = f"Budget: {answer_value.get('min_value')}-{answer_value.get('max_value')}"
                                    else:
                                        answer_value = str(answer_value)
                                elif isinstance(answer_value, list):
                                    answer_value = ', '.join(str(v) for v in answer_value)
                                prompt += f"  - {question_text}: {answer_value}\n"
                        else:
                            prompt += f"\n{user_name}: No explicit preferences recorded\n"
                    
                    prompt += f"""
SELECTIONS MADE BY MEMBERS ({len(selections)} total, select {optimal_count} consolidated options based on preferences above):
NOTE: You should select {optimal_count} options that best match the group's preferences. Consider top preferences and consensus, but provide a good variety of {optimal_count} options that reflect the exact property types, amenities, and locations members requested (e.g., cottages, beach-front, private villas). Ratings should only be used when two options meet *all* preference criteria equally.
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
    Rating: {rating}/5 (NOTE: Rating is SECONDARY - preferences are PRIMARY)
    Features: {', '.join(features) if features else 'N/A'}
    Highlights: {', '.join(highlights) if highlights else 'N/A'}
"""
            
            prompt += f"""

CRITICAL TASK - INTELLIGENT CONSOLIDATION BASED ON USER PREFERENCES:

⚠️ CRITICAL PRIORITY ORDER (MUST FOLLOW THIS ORDER):
1. **USER PREFERENCES ARE PRIMARY** - Match the actual preferences entered by users (budget, location, type, amenities, etc.)
2. **RATINGS ARE SECONDARY** - Only use ratings as a tie-breaker when multiple options match preferences equally
3. **CONSENSUS IS IMPORTANT** - Prioritize options selected by multiple users, but ONLY if they match user preferences

1. **Analyze ACTUAL User Preferences FIRST**: 
   - Review the preferences listed above for each user
   - Identify common themes: budget ranges, location preferences, activity types, quality expectations
   - Note any conflicts or differences between users
   - These preferences are MORE IMPORTANT than ratings - they show what users actually want

2. **Match Selections to Preferences**:
   - For each selection, determine exactly which user preferences (by member name) it satisfies and cite them in your reasoning
   - Prioritize selections that match MULTIPLE users' stated preferences, especially the most frequently mentioned themes (e.g., “Harshini’s cottage on the beach”)
   - If a selection matches user preferences but wasn't selected by that user, still consider it if it's a good fit
   - Budget: Match selections to the budget ranges specified in preferences
   - Location: Match to location preferences (beach, city center, etc.)
   - Type/style: If users request specific formats such as “cottage,” “villa,” “homestay,” etc., the chosen options must reflect those exact property types; do not substitute with unrelated property styles.
   - DO NOT prioritize or mention ratings unless two or more options are tied on all preference criteria. Ratings are strictly a tie-breaker after preference alignment.

3. **Handle Conflicts Intelligently**:
   - If preferences conflict (e.g., adventurous vs spiritual), use these strategies:
     a) Find options that satisfy MULTIPLE preferences simultaneously (e.g., "mountain temple trek" = adventure + spiritual)
     b) If no overlap exists, create a BALANCED MIX that represents all preferences proportionally
     c) Prioritize options with highest consensus/vote counts AND preference alignment
   
4. **Select Optimal Options**: Choose exactly the number specified per category:
"""
            for room_type, count in room_type_counts.items():
                prompt += f"   - {room_type}: {count} options (IMPORTANT: Show {count} options, not fewer)\n"
            
            # If filtering by room type, emphasize that only that room type should be returned
            if room_type_filter:
                prompt += f"""
CRITICAL: You are ONLY consolidating {room_type_filter}. Return consolidated_selections ONLY for {room_type_filter}, and analysis_details ONLY for {room_type_filter}. 
Do NOT include other room types in your response.
"""
            
            prompt += """
5. **Selection Criteria (IN ORDER OF PRIORITY)**:
   a) **FIRST**: Match user preferences (budget, location, type, amenities) - THIS IS MOST IMPORTANT
   b) **SECOND**: Represent group consensus (selected by multiple users)
   c) **THIRD**: Provide VARIETY - include different options that satisfy different aspects of preferences
   d) **FOURTH**: Use ratings only as a tie-breaker when options equally match preferences
   e) **FIFTH**: Ensure options are accessible and practical
   
   **CRITICAL**: You MUST return the exact number of options specified (e.g., if asked for 4 options, return 4, not 1 or 2).
   Consider top preferences but provide a diverse set of options that collectively satisfy the group's needs.

6. **Reasoning Requirements**: 
   - ALWAYS explain why each option was chosen based on USER PREFERENCES, citing member names and the exact preference (e.g., “Harshini requested a beachfront cottage under ₹6,000; this property is a beach-facing cottage priced within her range”)
   - Ratings can be referenced only as a tie-breaker and must be explicitly framed as secondary to the preference match.

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
  "recommendation": "2-3 sentence summary that explicitly references the key members and the exact preferences you satisfied (e.g., cite “Harshini’s cottage + beach request” and “Aditya’s ₹6K budget”). Mention ratings ONLY as a tie-breaker if two options were otherwise identical.",
  "analysis_details": {{
    "accommodation": {{
      "users_analyzed": ["list of user names whose selections were analyzed for this category"],
      "selection_basis": "Explanation of which user preferences led to each consolidated choice in this category",
      "reasoning": "Detailed reasoning for why these specific options were chosen based on the users' selections"
    }},
    "transportation": {{
      "users_analyzed": ["list of user names whose selections were analyzed for this category"],
      "selection_basis": "Explanation of which user preferences led to each consolidated choice in this category",
      "reasoning": "Detailed reasoning for why these specific options were chosen based on the users' selections"
    }},
    "dining": {{
      "users_analyzed": ["list of user names whose selections were analyzed for this category"],
      "selection_basis": "Explanation of which user preferences led to each consolidated choice in this category",
      "reasoning": "Detailed reasoning for why these specific options were chosen based on the users' selections"
    }},
    "activities": {{
      "users_analyzed": ["list of user names whose selections were analyzed for this category"],
      "selection_basis": "Explanation of which user preferences led to each consolidated choice in this category",
      "reasoning": "Detailed reasoning for why these specific options were chosen based on the users' selections"
    }}
  }}
}}

IMPORTANT: For each room type in analysis_details, include the actual user names from the selections above. Explain clearly which user's preferences influenced each consolidated choice and why.
{f'CRITICAL: You are ONLY consolidating {room_type_filter.upper()}. In your JSON response, ONLY include consolidated_selections and analysis_details for {room_type_filter}. Set other room types to empty arrays [] or omit them entirely.' if room_type_filter else ''}
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
                        # Add metadata with user information
                        consolidated_data['ai_analyzed'] = True
                        consolidated_data['total_members'] = total_members
                        consolidated_data['destination'] = destination
                        
                        # Log which room types were processed
                        processed_room_types = list(all_selections_by_room.keys())
                        print(f"✅ AI consolidation completed for room types: {processed_room_types}")
                        if room_type_filter:
                            print(f"   (Filtered to: {room_type_filter})")
                        print(f"   Consolidated selections keys: {list(consolidated_data.get('consolidated_selections', {}).keys())}")
                        print(f"   Analysis details keys: {list(consolidated_data.get('analysis_details', {}).keys())}")
                        
                        # Filter consolidated_selections and analysis_details to only include requested room types
                        if room_type_filter:
                            # Only keep the filtered room type
                            if 'consolidated_selections' in consolidated_data:
                                filtered_selections = {}
                                if room_type_filter in consolidated_data['consolidated_selections']:
                                    filtered_selections[room_type_filter] = consolidated_data['consolidated_selections'][room_type_filter]
                                consolidated_data['consolidated_selections'] = filtered_selections
                            
                            if 'analysis_details' in consolidated_data:
                                filtered_analysis = {}
                                if room_type_filter in consolidated_data['analysis_details']:
                                    filtered_analysis[room_type_filter] = consolidated_data['analysis_details'][room_type_filter]
                                consolidated_data['analysis_details'] = filtered_analysis
                            
                            # Ensure ai_status_by_room is set for the filtered room type
                            if 'ai_status_by_room' not in consolidated_data:
                                consolidated_data['ai_status_by_room'] = {}
                            consolidated_data['ai_status_by_room'][room_type_filter] = True
                        
                        # Add user information for each room type (only for processed room types)
                        consolidated_data['users_by_room'] = {
                            room_type: data.get('completed_by_users', [])
                            for room_type, data in all_selections_by_room.items()
                            if not room_type_filter or room_type == room_type_filter
                        }
                        
                        # Ensure analysis_details exists
                        if 'analysis_details' not in consolidated_data:
                            consolidated_data['analysis_details'] = {}
                        
                        # Add user names to analysis_details if not present, or ensure they're always included
                        # Only process room types that were actually consolidated
                        for room_type, data in all_selections_by_room.items():
                            # Skip if filtering and this isn't the filtered room type
                            if room_type_filter and room_type != room_type_filter:
                                continue
                                
                            if room_type not in consolidated_data.get('analysis_details', {}):
                                consolidated_data.setdefault('analysis_details', {})[room_type] = {
                                    'users_analyzed': data.get('completed_by_users', []),
                                    'user_count': data.get('user_count', 0)
                                }
                            else:
                                # Ensure users_analyzed is always present even if AI returned analysis_details
                                if 'users_analyzed' not in consolidated_data['analysis_details'][room_type]:
                                    consolidated_data['analysis_details'][room_type]['users_analyzed'] = data.get('completed_by_users', [])
                                if 'user_count' not in consolidated_data['analysis_details'][room_type]:
                                    consolidated_data['analysis_details'][room_type]['user_count'] = data.get('user_count', 0)
                        
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
