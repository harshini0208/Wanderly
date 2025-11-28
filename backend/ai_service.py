import os
import json
import time
import hashlib
from typing import List, Dict, Any, Tuple, Optional

import requests
from datetime import datetime, UTC

import google.generativeai as genai
from easemytrip_service import EaseMyTripService
from firebase_service import firebase_service
# Lazy import VertexAIClient to avoid import errors if vertexai isn't installed

class AIService:
    def __init__(self):
        """Initialize AI service with dynamic configuration loading"""
        # Configure Gemini AI
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize EaseMyTrip service for real data
        self.easemytrip_service = EaseMyTripService()
        
        # Google Maps API key
        self.maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.maps_api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY environment variable is required")
        
        # Load configurations dynamically
        self._load_configurations()
        
        # Caching layers
        self._preferences_cache = {}
        self._suggestion_cache = {}
        self._cache_ttl = 3600  # seconds

        # Lazy-load Vertex AI client (only initialize when actually needed)
        self._vertex_client = None  # type: ignore
        self._vertex_initialized = False
    
    def _get_vertex_client(self):
        """Lazy-load Vertex AI client only when needed (prevents startup timeouts)."""
        if self._vertex_initialized:
            return self._vertex_client
        
        self._vertex_initialized = True
        vertex_project = os.getenv("VERTEX_PROJECT_ID")
        if not vertex_project:
            return None
        
        try:
            # Lazy import to avoid ModuleNotFoundError if vertexai isn't installed
            import sys
            print("DEBUG: Attempting to import VertexAIClient...", file=sys.stderr, flush=True)
            from vertex_client import VertexAIClient
            print("DEBUG: VertexAIClient imported successfully", file=sys.stderr, flush=True)
            self._vertex_client = VertexAIClient.from_env()
            print("✓ Vertex AI client initialized for dining and activities", file=sys.stderr, flush=True)
            return self._vertex_client
        except ImportError as import_err:
            error_msg = f"⚠️ Failed to import Vertex AI client (module not installed): {import_err}"
            print(error_msg, file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return None
        except Exception as vertex_err:
            error_msg = f"⚠️ Failed to initialize Vertex AI client: {vertex_err}"
            print(error_msg, file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return None
    
    @property
    def vertex_client(self):
        """Property accessor for vertex_client (lazy-loaded)."""
        return self._get_vertex_client()
    
    def _load_configurations(self):
        """Load all configuration files dynamically"""
        try:
            # Load pricing configuration
            with open('config/pricing_ranges.json', 'r') as f:
                self.pricing_config = json.load(f)
            
            # Load accommodation types
            with open('config/accommodation_types.json', 'r') as f:
                self.accommodation_types = json.load(f)['accommodation_types']
            
            # Load room types configuration
            with open('config/room_types.json', 'r') as f:
                self.room_config = json.load(f)
            
            # Load transportation options
            with open('config/transportation_options.json', 'r') as f:
                self.transport_config = json.load(f)
                
            print("✓ All configuration files loaded successfully")
            
        except Exception as e:
            print(f"Error loading configurations: {e}")
            # Set fallback configurations
            self.pricing_config = {"currencies": {"USD": {"budget_min": 20, "budget_low": 50, "budget_mid": 100, "budget_high": 200, "budget_luxury": 500}}}
            self.accommodation_types = ["Hotel", "Hostel", "Airbnb", "Resort", "Guesthouse"]
            self.room_config = {"room_types": []}
            self.transport_config = {"transportation_options": ["Flight", "Train", "Bus", "Car Rental"]}
    
    def _get_cache_key(self, room_type: str, destination: str, context: str) -> str:
        """Generate a stable cache key for suggestion requests.
        Use the full context to avoid collisions when users provide different preferences.
        """
        key_str = f"{room_type}:{destination}:{context}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def generate_suggestions(self, room_type: str, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate AI-powered suggestions based on user answers and preferences"""
        answers = answers or []
        preference_constraints = self._extract_common_preferences(room_type, answers)
        
        # For transportation, use real EaseMyTrip data instead of AI
        if room_type == 'transportation':
            return self._generate_transportation_suggestions(destination, answers, group_preferences)
        
        # For accommodation, use Google Places API for real data
        if room_type == 'accommodation':
            return self._generate_accommodation_suggestions_places(destination, answers, group_preferences, preference_constraints)
        
        # For dining and activities, use Google Places API + Vertex AI for intelligent filtering
        if room_type == 'dining':
            return self._generate_dining_suggestions_places_vertex(destination, answers, group_preferences, preference_constraints)
        
        if room_type == 'activities':
            return self._generate_activities_suggestions_places_vertex(destination, answers, group_preferences, preference_constraints)
        
        # Get currency based on room type and user preference
        from utils import get_currency_from_destination
        
        # For stay and transportation, use FROM location currency (home currency)
        # For dining and activities, use destination currency (local currency)
        # Use from location currency for all room types (user's home currency)
        from_location = group_preferences.get('from_location', '') if group_preferences else ''
        currency = get_currency_from_destination(from_location) if from_location else '$'
        currency_source = f"from location ({from_location})"
        
        # Prepare context from answers
        context = self._prepare_context(room_type, destination, answers, group_preferences, preference_constraints)
        
        # Cache check to avoid redundant AI calls
        cache_key = self._get_cache_key(room_type, destination, context)
        cached_entry = self._suggestion_cache.get(cache_key)
        if cached_entry:
            cached_time, cached_suggestions = cached_entry
            if time.time() - cached_time < self._cache_ttl:
                print(f"✅ Using cached suggestions for {room_type} → skipped AI call")
                return cached_suggestions
        
        # Generate prompt for Gemini
        prompt = self._create_prompt(room_type, destination, context, currency, preference_constraints)
        
        try:
            use_vertex = room_type in ('dining', 'activities') and self._get_vertex_client() is not None
            
            print(f"\n{'='*80}")
            print(f"🚀 GENERATING AI SUGGESTIONS ({'Vertex AI' if use_vertex else 'Gemini API'})")
            print(f"{'='*80}")
            print(f"Room Type: {room_type}")
            print(f"Destination: {destination}")
            print(f"Prompt length: {len(prompt)} chars")
            print(f"First 500 chars of prompt:")
            print(prompt[:500])
            print(f"{'='*80}\n")
            
            if use_vertex:
                try:
                    response_text = self._generate_with_vertex(prompt)
                except Exception as vertex_err:
                    # If Vertex AI fails (404, permissions, etc.), fall back to Gemini API
                    print(f"\n⚠️ Vertex AI failed ({type(vertex_err).__name__}: {str(vertex_err)[:200]}), falling back to Gemini API")
                    print(f"{'='*80}\n")
                    response_text = self._generate_with_gemini(prompt)
            else:
                response_text = self._generate_with_gemini(prompt)
            
            print(f"\n{'='*80}")
            print(f"📥 RECEIVED AI RESPONSE")
            print(f"{'='*80}")
            print(f"Response source: {'Vertex AI' if use_vertex else 'Gemini API'}")
            print(f"Response text length: {len(response_text)} chars")
            print(f"{'='*80}\n")
            
            suggestions_data = self._parse_ai_response(response_text, room_type)
            
            # Enhance with Google Maps links
            enhanced_suggestions = []
            for suggestion in suggestions_data:
                enhanced_suggestion = self._enhance_with_maps(suggestion, destination, answers, group_preferences)
                enhanced_suggestions.append(enhanced_suggestion)
            
            # Cache fresh results
            self._suggestion_cache[cache_key] = (time.time(), enhanced_suggestions)
            return enhanced_suggestions
            
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ EXCEPTION IN generate_suggestions")
            print(f"{'='*80}")
            print(f"Room type: {room_type}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            print(f"Full traceback:")
            print(traceback.format_exc())
            print(f"{'='*80}\n")
            return self._get_fallback_suggestions(room_type, destination)
    
    def _generate_with_gemini(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        if not response or not getattr(response, "text", None):
            raise ValueError("Gemini API returned an empty response")
        return response.text
    
    def _generate_with_vertex(self, prompt: str) -> str:
        client = self._get_vertex_client()
        if not client:
            raise ValueError("Vertex AI client is not configured")
        return client.generate(prompt)
    
    def _prepare_context(self, room_type: str, destination: str, answers: List[Dict], group_preferences: Dict = None, preference_constraints: Dict = None) -> str:
        """Prepare context from user answers"""
        context_parts = [f"Destination: {destination}"]
        
        if group_preferences:
            context_parts.append(f"Travel dates: {group_preferences.get('start_date', 'Not specified')} to {group_preferences.get('end_date', 'Not specified')}")
            context_parts.append(f"Group size: {group_preferences.get('group_size', 'Not specified')}")
        
        # Process answers to extract preferences
        for answer in answers:
            question_text = answer.get('question_text', '')
            answer_value = answer.get('answer_value')
            
            if answer_value:
                if isinstance(answer_value, dict):
                    # Handle range questions
                    if 'min_value' in answer_value and 'max_value' in answer_value:
                        min_val = answer_value['min_value']
                        max_val = answer_value['max_value']
                        if min_val and max_val:
                            context_parts.append(f"{question_text}: {min_val} - {max_val}")
                elif isinstance(answer_value, list):
                    # Handle multiple selections - emphasize important preferences
                    if answer_value:
                        # Check for key preference categories and emphasize them
                        question_lower = question_text.lower()
                        if any(keyword in question_lower for keyword in ["type", "preference", "requirement", "need", "want"]):
                            # Extract the category from question text
                            if "accommodation" in question_lower:
                                context_parts.append(f"ACCOMMODATION TYPE PREFERENCES: {', '.join(answer_value)}")
                            elif "activity" in question_lower:
                                context_parts.append(f"ACTIVITY TYPE PREFERENCES: {', '.join(answer_value)}")
                            elif "meal" in question_lower or "food" in question_lower:
                                context_parts.append(f"MEAL TYPE PREFERENCES: {', '.join(answer_value)}")
                            elif "amenities" in question_lower or "features" in question_lower:
                                context_parts.append(f"AMENITIES/FEATURES REQUIRED: {', '.join(answer_value)}")
                            elif "budget" in question_lower or "price" in question_lower:
                                context_parts.append(f"BUDGET REQUIREMENTS: {', '.join(answer_value)}")
                            elif "location" in question_lower or "area" in question_lower:
                                context_parts.append(f"LOCATION/AREA PREFERENCES: {', '.join(answer_value)}")
                            else:
                                context_parts.append(f"PREFERENCES: {', '.join(answer_value)}")
                        else:
                            context_parts.append(f"{question_text}: {', '.join(answer_value)}")
                else:
                    # Handle single text/option questions - emphasize specific preferences
                    question_lower = question_text.lower()
                    
                    # Check for key preference categories and emphasize them
                    if any(keyword in question_lower for keyword in ["type", "preference", "requirement", "need", "want", "like"]):
                        if "accommodation" in question_lower:
                            context_parts.append(f"ACCOMMODATION TYPE PREFERENCE: {answer_value}")
                        elif "activity" in question_lower:
                            context_parts.append(f"ACTIVITY TYPE PREFERENCE: {answer_value}")
                        elif "meal" in question_lower or "food" in question_lower or "dining" in question_lower:
                            context_parts.append(f"DINING PREFERENCE: {answer_value}")
                        elif "dietary" in question_lower or "restriction" in question_lower:
                            context_parts.append(f"DIETARY RESTRICTIONS/FOOD PREFERENCES: {answer_value}")
                        elif "pet" in question_lower or "animal" in question_lower:
                            context_parts.append(f"PET-FRIENDLY REQUIREMENT: {answer_value}")
                        elif "beach" in question_lower or "waterfront" in question_lower:
                            context_parts.append(f"BEACH/WATERFRONT REQUIREMENT: {answer_value}")
                        elif "budget" in question_lower or "price" in question_lower:
                            context_parts.append(f"BUDGET REQUIREMENT: {answer_value}")
                        elif "amenities" in question_lower or "features" in question_lower:
                            context_parts.append(f"AMENITIES/FEATURES REQUIRED: {answer_value}")
                        elif "location" in question_lower or "area" in question_lower:
                            context_parts.append(f"LOCATION/AREA PREFERENCE: {answer_value}")
                        else:
                            context_parts.append(f"PREFERENCE: {answer_value}")
                    else:
                        context_parts.append(f"{question_text}: {answer_value}")
        
        if preference_constraints:
            budget = preference_constraints.get('budget')
            if budget and budget.get('min') is not None and budget.get('max') is not None:
                context_parts.append(f"Budget range: {budget['min']} - {budget['max']}")
            if preference_constraints.get('types'):
                context_parts.append(f"Preferred types: {', '.join(preference_constraints['types'])}")
            if preference_constraints.get('amenities'):
                context_parts.append(f"Required amenities: {', '.join(preference_constraints['amenities'])}")
            if preference_constraints.get('dietary'):
                context_parts.append(f"Dietary needs: {', '.join(preference_constraints['dietary'])}")
            if preference_constraints.get('location'):
                context_parts.append(f"Location preferences: {', '.join(preference_constraints['location'])}")
        
        context = "; ".join(context_parts)
        print(f"DEBUG CONTEXT FOR {room_type.upper()}: {context}")
        return context
    
    def _extract_common_preferences(self, room_type: str, answers: List[Dict]) -> Dict:
        """Extract normalized preferences shared across room types"""
        preferences = {
            'budget': None,
            'types': [],
            'amenities': [],
            'dietary': [],
            'location': [],
            'transport': [],
            'keywords': []
        }
        
        for answer in answers:
            question_text = (answer.get('question_text') or '').lower()
            answer_value = answer.get('answer_value')
            if answer_value in (None, '', []):
                answer_value = answer.get('answer_text')
            if not answer_value:
                continue
            
            values_list = []
            if isinstance(answer_value, list):
                values_list = [str(val).strip() for val in answer_value if val]
            elif isinstance(answer_value, dict):
                if 'min_value' in answer_value and 'max_value' in answer_value:
                    try:
                        min_val = float(str(answer_value['min_value']).replace(',', ''))
                        max_val = float(str(answer_value['max_value']).replace(',', ''))
                        preferences['budget'] = {'min': min_val, 'max': max_val}
                    except ValueError:
                        pass
                    continue
                elif 'min' in answer_value and 'max' in answer_value:
                    try:
                        min_val = float(str(answer_value['min']).replace(',', ''))
                        max_val = float(str(answer_value['max']).replace(',', ''))
                        preferences['budget'] = {'min': min_val, 'max': max_val}
                    except ValueError:
                        pass
                    continue
                else:
                    value = answer_value.get('value') or answer_value.get('answer_value') or answer_value.get('text')
                    if value:
                        values_list = [str(value).strip()]
            else:
                values_list = [str(answer_value).strip()]
            
            if 'budget' in question_text or 'price' in question_text:
                for value in values_list:
                    if '-' in value:
                        parts = value.split('-')
                        if len(parts) == 2:
                            try:
                                preferences['budget'] = {
                                    'min': float(parts[0].strip().replace(',', '')),
                                    'max': float(parts[1].strip().replace(',', ''))
                                }
                            except ValueError:
                                continue
            elif any(keyword in question_text for keyword in ['type', 'category', 'style']):
                preferences['types'].extend(values_list)
            elif any(keyword in question_text for keyword in ['amenities', 'feature', 'must have', 'need']):
                preferences['amenities'].extend(values_list)
            elif any(keyword in question_text for keyword in ['diet', 'dietary', 'vegan', 'vegetarian', 'food preference']):
                preferences['dietary'].extend(values_list)
            elif any(keyword in question_text for keyword in ['location', 'area', 'neighborhood']):
                preferences['location'].extend(values_list)
            elif 'transportation' in question_text:
                preferences['transport'].extend(values_list)
            else:
                preferences['keywords'].extend(values_list)
        
        # Deduplicate lists
        for key in ['types', 'amenities', 'dietary', 'location', 'transport', 'keywords']:
            if preferences[key]:
                preferences[key] = list(dict.fromkeys([val for val in preferences[key] if val]))
        
        return preferences

    def _build_preference_instructions(self, preference_constraints: Dict, currency: str) -> str:
        """Build explicit instructions for AI prompts from preferences"""
        if not preference_constraints:
            return ""
        
        lines = []
        budget = preference_constraints.get('budget')
        if budget and budget.get('min') is not None and budget.get('max') is not None:
            min_val = int(budget['min'])
            max_val = int(budget['max'])
            lines.append(f"- STRICT: price_range must stay between {currency}{min_val:,} and {currency}{max_val:,} (no exceptions).")
        
        if preference_constraints.get('types'):
            lines.append(f"- LIMIT results to these types only: {', '.join(preference_constraints['types'])}.")
        if preference_constraints.get('amenities'):
            lines.append(f"- Every result must include: {', '.join(preference_constraints['amenities'])}.")
        if preference_constraints.get('dietary'):
            lines.append(f"- Respect dietary requirements: {', '.join(preference_constraints['dietary'])}.")
        if preference_constraints.get('location'):
            lines.append(f"- Focus on areas: {', '.join(preference_constraints['location'])}.")
        
        return "\n".join(lines)
    
    def _create_prompt(self, room_type: str, destination: str, context: str, currency: str = '$', preference_constraints: Dict = None) -> str:
        """Create a detailed prompt for Gemini AI"""
        
        if room_type == 'transportation':
            return self._create_transportation_prompt(destination, context, currency, preference_constraints)
        elif room_type == 'accommodation':
            return self._create_accommodation_prompt(destination, context, currency, preference_constraints)
        elif room_type == 'dining':
            return self._create_dining_prompt(destination, context, currency, preference_constraints)
        elif room_type == 'activities':
            return self._create_activities_prompt(destination, context, currency, preference_constraints)
        else:
            return self._create_generic_prompt(room_type, destination, context, currency, preference_constraints)
    
    def _create_transportation_prompt(self, destination: str, context: str, currency: str = '$', preference_constraints: Dict = None) -> str:
        """Create specific prompt for transportation suggestions based on user preferences"""
        pref_text = self._build_preference_instructions(preference_constraints, currency)
        return f"""
You are a transportation booking expert AI assistant helping users find REAL TRANSPORTATION OPTIONS for their trip to {destination}.

User Context: {context}

CRITICAL REQUIREMENTS:
1. ONLY suggest REAL transportation services that match the user's preferences
2. Use actual company names and services
3. Do NOT suggest hotels, lounges, airports, or tourist attractions
4. Focus on TRANSPORTATION BOOKING OPTIONS only
5. Provide 5-12 REAL transportation suggestions
6. Each suggestion must be a bookable transportation service

USER PREFERENCE CONSTRAINTS:
{pref_text if pref_text else '- Respect any implicit constraints from the context.'}

TRANSPORTATION TYPES TO SUGGEST BASED ON USER PREFERENCES:
- If user selected "Flight": Suggest airlines (Emirates, Qatar Airways, Indigo, etc.)
- If user selected "Train": Suggest train services (Indian Railways, Amtrak, etc.)
- If user selected "Bus": Suggest bus services (RedBus, Greyhound, etc.)
- If user selected "Car rental": Suggest car rental companies (Hertz, Avis, etc.)
- If user selected "Public transport": Suggest metro/bus services
- If user selected "Mixed": Suggest combination of different transport modes

For each transportation suggestion, provide:
- name: The exact company/service name
- description: Brief description of the transportation service
- price_range: Realistic price range in {currency} (from location currency)
- rating: Real service rating if known, or realistic estimate
- location: Departure/arrival points
- features: Array of service features (e.g., "Direct route", "Free WiFi", "Comfortable seats")
- why_recommended: Why this service matches their preferences
- departure_time: Specific departure time (e.g., "06:30 AM", "10:45 PM")
- arrival_time: Specific arrival time (e.g., "02:15 PM", "08:30 AM")
- duration: Journey duration (e.g., "6h 45m", "8h 30m")

IMPORTANT: 
- ONLY suggest actual transportation services that match user preferences
- Do NOT suggest hotels, lounges, airports, or tourist attractions
- Focus on transportation booking options that can be booked online
- Use real company names that exist and can be booked
- Use {currency} for all price ranges (user's home currency for easier planning)

Format your response as a JSON array with this structure:
[
  {{
    "name": "REAL Transportation Service Name",
    "description": "Brief description of this transportation service...",
    "price_range": "{currency}X-Y",
    "rating": 4.5,
    "features": ["Direct route", "Free WiFi", "Comfortable seats"],
    "location": "Departure/arrival points",
    "why_recommended": "Why this service matches their specific preferences",
    "departure_time": "06:30 AM",
    "arrival_time": "02:15 PM",
    "duration": "7h 45m"
  }}
]

Respond ONLY with the JSON array, no additional text.
"""

    def _create_accommodation_prompt(self, destination: str, context: str, currency: str = '$', preference_constraints: Dict = None) -> str:
        """Create specific prompt for accommodation suggestions"""
        pref_text = self._build_preference_instructions(preference_constraints, currency)
        return f"""
You are a hotel booking expert AI assistant helping users find REAL ACCOMMODATION OPTIONS for their trip to {destination}.

User Context: {context}

CRITICAL REQUIREMENTS FOR ACCOMMODATION:
1. ONLY suggest REAL, EXISTING hotels, resorts, hostels, or vacation rentals
2. Use actual property names that can be found on Google Maps
3. Do NOT create fictional or made-up names
4. Focus on well-known, bookable establishments
5. Provide 5-12 REAL accommodation suggestions

USER PREFERENCE CONSTRAINTS:
{pref_text if pref_text else '- Respect user budget, property types, and amenities discussed in the context.'}

MANDATORY FILTERING REQUIREMENTS - STRICTLY FOLLOW ALL USER PREFERENCES:
- Analyze the user's accommodation type preferences carefully from the context
- If user selected specific accommodation types → ONLY suggest properties that match those exact types
- If user selected multiple types → Suggest a mix of properties that match ALL selected types
- MATCH the user's accommodation type preferences EXACTLY. If a user names a style such as "cottage", "villa", "heritage", etc., at least one recommendation must explicitly be that style and described as such.
- Ratings are purely a tie-breaker. NEVER prioritize a property just because it has a higher rating. If you must mention ratings, note that they are secondary to the named preferences.

DYNAMIC PREFERENCE MATCHING (Apply to ANY user preference mentioned in context):
- If user specified a budget range → ONLY suggest properties within that exact price range
- If user mentioned any specific requirements (pet-friendly, beachfront, pool, WiFi, parking, etc.) → ONLY suggest properties that offer those specific features
- If user mentioned dietary preferences → ONLY suggest properties that cater to those needs
- If user mentioned group size → ONLY suggest properties that can accommodate that group size
- If user mentioned location/area preferences → ONLY suggest properties in those specific areas
- If user mentioned any other specific requirements → ONLY suggest properties that meet those requirements
- NEVER suggest properties that don't match the user's specific requirements mentioned in the context
- When describing why a property was selected, explicitly reference the member names and the exact preference(s) you are satisfying (e.g., "Chosen for Harshini's request for a rustic beachside cottage and Aditya's budget limit of ₹6,000/night").

PROPERTY SPECIFICITY REQUIREMENTS:
- Use SPECIFIC property names, not generic descriptions like "[Type] in [Location]"
- Each suggestion must be a specific, bookable property with a real name
- Avoid generic placeholders - use actual property names that exist
- Provide 5-12 REAL property suggestions if available, do not make up options just for the sake of proving options, even if there are limited options for the user's selected preferences, keep the recommendations realistic and based on the user's preferences and dietary restrictions dont suggest anything that doesnt align with what the user has selected and entered.

Format your response as a JSON array with this structure:
[
  {{
    "name": "SPECIFIC REAL Property Name (not generic description)",
    "description": "Detailed description of this specific property and why it matches their EXACT preferences mentioned in the context...",
    "price_range": "{currency}X-Y (must match user's budget if specified in context)",
    "rating": 4.5,
    "features": ["Specific Feature 1", "Specific Feature 2", "Specific Feature 3"],
    "location": "Specific area/neighborhood in {destination}",
    "why_recommended": "Detailed explanation naming the specific member preferences this property satisfies (e.g., “Harshini’s beachfront cottage request and Aditya’s ₹6000 budget”). Mention member names from the context whenever possible.",
    "preference_match_summary": ["Harshini – beachfront cottage", "Aditya – budget under ₹6,000"]
  }}
]

Respond ONLY with the JSON array, no additional text.
"""

    def _create_dining_prompt(self, destination: str, context: str, currency: str = '$', preference_constraints: Dict = None) -> str:
        """Create specific prompt for dining suggestions"""
        pref_text = self._build_preference_instructions(preference_constraints, currency)
        return f"""
You are a restaurant expert AI assistant helping users find REAL RESTAURANTS for their trip to {destination}. Your goal is to return a rich, highly varied list that covers every cuisine, dietary, and experience preference mentioned by the group.

User Context: {context}

CRITICAL REQUIREMENTS FOR DINING:
1. ONLY suggest REAL, EXISTING restaurants, cafes, and food establishments
2. Use actual restaurant names that can be found on Google Maps
3. Do NOT create fictional or made-up names
4. Provide **15-20** REAL dining suggestions if available. Do not stop early unless there are truly fewer than 15 legitimate options; if fewer than 15 exist, return everything you can verify and explain the scarcity in the reasoning.
5. Ensure the list is DIVERSE. Cover every requested cuisine, diet, budget tier, and meal type. If users listed multiple cuisines or experiences, include at least one (ideally more) option per preference instead of repeating similar restaurants.
6. Consider the meal types selected (breakfast, lunch, dinner, brunch, late-night, snacks) and explicitly tag which meal(s) each venue is best for so members can act on their specific requests.

USER PREFERENCE CONSTRAINTS:
{pref_text if pref_text else '- Enforce any dietary, budget, or cuisine requirements inferred from the context.'}

INTELLIGENT FILTERING REQUIREMENTS:
- Carefully analyze the user's dietary restrictions and food preferences from the context
- Understand that "seafood", "fish", "non-veg", "meat" indicate non-vegetarian preferences
- Understand that "veg", "vegetarian", "pure veg" indicate vegetarian preferences
- Match restaurants to the user's actual dietary needs, not just keywords
- If user wants seafood lunch, suggest restaurants that serve seafood for lunch
- If user wants vegetarian breakfast, suggest restaurants that serve vegetarian food for breakfast
- Always respect the user's dietary choices and suggest appropriate establishments

MANDATORY FILTERING REQUIREMENTS:
- Analyze the user's dietary restrictions and food preferences carefully
- If user mentions vegetarian preferences (veg, vegetarian, pure veg, etc.), ONLY suggest vegetarian restaurants
- If user mentions non-vegetarian preferences (seafood, fish, meat, non-veg, etc.), ONLY suggest restaurants that serve those items
- If user specifies specific cuisines, ONLY suggest restaurants of that cuisine type
- If user specifies budget constraints, ONLY suggest restaurants within that price range
- If user specifies location preferences, ONLY suggest restaurants in those areas
- STRICTLY follow ALL user preferences and dietary restrictions - do not suggest restaurants that don't match their requirements
- NEVER suggest restaurants that contradict the user's dietary preferences
- ALWAYS match the meal type requested (breakfast, lunch, dinner, brunch, snacks)

Format your response as a JSON array with this structure:
[
  {{
    "name": "REAL Restaurant Name",
    "description": "Brief description of cuisine and atmosphere...",
    "price_range": "{currency}X-Y",
    "rating": 4.5,
    "features": ["Outdoor seating", "Vegetarian options", "Live music"],
    "location": "Actual area/neighborhood in {destination}",
    "meal_types": ["breakfast", "lunch", "dinner"],
    "why_recommended": "Why this restaurant matches the specific member preferences (quote the member names and their requests, e.g., “Harshini – vegan brunch”, “Aditya – seafood dinner”). Mention ratings only if two options are otherwise identical.",
    "preference_match_summary": ["MemberName – preference satisfied", "..."]
  }}
]

Respond ONLY with the JSON array, no additional text.
"""

    def _create_activities_prompt(self, destination: str, context: str, currency: str = '$', preference_constraints: Dict = None) -> str:
        """Create specific prompt for activities suggestions"""
        pref_text = self._build_preference_instructions(preference_constraints, currency)
        return f"""
You are a travel activities expert AI assistant helping users find REAL ACTIVITIES for their trip to {destination}.

User Context: {context}

CRITICAL REQUIREMENTS FOR ACTIVITIES:
1. ONLY suggest REAL, EXISTING tourist attractions, activities, and experiences
2. Use actual attraction names that can be found on Google Maps
3. Do NOT create fictional or made-up names
4. Focus on well-known, visitable establishments
5. Provide 5-12 REAL activity suggestions
6. MATCH the user's selected activity types and preferences EXACTLY

USER PREFERENCE CONSTRAINTS:
{pref_text if pref_text else '- Honor activity types, budgets, and group needs mentioned in the context.'}

IMPORTANT: Pay special attention to:
- If user selected "Adventure" activities, suggest adventure sports, hiking, water sports, etc.
- If user selected "Cultural" activities, suggest museums, temples, historical sites, etc.
- If user selected "Nature" activities, suggest parks, gardens, wildlife sanctuaries, etc.
- If user selected "Food & Drink" activities, suggest food tours, cooking classes, local markets, etc.
- If user selected "Relaxation" activities, suggest spas, beaches, peaceful gardens, etc.
- If user selected "Nightlife" activities, suggest bars, clubs, evening entertainment, etc.
- If user selected multiple types, suggest activities that combine these interests

Format your response as a JSON array with this structure:
[
  {{
    "name": "REAL Attraction/Activity Name",
    "description": "Brief description of what visitors can do...",
    "price_range": "{currency}X-Y",
    "rating": 4.5,
    "features": ["Guided tours", "Photo opportunities", "Family-friendly"],
    "location": "Actual area/neighborhood in {destination}",
    "why_recommended": "Why this activity matches their specific preferences"
  }}
]

Respond ONLY with the JSON array, no additional text.
"""

    def _create_generic_prompt(self, room_type: str, destination: str, context: str, currency: str = '$', preference_constraints: Dict = None) -> str:
        """Create generic prompt for other room types"""
        pref_text = self._build_preference_instructions(preference_constraints, currency)
        return f"""
You are a travel expert AI assistant helping users find REAL, EXISTING {room_type} options for their trip to {destination}.

User Context: {context}

CRITICAL REQUIREMENTS:
1. ONLY suggest REAL, EXISTING places that can be found on Google Maps
2. Use actual property names, hotel names, restaurant names, or attraction names
3. Do NOT create fictional or made-up names
4. Focus on well-known, searchable establishments
5. Use the user's specific preferences to filter and recommend from real options
6. Provide 5-12 suggestions (not 3-5)
7. Each suggestion must be a real, bookable option

USER PREFERENCE CONSTRAINTS:
{pref_text if pref_text else '- Strictly adhere to the budget and preference details included in the context.'}

Format your response as a JSON array with this structure:
[
  {{
    "name": "REAL Place Name",
    "description": "Brief description of this real place and why it matches their preferences...",
    "price_range": "{currency}X-Y",
    "rating": 4.5,
    "features": ["Real Feature 1", "Real Feature 2", "Real Feature 3"],
    "location": "Actual area/neighborhood in {destination}",
    "why_recommended": "Why this real place matches their specific preferences"
  }}
]

Respond ONLY with the JSON array, no additional text.
"""
    
    def _parse_ai_response(self, response_text: str, room_type: str) -> List[Dict]:
        """Parse the AI response and extract suggestions"""
        try:
            print(f"\n{'='*80}")
            print(f"🔍 PARSING AI RESPONSE FOR {room_type}")
            print(f"{'='*80}")
            print(f"Raw response length: {len(response_text)} chars")
            print(f"First 200 chars of raw response:")
            print(repr(response_text[:200]))
            print(f"Last 100 chars of raw response:")
            print(repr(response_text[-100:]))
            
            # Clean the response text
            cleaned_text = response_text.strip()
            
            print(f"\nAfter strip:")
            print(f"  Starts with '```json': {cleaned_text.startswith('```json')}")
            print(f"  Starts with '```': {cleaned_text.startswith('```')}")
            print(f"  Ends with '```': {cleaned_text.endswith('```')}")
            
            # Remove markdown code blocks
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
                print("  → Removed '```json' prefix")
            elif cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]
                print("  → Removed '```' prefix")
                
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
                print("  → Removed '```' suffix")
            
            cleaned_text = cleaned_text.strip()
            
            # Try to extract JSON array if wrapped in text
            import re
            # Look for JSON array pattern
            json_match = re.search(r'\[[\s\S]*\]', cleaned_text)
            if json_match:
                cleaned_text = json_match.group(0)
                print("  → Extracted JSON array from text")
            
            # Fix common JSON issues
            # Replace single quotes with double quotes (but not inside strings)
            # This is a simple fix - for production, use a more robust solution
            cleaned_text = re.sub(r"'(\w+)':", r'"\1":', cleaned_text)  # Fix keys
            cleaned_text = re.sub(r":\s*'([^']*)'", r': "\1"', cleaned_text)  # Fix string values (simple)
            
            # Remove trailing commas before closing brackets/braces
            cleaned_text = re.sub(r',(\s*[}\]])', r'\1', cleaned_text)
            
            print(f"\nFinal cleaned text (first 200 chars):")
            print(repr(cleaned_text[:200]))
            print(f"\nAttempting JSON parse...")
            
            # Parse JSON
            suggestions = json.loads(cleaned_text)
            
            print(f"✅ Successfully parsed {len(suggestions)} suggestions")
            print(f"{'='*80}\n")
            
            # Add required fields
            for i, suggestion in enumerate(suggestions):
                suggestion['id'] = f"suggestion_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{i}"
                suggestion['room_type'] = room_type
                suggestion['created_at'] = datetime.utcnow().isoformat()
                
                # Ensure all required fields exist
                suggestion.setdefault('name', f"Option {i+1}")
                suggestion.setdefault('description', "AI-generated suggestion")
                suggestion.setdefault('price_range', "Price varies")
                suggestion.setdefault('rating', 4.0)
                suggestion.setdefault('features', [])
                suggestion.setdefault('location', "Location not specified")
                suggestion.setdefault('why_recommended', "Recommended based on your preferences")
            
            return suggestions
            
        except json.JSONDecodeError as e:
            print(f"\n{'='*80}")
            print(f"❌ JSON PARSE ERROR for {room_type}")
            print(f"{'='*80}")
            print(f"JSONDecodeError: {str(e)}")
            print(f"Error at line {e.lineno}, column {e.colno}, position {e.pos}")
            if 'cleaned_text' in locals():
                print(f"\nProblematic text (100 chars before and after error):")
                start = max(0, e.pos - 100)
                end = min(len(cleaned_text), e.pos + 100)
                print(repr(cleaned_text[start:end]))
                print(f"\nFull cleaned text being parsed:")
                print(cleaned_text)
            else:
                print(f"\nRaw response text (first 500 chars):")
                print(repr(response_text[:500]))
            print(f"{'='*80}\n")
            return self._get_fallback_suggestions(room_type, "destination")
        
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ PARSING ERROR for {room_type}")
            print(f"{'='*80}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            print(f"Full traceback:")
            print(traceback.format_exc())
            print(f"{'='*80}\n")
            return self._get_fallback_suggestions(room_type, "destination")
    
    def _enhance_with_maps(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> Dict:
        """Enhance suggestion with appropriate links based on suggestion type"""
        try:
            suggestion_name = suggestion.get('name', '').lower()
            suggestion_description = suggestion.get('description', '').lower()
            
            # Determine transportation type based on user preferences from answers
            transport_type = self._get_user_transportation_preference(answers, group_preferences)
            
            # Check if suggestion matches the user's transportation preference
            # TEMPORARY FIX: Force bus detection for testing
            if suggestion_name in ['redbus', 'kpn travels', 'parveen travels', 'srs travels', 'vrl travels', 'orange tours']:
                booking_url = self._create_transportation_booking_url(suggestion, destination, 'bus', answers, group_preferences)
                suggestion['booking_url'] = booking_url
                suggestion['external_url'] = booking_url
                suggestion['link_type'] = 'booking'
            elif transport_type and self._is_transportation_suggestion(suggestion_name, suggestion_description, transport_type.lower()):
                # Generate booking URL for the specific transportation type
                booking_url = self._create_transportation_booking_url(suggestion, destination, transport_type, answers, group_preferences)
                suggestion['booking_url'] = booking_url
                suggestion['external_url'] = booking_url
                suggestion['link_type'] = 'booking'
            else:
                # Generate Google Maps search URL for other suggestions
                maps_url = self._create_maps_url(suggestion, destination)
                suggestion['maps_url'] = maps_url
                suggestion['maps_embed_url'] = self._create_maps_embed_url(suggestion, destination)
                suggestion['external_url'] = maps_url
                suggestion['link_type'] = 'maps'
            
            return suggestion
            
        except Exception as e:
            pass
    
    def _create_flight_booking_url(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> str:
        """Create a flight booking search URL with specific travel details"""
        try:
            import urllib.parse
            from datetime import datetime, UTC
            
            # Extract travel details from answers and group preferences
            departure_date = None
            return_date = None
            from_location = None
            
            # Get dates from answers
            if answers:
                for answer in answers:
                    question_text = answer.get('question_text', '').lower()
                    answer_value = answer.get('answer_value')
                    answer_text = answer.get('answer_text')  # Also check answer_text
                    
                    if 'departure date' in question_text:
                        departure_date = answer_value or answer_text
                    elif 'return date' in question_text:
                        return_date = answer_value or answer_text
            
            # Get source location from group preferences
            if group_preferences:
                from_location = group_preferences.get('from_location', '')
            
            # Fallback to group dates if room dates not provided
            if not departure_date and group_preferences:
                departure_date = group_preferences.get('start_date', '')
            if not return_date and group_preferences:
                return_date = group_preferences.get('end_date', '')
            
            # Clean destination
            destination_clean = destination.replace(',', '').strip()
            
            # Format dates for URLs
            def format_date_for_url(date_str):
                if not date_str:
                    return ''
                try:
                    # Handle ISO format dates
                    if 'T' in date_str:
                        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    return date_obj.strftime('%Y-%m-%d')
                except:
                    return ''
            
            departure_formatted = format_date_for_url(departure_date)
            return_formatted = format_date_for_url(return_date)
            
            # Create airline-specific booking URLs
            airline_name = suggestion.get('name', '').lower()
            airline_url = self._create_airline_specific_url(airline_name, from_location, destination_clean, departure_formatted, return_formatted)
            
            if airline_url:
                return airline_url
            
            # Fallback to Google Flights with specific details
            if departure_formatted:
                if return_formatted:
                    # Round trip
                    google_url = f"https://www.google.com/flights?q=Flights+from+{urllib.parse.quote_plus(from_location)}+to+{urllib.parse.quote_plus(destination_clean)}+on+{departure_formatted}+returning+{return_formatted}"
                else:
                    # One way
                    google_url = f"https://www.google.com/flights?q=Flights+from+{urllib.parse.quote_plus(from_location)}+to+{urllib.parse.quote_plus(destination_clean)}+on+{departure_formatted}"
            else:
                # Fallback without specific dates
                google_url = f"https://www.google.com/flights?q=Flights+from+{urllib.parse.quote_plus(from_location)}+to+{urllib.parse.quote_plus(destination_clean)}"
            
            return google_url
            
        except Exception as e:
            # Fallback to basic Google Flights
            import urllib.parse
            encoded_destination = urllib.parse.quote_plus(destination)
            return f"https://www.google.com/flights?q=Flights+to+{encoded_destination}"
    
    def _create_airline_specific_url(self, airline_name: str, from_location: str, destination: str, departure_date: str, return_date: str) -> str:
        """Create airline-specific booking URLs using AI to determine the airline's website"""
        try:
            import urllib.parse
            
            # Use the actual locations as provided (no hardcoded mapping)
            from_clean = urllib.parse.quote_plus(from_location.strip())
            dest_clean = urllib.parse.quote_plus(destination.strip())
            
            # Use AI to determine the airline's booking website
            airline_prompt = f"""
            What is the official booking website for {airline_name}?
            
            Respond with only the domain name (e.g., "emirates.com" or "qatarairways.com").
            If you don't know the exact domain, respond with "UNKNOWN".
            """
            
            try:
                response = self.model.generate_content(airline_prompt)
                airline_domain = response.text.strip().lower()
                
                if airline_domain and airline_domain != "unknown" and "." in airline_domain:
                    # Create dynamic booking URL with actual travel details
                    if return_date:
                        return f"https://www.{airline_domain}/book/?origin={from_clean}&destination={dest_clean}&departure={departure_date}&return={return_date}&tripType=roundtrip"
                    else:
                        return f"https://www.{airline_domain}/book/?origin={from_clean}&destination={dest_clean}&departure={departure_date}&tripType=oneway"
                else:
                    return None
                    
            except Exception as ai_error:
                return None
            
        except Exception as e:
            return None
    
    def _is_transportation_suggestion(self, name: str, description: str, transport_type: str) -> bool:
        """Dynamically determine if a suggestion is a specific type of transportation using AI analysis"""
        try:
            # Use AI to analyze the suggestion type
            analysis_prompt = f"""
            Analyze this travel suggestion and determine if it's a {transport_type} service or something else.
            
            Name: {name}
            Description: {description}
            
            Respond with only "{transport_type.upper()}" if it's a {transport_type} service, or "OTHER" if it's anything else.
            """
            
            response = self.model.generate_content(analysis_prompt)
            result = response.text.strip().upper()
            
            return result == transport_type.upper()
            
        except Exception as e:
            # Fallback to basic pattern matching
            return self._fallback_transportation_detection(name, description, transport_type)
    
    def _fallback_transportation_detection(self, name: str, description: str, transport_type: str) -> bool:
        """Fallback pattern-based transportation detection"""
        text = f"{name} {description}".lower()
        
        if transport_type == 'flight':
            flight_terms = ['airline', 'airlines', 'airways', 'aviation', 'aircraft', 'flight', 'air', 'fly', 'flying', 'airport', 'terminal', 'gate', 'departure', 'arrival', 'boarding', 'check-in', 'baggage', 'seat', 'cabin', 'pilot', 'crew', 'passenger', 'booking', 'reservation']
            return any(term in text for term in flight_terms)
        elif transport_type == 'train':
            train_terms = ['railway', 'railways', 'train', 'trains', 'rail', 'metro', 'subway', 'locomotive', 'station', 'platform', 'express', 'mail', 'passenger', 'booking', 'ticket', 'fare', 'route', 'journey']
            return any(term in text for term in train_terms)
        elif transport_type == 'bus':
            bus_terms = ['bus', 'buses', 'coach', 'coaches', 'transit', 'public transport', 'shuttle', 'redbus', 'travels', 'operator', 'transport', 'booking', 'ticket', 'fare', 'route', 'journey', 'smartbus', 'intrcity', 'orange', 'kpn', 'parveen']
            return any(term in text for term in bus_terms)
        elif transport_type == 'car':
            car_terms = ['rental', 'car', 'vehicle', 'hire', 'drive', 'automobile', 'taxi', 'cab']
            return any(term in text for term in car_terms)
        
        return False
    
    def _get_user_transportation_preference(self, answers: List[Dict], group_preferences: Dict = None) -> str:
        """Extract user's transportation preference from answers - STRICT MATCHING
        Prioritizes answers matching the current trip_leg if specified in group_preferences"""
        if not answers:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ No answers provided")
            return None
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Analyzing {len(answers)} answers for transportation preference...")
        
        # Get current trip_leg from group_preferences
        current_trip_leg = (group_preferences.get('trip_leg') or '').lower() if group_preferences else ''
        if current_trip_leg:
            logger.info(f"🎯 Prioritizing answers for trip_leg: '{current_trip_leg}'")
        
        # Normalize transport type mappings (case-insensitive)
        transport_mapping = {
            'bus': 'bus',
            'train': 'train',
            'flight': 'flight',
            'flights': 'flight',
            'airplane': 'flight',
            'plane': 'flight',
            'airline': 'flight',
            'car rental': 'car rental',
            'car': 'car rental',
            'rental': 'car rental',
            'mixed': 'mixed'
        }
        
        # Debug: print all answers
        for i, answer in enumerate(answers):
            question_text = answer.get('question_text', '')
            question_id = answer.get('question_id', 'N/A')
            answer_value = answer.get('answer_value')
            answer_text = answer.get('answer_text')
            section = (answer.get('section') or answer.get('trip_leg') or '').lower()
            
            logger.info(f"   Answer {i+1}:")
            logger.info(f"      ID: {question_id}")
            logger.info(f"      Q: {question_text}")
            logger.info(f"      Section/TripLeg: {section}")
            logger.info(f"      A (value): {answer_value} (type: {type(answer_value).__name__})")
            logger.info(f"      A (text): {answer_text}")
        
        # First pass: Look for explicit transportation preference question
        # Prioritize answers matching current trip_leg
        leg_specific_answers = []
        general_answers = []
        
        for answer in answers:
            section = (answer.get('section') or answer.get('trip_leg') or '').lower()
            if current_trip_leg and section == current_trip_leg:
                leg_specific_answers.append(answer)
            else:
                general_answers.append(answer)
        
        # Check leg-specific answers first, then general answers
        answers_to_check = leg_specific_answers + general_answers if current_trip_leg else answers
        
        for answer in answers_to_check:
            question_text = answer.get('question_text', '').lower()
            question_id = answer.get('question_id', '')
            answer_value = answer.get('answer_value')
            answer_text = answer.get('answer_text')
            
            # CRITICAL: Check for transportation preference question specifically
            is_transport_question = (
                ('transportation' in question_text and 'prefer' in question_text) or
                ('transportation' in question_text and 'method' in question_text) or
                ('what transportation' in question_text) or
                ('preferred transportation' in question_text) or
                ('travel' in question_text and 'prefer' in question_text and 'method' in question_text) or
                # Also check question_id for transport-related IDs
                ('transport' in question_id.lower() and 'prefer' in question_id.lower())
            )
            
            # Fallback: If question_text is empty but answer_value is a known transport type,
            # and this answer is in the leg-specific bucket, treat it as transport preference
            if not is_transport_question and not question_text and answer_value:
                answer_str = str(answer_value).strip().lower()
                if answer_str in transport_mapping and answer in leg_specific_answers:
                    is_transport_question = True
                    logger.info(f"   Treating '{answer_value}' as transport preference (leg-specific answer with transport value)")
            
            if is_transport_question:
                # Get the actual answer value (check both fields)
                value_to_check = answer_value
                if not value_to_check and answer_text:
                    value_to_check = answer_text
                
                if not value_to_check:
                    continue
                
                # Handle different answer formats
                if isinstance(value_to_check, list):
                    # Multiple selection - take first and normalize
                    if value_to_check:
                        result = str(value_to_check[0]).strip()
                        normalized = transport_mapping.get(result.lower(), result.lower())
                        logger.info(f"✅ Found transportation preference (from list): '{result}' -> normalized: '{normalized}'")
                        return normalized
                elif isinstance(value_to_check, str):
                    # Direct string - normalize it
                    result = value_to_check.strip()
                    normalized = transport_mapping.get(result.lower(), result.lower())
                    logger.info(f"✅ Found transportation preference (as string): '{result}' -> normalized: '{normalized}'")
                    return normalized
                elif isinstance(value_to_check, dict):
                    # Sometimes answers are wrapped in objects
                    value = value_to_check.get('value') or value_to_check.get('answer_value') or value_to_check.get('text')
                    if value:
                        result = str(value).strip()
                        normalized = transport_mapping.get(result.lower(), result.lower())
                        logger.info(f"✅ Found transportation preference (from object): '{result}' -> normalized: '{normalized}'")
                        return normalized
        
        # Second pass: Check ALL answers for transport keywords as fallback
        logger.warning("⚠️ No explicit transportation preference found - checking all answers for keywords...")
        for answer in answers_to_check:
            answer_value = answer.get('answer_value')
            answer_text = answer.get('answer_text')
            
            # Combine all text values
            text_to_check = ''
            if isinstance(answer_value, str):
                text_to_check = answer_value.lower()
            elif isinstance(answer_value, list):
                text_to_check = ' '.join([str(v).lower() for v in answer_value])
            elif isinstance(answer_value, dict):
                text_to_check = str(answer_value.get('value') or answer_value.get('text') or '').lower()
            
            if answer_text:
                text_to_check += ' ' + str(answer_text).lower()
            
            # Check if answer contains transport keywords
            for keyword, transport_type in transport_mapping.items():
                if keyword in text_to_check:
                    logger.info(f"✅ Found transportation keyword '{keyword}' in answer -> '{transport_type}'")
                    return transport_type
        
        logger.warning("⚠️ No transportation preference found in any answers")
        return None
    
    def _extract_departure_date(self, answers: List[Dict], group_preferences: Dict = None) -> str:
        """Extract departure date from answers, with fallback to group_preferences['start_date']"""
        if not answers:
            # Fallback to group start_date if available
            if group_preferences and group_preferences.get('start_date'):
                start_date = group_preferences['start_date']
                # Handle ISO format dates
                if 'T' in str(start_date):
                    return str(start_date).split('T')[0]
                return str(start_date)
            return "2024-10-25"  # Default date
        
        for answer in answers:
            question_text = (answer.get('question_text') or '').lower()
            section = (answer.get('section') or answer.get('trip_leg') or '').lower()
            question_id = (answer.get('question_id') or '').lower()
            
            # Check if this is a departure date answer by multiple criteria
            is_departure_date = (
                ('departure' in question_text and 'date' in question_text) or
                (section == 'departure' and 'date' in question_text) or
                (section == 'departure' and isinstance(answer.get('answer_value'), str) and len(answer.get('answer_value', '')) == 10)  # Date format YYYY-MM-DD
            )
            
            if is_departure_date:
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        
        # Fallback to group start_date if available
        if group_preferences and group_preferences.get('start_date'):
            start_date = group_preferences['start_date']
            # Handle ISO format dates
            if 'T' in str(start_date):
                return str(start_date).split('T')[0]
            return str(start_date)
        
        return "2024-10-25"  # Default date
    
    def _extract_return_date(self, answers: List[Dict], group_preferences: Dict = None) -> str:
        """Extract return date from answers, with fallback to group_preferences['end_date']"""
        if not answers:
            # Fallback to group end_date if available
            if group_preferences and group_preferences.get('end_date'):
                end_date = group_preferences['end_date']
                # Handle ISO format dates
                if 'T' in str(end_date):
                    return str(end_date).split('T')[0]
                return str(end_date)
            return "2024-10-27"  # Default date
        
        for answer in answers:
            question_text = (answer.get('question_text') or '').lower()
            section = (answer.get('section') or '').lower()
            trip_leg = (answer.get('trip_leg') or '').lower()
            question_id = (answer.get('question_id') or '').lower()
            
            # Check if this is a return date answer by multiple criteria
            is_return_date = (
                ('return' in question_text and 'date' in question_text) or
                (section == 'return' and 'date' in question_text) or
                (trip_leg == 'return' and 'date' in question_text) or
                ('return' in question_id and 'date' in question_id) or
                (section == 'return' and isinstance(answer.get('answer_value'), str) and len(answer.get('answer_value', '')) == 10)  # Date format YYYY-MM-DD
            )
            
            if is_return_date:
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        
        # Fallback to group end_date if available
        if group_preferences and group_preferences.get('end_date'):
            end_date = group_preferences['end_date']
            # Handle ISO format dates
            if 'T' in str(end_date):
                return str(end_date).split('T')[0]
            return str(end_date)
        
        return "2024-10-27"  # Default date
    
    def _create_transportation_booking_url(self, suggestion: Dict, destination: str, transport_type: str, answers: List[Dict] = None, group_preferences: Dict = None) -> str:
        """Create booking URL based on transportation type"""
        if transport_type.lower() == 'flight':
            return self._create_flight_booking_url(suggestion, destination, answers, group_preferences)
        elif transport_type.lower() == 'train':
            return self._create_train_booking_url(suggestion, destination, answers, group_preferences)
        elif transport_type.lower() == 'bus':
            return self._create_bus_booking_url(suggestion, destination, answers, group_preferences)
        elif transport_type.lower() == 'car rental':
            return self._create_car_rental_booking_url(suggestion, destination, answers, group_preferences)
        else:
            # For other transportation types, use Google Maps
            return self._create_maps_url(suggestion, destination)
    
    def _create_train_booking_url(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> str:
        """Create train booking URL using EaseMyTrip"""
        try:
            import urllib.parse
            
            # Extract travel details
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            departure_date = self._extract_departure_date(answers, group_preferences)
            return_date = self._extract_return_date(answers, group_preferences)
            
            # Use EaseMyTrip for train bookings
            easemytrip_url = f"https://www.easemytrip.com/railways/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={departure_date}"
            return easemytrip_url
            
        except Exception as e:
            return self._create_maps_url(suggestion, destination)
    
    def _generate_train_booking_url_with_ai(self, from_location: str, destination: str, departure_date: str, return_date: str) -> str:
        """Use AI to generate the most appropriate train booking URL for any location"""
        try:
            prompt = f"""
            Generate the most appropriate train booking URL for travel from "{from_location}" to "{destination}" on {departure_date}.
            
            Consider the countries/regions involved and provide a working booking URL for the most popular train booking website in that region.
            
            Examples of appropriate URLs:
            - For India: https://www.irctc.co.in/nget/train-search?from=FROM&to=TO&departure=DATE
            - For USA: https://www.amtrak.com/home?from=FROM&to=TO&departure=DATE
            - For Europe: https://www.thetrainline.com/search?from=FROM&to=TO&departure=DATE
            - For Japan: https://www.jrpass.com/ or https://www.hyperdia.com/
            - For China: https://www.trip.com/trains/
            
            Respond with ONLY the complete booking URL, properly formatted with the actual locations and date.
            Use URL encoding for special characters in location names.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            # Validate that it looks like a URL
            if result.startswith('http') and ('train' in result.lower() or 'rail' in result.lower() or 'amtrak' in result.lower() or 'irctc' in result.lower()):
                return result
            else:
                # Fallback to generic train booking
                import urllib.parse
                return f"https://www.thetrainline.com/search?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={departure_date}"
                
        except Exception as e:
            # Fallback to generic train booking
            import urllib.parse
            return f"https://www.thetrainline.com/search?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={departure_date}"
    
    def _create_bus_booking_url(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> str:
        """Create bus booking URL using EaseMyTrip"""
        try:
            import urllib.parse
            
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            departure_date = self._extract_departure_date(answers, group_preferences)
            
            # Use EaseMyTrip for bus bookings
            easemytrip_url = f"https://www.easemytrip.com/bus/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={departure_date}"
            return easemytrip_url
            
        except Exception as e:
            return self._create_maps_url(suggestion, destination)
    
    def _generate_bus_booking_url_with_ai(self, from_location: str, destination: str, departure_date: str) -> str:
        """Use AI to generate the most appropriate bus booking URL for any location"""
        try:
            prompt = f"""
            Generate the most appropriate bus booking URL for travel from "{from_location}" to "{destination}" on {departure_date}.
            
            Consider the countries/regions involved and provide a working booking URL for the most popular bus booking website in that region.
            
            Examples of appropriate URLs:
            - For India: https://www.redbus.in/bus-tickets/FROM-TO?date=DATE
            - For USA/Canada: https://www.greyhound.com/search?from=FROM&to=TO&departure=DATE
            - For Europe: https://www.flixbus.com/bus/FROM-TO?departure=DATE
            - For Latin America: https://www.busbud.com/en/search?from=FROM&to=TO&departure=DATE
            - For Asia: https://www.busbud.com/en/search?from=FROM&to=TO&departure=DATE
            
            Respond with ONLY the complete booking URL, properly formatted with the actual locations and date.
            Use URL encoding for special characters in location names.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            # Validate that it looks like a URL
            if result.startswith('http') and ('bus' in result.lower() or 'greyhound' in result.lower() or 'redbus' in result.lower() or 'flixbus' in result.lower()):
                return result
            else:
                # Fallback to generic bus booking
                import urllib.parse
                return f"https://www.busbud.com/en/search?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={departure_date}"
                
        except Exception as e:
            # Fallback to generic bus booking
            import urllib.parse
            return f"https://www.busbud.com/en/search?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={departure_date}"
    
    def _create_car_rental_booking_url(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> str:
        """Create car rental booking URL using AI to generate appropriate booking site for any location"""
        try:
            import urllib.parse
            
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            departure_date = self._extract_departure_date(answers)
            return_date = self._extract_return_date(answers, group_preferences)
            
            # Use AI to generate the best car rental booking URL for this specific route
            booking_url = self._generate_car_rental_booking_url_with_ai(from_location, destination, departure_date, return_date)
            return booking_url
            
        except Exception as e:
            return self._create_maps_url(suggestion, destination)
    
    def _generate_car_rental_booking_url_with_ai(self, from_location: str, destination: str, departure_date: str, return_date: str) -> str:
        """Use AI to generate the most appropriate car rental booking URL for any location"""
        try:
            prompt = f"""
            Generate the most appropriate car rental booking URL for travel from "{from_location}" to "{destination}" from {departure_date} to {return_date}.
            
            Consider the countries/regions involved and provide a working booking URL for the most popular car rental booking website in that region.
            
            Examples of appropriate URLs:
            - For global coverage: https://www.rentalcars.com/en/city/DESTINATION/?pickupDate=DATE&returnDate=DATE
            - For USA: https://www.hertz.com/rentacar/reservation/?pickupLocation=FROM&returnLocation=TO&pickupDate=DATE&returnDate=DATE
            - For Europe: https://www.europcar.com/en-us/car-rental/DESTINATION/?pickupDate=DATE&returnDate=DATE
            - For Asia: https://www.avis.com/en/locations?pickupLocation=FROM&returnLocation=TO&pickupDate=DATE&returnDate=DATE
            
            Respond with ONLY the complete booking URL, properly formatted with the actual locations and dates.
            Use URL encoding for special characters in location names.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            # Validate that it looks like a URL
            if result.startswith('http') and ('rental' in result.lower() or 'hertz' in result.lower() or 'avis' in result.lower() or 'europcar' in result.lower()):
                return result
            else:
                # Fallback to generic car rental booking
                import urllib.parse
                return f"https://www.rentalcars.com/en/city/{urllib.parse.quote(destination.lower())}/?pickupDate={departure_date}&returnDate={return_date}"
                
        except Exception as e:
            # Fallback to generic car rental booking
            import urllib.parse
            return f"https://www.rentalcars.com/en/city/{urllib.parse.quote(destination.lower())}/?pickupDate={departure_date}&returnDate={return_date}"
    
    def _create_maps_url(self, suggestion: Dict, destination: str) -> str:
        """Create a Google Maps search URL"""
        try:
            import urllib.parse
            # Create a Google Maps search URL for the exact property name
            place_name = suggestion.get('name', '')
            location = suggestion.get('location', '')
            
            # Build search query for the exact property
            if place_name:
                # Search for the exact property name first
                search_query = f'"{place_name}"'
                if location:
                    search_query += f' {location}'
                if destination:
                    search_query += f' {destination}'
            else:
                # Fallback to location-based search
                search_query = f"{location} {destination}" if location else destination
            
            # URL encode the search query
            encoded_query = urllib.parse.quote_plus(search_query)
            
            # Create Google Maps search URL
            maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            return maps_url
            
        except Exception as e:
            # Fallback to basic destination search
            import urllib.parse
            encoded_destination = urllib.parse.quote_plus(destination)
            return f"https://www.google.com/maps/search/?api=1&query={encoded_destination}"
    
    def _generate_transportation_suggestions(self, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate transportation suggestions using real EaseMyTrip data"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            departure_date = self._extract_departure_date(answers, group_preferences)
            return_date = self._extract_return_date(answers, group_preferences)
            
            # Determine if this is a return trip
            trip_leg = (group_preferences.get('trip_leg') or '').lower() if group_preferences else ''
            is_return_trip = trip_leg == 'return'
            
            # Use return_date for return trips, departure_date for departure trips
            travel_date = return_date if is_return_trip and return_date else departure_date
            
            # Get user's transportation preference (prioritize answers matching current trip_leg)
            transport_type = self._get_user_transportation_preference(answers, group_preferences)
            
            # Determine if this is international travel
            is_international = self._is_international_travel(from_location, destination)
            
            # Debug logging
            logger.info(f"🔍 TRANSPORTATION REQUEST DEBUG:")
            logger.info(f"   From: {from_location}, To: {destination}")
            logger.info(f"   International: {is_international}")
            logger.info(f"   Trip Leg: {trip_leg or 'departure'}")
            logger.info(f"   Departure Date: {departure_date}, Return Date: {return_date}")
            logger.info(f"   Using Travel Date: {travel_date}")
            logger.info(f"   Detected Transport Type: {transport_type}")
            logger.info(f"   Transport Type Lower: {transport_type.lower() if transport_type else None}")
            
            suggestions = []
            
            # CRITICAL: Only generate suggestions for user's selected transport type
            # Respect user choice - if they select Bus, ONLY show buses - NO FALLBACKS
            transport_type_lower = transport_type.lower() if transport_type else ''
            
            if transport_type_lower == 'bus':
                logger.info("🚌 Generating BUS suggestions ONLY (user selected Bus) - NO FALLBACK TO FLIGHTS")
                bus_suggestions = self.easemytrip_service.get_bus_options(from_location, destination, travel_date)
                if not bus_suggestions:
                    logger.warning("⚠️ No bus suggestions returned - returning empty array instead of falling back to flights")
                    suggestions = []
                else:
                    suggestions = self._enhance_transport_suggestions(
                        bus_suggestions,
                        from_location, destination, answers, group_preferences
                    )
            elif transport_type_lower == 'train':
                logger.info("🚂 Generating TRAIN suggestions ONLY (user selected Train) - NO FALLBACK TO FLIGHTS")
                train_suggestions = self.easemytrip_service.get_train_options(from_location, destination, travel_date)
                if not train_suggestions:
                    logger.warning("⚠️ No train suggestions returned - returning empty array instead of falling back to flights")
                    suggestions = []
                else:
                    suggestions = self._enhance_transport_suggestions(
                        train_suggestions,
                        from_location, destination, answers, group_preferences
                    )
            elif transport_type_lower == 'flight' or transport_type_lower == 'flights':
                logger.info("✈️ Generating FLIGHT suggestions ONLY (user selected Flight)...")
                flight_suggestions = self._generate_ai_flight_suggestions(from_location, destination, departure_date, return_date, passengers=1, class_type="Economy", answers=answers)
                suggestions = self._enhance_transport_suggestions(
                    flight_suggestions if flight_suggestions else [],
                    from_location, destination, answers, group_preferences
                )
            elif transport_type:
                # User selected something other than bus/train/flight
                logger.warning(f"⚠️ Unrecognized transport type '{transport_type}' - returning empty suggestions")
                suggestions = []
            else:
                # Only fallback if NO preference was selected
                logger.warning(f"⚠️ No transport preference selected - defaulting based on route...")
                if is_international:
                    logger.info(f"⚠️ No preference - INTERNATIONAL travel, defaulting to FLIGHTS...")
                    flight_suggestions = self._generate_ai_flight_suggestions(from_location, destination, departure_date, return_date, passengers=1, class_type="Economy", answers=answers)
                    suggestions = self._enhance_transport_suggestions(
                        flight_suggestions if flight_suggestions else [],
                        from_location, destination, answers, group_preferences
                    )
                else:
                    logger.info(f"⚠️ No preference - domestic travel, defaulting to BUS...")
                    bus_suggestions = self.easemytrip_service.get_bus_options(from_location, destination, travel_date)
                    suggestions = self._enhance_transport_suggestions(
                        bus_suggestions if bus_suggestions else [],
                        from_location, destination, answers, group_preferences
                    )
            
            logger.info(f"✅ Generated {len(suggestions)} suggestions")
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Error generating transportation suggestions: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._get_fallback_transportation_suggestions(destination, answers)
    
    def _is_international_travel(self, from_location: str, destination: str) -> bool:
        """Determine if travel is international by comparing currencies (no AI call)"""
        try:
            from utils import get_currency_from_destination
            
            from_currency = get_currency_from_destination(from_location)
            dest_currency = get_currency_from_destination(destination)
            
            if not from_currency or not dest_currency:
                return False
            
            # Different currencies → assume international
            return from_currency != dest_currency
            
        except Exception as e:
            print(f"Error determining international travel: {e}")
            return False
    
    def _extract_transport_preferences_ai(self, answers: List[Dict], trip_leg: str = 'departure') -> Dict:
        """Extract transportation preferences from user's textbox answers using AI.
        Returns structured preferences like bus_type, time_preference, amenities, etc."""
        if not answers:
            return {}
        
        # Find preference text answers for the specific trip leg
        preference_texts = []
        for answer in answers:
            section = (answer.get('section') or answer.get('trip_leg') or '').lower()
            question_text = (answer.get('question_text') or '').lower()
            answer_value = answer.get('answer_value', '')
            
            # Check if this is a preference text answer for the current trip leg
            is_preference_question = (
                'preference' in question_text or
                'specific' in question_text or
                'custom' in question_text
            )
            
            # Match trip leg or general preferences
            if (section == trip_leg or not section) and is_preference_question and answer_value:
                if isinstance(answer_value, str) and len(answer_value.strip()) > 0:
                    preference_texts.append(answer_value.strip())
        
        if not preference_texts:
            return {}
        
        # Combine all preference texts
        combined_preferences = ' '.join(preference_texts)
        
        # Use AI to extract structured preferences
        try:
            prompt = f"""Extract transportation preferences from this user text: "{combined_preferences}"

Return a JSON object with these fields (use null if not mentioned):
{{
  "bus_type": ["AC Sleeper", "Non-AC", "Sleeper", "Seater", "Semi-Sleeper"] or null,
  "time_preference": ["morning", "afternoon", "evening", "night", "late night"] or null,
  "amenities": ["WiFi", "Charging", "Blanket", "Water", "Snacks"] or null,
  "preferred_operators": [list of operator names] or null,
  "avoid_operators": [list of operator names to avoid] or null,
  "seat_preference": ["window", "aisle", "lower", "upper"] or null,
  "other_requirements": [any other specific requirements] or null
}}

Examples:
- "AC Sleeper bus, preferably night time" -> {{"bus_type": ["AC Sleeper"], "time_preference": ["night"]}}
- "I want morning train with WiFi" -> {{"time_preference": ["morning"], "amenities": ["WiFi"]}}
- "Avoid KSRTC, prefer VRL" -> {{"avoid_operators": ["KSRTC"], "preferred_operators": ["VRL"]}}

Return ONLY valid JSON, no other text."""
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            import json
            preferences = json.loads(response_text)
            return preferences
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Failed to extract preferences with AI: {e}, using fallback")
            # Fallback to simple keyword matching
            return self._extract_preferences_fallback(combined_preferences)
    
    def _extract_preferences_fallback(self, text: str) -> Dict:
        """Fallback preference extraction using keyword matching"""
        text_lower = text.lower()
        preferences = {}
        
        # Bus type detection
        bus_types = []
        if any(word in text_lower for word in ['ac sleeper', 'air conditioned sleeper', 'ac sleeper']):
            bus_types.append('AC Sleeper')
        if any(word in text_lower for word in ['non-ac', 'non ac', 'non air conditioned']):
            bus_types.append('Non-AC')
        if 'sleeper' in text_lower and 'ac sleeper' not in text_lower:
            bus_types.append('Sleeper')
        if 'seater' in text_lower:
            bus_types.append('Seater')
        if 'semi-sleeper' in text_lower or 'semi sleeper' in text_lower:
            bus_types.append('Semi-Sleeper')
        if bus_types:
            preferences['bus_type'] = bus_types
        
        # Time preference
        time_prefs = []
        if any(word in text_lower for word in ['morning', 'early morning', 'am']):
            time_prefs.append('morning')
        if any(word in text_lower for word in ['afternoon', 'noon']):
            time_prefs.append('afternoon')
        if any(word in text_lower for word in ['evening', 'evening']):
            time_prefs.append('evening')
        if any(word in text_lower for word in ['night', 'night time', 'nighttime', 'late night', 'overnight']):
            time_prefs.append('night')
        if time_prefs:
            preferences['time_preference'] = time_prefs
        
        return preferences
    
    def _filter_suggestions_by_preferences(self, suggestions: List[Dict], preferences: Dict) -> List[Dict]:
        """Filter suggestions based on extracted preferences"""
        if not preferences or not suggestions:
            return suggestions
        
        scored = []
        for suggestion in suggestions:
            score = 0
            suggestion_text = f"{suggestion.get('name', '')} {suggestion.get('description', '')} {suggestion.get('bus_type', '')} {suggestion.get('type', '')}".lower()
            departure_time = suggestion.get('departure_time', '')
            
            # Check bus type preference
            if preferences.get('bus_type'):
                preferred_types = [bt.lower() for bt in preferences['bus_type']]
                if any(pt in suggestion_text for pt in preferred_types):
                    score += 10
                else:
                    score -= 5  # Penalize if doesn't match
            
            # Check time preference
            if preferences.get('time_preference') and departure_time:
                time_prefs = [tp.lower() for tp in preferences['time_preference']]
                hour = self._extract_hour_from_time(departure_time)
                
                if 'night' in time_prefs and hour and (hour >= 20 or hour < 6):
                    score += 10
                elif 'morning' in time_prefs and hour and 6 <= hour < 12:
                    score += 10
                elif 'afternoon' in time_prefs and hour and 12 <= hour < 17:
                    score += 10
                elif 'evening' in time_prefs and hour and 17 <= hour < 20:
                    score += 10
                else:
                    score -= 3  # Small penalty for not matching time
            
            # Check operator preferences
            if preferences.get('preferred_operators'):
                operator_name = suggestion.get('operator', '').lower()
                if any(op.lower() in operator_name for op in preferences['preferred_operators']):
                    score += 5
            
            if preferences.get('avoid_operators'):
                operator_name = suggestion.get('operator', '').lower()
                if any(op.lower() in operator_name for op in preferences['avoid_operators']):
                    score -= 20  # Strong penalty, but don't exclude completely
            
            suggestion['_preference_score'] = score
            scored.append(suggestion)

        filtered = [s for s in scored if s.get('_preference_score', 0) >= -10]
        MIN_RESULTS = 8
        if len(filtered) < MIN_RESULTS:
            filtered = scored[:]
        
        # Sort by preference score (highest first)
        filtered.sort(key=lambda x: x.get('_preference_score', 0), reverse=True)
        
        # Remove the score field before returning
        for suggestion in filtered:
            suggestion.pop('_preference_score', None)
        
        return filtered
    
    def _extract_hour_from_time(self, time_str: str) -> Optional[int]:
        """Extract hour (0-23) from time string like '22:30' or '10:45 PM'"""
        try:
            if 'PM' in time_str.upper() or 'AM' in time_str.upper():
                from datetime import datetime
                time_obj = datetime.strptime(time_str.strip(), '%I:%M %p')
                return time_obj.hour
            else:
                parts = time_str.split(':')
                if len(parts) >= 2:
                    return int(parts[0])
        except:
            pass
        return None

    def _enhance_transport_suggestions(self, suggestions: List[Dict], from_location: str, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> List[Dict]:
        """Enhance transportation suggestions - NO MAPS, ONLY EaseMyTrip booking URLs"""
        import urllib.parse
        
        # Extract preferences using AI
        trip_leg = (group_preferences.get('trip_leg') or 'departure').lower() if group_preferences else 'departure'
        preferences = self._extract_transport_preferences_ai(answers, trip_leg)
        
        # Filter suggestions based on preferences
        if preferences:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🎯 Filtering {len(suggestions)} suggestions based on preferences: {preferences}")
            suggestions = self._filter_suggestions_by_preferences(suggestions, preferences)
            logger.info(f"✅ Filtered to {len(suggestions)} matching suggestions")
        
        # Extract departure date from answers or group preferences
        
        # Extract departure date from answers or group preferences
        departure_date = self._extract_departure_date(answers, group_preferences) if answers else ''
        if not departure_date and group_preferences:
            departure_date = group_preferences.get('start_date', '2024-10-25')
        if not departure_date:
            departure_date = '2024-10-25'
        
        return_date = self._extract_return_date(answers, group_preferences) if answers else ''
        if not return_date and group_preferences:
            return_date = group_preferences.get('end_date', '')
        
        enhanced = []
        for suggestion in suggestions:
            # CRITICAL: Remove any maps URLs - transportation doesn't need maps
            if 'maps_url' in suggestion:
                del suggestion['maps_url']
            if 'maps_embed_url' in suggestion:
                del suggestion['maps_embed_url']
            
            # CRITICAL: Ensure booking URL is EaseMyTrip only
            # Determine transport type from suggestion - check multiple fields
            suggestion_name = (suggestion.get('name') or suggestion.get('title') or '').lower()
            suggestion_desc = (suggestion.get('description') or '').lower()
            suggestion_type = (suggestion.get('type') or '').lower()
            suggestion_operator = (suggestion.get('operator') or '').lower()
            
            # Combine all fields for checking
            combined_text = f"{suggestion_name} {suggestion_desc} {suggestion_type} {suggestion_operator}"
            
            # Format departure date - handle different date formats
            suggestion_departure = suggestion.get('departure_date') or suggestion.get('departure_time') or departure_date
            # Convert date format if needed (e.g., "30/10/2025" to "2025-10-30")
            if suggestion_departure and '/' in str(suggestion_departure):
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(suggestion_departure, '%d/%m/%Y')
                    suggestion_departure = date_obj.strftime('%Y-%m-%d')
                except:
                    pass  # Keep original format if conversion fails
            
            # Create EaseMyTrip URL based on transport type
            if any(word in combined_text for word in ['bus', 'travels', 'coach', 'ksrtc', 'vrl', 'orange', 'srs', 'kpn', 'neeta']):
                booking_url = f"https://www.easemytrip.com/bus/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={suggestion_departure}"
            elif any(word in combined_text for word in ['train', 'express', 'railway', 'rail']):
                booking_url = f"https://www.easemytrip.com/railways/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={suggestion_departure}"
            elif any(word in combined_text for word in ['flight', 'airline', 'airways', 'air', 'emirates', 'qatar', 'indi', 'jet', 'spice']):
                suggestion_return = suggestion.get('return_date') or return_date
                # Format return date if needed
                if suggestion_return and '/' in str(suggestion_return):
                    try:
                        from datetime import datetime
                        date_obj = datetime.strptime(suggestion_return, '%d/%m/%Y')
                        suggestion_return = date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
                if suggestion_return:
                    booking_url = f"https://www.easemytrip.com/flights/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={suggestion_departure}&return={suggestion_return}"
                else:
                    booking_url = f"https://www.easemytrip.com/flights/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={suggestion_departure}"
            else:
                # Default to bus
                booking_url = f"https://www.easemytrip.com/bus/?from={urllib.parse.quote(from_location)}&to={urllib.parse.quote(destination)}&departure={suggestion_departure}"
            
            # Set booking URLs - ensure EaseMyTrip only
            suggestion['booking_url'] = booking_url
            suggestion['external_url'] = booking_url
            suggestion['link_type'] = 'booking'
            
            enhanced.append(suggestion)
        
        return enhanced
    
    def _generate_flight_suggestions_ai(self, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate flight suggestions using AI (since EaseMyTrip flight API is complex)"""
        try:
            context = self._prepare_context('transportation', destination, answers, group_preferences, None)
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            from utils import get_currency_from_destination
            currency = get_currency_from_destination(from_location) if from_location else '$'
            
            prompt = f"""
You are a flight booking expert. Generate 5-8 REAL flight options for travel from {from_location} to {destination}.

User Context: {context}
Currency: {currency} (user's home currency for planning)

IMPORTANT: Only suggest REAL airlines and flights that actually exist and can be booked.

For each flight suggestion, provide:
- name: Real airline name (e.g., Emirates, Qatar Airways, IndiGo, SpiceJet)
- description: Brief description of the flight service
- price_range: Realistic price range in {currency}
- rating: Real airline rating
- features: Array of flight features (e.g., "Direct flight", "Free meals", "Entertainment")
- location: Departure/arrival airports
- why_recommended: Why this airline is recommended
- departure_time: Realistic departure time
- arrival_time: Realistic arrival time
- duration: Flight duration

JSON FORMAT:
{{
  "suggestions": [
    {{
      "name": "Emirates",
      "description": "Premium airline with excellent service",
      "price_range": "{currency}15,000-{currency}25,000",
      "rating": 4.5,
      "features": ["Direct flight", "Free meals", "Entertainment", "WiFi"],
      "location": "{from_location} to {destination}",
      "why_recommended": "Excellent service and on-time performance",
      "departure_time": "02:30 AM",
      "arrival_time": "08:45 AM",
      "duration": "6h 15m"
    }}
  ]
}}

Generate 5-8 realistic flight options.
"""
            
            response = self.model.generate_content(prompt)
            suggestions_text = response.text
            suggestions_data = json.loads(suggestions_text)
            suggestions = suggestions_data.get('suggestions', [])
            
            # Enhance with booking URLs
            enhanced_suggestions = []
            for suggestion in suggestions:
                enhanced = self._enhance_with_maps(suggestion, destination, answers, group_preferences)
                enhanced_suggestions.append(enhanced)
            
            return enhanced_suggestions
            
        except Exception as e:
            return self._get_fallback_transportation_suggestions(destination, answers)
    
    def _generate_ai_flight_suggestions(self, origin: str, destination: str, 
                                       departure_date: str, return_date: str = None, 
                                       passengers: int = 1, class_type: str = "Economy", answers: List[Dict] = None) -> List[Dict]:
        """Generate flight suggestions using AI - fully dynamic, no hardcoding"""
        try:
            # Get currency dynamically
            from utils import get_currency_from_destination
            currency = get_currency_from_destination(origin) if origin else '$'
            
            # Build context from user answers
            context = self._build_flight_context_from_answers(answers) if answers else ""
            
            # Create AI prompt
            prompt = f"""You are a flight booking expert. Generate realistic flight options.

TRIP DETAILS:
- From: {origin}
- To: {destination}
- Departure: {departure_date}
- Return: {return_date or 'One-way'}
- Passengers: {passengers}
- Class: {class_type}
- Currency: {currency}

{context}

INSTRUCTIONS:
1. Analyze the route (distance, popularity, international/domestic)
2. Select real airlines that operate this route
3. Price realistically based on route length, seasonality, and class
4. Use appropriate currency ({currency}) for the origin location
5. Provide 5-7 diverse options (budget to premium, direct to connecting)
6. Include realistic flight times and durations
7. Add relevant features (WiFi, meals, entertainment, etc.)

OUTPUT FORMAT (JSON):
{{
  "suggestions": [
    {{
      "airline": "Airline Name",
      "flight_number": "XX123",
      "price": 15000,
      "currency": "{currency}",
      "departure_time": "08:30",
      "arrival_time": "15:45",
      "duration": "9h 15m",
      "stops": "Direct",
      "class_type": "{class_type}",
      "seats_available": 15,
      "rating": 4.2,
      "features": ["Feature1", "Feature2"],
      "why_recommended": "Brief reason",
      "booking_url": "https://www.google.com/flights?q={origin}%20to%20{destination}",
      "name": "Airline Name",
      "description": "Flight description"
    }}
  ]
}}

Generate realistic, bookable options now."""
            
            # Call AI service
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                # Parse and return
                return self._parse_flight_response(response.text, origin, destination, departure_date, return_date)
            else:
                # Fallback to AI-generated fallback
                return self._generate_ai_flight_fallback(origin, destination, departure_date, return_date, currency, class_type)
            
        except Exception as e:
            print(f"Error generating flight suggestions: {e}")
            # Ultimate fallback
            return []
    
    def _build_flight_context_from_answers(self, answers: List[Dict]) -> str:
        """Extract relevant context from user answers dynamically"""
        context_parts = []
        
        for answer in answers:
            question = answer.get('question_text', '').lower()
            value = answer.get('answer_value')
            
            # Budget constraints
            if 'budget' in question or 'price' in question:
                if isinstance(value, dict) and 'min_value' in value:
                    context_parts.append(f"Budget: {value['min_value']} - {value['max_value']} per person")
                elif value:
                    context_parts.append(f"Budget preference: {value}")
            
            # Travel preferences
            elif 'prefer' in question or 'priority' in question:
                if value:
                    context_parts.append(f"User preference: {value}")
            
            # Timing preferences
            elif 'time' in question or 'departure' in question:
                if value:
                    context_parts.append(f"Timing: {value}")
        
        return "\n".join(f"- {part}" for part in context_parts) if context_parts else ""
    
    def _generate_ai_flight_fallback(self, origin: str, destination: str, departure_date: str, 
                                     return_date: str = None, currency: str = "₹", class_type: str = "Economy") -> List[Dict]:
        """Use AI to generate fallback data if parsing fails"""
        fallback_prompt = f"""Generate 3 simple flight options for {origin} to {destination} in {currency}.
Return ONLY valid JSON array:
[{{"airline":"Name","price":1000,"currency":"{currency}","duration":"2h 30m","departure_time":"08:00","arrival_time":"10:30","rating":4.0,"features":["Meals"]}}]"""
        
        try:
            import json
            import re
            response = self.model.generate_content(fallback_prompt)
            
            if response and response.text:
                json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
                if json_match:
                    flights = json.loads(json_match.group())
                    
                    # Add required fields
                    for flight in flights:
                        flight.update({
                            'origin': origin,
                            'destination': destination,
                            'departure_date': departure_date,
                            'return_date': return_date,
                            'location': f"{origin} to {destination}",
                            'name': flight.get('airline', 'Flight'),
                            'description': f"Flight to {destination}",
                            'booking_url': f"https://www.google.com/flights?q={origin}+to+{destination}",
                            'external_url': f"https://www.google.com/flights?q={origin}+to+{destination}",
                            'link_type': 'booking'
                        })
                    
                    return flights
        except Exception as e:
            print(f"Fallback error: {e}")
        
        return []

    def _parse_flight_response(self, ai_response: str, origin: str, destination: str, 
                              departure_date: str, return_date: str = None) -> List[Dict]:
        """Parse AI response into structured flight data"""
        try:
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                suggestions = parsed.get('suggestions', [])
                
                # Enrich each suggestion with metadata
                for suggestion in suggestions:
                    suggestion.update({
                        'origin': origin,
                        'destination': destination,
                        'departure_date': departure_date,
                        'return_date': return_date,
                        'location': f"{origin} to {destination}",
                        'name': suggestion.get('airline', 'Flight'),
                        'description': suggestion.get('description', f"Flight to {destination}"),
                        'external_url': suggestion.get('booking_url', f"https://www.google.com/flights?q={origin}+to+{destination}"),
                        'link_type': 'booking'
                    })
                
                return suggestions
            
            return []
        except Exception as e:
            print(f"Parse error: {e}")
        return []
    
    def _generate_accommodation_suggestions_places(self, destination: str, answers: List[Dict], group_preferences: Dict = None, preference_constraints: Dict = None) -> List[Dict]:
        """Generate accommodation suggestions using Google Places API"""
        try:
            print(f"\n{'='*50}")
            print(f"GENERATING ACCOMMODATION SUGGESTIONS")
            print(f"🔍 DESTINATION RECEIVED: '{destination}'")
            print(f"{'='*50}\n")
            
            # Extract user preferences and travel data
            context = self._prepare_context('accommodation', destination, answers, group_preferences, None)
            
            # Get currency
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            from utils import get_currency_from_destination
            currency = get_currency_from_destination(from_location) if from_location else '$'
            
            # Extract travel dates
            start_date = group_preferences.get('start_date', '') if group_preferences else ''
            end_date = group_preferences.get('end_date', '') if group_preferences else ''
            
            # Get user's accommodation preferences
            accommodation_preferences = self._extract_accommodation_preferences(answers)
            if preference_constraints:
                budget_pref = preference_constraints.get('budget')
                if budget_pref and not accommodation_preferences.get('budget_range'):
                    accommodation_preferences['budget_range'] = budget_pref
                    accommodation_preferences['BUDGET_RANGE'] = budget_pref
                if preference_constraints.get('types'):
                    accommodation_preferences.setdefault('accommodation_types', preference_constraints['types'])
                if preference_constraints.get('amenities'):
                    accommodation_preferences.setdefault('amenities', preference_constraints['amenities'])
                if preference_constraints.get('location'):
                    accommodation_preferences.setdefault('LOCATION_PREFERENCES', preference_constraints['location'])
            print(f"✓ Extracted preferences: {accommodation_preferences}")
            
            # OPTIMIZED: Search Google Places API with EXACT budget range in queries (filters at API level)
            places_results = self._search_google_places(destination, accommodation_preferences, currency)
            print(f"✓ Google Places returned {len(places_results)} results")
            
            # Format results based on user preferences
            suggestions = self._format_places_results(places_results, destination, context, currency, start_date, end_date, accommodation_preferences)
            print(f"✓ Formatted {len(suggestions)} suggestions")
            
            # OPTIMIZED: Since queries already include exact budget range and accommodation types,
            # we can skip expensive AI preference filtering - just do quick validation
            print(f"Before quick validation: {len(suggestions)} suggestions")
            
            # Only quick budget check to remove obvious outliers (no slow AI)
            suggestions = self._quick_budget_validation(suggestions, accommodation_preferences, currency)
            print(f"After quick budget validation: {len(suggestions)} suggestions")
            
            # Store suggestions in database for future reference (background, non-blocking)
            try:
                # Run in background thread to avoid blocking
                import threading
                threading.Thread(
                    target=self._store_accommodation_suggestions,
                    args=(suggestions, destination, answers, group_preferences),
                    daemon=True
                ).start()
            except Exception as e:
                print(f"Error starting background storage: {e}")
            
            # Return ALL suggestions (no pagination limit)
            print(f"✓ Returning all {len(suggestions)} suggestions")
            
            return suggestions
            
        except Exception as e:
            print(f"Error generating accommodation suggestions: {e}")
            return self._get_fallback_accommodation_suggestions(destination)
    
    def _generate_dining_suggestions_places_vertex(self, destination: str, answers: List[Dict], group_preferences: Dict = None, preference_constraints: Dict = None) -> List[Dict]:
        """Generate dining suggestions using Google Places API + Vertex AI for intelligent filtering"""
        try:
            print(f"\n{'='*50}")
            print(f"GENERATING DINING SUGGESTIONS (Places API + Vertex AI)")
            print(f"🔍 DESTINATION: '{destination}'")
            print(f"{'='*50}\n")
            
            # Extract user preferences
            context = self._prepare_context('dining', destination, answers, group_preferences, None)
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            from utils import get_currency_from_destination
            currency = get_currency_from_destination(from_location) if from_location else '$'
            
            # Extract dining preferences from answers
            dining_preferences = self._extract_dining_preferences(answers, preference_constraints)
            print(f"✓ Extracted dining preferences: {dining_preferences}")
            
            # Step 1: Get real restaurants from Google Places API
            places_results = self._search_google_places_dining(destination, dining_preferences, currency)
            print(f"✓ Google Places returned {len(places_results)} restaurant results")
            
            if not places_results:
                print("⚠️ No restaurants found from Places API, falling back to AI-only")
                return self._generate_dining_suggestions_ai_fallback(destination, answers, group_preferences, preference_constraints)
            
            # Step 2: Use Vertex AI to intelligently filter, rank, and describe based on user preferences
            suggestions = self._filter_and_rank_with_vertex_ai(
                places_results=places_results,
                room_type='dining',
                destination=destination,
                user_preferences=context,
                dining_preferences=dining_preferences,
                currency=currency
            )
            
            print(f"✓ Vertex AI filtered/ranked to {len(suggestions)} best matches")
            return suggestions
            
        except Exception as e:
            print(f"Error generating dining suggestions (Places + Vertex): {e}")
            import traceback
            traceback.print_exc()
            # Fallback to AI-only generation
            return self._generate_dining_suggestions_ai_fallback(destination, answers, group_preferences, preference_constraints)
    
    def _generate_activities_suggestions_places_vertex(self, destination: str, answers: List[Dict], group_preferences: Dict = None, preference_constraints: Dict = None) -> List[Dict]:
        """Generate activities suggestions using Google Places API + Vertex AI for intelligent filtering"""
        try:
            print(f"\n{'='*50}")
            print(f"GENERATING ACTIVITIES SUGGESTIONS (Places API + Vertex AI)")
            print(f"🔍 DESTINATION: '{destination}'")
            print(f"{'='*50}\n")
            
            # Extract user preferences
            context = self._prepare_context('activities', destination, answers, group_preferences, None)
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            from utils import get_currency_from_destination
            currency = get_currency_from_destination(from_location) if from_location else '$'
            
            # Extract activity preferences from answers
            activity_preferences = self._extract_activity_preferences(answers, preference_constraints)
            print(f"✓ Extracted activity preferences: {activity_preferences}")
            
            # Step 1: Get real activities/attractions from Google Places API
            places_results = self._search_google_places_activities(destination, activity_preferences, currency)
            print(f"✓ Google Places returned {len(places_results)} activity results")
            
            if not places_results:
                print("⚠️ No activities found from Places API, falling back to AI-only")
                return self._generate_activities_suggestions_ai_fallback(destination, answers, group_preferences, preference_constraints)
            
            # Step 2: Use Vertex AI to intelligently filter, rank, and describe based on user preferences
            suggestions = self._filter_and_rank_with_vertex_ai(
                places_results=places_results,
                room_type='activities',
                destination=destination,
                user_preferences=context,
                activity_preferences=activity_preferences,
                currency=currency
            )
            
            print(f"✓ Vertex AI filtered/ranked to {len(suggestions)} best matches")
            return suggestions
            
        except Exception as e:
            print(f"Error generating activities suggestions (Places + Vertex): {e}")
            import traceback
            traceback.print_exc()
            # Fallback to AI-only generation
            return self._generate_activities_suggestions_ai_fallback(destination, answers, group_preferences, preference_constraints)
    
    def _extract_accommodation_preferences(self, answers: List[Dict]) -> Dict:
        """Extract accommodation preferences from user answers completely dynamically - WITH CACHING"""
        # Create a cache key from answers
        cache_key = str([(a.get('question_text'), a.get('answer_value')) for a in answers])
        
        # Check cache first
        if cache_key in self._preferences_cache:
            print("✓ Using cached preferences")
            return self._preferences_cache[cache_key]
        
        preferences = {}
        
        for answer in answers:
            question_text = answer.get('question_text', '')
            answer_value = answer.get('answer_value')
            
            if not answer_value:
                continue
            
            # Use AI to determine the preference key and value dynamically
            preference_key, processed_value = self._process_user_answer_dynamically(question_text, answer_value)
            
            if preference_key and processed_value is not None:
                # Handle different data types dynamically
                if isinstance(processed_value, list):
                    if preference_key not in preferences:
                        preferences[preference_key] = []
                    preferences[preference_key].extend(processed_value)
                elif isinstance(processed_value, dict):
                    preferences[preference_key] = processed_value
                else:
                    preferences[preference_key] = processed_value
        
        print(f"✓ Extracted preferences (cached): {preferences}")
        
        # Cache the result
        self._preferences_cache[cache_key] = preferences
        
        return preferences
    
    def _process_user_answer_dynamically(self, question_text: str, answer_value) -> tuple:
        """Use AI to process user answers and determine preference key-value pairs"""
        try:
            prompt = f"""
            Process this user answer for accommodation preferences and determine the appropriate preference key and processed value.
            
            Question: "{question_text}"
            Answer: {answer_value}
            
            Determine:
            1. The most appropriate preference key name (e.g., "accommodation_types", "budget_range", "location_preferences", "amenities", "special_requirements")
            2. The processed value in the most useful format
            
            Examples:
            - Question: "What type of accommodation?" Answer: ["hotel", "resort"] → Key: "accommodation_types", Value: ["hotel", "resort"]
            - Question: "Budget range?" Answer: {{"min": 10000, "max": 25000}} → Key: "budget_range", Value: {{"min": 10000, "max": 25000}}
            - Question: "Location preference?" Answer: "near consulate" → Key: "location_preferences", Value: ["near consulate"]
            - Question: "Any special requirements?" Answer: "pet friendly" → Key: "special_requirements", Value: ["pet friendly"]
            
            Return in format: "KEY|VALUE"
            If no valid preference can be extracted, return "NONE|NONE"
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            if "|" in result and result != "NONE|NONE":
                key, value_str = result.split("|", 1)
                key = key.strip()
                value_str = value_str.strip()
                
                # Parse the value based on its content
                processed_value = self._parse_ai_value(value_str, answer_value)
                
                return key, processed_value
            
            return None, None
            
        except Exception as e:
            print(f"Error processing user answer dynamically: {e}")
            return None, None
    
    def _parse_ai_value(self, value_str: str, original_value) -> any:
        """Parse AI-generated value string into appropriate data type"""
        try:
            # Clean the value string
            value_str = value_str.strip()
            
            # Try to parse as JSON first
            if value_str.startswith('[') or value_str.startswith('{'):
                import json
                try:
                    return json.loads(value_str)
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract meaningful data
                    if value_str.startswith('[') and value_str.endswith(']'):
                        # Extract list items manually
                        content = value_str[1:-1].strip()
                        if content:
                            items = [item.strip().strip('"\'') for item in content.split(',')]
                            return items
                        return []
                    elif value_str.startswith('{') and value_str.endswith('}'):
                        # Extract dict items manually
                        content = value_str[1:-1].strip()
                        if content:
                            # Simple key-value extraction
                            pairs = content.split(',')
                            result = {}
                            for pair in pairs:
                                if ':' in pair:
                                    key, val = pair.split(':', 1)
                                    key = key.strip().strip('"\'')
                                    val = val.strip().strip('"\'')
                                    result[key] = val
                            return result
                        return {}
            
            # Handle boolean values
            if value_str.lower() in ['true', 'false']:
                return value_str.lower() == 'true'
            
            # Handle numeric values
            if value_str.isdigit():
                return int(value_str)
            
            # Handle numeric ranges
            if '-' in value_str and value_str.replace('-', '').replace('.', '').isdigit():
                parts = value_str.split('-')
                if len(parts) == 2:
                    return {'min': float(parts[0]), 'max': float(parts[1])}
            
            # Handle list-like strings
            if ',' in value_str:
                return [item.strip().strip('"\'') for item in value_str.split(',')]
            
            # Return as string
            return value_str
            
        except Exception as e:
            print(f"Error parsing AI value: {e}")
            # Fallback to original value
            return original_value
    
    def _search_google_places(self, destination: str, preferences: Dict, currency: str = '₹') -> List[Dict]:
        """Search Google Places API for accommodations with EXACT budget range in queries"""
        try:
            import urllib.parse
            
            print(f"🔍 _search_google_places called with destination: '{destination}', currency: '{currency}'")
            
            # Create multiple search queries with EXACT budget range for better coverage
            queries = self._create_multiple_search_queries(destination, preferences, currency)
            print(f"🔍 Generated {len(queries)} queries with exact budget ranges: {queries}")
            
            all_results = []
            seen_place_ids = set()
            
            # OPTIMIZED: Process queries in parallel for faster results (use threading)
            import threading
            import queue
            
            results_queue = queue.Queue()
            
            def search_query(query):
                """Search a single query and put results in queue"""
                try:
                    places_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json"
                    params = {
                        'query': f"{query}",
                        'key': self.maps_api_key
                    }
                    
                    response = requests.get(places_url, params=params, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'OK':
                            for place in data.get('results', []):
                                results_queue.put(place)
                        else:
                            print(f"⚠️ Google Places API returned status: {data.get('status')} for query: '{query}'")
                except Exception as e:
                    print(f"Error with query '{query}': {e}")
            
            # Start parallel searches
            threads = []
            for query in queries:
                print(f"🔍 Searching Google Places with query: '{query}'")
                thread = threading.Thread(target=search_query, args=(query,), daemon=True)
                thread.start()
                threads.append(thread)
            
            # Wait for all threads to complete (max 10 seconds)
            for thread in threads:
                thread.join(timeout=10)
            
            # Collect all results
            while not results_queue.empty():
                place = results_queue.get_nowait()
                place_id = place.get('place_id')
                if place_id and place_id not in seen_place_ids:
                    place_name = place.get('name')
                    place_location = place.get('formatted_address', 'Unknown location')
                    print(f"✓ Found: {place_name} in {place_location}")
                    all_results.append(place)
                    seen_place_ids.add(place_id)
            
            # Limit results for performance (enough for hackathon)
            all_results = all_results[:20]  # Limit to 20 results max
            
            print(f"Google Places API returned {len(all_results)} results")
            return all_results
                
        except Exception as e:
            print(f"Error searching Google Places: {e}")
            return []
    
    def _search_google_places_dining(self, destination: str, preferences: Dict, currency: str = '$') -> List[Dict]:
        """Search Google Places API for restaurants"""
        try:
            print(f"🔍 Searching Google Places for restaurants in '{destination}'")
            
            # Build search queries based on preferences
            queries = []
            cuisine_types = preferences.get('cuisine_types', [])
            dining_experiences = preferences.get('dining_experiences', [])
            
            # Base query
            base_query = f"restaurants in {destination}"
            queries.append(base_query)
            
            # Add cuisine-specific queries
            for cuisine in cuisine_types[:3]:  # Limit to 3 to avoid too many API calls
                queries.append(f"{cuisine} restaurants in {destination}")
            
            # Add experience-specific queries
            for exp in dining_experiences[:2]:
                if 'fine dining' in exp.lower() or 'trendy' in exp.lower():
                    queries.append(f"fine dining restaurants in {destination}")
                elif 'street food' in exp.lower() or 'hidden gems' in exp.lower():
                    queries.append(f"street food {destination}")
                elif 'café' in exp.lower() or 'brunch' in exp.lower():
                    queries.append(f"cafes brunch {destination}")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_queries = []
            for q in queries:
                if q not in seen:
                    seen.add(q)
                    unique_queries.append(q)
            
            all_results = []
            seen_place_ids = set()
            
            # Search each query
            for query in unique_queries[:5]:  # Limit to 5 queries max
                try:
                    places_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                    params = {
                        'query': query,
                        'type': 'restaurant',
                        'key': self.maps_api_key
                    }
                    
                    response = requests.get(places_url, params=params, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'OK':
                            for place in data.get('results', []):
                                place_id = place.get('place_id')
                                if place_id and place_id not in seen_place_ids:
                                    all_results.append(place)
                                    seen_place_ids.add(place_id)
                except Exception as e:
                    print(f"Error with query '{query}': {e}")
            
            print(f"✓ Found {len(all_results)} unique restaurants from Places API")
            return all_results[:30]  # Return up to 30 for Vertex AI to filter
            
        except Exception as e:
            print(f"Error searching Google Places for dining: {e}")
            return []
    
    def _search_google_places_activities(self, destination: str, preferences: Dict, currency: str = '$') -> List[Dict]:
        """Search Google Places API for activities/attractions"""
        try:
            print(f"🔍 Searching Google Places for activities in '{destination}'")
            
            # Build search queries based on preferences
            queries = []
            activity_types = preferences.get('activity_types', [])
            
            # Base queries for different activity categories
            base_queries = [
                f"tourist attractions in {destination}",
                f"things to do in {destination}",
                f"activities in {destination}"
            ]
            queries.extend(base_queries)
            
            # Add type-specific queries
            type_mapping = {
                'cultural': ['museums', 'historical sites', 'temples', 'churches'],
                'adventure': ['hiking', 'adventure sports', 'outdoor activities'],
                'nature': ['parks', 'nature reserves', 'beaches', 'mountains'],
                'nightlife': ['bars', 'clubs', 'nightlife'],
                'relaxation': ['spas', 'wellness centers', 'beaches']
            }
            
            for activity_type in activity_types:
                if activity_type.lower() in type_mapping:
                    for keyword in type_mapping[activity_type.lower()][:2]:
                        queries.append(f"{keyword} in {destination}")
            
            # Remove duplicates
            seen = set()
            unique_queries = []
            for q in queries:
                if q not in seen:
                    seen.add(q)
                    unique_queries.append(q)
            
            all_results = []
            seen_place_ids = set()
            
            # Search each query
            for query in unique_queries[:6]:  # Limit to 6 queries max
                try:
                    places_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                    params = {
                        'query': query,
                        'key': self.maps_api_key
                    }
                    
                    response = requests.get(places_url, params=params, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'OK':
                            for place in data.get('results', []):
                                place_id = place.get('place_id')
                                if place_id and place_id not in seen_place_ids:
                                    all_results.append(place)
                                    seen_place_ids.add(place_id)
                except Exception as e:
                    print(f"Error with query '{query}': {e}")
            
            print(f"✓ Found {len(all_results)} unique activities from Places API")
            return all_results[:30]  # Return up to 30 for Vertex AI to filter
            
        except Exception as e:
            print(f"Error searching Google Places for activities: {e}")
            return []
    
    def _filter_and_rank_with_vertex_ai(self, places_results: List[Dict], room_type: str, destination: str, 
                                         user_preferences: str, dining_preferences: Dict = None, 
                                         activity_preferences: Dict = None, currency: str = '$') -> List[Dict]:
        """Use Vertex AI to intelligently filter, rank, and describe Places API results"""
        try:
            print(f"🤖 Using Vertex AI to filter and rank {len(places_results)} {room_type} results")
            
            # Prepare Places data for AI
            places_data = []
            for place in places_results:
                place_info = {
                    'name': place.get('name', 'Unknown'),
                    'address': place.get('formatted_address', ''),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'price_level': place.get('price_level', None),
                    'types': place.get('types', []),
                    'place_id': place.get('place_id', '')
                }
                places_data.append(place_info)
            
            # Build prompt for Vertex AI
            if room_type == 'dining':
                preferences_text = self._format_dining_preferences_for_ai(dining_preferences)
                prompt = f"""You are an expert travel advisor. Analyze these restaurants from Google Places API and select the BEST 15-20 that match the user's preferences.

DESTINATION: {destination}
USER PREFERENCES:
{preferences_text}

RESTAURANTS FROM GOOGLE PLACES API:
{json.dumps(places_data, indent=2)}

TASK:
1. Filter restaurants that match user preferences (cuisine, dining experience, dietary needs)
2. Rank them by relevance to preferences (NOT just by rating - preferences are primary, rating is tie-breaker)
3. For each selected restaurant, provide:
   - name (exact from Places API)
   - description (2-3 sentences explaining why it matches user preferences)
   - price_range (CRITICAL: Generate realistic per-person cost estimate in {currency} based on:
     * Destination cost of living (e.g., Udupi/Karnataka = budget-friendly, Mumbai/Delhi = moderate, Dubai/Singapore = expensive)
     * Restaurant name and type (e.g., "Fish Hotel" = budget, "Fine Dining" = expensive)
     * Price level from Places API (if available)
     * Typical meal cost for this type of restaurant in this destination
     Format: "{currency}XX-{currency}YY" per person, e.g., "₹150-₹300" for mid-range in Udupi, "₹50-₹100" for budget, "₹500-₹1000" for fine dining)
   - rating (from Places API)
   - location (address from Places API)
   - why_recommended (specific reason matching user preferences)

CRITICAL:
- Return EXACTLY 15-20 restaurants (prioritize variety and preference matching)
- Use ratings ONLY as tie-breaker, NOT primary criteria
- Match user's cuisine preferences, dining experiences, and dietary needs
- Ensure diverse options (mix of different cuisines/experiences if user selected multiple)
- NO duplicates

Return JSON array format:
[
  {{
    "name": "Restaurant Name",
    "description": "Why this restaurant matches preferences...",
    "price_range": "{currency}150-{currency}300",
    "rating": 4.5,
    "location": "Full address",
    "why_recommended": "Specific reason matching user preferences"
  }}
]

IMPORTANT: price_range must be realistic for {destination} - use destination-appropriate pricing (e.g., ₹50-₹200 for budget in Udupi, ₹200-₹500 for mid-range in Mumbai, $30-$80 for moderate in Dubai)."""
            else:  # activities
                preferences_text = self._format_activity_preferences_for_ai(activity_preferences)
                prompt = f"""You are an expert travel advisor. Analyze these activities/attractions from Google Places API and select the BEST 15-20 that match the user's preferences.

DESTINATION: {destination}
USER PREFERENCES:
{preferences_text}

ACTIVITIES FROM GOOGLE PLACES API:
{json.dumps(places_data, indent=2)}

TASK:
1. Filter activities that match user preferences (activity types, specific interests)
2. Rank them by relevance to preferences (NOT just by rating - preferences are primary, rating is tie-breaker)
3. For each selected activity, provide:
   - name (exact from Places API)
   - description (2-3 sentences explaining why it matches user preferences)
   - price_range (CRITICAL: Generate realistic cost estimate in {currency} based on:
     * Destination cost of living (e.g., Udupi/Karnataka = budget-friendly, Mumbai/Delhi = moderate, Dubai/Singapore = expensive)
     * Activity type (e.g., "Temple" = often free/low, "Museum" = moderate, "Adventure Sports" = expensive)
     * Activity name and characteristics
     * Price level from Places API (if available)
     Format: "{currency}XX-{currency}YY" per person, or "Free" if no cost, or "Varies" if cost depends on options
     Examples: "Free" for temples/parks, "₹50-₹200" for museums in Udupi, "₹500-₹2000" for adventure activities)
   - rating (from Places API)
   - location (address from Places API)
   - why_recommended (specific reason matching user preferences)

CRITICAL:
- Return EXACTLY 15-20 activities (prioritize variety and preference matching)
- Use ratings ONLY as tie-breaker, NOT primary criteria
- Match user's activity type preferences and specific interests
- Ensure diverse options (mix of different activity types if user selected multiple)
- NO duplicates

Return JSON array format:
[
  {{
    "name": "Activity Name",
    "description": "Why this activity matches preferences...",
    "price_range": "{currency}100-{currency}300",
    "rating": 4.5,
    "location": "Full address",
    "why_recommended": "Specific reason matching user preferences"
  }}
]

IMPORTANT: price_range must be realistic for {destination} - use "Free" for free activities, or destination-appropriate pricing (e.g., ₹50-₹200 for museums in Udupi, ₹500-₹2000 for adventure activities, "Free" for temples/parks)."""
            
            # Use Vertex AI to generate filtered/ranked suggestions
            use_vertex = True
            try:
                vertex_client = self._get_vertex_client()
                if vertex_client:
                    response_text = vertex_client.generate(
                        prompt,
                        temperature=0.4,
                        max_output_tokens=8192
                    )
                    print("✓ Vertex AI successfully filtered and ranked suggestions")
                else:
                    use_vertex = False
                    raise ValueError("Vertex AI client not available")
            except Exception as vertex_err:
                print(f"⚠️ Vertex AI failed ({type(vertex_err).__name__}: {vertex_err}), falling back to Gemini API")
                use_vertex = False
                response_text = self._generate_with_gemini(prompt)
            
            # Parse AI response
            response_text = self._clean_json_response(response_text)
            suggestions = json.loads(response_text)
            
            if not isinstance(suggestions, list):
                suggestions = []
            
            # Enrich with Places API data (photos, coordinates, etc.)
            enriched_suggestions = []
            for suggestion in suggestions[:20]:  # Limit to 20
                name = suggestion.get('name', '')
                # Find matching place from Places API
                matching_place = None
                for place in places_results:
                    if place.get('name', '').lower() == name.lower():
                        matching_place = place
                        break
                
                enriched = {
                    'name': suggestion.get('name', ''),
                    'description': suggestion.get('description', ''),
                    'price_range': suggestion.get('price_range', 'Varies'),
                    'rating': suggestion.get('rating', 0),
                    'location': suggestion.get('location', ''),
                    'why_recommended': suggestion.get('why_recommended', ''),
                    'external_url': f"https://www.google.com/maps/place/?q=place_id:{matching_place.get('place_id', '')}" if matching_place else '',
                    'link_type': 'maps' if matching_place else 'none'
                }
                
                # Add photos if available
                if matching_place and 'photos' in matching_place and matching_place['photos']:
                    photo_ref = matching_place['photos'][0].get('photo_reference', '')
                    if photo_ref:
                        enriched['image_url'] = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_ref}&key={self.maps_api_key}"
                
                enriched_suggestions.append(enriched)
            
            print(f"✓ Returning {len(enriched_suggestions)} {room_type} suggestions (Places API + Vertex AI)")
            return enriched_suggestions
            
        except Exception as e:
            print(f"Error filtering with Vertex AI: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return basic formatted Places results
            return self._format_places_results_basic(places_results, room_type, currency)
    
    def _extract_dining_preferences(self, answers: List[Dict], preference_constraints: Dict = None) -> Dict:
        """Extract dining preferences from user answers"""
        preferences = {}
        
        for answer in answers:
            question_text = answer.get('question_text', '').lower()
            answer_value = answer.get('answer_value')
            
            if not answer_value:
                continue
            
            if 'dining experiences' in question_text or 'interested in' in question_text:
                if isinstance(answer_value, list):
                    preferences['dining_experiences'] = answer_value
                else:
                    preferences['dining_experiences'] = [answer_value]
            
            elif 'cuisines' in question_text or 'food styles' in question_text:
                if isinstance(answer_value, list):
                    preferences['cuisine_types'] = answer_value
                else:
                    preferences['cuisine_types'] = [answer_value]
            
            elif 'dietary' in question_text or 'preferences' in question_text:
                if isinstance(answer_value, str):
                    preferences['dietary_needs'] = answer_value
        
        if preference_constraints:
            preferences.update(preference_constraints)
        
        return preferences
    
    def _extract_activity_preferences(self, answers: List[Dict], preference_constraints: Dict = None) -> Dict:
        """Extract activity preferences from user answers"""
        preferences = {}
        
        for answer in answers:
            question_text = answer.get('question_text', '').lower()
            answer_value = answer.get('answer_value')
            
            if not answer_value:
                continue
            
            if 'type of activities' in question_text:
                if isinstance(answer_value, list):
                    preferences['activity_types'] = answer_value
                else:
                    preferences['activity_types'] = [answer_value]
            
            elif 'specific activities' in question_text or 'experiences' in question_text:
                if isinstance(answer_value, str):
                    preferences['specific_interests'] = answer_value
        
        if preference_constraints:
            preferences.update(preference_constraints)
        
        return preferences
    
    def _format_dining_preferences_for_ai(self, preferences: Dict) -> str:
        """Format dining preferences for AI prompt"""
        parts = []
        if preferences.get('dining_experiences'):
            parts.append(f"Dining Experiences: {', '.join(preferences['dining_experiences'])}")
        if preferences.get('cuisine_types'):
            parts.append(f"Cuisine Types: {', '.join(preferences['cuisine_types'])}")
        if preferences.get('dietary_needs'):
            parts.append(f"Dietary Needs: {preferences['dietary_needs']}")
        return "\n".join(parts) if parts else "No specific preferences"
    
    def _format_activity_preferences_for_ai(self, preferences: Dict) -> str:
        """Format activity preferences for AI prompt"""
        parts = []
        if preferences.get('activity_types'):
            parts.append(f"Activity Types: {', '.join(preferences['activity_types'])}")
        if preferences.get('specific_interests'):
            parts.append(f"Specific Interests: {preferences['specific_interests']}")
        return "\n".join(parts) if parts else "No specific preferences"
    
    def _format_places_results_basic(self, places_results: List[Dict], room_type: str, currency: str) -> List[Dict]:
        """Basic formatting of Places API results (fallback) - uses AI for price estimation"""
        suggestions = []
        for place in places_results[:15]:
            name = place.get('name', 'Unknown')
            address = place.get('formatted_address', '')
            rating = place.get('rating', 0)
            price_level = place.get('price_level', None)
            
            # Use AI to estimate realistic price based on destination, place name, and type
            price_range = self._estimate_price_with_ai(name, address, room_type, price_level, currency)
            
            suggestion = {
                'name': name,
                'description': f"Located in {address}",
                'price_range': price_range,
                'rating': rating,
                'location': address,
                'why_recommended': f"Highly rated {room_type} option",
                'external_url': f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}",
                'link_type': 'maps'
            }
            
            # Add photo if available
            if 'photos' in place and place['photos']:
                photo_ref = place['photos'][0].get('photo_reference', '')
                if photo_ref:
                    suggestion['image_url'] = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_ref}&key={self.maps_api_key}"
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def _estimate_price_with_ai(self, name: str, address: str, room_type: str, price_level: int, currency: str) -> str:
        """Use AI to estimate realistic price for a place based on name, location, and type"""
        try:
            # Extract destination from address
            destination = address.split(',')[-2].strip() if ',' in address else address.split(',')[-1].strip()
            
            if room_type == 'dining':
                prompt = f"""Estimate the realistic per-person meal cost for this restaurant in {currency}:

RESTAURANT NAME: {name}
LOCATION: {address}
DESTINATION: {destination}
PRICE LEVEL (1-4, if available): {price_level if price_level else 'Not specified'}

Consider:
- Destination cost of living (e.g., Udupi/Karnataka = budget-friendly ₹50-₹200, Mumbai/Delhi = moderate ₹200-₹500, Dubai/Singapore = expensive $30-$100)
- Restaurant type from name (e.g., "Fish Hotel" = budget, "Fine Dining" = expensive, "Cafe" = moderate)
- Price level indicator (1=budget, 2=moderate, 3=expensive, 4=very expensive)

Respond with ONLY the price range in format: "{currency}XX-{currency}YY" per person
Examples: "₹50-₹150" for budget in Udupi, "₹200-₹500" for mid-range in Mumbai, "$20-$50" for moderate in Dubai

If unsure, use moderate pricing for the destination."""
            else:  # activities
                prompt = f"""Estimate the realistic per-person cost for this activity in {currency}:

ACTIVITY NAME: {name}
LOCATION: {address}
DESTINATION: {destination}
PRICE LEVEL (1-4, if available): {price_level if price_level else 'Not specified'}

Consider:
- Destination cost of living
- Activity type (e.g., "Temple" = often free/low, "Museum" = moderate, "Adventure Sports" = expensive)
- Activity name and characteristics

Respond with ONLY:
- "Free" if no cost
- "{currency}XX-{currency}YY" per person if there's a cost
- "Varies" if cost depends on options

Examples: "Free" for temples/parks, "₹50-₹200" for museums in Udupi, "₹500-₹2000" for adventure activities"""
            
            response = self.model.generate_content(prompt)
            price_estimate = response.text.strip()
            
            # Clean up the response (remove quotes, extra text)
            price_estimate = price_estimate.replace('"', '').replace("'", '').strip()
            
            # Validate format
            if price_estimate.lower() in ['free', 'varies']:
                return price_estimate
            elif currency in price_estimate and ('-' in price_estimate or price_estimate.replace(currency, '').replace('-', '').isdigit()):
                return price_estimate
            else:
                # Fallback to basic estimation
                return self._fallback_price_estimate(price_level, currency, room_type)
                
        except Exception as e:
            print(f"Error estimating price with AI for {name}: {e}")
            # Fallback to basic estimation
            return self._fallback_price_estimate(price_level, currency, room_type)
    
    def _fallback_price_estimate(self, price_level: int, currency: str, room_type: str) -> str:
        """Fallback price estimation when AI fails"""
        if room_type == 'dining':
            if price_level:
                price_ranges = {
                    1: f"{currency}50-{currency}150",
                    2: f"{currency}150-{currency}300",
                    3: f"{currency}300-{currency}600",
                    4: f"{currency}600+"
                }
                return price_ranges.get(price_level, "Varies")
            else:
                return f"{currency}150-{currency}300"  # Default moderate
        else:  # activities
            if price_level:
                price_ranges = {
                    1: "Free",
                    2: f"{currency}50-{currency}200",
                    3: f"{currency}200-{currency}500",
                    4: f"{currency}500+"
                }
                return price_ranges.get(price_level, "Varies")
            else:
                return f"{currency}100-{currency}300"  # Default moderate
    
    def _generate_dining_suggestions_ai_fallback(self, destination: str, answers: List[Dict], group_preferences: Dict = None, preference_constraints: Dict = None) -> List[Dict]:
        """Fallback to AI-only generation if Places API fails"""
        print("⚠️ Falling back to AI-only dining suggestions")
        # Use prompt-based AI generation (bypassing Places API)
        from utils import get_currency_from_destination
        from_location = group_preferences.get('from_location', '') if group_preferences else ''
        currency = get_currency_from_destination(from_location) if from_location else '$'
        context = self._prepare_context('dining', destination, answers, group_preferences, preference_constraints)
        prompt = self._create_dining_prompt(destination, context, currency, preference_constraints)
        
        try:
            use_vertex = self._get_vertex_client() is not None
            if use_vertex:
                try:
                    response_text = self._generate_with_vertex(prompt)
                except Exception:
                    response_text = self._generate_with_gemini(prompt)
            else:
                response_text = self._generate_with_gemini(prompt)
            
            suggestions_data = self._parse_ai_response(response_text, 'dining')
            enhanced_suggestions = []
            for suggestion in suggestions_data:
                enhanced_suggestion = self._enhance_with_maps(suggestion, destination, answers, group_preferences)
                enhanced_suggestions.append(enhanced_suggestion)
            return enhanced_suggestions
        except Exception as e:
            print(f"Error in AI fallback for dining: {e}")
            return self._get_fallback_suggestions('dining', destination)
    
    def _generate_activities_suggestions_ai_fallback(self, destination: str, answers: List[Dict], group_preferences: Dict = None, preference_constraints: Dict = None) -> List[Dict]:
        """Fallback to AI-only generation if Places API fails"""
        print("⚠️ Falling back to AI-only activities suggestions")
        # Use prompt-based AI generation (bypassing Places API)
        from utils import get_currency_from_destination
        from_location = group_preferences.get('from_location', '') if group_preferences else ''
        currency = get_currency_from_destination(from_location) if from_location else '$'
        context = self._prepare_context('activities', destination, answers, group_preferences, preference_constraints)
        prompt = self._create_activities_prompt(destination, context, currency, preference_constraints)
        
        try:
            use_vertex = self._get_vertex_client() is not None
            if use_vertex:
                try:
                    response_text = self._generate_with_vertex(prompt)
                except Exception:
                    response_text = self._generate_with_gemini(prompt)
            else:
                response_text = self._generate_with_gemini(prompt)
            
            suggestions_data = self._parse_ai_response(response_text, 'activities')
            enhanced_suggestions = []
            for suggestion in suggestions_data:
                enhanced_suggestion = self._enhance_with_maps(suggestion, destination, answers, group_preferences)
                enhanced_suggestions.append(enhanced_suggestion)
            return enhanced_suggestions
        except Exception as e:
            print(f"Error in AI fallback for activities: {e}")
            return self._get_fallback_suggestions('activities', destination)
    
    def _estimate_price_from_level(self, price_level: int, currency: str, location: str, name: str) -> str:
        """Fallback price estimation based on price level and location - DYNAMIC"""
        # Use AI to determine location cost characteristics dynamically
        location_lower = location.lower() if location else ''
        
        # Use AI to determine if location is expensive, moderate, or budget
        prompt = f"""Categorize this location's typical accommodation cost level:

LOCATION: {location}

Respond with ONLY ONE word:
- "EXPENSIVE" if it's a high-cost city (e.g., London, Tokyo, New York, Paris, Singapore, Zurich)
- "MODERATE" if it's a mid-range cost city (e.g., most major cities)
- "BUDGET" if it's a low-cost destination (e.g., Bangkok, Phuket, Bali, Chiang Mai)

Be conservative - if unsure, respond "MODERATE".
"""

        try:
            response = self.model.generate_content(prompt)
            cost_level = response.text.strip().upper()
        except Exception as e:
            print(f"Error in AI cost level determination: {e}")
            cost_level = "MODERATE"  # Fallback
        
        # Set multipliers based on AI-determined cost level
        if "EXPENSIVE" in cost_level:
            is_expensive = True
            is_indian = False
            is_budget = False
        elif "BUDGET" in cost_level:
            is_expensive = False
            is_indian = False
            is_budget = True
        else:  # MODERATE or fallback
            # Quick heuristic: check if it might be Indian (for currency-specific logic)
            is_indian = ('india' in location_lower or 'indian' in location_lower or 
                        any(city in location_lower for city in ['mumbai', 'delhi', 'bangalore', 'chennai']))
            is_expensive = False
            is_budget = False
        
        # Set base multipliers
        if is_expensive:
            multiplier = 1.5
        elif is_indian and currency == '₹':
            multiplier = 0.8
        elif is_budget:
            multiplier = 0.3
        else:
            multiplier = 1.0
        
        # Dynamically calculate currency-specific base prices
        # Use the dynamic pricing function
        base_prices = self._get_destination_pricing_data(None, currency)
        
        # Map price_level to price tiers
        if price_level == 0:
            min_price = base_prices['budget_min']
            max_price = base_prices['budget_low']
        elif price_level == 1:
            min_price = base_prices['budget_low']
            max_price = base_prices['budget_mid']
        elif price_level == 2:
            min_price = base_prices['budget_mid']
            max_price = base_prices['budget_high']
        elif price_level == 3:
            min_price = base_prices['budget_high']
            max_price = base_prices['budget_luxury']
        else:  # price_level == 4
            min_price = base_prices['budget_luxury']
            max_price = base_prices['budget_luxury'] * 1.5
        
        return f"{currency}{int(min_price * multiplier):,}-{currency}{int(max_price * multiplier):,}"
    
    def _create_multiple_search_queries(self, destination: str, preferences: Dict, currency: str = '₹') -> List[str]:
        """Create multiple targeted search queries - one per accommodation type with EXACT budget range"""
        try:
            queries = []
            accommodation_types = preferences.get('accommodation_types', ['Hotel'])  # Default to 'Hotel' if none provided
            
            # Get unique accommodation types to avoid duplicate queries
            unique_types = list(dict.fromkeys(accommodation_types))[:3]  # Limit to 3 types max for speed
            
            # Generate one query per accommodation type with exact budget range
            for acc_type in unique_types:
                query = self._create_ai_optimized_search_query(destination, preferences, acc_type, currency)
                queries.append(query)
            
            # Remove duplicates and limit to max 3 queries for speed (fewer API calls)
            unique_queries = list(dict.fromkeys(queries))[:3]
            return unique_queries if unique_queries else [self._create_ai_optimized_search_query(destination, preferences, 'Hotel', currency)]
            
        except Exception as e:
            print(f"Error creating multiple search queries: {e}")
            return [self._create_ai_optimized_search_query(destination, preferences, 'Hotel', currency)]
    
    def _extract_departure_date(self, answers: List[Dict], group_preferences: Dict = None) -> str:
        """Extract departure date with environment variable fallback"""
        if not answers:
            # Fallback to group start_date if available
            if group_preferences and group_preferences.get('start_date'):
                start_date = group_preferences['start_date']
                if 'T' in str(start_date):
                    return str(start_date).split('T')[0]
                return str(start_date)
            return os.getenv('DEFAULT_DEPARTURE_DATE', datetime.now(UTC).strftime('%Y-%m-%d'))
        
        for answer in answers:
            question_text = (answer.get('question_text') or '').lower()
            section = (answer.get('section') or answer.get('trip_leg') or '').lower()
            
            # Check if this is a departure date answer by multiple criteria
            is_departure_date = (
                ('departure' in question_text and 'date' in question_text) or
                (section == 'departure' and 'date' in question_text) or
                (section == 'departure' and isinstance(answer.get('answer_value'), str) and len(answer.get('answer_value', '')) == 10)  # Date format YYYY-MM-DD
            )
            
            if is_departure_date:
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        
        # Fallback to group start_date if available
        if group_preferences and group_preferences.get('start_date'):
            start_date = group_preferences['start_date']
            if 'T' in str(start_date):
                return str(start_date).split('T')[0]
            return str(start_date)
        
        return os.getenv('DEFAULT_DEPARTURE_DATE', datetime.now(UTC).strftime('%Y-%m-%d'))
    
    def _extract_return_date(self, answers: List[Dict], group_preferences: Dict = None) -> str:
        """Extract return date with environment variable fallback"""
        if not answers:
            # Fallback to group end_date if available
            if group_preferences and group_preferences.get('end_date'):
                end_date = group_preferences['end_date']
                if 'T' in str(end_date):
                    return str(end_date).split('T')[0]
                return str(end_date)
            return os.getenv('DEFAULT_RETURN_DATE', datetime.now(UTC).strftime('%Y-%m-%d'))
        
        for answer in answers:
            question_text = (answer.get('question_text') or '').lower()
            section = (answer.get('section') or '').lower()
            trip_leg = (answer.get('trip_leg') or '').lower()
            question_id = (answer.get('question_id') or '').lower()
            
            # Check if this is a return date answer by multiple criteria
            is_return_date = (
                ('return' in question_text and 'date' in question_text) or
                (section == 'return' and 'date' in question_text) or
                (trip_leg == 'return' and 'date' in question_text) or
                ('return' in question_id and 'date' in question_id) or
                (section == 'return' and isinstance(answer.get('answer_value'), str) and len(answer.get('answer_value', '')) == 10)  # Date format YYYY-MM-DD
            )
            
            if is_return_date:
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        
        # Fallback to group end_date if available
        if group_preferences and group_preferences.get('end_date'):
            end_date = group_preferences['end_date']
            if 'T' in str(end_date):
                return str(end_date).split('T')[0]
            return str(end_date)
        
        return os.getenv('DEFAULT_RETURN_DATE', datetime.now(UTC).strftime('%Y-%m-%d'))
    
    def _get_fallback_transportation_suggestions(self, destination: str, answers: List[Dict]) -> List[Dict]:
        """Generate dynamic fallback transportation suggestions using AI"""
        try:
            from_location = next((a['answer_value'] for a in answers if 'from_location' in a.get('question_text', '').lower()), '')
            prompt = f"""
            Generate a fallback transportation suggestion for travel from {from_location} to {destination}.
            Return a JSON object with one suggestion:
            {{
                "name": "Service Name",
                "description": "Description",
                "price_range": "CurrencyX-Y",
                "rating": number,
                "features": ["Feature1", "Feature2"],
                "location": "From-To",
                "why_recommended": "Reason",
                "booking_url": "URL",
                "external_url": "URL",
                "link_type": "booking"
            }}
            """
            response = self.model.generate_content(prompt)
            suggestion = json.loads(response.text.strip())
            return [suggestion]
        except Exception as e:
            print(f"Error generating fallback transportation: {e}")
            return [{
                "name": "General Transport Search",
                "description": "Search for transportation options",
                "price_range": "Varies",
                "rating": 0,
                "features": ["Multiple options"],
                "location": f"To {destination}",
                "why_recommended": "Generic transport search",
                "booking_url": f"https://www.google.com/search?q=transportation+to+{destination.replace(' ', '+')}",
                "external_url": f"https://www.google.com/search?q=transportation+to+{destination.replace(' ', '+')}",
                "link_type": "search"
            }]
    
    def _calculate_currency_based_pricing(self, currency: str, destination: str = None, preferences: Dict = None) -> Dict:
        """Calculate dynamic pricing based on currency, destination, and user preferences"""
        try:
            # Load base pricing from config
            base_prices = self.pricing_config['currencies'].get(currency, self.pricing_config['currencies']['USD'])
            
            # Adjust prices dynamically using AI if destination or preferences provided
            if destination or preferences:
                prompt = f"""
                Adjust the following base pricing for accommodations in {destination} based on user preferences.
                
                BASE PRICES: {json.dumps(base_prices)}
                CURRENCY: {currency}
                PREFERENCES: {json.dumps(preferences, default=str)}
                
                Consider:
                - Destination's economic context (e.g., luxury vs budget destination)
                - User preferences (e.g., accommodation type, amenities)
                - Local pricing norms
                
                Return adjusted pricing as JSON:
                {{"budget_min": number, "budget_low": number, "budget_mid": number, "budget_high": number, "budget_luxury": number}}
                """
                try:
                    response = self.model.generate_content(prompt)
                    adjusted_prices = json.loads(response.text.strip())
                    return adjusted_prices
                except Exception as e:
                    print(f"Error in AI pricing adjustment: {e}")
                    return base_prices
            return base_prices
            
        except Exception as e:
            print(f"Error calculating currency-based pricing: {e}")
            return self.pricing_config['currencies'].get('USD', {"budget_min": 20, "budget_low": 50, "budget_mid": 100, "budget_high": 200, "budget_luxury": 500})
    
    def get_accommodation_types(self, destination: str) -> List[str]:
        """Get accommodation types enhanced with AI for destination-specific types"""
        try:
            # Load base types from config
            base_types = self.accommodation_types.copy()
            
            # Enhance with AI for destination-specific types
            prompt = f"""
            Suggest additional accommodation types suitable for {destination}.
            Base types: {base_types}
            
            Return ONLY a JSON array of unique accommodation types, including base types and any destination-specific additions.
            Do not include any explanations or text outside the JSON array.
            
            Example response format:
            ["Hotel", "Hostel", "Airbnb", "Resort", "Guesthouse", "Boutique Hotel", "Villa", "Eco Lodge"]
            """
            response = self.model.generate_content(prompt)
            enhanced_types = json.loads(response.text.strip())
            
            # Ensure base types are included
            all_types = list(set(base_types + enhanced_types))
            return all_types
            
        except json.JSONDecodeError as e:
            print(f"Error parsing AI response for accommodation types: {e}")
            return self.accommodation_types
        except Exception as e:
            print(f"Error enhancing accommodation types: {e}")
            return self.accommodation_types
    
    def get_dynamic_options(self, room_type: str, destination: str) -> List[str]:
        """Generate dynamic options for room type questions based on destination"""
        try:
            if room_type == 'accommodation':
                return self.get_accommodation_types(destination)
            elif room_type == 'transportation':
                return self.transport_config.get('transportation_options', [])
            elif room_type == 'itinerary':
                return self.transport_config.get('activity_types', [])
            elif room_type == 'eat':
                return self.transport_config.get('cuisine_types', [])
            else:
                # Generic AI-generated options
                prompt = f"""
                Generate a list of appropriate options for {room_type} questions in {destination}.
                
                Return ONLY a JSON array of options relevant to the room type and destination.
                Do not include any explanations or text outside the JSON array.
                
                Example response format:
                ["Option 1", "Option 2", "Option 3", "No preference"]
                """
                try:
                    response = self.model.generate_content(prompt)
                    return json.loads(response.text.strip())
                except json.JSONDecodeError as e:
                    print(f"Error parsing AI response for dynamic options: {e}")
                    return []
                except Exception as e:
                    print(f"Error getting AI dynamic options: {e}")
                    return []
                
        except Exception as e:
            print(f"Error getting dynamic options: {e}")
            return []
    
    def _get_budget_query_terms(self, preferences: Dict, currency: str) -> str:
        """Extract EXACT budget range from preferences and format for Google Places query"""
        try:
            # Get budget range from preferences (check multiple possible keys)
            budget_info = preferences.get('BUDGET_RANGE') or preferences.get('budget_range') or {}
            
            if not budget_info or not isinstance(budget_info, dict):
                return ''
            
            # Get min and max values
            budget_min = budget_info.get('min')
            budget_max = budget_info.get('max')
            
            if not budget_min or not budget_max:
                return ''
            
            try:
                min_val = float(budget_min)
                max_val = float(budget_max)
                
                # Format as exact range in query (e.g., "₹4000-5000 per night")
                # This helps Google Places return more budget-relevant results
                if currency == '₹':
                    return f"₹{int(min_val)}-{int(max_val)} per night"
                elif currency == '$':
                    return f"${int(min_val)}-{int(max_val)} per night"
                elif currency == '€':
                    return f"€{int(min_val)}-{int(max_val)} per night"
                elif currency == '£':
                    return f"£{int(min_val)}-{int(max_val)} per night"
                else:
                    # Generic format with currency symbol
                    return f"{currency}{int(min_val)}-{int(max_val)} per night"
                    
            except (ValueError, TypeError):
                return ''
                
        except Exception as e:
            print(f"Error extracting budget query terms: {e}")
            return ''
    
    def _create_ai_optimized_search_query(self, destination: str, preferences: Dict, accommodation_type: str = None, currency: str = '₹') -> str:
        """Create a dynamic search query based on preferences - INCLUDES EXACT BUDGET RANGE"""
        try:
            # Extract preferences dynamically
            location_prefs = preferences.get('LOCATION_PREFERENCES', [])
            accommodation_types = preferences.get('accommodation_types', [])
            
            # Extract EXACT budget range and add to query (currency-aware)
            budget_terms = self._get_budget_query_terms(preferences, currency)
            
            # Use provided accommodation_type or select the first one
            selected_type = accommodation_type or (accommodation_types[0] if accommodation_types else 'Hotel')
            
            # Build query with destination, location preferences, and EXACT budget range
            query_parts = [selected_type]
            
            # Add location preferences first (more specific)
            if location_prefs:
                location_keywords = ' '.join(location_prefs[:2])  # Take first 2 location keywords
                query_parts.append(location_keywords)
            
            # Always add destination
            query_parts.append(destination)
            
            # Add EXACT budget range at the end (e.g., "₹4000-5000 per night")
            if budget_terms:
                query_parts.append(budget_terms)
            
            query = ' '.join(query_parts)
            
            # Check if the query needs AI optimization
            location_keywords = ' '.join(location_prefs[:2]) if location_prefs else ''
            if self._needs_ai_optimization(location_keywords, selected_type):
                prompt = f"""
                Optimize the following Google Places API search query for clarity and compatibility.
                DO NOT change the destination name '{destination}' - it must stay in the query.
                
                Original query: '{query}'
                
                REQUIREMENTS:
                1. MUST keep '{destination}' in the query
                2. Keep '{selected_type}' accommodation type
                3. Keep location preferences '{location_keywords}' if specified
                4. Make the query more Google Places API-friendly
                5. Keep it concise
                
                Return ONLY the optimized query, nothing else.
                """
                response = self.model.generate_content(prompt)
                optimized_query = response.text.strip()
                
                # Validate that destination is still in the optimized query
                if optimized_query and len(optimized_query) >= 5 and destination.lower() in optimized_query.lower():
                    return optimized_query
            
            # Return the constructed query if AI optimization is not needed or fails
            return query
            
        except Exception as e:
            print(f"Error creating AI-optimized query: {e}")
            return self._create_basic_search_query(destination, preferences)
    
    def _needs_ai_optimization(self, location: str, accommodation_type: str) -> bool:
        """Determine if AI optimization is needed based on complexity of location or accommodation type"""
        try:
            # Check for complex location names that might need rephrasing
            complex_location_keywords = ['lake', 'mountain', 'beach', 'downtown', 'airport', 'station', 'center', 'plaza', 'square']
            location_lower = location.lower()
            
            # Check for complex accommodation types
            complex_accommodation_types = ['boutique', 'luxury', 'eco', 'heritage', 'vintage']
            accommodation_lower = accommodation_type.lower()
            
            # Use AI if location contains complex keywords or accommodation type is complex
            needs_optimization = (
                any(keyword in location_lower for keyword in complex_location_keywords) or
                any(keyword in accommodation_lower for keyword in complex_accommodation_types)
            )
            
            return needs_optimization
            
        except Exception as e:
            print(f"Error checking if AI optimization needed: {e}")
            return False
    
    def _create_basic_search_query(self, destination: str, preferences: Dict) -> str:
        """Create basic search query dynamically from preferences"""
        try:
            # Extract preferences dynamically
            location_prefs = preferences.get('LOCATION_PREFERENCES', [])
            accommodation_types = preferences.get('accommodation_types', [])
            
            # Use first accommodation type or default
            acc_type = accommodation_types[0] if accommodation_types else 'Hotel'
            
            # CRITICAL: Always include destination in query
            if location_prefs:
                # Add location preferences as keywords (e.g., "Hotel beachside Udupi")
                location_keywords = ' '.join(location_prefs[:2])
                return f"{acc_type} {location_keywords} {destination}"
            else:
                return f"{acc_type} {destination}"
            
        except Exception as e:
            print(f"Error creating basic search query: {e}")
            return f"Hotel {destination}"
    
    def _format_places_results(self, places_results: List[Dict], destination: str, context: str, currency: str, start_date: str, end_date: str, preferences: Dict = None) -> List[Dict]:
        """Format Google Places results into accommodation suggestions with relevance scoring"""
        suggestions = []
        
        for place in places_results:  # Process ALL results, not just first 12
            try:
                # Extract place details
                name = place.get('name', 'Unknown')
                rating = place.get('rating', 0)
                price_level = place.get('price_level', 0)
                vicinity = place.get('vicinity', destination)
                
                # CRITICAL: Filter out properties from different cities - DYNAMIC approach
                destination_lower = destination.lower()
                vicinity_lower = vicinity.lower() if vicinity else ''
                name_lower = name.lower()
                
                # Extract the base city name from destination (handle multi-word destinations)
                destination_keywords = [kw for kw in destination_lower.split() if len(kw) > 2]
                primary_destination = destination_keywords[0] if destination_keywords else destination_lower
                
                # Check if destination appears in vicinity or name
                has_destination_match = (
                    any(keyword in vicinity_lower or keyword in name_lower for keyword in destination_keywords if len(keyword) > 2) or
                    destination_lower in vicinity_lower or 
                    destination_lower in name_lower
                )
                
                # Extract potential city from vicinity (format: "City, State, Country")
                if vicinity and ',' in vicinity:
                    potential_location = vicinity.split(',')[0].lower().strip()
                    
                    # If we have a potential location that's different from destination
                    if potential_location and len(potential_location) > 2:
                        # Calculate similarity to destination
                        # Check if it's similar (fuzzy match - same base city)
                        is_similar_location = (
                            primary_destination in potential_location or
                            potential_location in primary_destination or
                            has_destination_match
                        )
                        
                        # If clearly different and no destination match, likely wrong city
                        if not is_similar_location and not has_destination_match:
                            print(f"✗ Skipping property from different city: {name} in {vicinity} (destination: {destination})")
                            continue
                
                # OPTIMIZED: Skip expensive AI check - be lenient and include property if we're unsure
                # Since we're already filtering at query level with exact budget and accommodation types,
                # we can trust Google Places results more
                if not has_destination_match and vicinity:
                    # Quick heuristic: if destination keyword appears anywhere, include it
                    # (Faster than AI call - no blocking)
                    pass  # Include the property (be lenient for speed)
                
                # OPTIMIZED: Skip expensive place details API call - use basic info from search results
                # This saves one API call per result (much faster!)
                place_details = {}  # Use empty dict - we have enough info from search results
                
                # Build features list from basic place data (no extra API call)
                features = self._extract_dynamic_features(place_details, place)
                
                # OPTIMIZED: Use quick price estimation from price_level (no AI call)
                preferred_budget = preferences.get('budget_range') or preferences.get('BUDGET_RANGE')
                price_indicator = self._get_quick_price_estimate(place, currency, preferred_budget)
                
                # OPTIMIZED: Use simple description from rating/vicinity (no AI call)
                real_description = self._get_quick_description(place, name)
                
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(place, preferences or {})
                
                # Create booking URLs for actual price lookup
                website = place.get('website', '')
                maps_url = f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}"
                
                # Create suggestion with booking links
                suggestion = {
                    'name': name,
                    'description': real_description,
                    'price_range': price_indicator,
                    'rating': rating,
                    'features': features[:5],  # Limit to 5 features
                    'location': vicinity,
                    'why_recommended': f"Found via Google Places API. Rated {rating}/5 stars. {price_indicator}.",
                    'place_id': place.get('place_id'),
                    # Use place name + location for Google Maps URL (more reliable than place_id)
                    'maps_url': self._create_maps_url({'name': name, 'location': vicinity}, destination),
                    'maps_embed_url': self._create_maps_embed_url({'place_id': place.get('place_id'), 'name': name, 'location': vicinity}, destination),
                    'external_url': self._create_maps_url({'name': name, 'location': vicinity}, destination),
                    'link_type': 'maps',
                    'relevance_score': relevance_score
                }
                
                suggestions.append(suggestion)
                
            except Exception as e:
                print(f"Error formatting place result: {e}")
                continue
        
        # Sort by relevance score (highest first)
        suggestions.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return suggestions
    
    def _calculate_relevance_score(self, place: Dict, preferences: Dict) -> float:
        """Calculate relevance score for a place based on user preferences"""
        try:
            score = 0
            place_name = place.get('name', '').lower()
            place_vicinity = place.get('vicinity', '').lower()
            rating = place.get('rating', 0)
            
            # Boost score for location preference
            location_prefs = preferences.get('LOCATION_PREFERENCES', [])
            for loc_pref in location_prefs:
                loc_pref_lower = loc_pref.lower()
                if loc_pref_lower in place_vicinity or loc_pref_lower in place_name:
                    score += 50
            
            # Boost score for accommodation type
            acc_types = preferences.get('accommodation_types', [])
            for acc_type in acc_types:
                if acc_type.lower() in place_name:
                    score += 30
            
            # Boost score for high ratings
            score += rating * 10
            
            # Boost score for special requirements
            special_reqs = preferences.get('SPECIAL_REQUIREMENTS', [])
            for req in special_reqs:
                req_lower = req.lower()
                if req_lower in place_name or req_lower in place_vicinity:
                    score += 20
            
            return score
            
        except Exception as e:
            print(f"Error calculating relevance score: {e}")
            return 0
    
    def _create_maps_embed_url(self, suggestion: Dict, destination: str) -> str:
        """Create Google Maps embed URL for popup display"""
        try:
            place_id = suggestion.get('place_id', '')
            if place_id:
                # Use Embed API for direct map display
                return f"https://www.google.com/maps/embed/v1/place?key={self.maps_api_key}&q=place_id:{place_id}"
            
            # Fallback to search URL
            place_name = suggestion.get('name', '')
            location = suggestion.get('location', '')
            search_query = f'"{place_name}" {location} {destination}' if place_name else f"{location} {destination}"
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(search_query)
            return f"https://www.google.com/maps/embed/v1/search?key={self.maps_api_key}&q={encoded_query}"
            
        except Exception as e:
            print(f"Error creating maps embed URL: {e}")
            import urllib.parse
            return f"https://www.google.com/maps/embed/v1/search?key={self.maps_api_key}&q={urllib.parse.quote_plus(destination)}"
    
    def _extract_dynamic_features(self, place_details: Dict, place: Dict) -> List[str]:
        """Extract features dynamically from Google Places data"""
        features = []
        
        try:
            # Extract features from place details
            if place_details:
                # Contact information
                if place_details.get('formatted_phone_number'):
                    features.append('Phone available')
                if place_details.get('website'):
                    features.append('Website available')
                
                # Operating hours
                opening_hours = place_details.get('opening_hours', {})
                if opening_hours.get('open_now'):
                    features.append('Open now')
                
                # Amenities from place details
                amenities = place_details.get('amenities', [])
                if amenities:
                    features.extend(amenities[:3])
                
                # Editorial summary features
                editorial_summary = place_details.get('editorial_summary', {})
                if editorial_summary.get('overview'):
                    # Extract key features from overview text
                    overview_features = self._extract_features_from_text(editorial_summary['overview'])
                    features.extend(overview_features[:2])
            
            # Extract features from main place data
            if place:
                # Rating-based features
                rating = place.get('rating', 0)
                if rating >= 4.5:
                    features.append('Highly rated')
                elif rating >= 4.0:
                    features.append('Well rated')
                
                # Price level features
                price_level = place.get('price_level', 0)
                if price_level >= 3:
                    features.append('Premium pricing')
                elif price_level <= 1:
                    features.append('Budget friendly')
                
                # Business status
                business_status = place.get('business_status', '')
                if business_status == 'OPERATIONAL':
                    features.append('Currently operational')
            
            # Remove duplicates and limit to 5 features
            features = list(dict.fromkeys(features))[:5]
            
            # Ensure we have at least some features
            if not features:
                features = ['Accommodation available']
            
            return features
            
        except Exception as e:
            print(f"Error extracting dynamic features: {e}")
            return ['Accommodation available']
    
    def _extract_features_from_text(self, text: str) -> List[str]:
        """Extract features using keyword matching (no AI calls)"""
        try:
            if not text or len(text) < 5:
                return []
            
            feature_keywords = {
                'wifi': 'Free WiFi',
                'pool': 'Swimming Pool',
                'parking': 'Free Parking',
                'breakfast': 'Breakfast Included',
                'gym': 'Fitness Center',
                'spa': 'Spa',
                'restaurant': 'On-site Restaurant',
                'beach': 'Beachfront',
                'pet': 'Pet Friendly',
                'air conditioning': 'Air Conditioning',
                'balcony': 'Balcony',
                'kitchen': 'Kitchen Access',
                'bar': 'In-house Bar'
            }
            
            text_lower = text.lower()
            features = []
            for keyword, label in feature_keywords.items():
                if keyword in text_lower:
                    features.append(label)
                if len(features) >= 3:
                    break
            
            return features[:3]
        except Exception as e:
            print(f"Error extracting features from text: {e}")
            return []
    
    def _store_accommodation_suggestions(self, suggestions: List[Dict], destination: str, answers: List[Dict], group_preferences: Dict = None):
        """Store accommodation suggestions in database for analytics and future reference"""
        try:
            # Create accommodation search record
            search_data = {
                'destination': destination,
                'search_timestamp': datetime.utcnow().isoformat(),
                'user_preferences': self._extract_accommodation_preferences(answers),
                'group_preferences': group_preferences,
                'suggestions_count': len(suggestions),
                'suggestions': suggestions
            }
            
            # Store in Firebase for analytics
            firebase_service.db.collection('accommodation_searches').add(search_data)
            
            # Store individual suggestions for future reference
            for suggestion in suggestions:
                suggestion_data = {
                    'name': suggestion.get('name'),
                    'destination': destination,
                    'place_id': suggestion.get('place_id'),
                    'rating': suggestion.get('rating'),
                    'price_range': suggestion.get('price_range'),
                    'features': suggestion.get('features'),
                    'location': suggestion.get('location'),
                    'search_timestamp': datetime.utcnow().isoformat(),
                    'user_preferences': self._extract_accommodation_preferences(answers)
                }
                firebase_service.db.collection('accommodation_suggestions').add(suggestion_data)
                
        except Exception as e:
            print(f"Error storing accommodation suggestions: {e}")
            # Don't fail the main process if storage fails
    
    def _quick_budget_validation(self, suggestions: List[Dict], preferences: Dict, currency: str) -> List[Dict]:
        """Quick budget validation without AI - filters obvious outliers only (FAST)"""
        try:
            # Get budget range from preferences
            budget_info = preferences.get('BUDGET_RANGE') or preferences.get('budget_range') or {}
            
            if not budget_info or not isinstance(budget_info, dict):
                return suggestions
            
            budget_min = budget_info.get('min')
            budget_max = budget_info.get('max')
            
            if not budget_min or not budget_max:
                return suggestions
            
            try:
                min_val = float(budget_min)
                max_val = float(budget_max)
            except (ValueError, TypeError):
                return suggestions
            
            # Quick validation: only filter obvious outliers
            # Allow 50% buffer above max budget to account for price variations
            threshold = max_val * 1.5
            
            filtered = []
            for suggestion in suggestions:
                price_range = suggestion.get('price_range', '')
                
                # Quick price extraction from price_range string (e.g., "₹4000-5000" or "$100-200")
                price_val = self._extract_price_from_string(price_range, currency)
                
                if not price_val:
                    # If we can't extract price, keep it (don't filter unknown)
                    filtered.append(suggestion)
                elif price_val <= threshold:
                    # Within reasonable threshold
                    filtered.append(suggestion)
                # Else: obvious outlier, skip it
            
            return filtered
            
        except Exception as e:
            print(f"Error in quick budget validation: {e}")
            return suggestions
    
    def _extract_price_from_string(self, price_str: str, currency: str) -> float:
        """Quickly extract numeric price from price_range string (e.g., "₹4000-5000" -> 4500)"""
        try:
            if not price_str:
                return None
            
            # Remove currency symbols and extract numbers
            import re
            # Find all numbers in the string
            numbers = re.findall(r'\d+\.?\d*', price_str.replace(',', ''))
            
            if not numbers:
                return None
            
            # If range (e.g., "4000-5000"), take average
            if len(numbers) >= 2:
                return (float(numbers[0]) + float(numbers[1])) / 2
            else:
                return float(numbers[0])
                
        except Exception:
            return None
    
    def _parse_budget_range(self, budget_info: any) -> tuple:
        """Parse budget information to extract min and max values"""
        try:
            if isinstance(budget_info, dict):
                if 'min_value' in budget_info and 'max_value' in budget_info:
                    min_val = float(str(budget_info['min_value']).replace(',', ''))
                    max_val = float(str(budget_info['max_value']).replace(',', ''))
                    return min_val, max_val
                elif 'min' in budget_info and 'max' in budget_info:
                    min_val = float(str(budget_info['min']).replace(',', ''))
                    max_val = float(str(budget_info['max']).replace(',', ''))
                    return min_val, max_val
            
            elif isinstance(budget_info, str) and '-' in budget_info:
                parts = budget_info.split('-')
                if len(parts) == 2:
                    min_val = float(parts[0].strip().replace(',', ''))
                    max_val = float(parts[1].strip().replace(',', ''))
                    return min_val, max_val
            
            # Default fallback
            return 1000, 50000
            
        except Exception as e:
            print(f"Error parsing budget range: {e}")
            return 1000, 50000
    
    def _get_currency_from_destination(self, destination: str) -> str:
        """Get currency based on destination"""
        try:
            # Import the utility function
            from utils import get_currency_from_destination
            return get_currency_from_destination(destination)
        except Exception as e:
            print(f"Error getting currency from destination: {e}")
            # Fallback based on common destinations
            destination_lower = destination.lower()
            if any(country in destination_lower for country in ['india', 'chennai', 'mumbai', 'delhi', 'bangalore', 'kodaikanal', 'goa']):
                return "INR"
            elif any(country in destination_lower for country in ['usa', 'united states', 'new york', 'california']):
                return "USD"
            elif any(country in destination_lower for country in ['uk', 'united kingdom', 'london']):
                return "GBP"
            elif any(country in destination_lower for country in ['japan', 'tokyo']):
                return "JPY"
            else:
                return "USD"  # Default fallback
    
    def _get_quick_price_estimate(self, place: Dict, currency: str, preferred_budget: Dict = None) -> str:
        """Fast price estimation using lookup tables instead of AI"""
        try:
            price_level = int(place.get('price_level', 2) or 2)
            rating = float(place.get('rating') or 0)
            
            base_prices = self._get_dynamic_base_prices(currency)
            
            # Determine multiplier from price level
            multiplier = 1.0
            if price_level >= 3:
                multiplier = 1.3
            elif price_level <= 1:
                multiplier = 0.7
            
            # Rating adjustments
            if rating >= 4.5:
                multiplier *= 1.15
            elif rating >= 4.0:
                multiplier *= 1.05
            
            tiers = [
                ('budget_min', 'budget_low'),
                ('budget_low', 'budget_mid'),
                ('budget_mid', 'budget_high'),
                ('budget_high', 'budget_luxury'),
                ('budget_luxury', 'budget_luxury')
            ]
            min_tier, max_tier = tiers[min(price_level, 4)]
            
            base_min = base_prices.get(min_tier, 1000)
            base_max = base_prices.get(max_tier, 5000)
            
            adjusted_min = int(base_min * multiplier)
            adjusted_max = int(base_max * multiplier)
            
            # Round to cleaner numbers
            def _round(value: int) -> int:
                if value < 100:
                    unit = 10
                elif value < 1000:
                    unit = 50
                elif value < 10000:
                    unit = 100
                elif value < 100000:
                    unit = 500
                else:
                    unit = 1000
                return max(unit, round(value / unit) * unit)
            
            adjusted_min = _round(adjusted_min)
            adjusted_max = _round(max(adjusted_min, adjusted_max))
            
            if preferred_budget and isinstance(preferred_budget, dict):
                min_pref = preferred_budget.get('min')
                max_pref = preferred_budget.get('max')
                if min_pref is not None:
                    adjusted_min = max(adjusted_min, int(min_pref))
                if max_pref is not None:
                    adjusted_max = min(adjusted_max, int(max_pref))
                if adjusted_min > adjusted_max and max_pref is not None:
                    adjusted_max = adjusted_min
            
            if max_tier == 'budget_luxury' and price_level == 4:
                return f"{currency}{adjusted_min}+"
            return f"{currency}{adjusted_min}-{currency}{adjusted_max}"
                
        except Exception as e:
            print(f"Error in quick price estimate: {e}")
            base_prices = self._get_dynamic_base_prices(currency)
            base_min = base_prices.get('budget_mid', 1000)
            base_max = base_prices.get('budget_high', 5000)
            return f"{currency}{int(base_min)}-{currency}{int(base_max)}"
    
    def _get_dynamic_base_prices(self, currency: str) -> Dict:
        """Get dynamic base prices for any currency - SCALABLE"""
        try:
            # Try to load from pricing config first (from pricing_ranges.json)
            if hasattr(self, 'pricing_config') and self.pricing_config:
                currencies = self.pricing_config.get('currencies', {})
                # Try both symbol and code format (e.g., '₹' and 'INR', '$' and 'USD')
                currency_data = currencies.get(currency, {})
                if not currency_data:
                    # Try common currency code mappings
                    currency_code_map = {
                        '₹': 'INR', '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY',
                        '₩': 'KRW', '₱': 'PHP', '₫': 'VND', '฿': 'THB',
                        '₺': 'TRY', '₪': 'ILS', '₦': 'NGN'
                    }
                    currency_code = currency_code_map.get(currency, currency.upper())
                    currency_data = currencies.get(currency_code, {})
                
                if currency_data:
                    # Convert to expected format (use budget_* keys)
                    result = {
                        'budget_min': currency_data.get('budget_min', 0),
                        'budget_low': currency_data.get('budget_low', 0),
                        'budget_mid': currency_data.get('budget_mid', 0),
                        'budget_high': currency_data.get('budget_high', 0),
                        'budget_luxury': currency_data.get('budget_luxury', 0)
                    }
                    # Only return if we have valid data
                    if result['budget_min'] > 0:
                        return result
            
            # Fallback: Calculate base prices dynamically based on currency
            # Use approximate exchange rate multipliers relative to USD
            # This makes it scalable for ANY currency without hardcoding
            
            # Base prices in USD (reference)
            usd_base = {
                'budget_min': 30,
                'budget_low': 80,
                'budget_mid': 150,
                'budget_high': 300,
                'budget_luxury': 500
            }
            
            # Approximate currency multipliers (relative to USD)
            # These are rough estimates - in production, use real-time exchange rates
            currency_multipliers = {
                # Major currencies
                '$': 1.0, 'USD': 1.0,
                '€': 0.92, 'EUR': 0.92,
                '£': 0.79, 'GBP': 0.79,
                '¥': 150.0, 'JPY': 150.0,
                'CHF': 0.88,
                'C$': 1.35, 'CAD': 1.35,
                'A$': 1.52, 'AUD': 1.52,
                'NZ$': 1.68, 'NZD': 1.68,
                
                # Asian currencies
                '₹': 83.0, 'INR': 83.0,
                '₩': 1300.0, 'KRW': 1300.0,
                'S$': 1.34, 'SGD': 1.34,
                'HK$': 7.8, 'HKD': 7.8,
                'RM': 4.7, 'MYR': 4.7,
                'Rp': 15700.0, 'IDR': 15700.0,
                '₱': 56.0, 'PHP': 56.0,
                '₫': 24500.0, 'VND': 24500.0,
                '฿': 36.0, 'THB': 36.0,
                'NT$': 32.0, 'TWD': 32.0,
                
                # Middle Eastern
                'AED': 3.67, 'SAR': 3.75, 'QAR': 3.64,
                
                # African
                'R': 18.5, 'ZAR': 18.5,
                '₦': 1600.0, 'NGN': 1600.0,
                'KSh': 130.0, 'KES': 130.0,
                'EGP': 31.0,
                
                # European (non-EUR)
                'NOK': 10.7, 'SEK': 10.9, 'DKK': 6.9,
                'CZK': 23.0, 'PLN': 4.0, 'HUF': 360.0,
                '₺': 32.0, 'TRY': 32.0,
                
                # Americas
                'R$': 5.0, 'BRL': 5.0,
                'S/': 3.7, 'PEN': 3.7,
            }
            
            # Get multiplier for currency (default to 1.0 if unknown)
            multiplier = currency_multipliers.get(currency, 1.0)
            
            # If currency not in map, try to estimate from common patterns
            if multiplier == 1.0 and currency not in ['$', 'USD']:
                # Try to estimate: if currency looks like it might be a high-value currency
                # (single char + uncommon symbol = likely low multiplier)
                # Multi-word currencies = likely higher multiplier
                if len(currency) == 1:
                    # Single char currencies are often high-value (like €, £, ¥)
                    if currency in ['€', '£', '¥']:
                        multiplier = currency_multipliers.get(currency, 1.0)
                    else:
                        # Unknown single char - assume similar to USD
                        multiplier = 1.0
                elif len(currency) > 3:
                    # Multi-char currency codes - likely smaller denominations (like INR, KRW)
                    # Default to moderate multiplier - but this is a rough guess
                    multiplier = 50.0  # Generic fallback for unknown currencies
                else:
                    # 2-3 char codes - could be anything, use conservative estimate
                    multiplier = 10.0  # Generic fallback
            
            # Calculate dynamic base prices
            return {
                'budget_min': usd_base['budget_min'] * multiplier,
                'budget_low': usd_base['budget_low'] * multiplier,
                'budget_mid': usd_base['budget_mid'] * multiplier,
                'budget_high': usd_base['budget_high'] * multiplier,
                'budget_luxury': usd_base['budget_luxury'] * multiplier
            }
            
        except Exception as e:
            print(f"Error getting dynamic base prices: {e}")
            # Ultimate fallback
            return {
                'budget_min': 1000,
                'budget_low': 2000,
                'budget_mid': 5000,
                'budget_high': 10000,
                'budget_luxury': 20000
            }
    
    def _get_quick_description(self, place: Dict, name: str) -> str:
        """Quick description from basic place data (NO AI - FAST)"""
        try:
            rating = place.get('rating', 0)
            vicinity = place.get('vicinity', '')
            price_level = place.get('price_level', 2)
            
            # Build simple description from available data
            rating_text = f"{rating}/5 stars" if rating > 0 else "Well-reviewed"
            price_text = {0: "Budget-friendly", 1: "Affordable", 2: "Mid-range", 3: "Upscale", 4: "Luxury"}.get(price_level, "Accommodation")
            
            description = f"{name} - {price_text} accommodation in {vicinity if vicinity else 'the area'}. {rating_text}."
            return description
            
        except Exception as e:
            print(f"Error in quick description: {e}")
            return f"{name} - Quality accommodation option."
    
    def _determine_price_range(self, price_level: int, currency: str, destination: str = None) -> str:
        """Determine price range based on Google's price level and destination"""
        try:
            # Get destination-specific pricing data from database or API
            base_prices = self._get_destination_pricing_data(destination, currency)
            
            if price_level == 0:
                return f"{currency}{base_prices['budget_min']}-{currency}{base_prices['budget_low']}"
            elif price_level == 1:
                return f"{currency}{base_prices['budget_low']}-{currency}{base_prices['budget_mid']}"
            elif price_level == 2:
                return f"{currency}{base_prices['budget_mid']}-{currency}{base_prices['budget_high']}"
            elif price_level == 3:
                return f"{currency}{base_prices['budget_high']}-{currency}{base_prices['budget_luxury']}"
            elif price_level == 4:
                return f"{currency}{base_prices['budget_luxury']}+"
            else:
                return f"{currency}{base_prices['budget_low']}-{currency}{base_prices['budget_mid']}"
        except Exception as e:
            # Fallback to dynamic calculation based on currency
            return self._calculate_dynamic_price_range(price_level, currency)
    
    def _get_destination_pricing_data(self, destination: str, currency: str) -> Dict:
        """Get destination-specific pricing data from database or external API"""
        try:
            # Try to get from database first
            if destination:
                # Query database for destination pricing data
                pricing_data = self._query_destination_pricing(destination, currency)
                if pricing_data:
                    return pricing_data
            
            # Fallback to currency-based calculation
            return self._calculate_currency_based_pricing(currency)
            
        except Exception as e:
            print(f"Error getting destination pricing: {e}")
            return self._calculate_currency_based_pricing(currency)
    
    def _query_destination_pricing(self, destination: str, currency: str) -> Dict:
        """Query database for destination-specific pricing"""
        try:
            # This would query your database for destination pricing data
            # For now, return None to use fallback
            return None
        except Exception as e:
            print(f"Database query error: {e}")
            return None
    
    def _calculate_currency_based_pricing(self, currency: str) -> Dict:
        """Calculate pricing based on currency and economic factors"""
        # Dynamic pricing based on currency strength and typical accommodation costs
        currency_multipliers = {
            '$': {'budget_min': 30, 'budget_low': 80, 'budget_mid': 150, 'budget_high': 300, 'budget_luxury': 500},
            '₹': {'budget_min': 2000, 'budget_low': 5000, 'budget_mid': 10000, 'budget_high': 20000, 'budget_luxury': 35000},
            '€': {'budget_min': 25, 'budget_low': 70, 'budget_mid': 130, 'budget_high': 250, 'budget_luxury': 400},
            '£': {'budget_min': 20, 'budget_low': 60, 'budget_mid': 120, 'budget_high': 220, 'budget_luxury': 350},
            '¥': {'budget_min': 3000, 'budget_low': 8000, 'budget_mid': 15000, 'budget_high': 30000, 'budget_luxury': 50000}
        }
        
        return currency_multipliers.get(currency, currency_multipliers['$'])
    
    def _calculate_dynamic_price_range(self, price_level: int, currency: str) -> str:
        """Calculate dynamic price range when database data is unavailable"""
        base_prices = self._calculate_currency_based_pricing(currency)
        
        if price_level == 0:
            return f"{currency}{base_prices['budget_min']}-{currency}{base_prices['budget_low']}"
        elif price_level == 1:
            return f"{currency}{base_prices['budget_low']}-{currency}{base_prices['budget_mid']}"
        elif price_level == 2:
            return f"{currency}{base_prices['budget_mid']}-{currency}{base_prices['budget_high']}"
        elif price_level == 3:
            return f"{currency}{base_prices['budget_high']}-{currency}{base_prices['budget_luxury']}"
        elif price_level == 4:
            return f"{currency}{base_prices['budget_luxury']}+"
        else:
            return f"{currency}{base_prices['budget_low']}-{currency}{base_prices['budget_mid']}"
    
    def _get_fallback_accommodation_suggestions(self, destination: str) -> List[Dict]:
        """Fallback accommodation suggestions when Google Places API fails"""
        try:
            import urllib.parse
            
            # Create Google Maps search URL for accommodations
            search_query = f"hotels accommodations {destination}"
            encoded_query = urllib.parse.quote_plus(search_query)
            maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            return [
                {
                    "name": f"Accommodations in {destination}",
                    "description": f"Search for hotels and accommodations in {destination} using Google Maps",
                    "price_range": "Varies",
                    "rating": "N/A - Search results",
                    "features": ["Real-time availability", "User reviews", "Direct booking"],
                    "location": destination,
                    "why_recommended": "Direct access to Google Maps accommodation search",
                    "maps_url": maps_url,
                    "external_url": maps_url,
                    "link_type": "maps"
                }
            ]
        except Exception as e:
            return [
                {
                    "name": "Google Maps Accommodation Search",
                    "description": f"Search for accommodations in {destination}",
                    "price_range": "Varies",
                    "rating": "N/A - Search results",
                    "features": ["Real-time availability", "User reviews"],
                    "location": destination,
                    "why_recommended": "Direct access to real accommodation options",
                    "external_url": "https://www.google.com/maps/",
                    "link_type": "maps"
                }
            ]

    def _get_fallback_transportation_suggestions(self, destination: str, answers: List[Dict]) -> List[Dict]:
        """Fallback transportation suggestions when real data fails"""
        return [
            {
                "name": "RedBus",
                "description": "Online bus booking platform",
                "price_range": "₹500-₹1500",
                "rating": 4.2,
                "features": ["Online Booking", "Multiple Operators", "Easy Cancellation"],
                "location": f"To {destination}",
                "why_recommended": "Reliable bus booking service",
                "booking_url": "https://www.easemytrip.com/bus/",
                "external_url": "https://www.easemytrip.com/bus/",
                "link_type": "booking"
            }
        ]
    
    def _get_fallback_suggestions(self, room_type: str, destination: str) -> List[Dict]:
        """No fallback - AI service must work"""
        raise Exception("AI service failed and no fallback suggestions are available. Please check your API configuration.")
    
    def analyze_weather_and_suggest_activities(
        self, 
        destination: str, 
        weather_data: List[Dict], 
        existing_activities: List[Dict] = None,
        group_preferences: Dict = None
    ) -> Dict:
        """Analyze weather conditions and distribute existing activities across days with AI reasoning.
        
        Args:
            destination: The travel destination
            weather_data: List of weather forecasts for each day
            existing_activities: ACTUAL activities from the activities room (voted by users)
            group_preferences: Group preferences like group_size, etc.
        
        Returns:
            Dict with:
            - daily_analysis: Brief weather analysis for each day
            - activity_distribution: How to distribute activities across days based on weather
        """
        try:
            # Only use actual activities that users have voted for
            if not existing_activities or len(existing_activities) == 0:
                return {
                    "daily_analysis": {},
                    "activity_distribution": {},
                    "message": "No activities available yet. Activities will be distributed once users vote."
                }
            
            # Build weather summary per day
            weather_summary = []
            for i, day_weather in enumerate(weather_data):
                date = day_weather.get('date', f'Day {i+1}')
                condition = day_weather.get('condition', 'Unknown')
                temp = day_weather.get('temperature', 0)
                temp_unit = day_weather.get('temperature_unit', 'C')
                precip = day_weather.get('precipitation_probability', 0)
                is_bad = day_weather.get('is_bad_weather', False)
                
                weather_summary.append(
                    f"Day {i+1} ({date}): {condition}, {temp}°{temp_unit}, "
                    f"{precip}% rain, {'Bad weather' if is_bad else 'Good weather'}"
                )
            
            weather_text = "\n".join(weather_summary)
            
            # Extract activity names from existing activities
            activity_names = [act.get('name') or act.get('title', 'Unknown') for act in existing_activities[:10]]
            
            # Create AI prompt - BRIEF and focused on distributing EXISTING activities
            prompt = f"""You are a travel planning AI. Distribute the EXISTING activities across days based on weather.

Destination: {destination}

WEATHER FORECAST:
{weather_text}

EXISTING ACTIVITIES (use ONLY these, do not make up new ones):
{json.dumps(activity_names, indent=2)}

TASK:
1. For EACH day, provide a BRIEF 1-sentence weather analysis
2. Distribute the existing activities across days based on weather suitability
3. For each activity-day pairing, provide a BRIEF 1-sentence reason

RULES:
- Use ONLY the activities listed above
- Do NOT suggest new activities
- Keep analysis BRIEF (1 sentence per day)
- Keep reasoning BRIEF (1 sentence per activity-day)

Format as JSON:
{{
  "daily_analysis": {{
    "1": "Brief 1-sentence weather analysis for Day 1",
    "2": "Brief 1-sentence weather analysis for Day 2",
    ...
  }},
  "activity_distribution": {{
    "Activity Name 1": {{
      "best_days": [1, 2],
      "reasoning": "Brief 1-sentence why this activity suits these days' weather"
    }},
    ...
  }}
}}"""

            # Generate with Gemini
            response_text = self._generate_with_gemini(prompt)
            
            # Parse response
            try:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = json.loads(response_text)
                
                # Ensure all required fields
                if 'daily_analysis' not in result:
                    result['daily_analysis'] = {}
                if 'activity_distribution' not in result:
                    result['activity_distribution'] = {}
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"Error parsing AI weather analysis response: {e}")
                print(f"Response text: {response_text[:500]}")
                # Return fallback
                return {
                    "daily_analysis": {},
                    "activity_distribution": {},
                    "message": "Weather analysis temporarily unavailable."
                }
                
        except Exception as e:
            print(f"Error in analyze_weather_and_suggest_activities: {e}")
            import traceback
            traceback.print_exc()
            return {
                "daily_analysis": {},
                "activity_distribution": {},
                "message": "Weather analysis service temporarily unavailable."
            }