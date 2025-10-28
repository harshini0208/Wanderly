import os
import json
import requests
from typing import List, Dict, Any, Tuple
import google.generativeai as genai
from datetime import datetime, UTC
from easemytrip_service import EaseMyTripService
from firebase_service import firebase_service

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
        
        # Caching for preference extraction (avoid redundant processing)
        self._preferences_cache = {}
    
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
    
    def generate_suggestions(self, room_type: str, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate AI-powered suggestions based on user answers and preferences"""
        
        # For transportation, use real EaseMyTrip data instead of AI
        if room_type == 'transportation':
            return self._generate_transportation_suggestions(destination, answers, group_preferences)
        
        # For accommodation, use Google Places API for real data
        if room_type == 'accommodation':
            return self._generate_accommodation_suggestions_places(destination, answers, group_preferences)
        
        # Get currency based on room type and user preference
        from utils import get_currency_from_destination
        
        # For stay and transportation, use FROM location currency (home currency)
        # For dining and activities, use destination currency (local currency)
        # Use from location currency for all room types (user's home currency)
        from_location = group_preferences.get('from_location', '') if group_preferences else ''
        currency = get_currency_from_destination(from_location) if from_location else '$'
        currency_source = f"from location ({from_location})"
        
        # Prepare context from answers
        context = self._prepare_context(room_type, destination, answers, group_preferences)
        
        # Generate prompt for Gemini
        prompt = self._create_prompt(room_type, destination, context, currency)
        
        try:
            # Generate suggestions using Gemini
            response = self.model.generate_content(prompt)
            suggestions_data = self._parse_ai_response(response.text, room_type)
            
            # Enhance with Google Maps links
            enhanced_suggestions = []
            for suggestion in suggestions_data:
                enhanced_suggestion = self._enhance_with_maps(suggestion, destination, answers, group_preferences)
                enhanced_suggestions.append(enhanced_suggestion)
            
            return enhanced_suggestions
            
        except Exception as e:
            return self._get_fallback_suggestions(room_type, destination)
    
    def _prepare_context(self, room_type: str, destination: str, answers: List[Dict], group_preferences: Dict = None) -> str:
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
        
        context = "; ".join(context_parts)
        print(f"DEBUG CONTEXT FOR {room_type.upper()}: {context}")
        return context
    
    def _create_prompt(self, room_type: str, destination: str, context: str, currency: str = '$') -> str:
        """Create a detailed prompt for Gemini AI"""
        
        if room_type == 'transportation':
            return self._create_transportation_prompt(destination, context, currency)
        elif room_type == 'accommodation':
            return self._create_accommodation_prompt(destination, context, currency)
        elif room_type == 'dining':
            return self._create_dining_prompt(destination, context, currency)
        elif room_type == 'activities':
            return self._create_activities_prompt(destination, context, currency)
        else:
            return self._create_generic_prompt(room_type, destination, context, currency)
    
    def _create_transportation_prompt(self, destination: str, context: str, currency: str = '$') -> str:
        """Create specific prompt for transportation suggestions based on user preferences"""
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

    def _create_accommodation_prompt(self, destination: str, context: str, currency: str = '$') -> str:
        """Create specific prompt for accommodation suggestions"""
        return f"""
You are a hotel booking expert AI assistant helping users find REAL ACCOMMODATION OPTIONS for their trip to {destination}.

User Context: {context}

CRITICAL REQUIREMENTS FOR ACCOMMODATION:
1. ONLY suggest REAL, EXISTING hotels, resorts, hostels, or vacation rentals
2. Use actual property names that can be found on Google Maps
3. Do NOT create fictional or made-up names
4. Focus on well-known, bookable establishments
5. Provide 5-12 REAL accommodation suggestions

MANDATORY FILTERING REQUIREMENTS - STRICTLY FOLLOW ALL USER PREFERENCES:
- Analyze the user's accommodation type preferences carefully from the context
- If user selected specific accommodation types → ONLY suggest properties that match those exact types
- If user selected multiple types → Suggest a mix of properties that match ALL selected types
- MATCH the user's accommodation type preferences EXACTLY - do not suggest types they didn't select

DYNAMIC PREFERENCE MATCHING (Apply to ANY user preference mentioned in context):
- If user specified a budget range → ONLY suggest properties within that exact price range
- If user mentioned any specific requirements (pet-friendly, beachfront, pool, WiFi, parking, etc.) → ONLY suggest properties that offer those specific features
- If user mentioned dietary preferences → ONLY suggest properties that cater to those needs
- If user mentioned group size → ONLY suggest properties that can accommodate that group size
- If user mentioned location/area preferences → ONLY suggest properties in those specific areas
- If user mentioned any other specific requirements → ONLY suggest properties that meet those requirements
- NEVER suggest properties that don't match the user's specific requirements mentioned in the context

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
    "why_recommended": "Detailed explanation of why this specific property matches their exact requirements and preferences from the context"
  }}
]

Respond ONLY with the JSON array, no additional text.
"""

    def _create_dining_prompt(self, destination: str, context: str, currency: str = '$') -> str:
        """Create specific prompt for dining suggestions"""
        return f"""
You are a restaurant expert AI assistant helping users find REAL RESTAURANTS for their trip to {destination}.

User Context: {context}

CRITICAL REQUIREMENTS FOR DINING:
1. ONLY suggest REAL, EXISTING restaurants, cafes, and food establishments
2. Use actual restaurant names that can be found on Google Maps
3. Do NOT create fictional or made-up names
4. Provide 5-12 REAL dining suggestions if available, do not make up options just for the sake of proving options, even if there are limited options for the user's selected preferences, keep the recommendations realistic and based on the user's preferences and dietary restrictions dont suggest anything that doesnt align with what the user has selected and entered.
5. Consider the meal types selected (breakfast, lunch, dinner, brunch, snacks) and suggest appropriate establishments for each
6. If multiple meal types are selected, provide a mix of establishments suitable for different meal times

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
    "why_recommended": "Why this restaurant matches their specific preferences and meal type needs"
  }}
]

Respond ONLY with the JSON array, no additional text.
"""

    def _create_activities_prompt(self, destination: str, context: str, currency: str = '$') -> str:
        """Create specific prompt for activities suggestions"""
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

    def _create_generic_prompt(self, room_type: str, destination: str, context: str, currency: str = '$') -> str:
        """Create generic prompt for other room types"""
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
            # Clean the response text
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            
            # Parse JSON
            suggestions = json.loads(cleaned_text)
            
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
            return self._get_fallback_suggestions(room_type, "destination")
    
    def _enhance_with_maps(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> Dict:
        """Enhance suggestion with appropriate links based on suggestion type"""
        try:
            suggestion_name = suggestion.get('name', '').lower()
            suggestion_description = suggestion.get('description', '').lower()
            
            # Determine transportation type based on user preferences from answers
            transport_type = self._get_user_transportation_preference(answers)
            
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
    
    def _get_user_transportation_preference(self, answers: List[Dict]) -> str:
        """Extract user's transportation preference from answers"""
        if not answers:
            return None
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Analyzing {len(answers)} answers for transportation preference...")
        
        # Debug: print all answers
        for i, answer in enumerate(answers):
            question_text = answer.get('question_text', '').lower()
            question_id = answer.get('question_id', 'N/A')
            answer_value = answer.get('answer_value')
            
            logger.info(f"   Answer {i+1}:")
            logger.info(f"      ID: {question_id}")
            logger.info(f"      Q: {question_text}")
            logger.info(f"      A: {answer_value} (type: {type(answer_value).__name__})")
        
        for answer in answers:
            question_text = answer.get('question_text', '').lower()
            answer_value = answer.get('answer_value')
            
            # Check for transportation-related keywords more broadly
            has_transport_keyword = (
                'transportation' in question_text or 
                'travel' in question_text or
                'prefer' in question_text or
                'methods' in question_text
            )
            
            if has_transport_keyword and answer_value:
                # Handle different answer formats
                if isinstance(answer_value, list):
                    # Multiple selection - take first
                    if answer_value:
                        result = answer_value[0]
                        logger.info(f"✅ Found transportation preference (from list): {result}")
                        return result
                elif isinstance(answer_value, str):
                    logger.info(f"✅ Found transportation preference (as string): {answer_value}")
                    return answer_value
                elif isinstance(answer_value, dict):
                    # Sometimes answers are wrapped in objects
                    value = answer_value.get('value') or answer_value.get('answer_value') or answer_value.get('text')
                    if value:
                        logger.info(f"✅ Found transportation preference (from object): {value}")
                        return value
                else:
                    logger.warning(f"⚠️ Transportation answer found but unexpected format: {answer_value} (type: {type(answer_value).__name__})")
        
        logger.warning("⚠️ No transportation preference found in answers")
        return None
    
    def _extract_departure_date(self, answers: List[Dict]) -> str:
        """Extract departure date from answers"""
        if not answers:
            return "2024-10-25"  # Default date
        
        for answer in answers:
            question_text = answer.get('question_text', '').lower()
            if 'departure' in question_text and 'date' in question_text:
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        
        return "2024-10-25"  # Default date
    
    def _extract_return_date(self, answers: List[Dict]) -> str:
        """Extract return date from answers"""
        if not answers:
            return "2024-10-27"  # Default date
        
        for answer in answers:
            question_text = answer.get('question_text', '').lower()
            if 'return' in question_text and 'date' in question_text:
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        
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
            departure_date = self._extract_departure_date(answers)
            return_date = self._extract_return_date(answers)
            
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
            departure_date = self._extract_departure_date(answers)
            
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
            return_date = self._extract_return_date(answers)
            
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
            departure_date = self._extract_departure_date(answers)
            return_date = self._extract_return_date(answers)
            
            # Get user's transportation preference
            transport_type = self._get_user_transportation_preference(answers)
            
            # Determine if this is international travel
            is_international = self._is_international_travel(from_location, destination)
            
            # Debug logging
            logger.info(f"🔍 TRANSPORTATION REQUEST DEBUG:")
            logger.info(f"   From: {from_location}, To: {destination}")
            logger.info(f"   International: {is_international}")
            logger.info(f"   Departure: {departure_date}, Return: {return_date}")
            logger.info(f"   Detected Transport Type: {transport_type}")
            logger.info(f"   Transport Type Lower: {transport_type.lower() if transport_type else None}")
            
            suggestions = []
            
            # Get real data based on transport type
            if transport_type and transport_type.lower() == 'bus':
                logger.info("🚌 Generating BUS suggestions...")
                suggestions = self._enhance_transport_suggestions(
                    self.easemytrip_service.get_bus_options(from_location, destination, departure_date),
                    from_location, destination
                )
            elif transport_type and transport_type.lower() == 'train':
                logger.info("🚂 Generating TRAIN suggestions...")
                suggestions = self._enhance_transport_suggestions(
                    self.easemytrip_service.get_train_options(from_location, destination, departure_date),
                    from_location, destination
                )
            elif transport_type and transport_type.lower() == 'flight':
                logger.info("✈️ Generating FLIGHT suggestions...")
                # Use the new AI flight suggestion method with better integration
                suggestions = self._enhance_transport_suggestions(
                    self._generate_ai_flight_suggestions(from_location, destination, departure_date, return_date, passengers=1, class_type="Economy", answers=answers),
                    from_location, destination
                )
            else:
                # SMART FALLBACK: Check if international, then default to flights not buses!
                if is_international:
                    logger.info(f"⚠️ No transport preference - INTERNATIONAL travel detected, defaulting to FLIGHTS...")
                    suggestions = self._enhance_transport_suggestions(
                        self._generate_ai_flight_suggestions(from_location, destination, departure_date, return_date, passengers=1, class_type="Economy", answers=answers),
                        from_location, destination
                    )
                else:
                    logger.info(f"⚠️ No transport preference - domestic travel, defaulting to BUS...")
                    suggestions = self._enhance_transport_suggestions(
                        self.easemytrip_service.get_bus_options(from_location, destination, departure_date),
                        from_location, destination
                    )
            
            logger.info(f"✅ Generated {len(suggestions)} suggestions")
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Error generating transportation suggestions: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._get_fallback_transportation_suggestions(destination, answers)
    
    def _is_international_travel(self, from_location: str, destination: str) -> bool:
        """Determine if travel is international by checking if countries are different"""
        try:
            from utils import get_currency_from_destination
            
            from_currency = get_currency_from_destination(from_location)
            dest_currency = get_currency_from_destination(destination)
            
            # Different currencies = different countries (usually)
            if from_currency != dest_currency:
                return True
            
            # Also check common international routes
            from_loc_lower = from_location.lower()
            dest_lower = destination.lower()
            
            # Check if locations are in different countries
            indian_cities = ['mumbai', 'delhi', 'bangalore', 'chennai', 'hyderabad', 'pune', 'kolkata', 'ahmedabad']
            us_cities = ['new york', 'los angeles', 'chicago', 'san francisco', 'miami']
            uk_cities = ['london', 'manchester', 'edinburgh', 'birmingham']
            european_cities = ['paris', 'berlin', 'amsterdam', 'rome', 'barcelona', 'mADRID']
            asian_cities = ['tokyo', 'singapore', 'bangkok', 'seoul', 'hong kong', 'kuala lumpur']
            middle_east = ['dubai', 'doha', 'abu dhabi', 'riyadh']
            
            from_region = None
            dest_region = None
            
            if any(city in from_loc_lower for city in indian_cities):
                from_region = 'india'
            elif any(city in from_loc_lower for city in us_cities):
                from_region = 'us'
            elif any(city in from_loc_lower for city in uk_cities):
                from_region = 'uk'
            elif any(city in from_loc_lower for city in european_cities):
                from_region = 'europe'
            elif any(city in from_loc_lower for city in asian_cities):
                from_region = 'asia'
            elif any(city in from_loc_lower for city in middle_east):
                from_region = 'middle_east'
            
            if any(city in dest_lower for city in indian_cities):
                dest_region = 'india'
            elif any(city in dest_lower for city in us_cities):
                dest_region = 'us'
            elif any(city in dest_lower for city in uk_cities):
                dest_region = 'uk'
            elif any(city in dest_lower for city in european_cities):
                dest_region = 'europe'
            elif any(city in dest_lower for city in asian_cities):
                dest_region = 'asia'
            elif any(city in dest_lower for city in middle_east):
                dest_region = 'middle_east'
            
            # If both regions detected and different, it's international
            if from_region and dest_region and from_region != dest_region:
                return True
            
            # Check if one is clearly international (contains international city names)
            international_keywords = ['airport', 'international', 'flying', 'from india', 'to london', 'to new york']
            if any(kw in from_loc_lower or kw in dest_lower for kw in international_keywords):
                return True
            
            return False
            
        except Exception as e:
            print(f"Error determining international travel: {e}")
            return False
    
    def _enhance_transport_suggestions(self, suggestions: List[Dict], from_location: str, destination: str) -> List[Dict]:
        """Enhance transportation suggestions with additional metadata"""
        enhanced = []
        for suggestion in suggestions:
            # Add maps URL for booking
            if 'maps_url' not in suggestion:
                import urllib.parse
                search_query = f"transportation {from_location} to {destination}"
                encoded_query = urllib.parse.quote_plus(search_query)
                suggestion['maps_url'] = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            # Ensure booking URL exists
            if 'booking_url' not in suggestion and 'external_url' in suggestion:
                suggestion['booking_url'] = suggestion['external_url']
            elif 'external_url' not in suggestion and 'booking_url' in suggestion:
                suggestion['external_url'] = suggestion['booking_url']
            
            # Add link type if not present
            if 'link_type' not in suggestion:
                suggestion['link_type'] = 'booking'
            
            enhanced.append(suggestion)
        
        return enhanced
    
    def _generate_flight_suggestions_ai(self, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate flight suggestions using AI (since EaseMyTrip flight API is complex)"""
        try:
            context = self._prepare_context('transportation', destination, answers, group_preferences)
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
    
    def _generate_accommodation_suggestions_places(self, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate accommodation suggestions using Google Places API"""
        try:
            # TEMPORARY: Skip all filtering for debugging
            SKIP_FILTERING = False  # ← Set to True to see all results
            
            print(f"\n{'='*50}")
            print(f"GENERATING ACCOMMODATION SUGGESTIONS")
            print(f"🔍 DESTINATION RECEIVED: '{destination}'")
            print(f"{'='*50}\n")
            
            # Extract user preferences and travel data
            context = self._prepare_context('accommodation', destination, answers, group_preferences)
            
            # Get currency
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            from utils import get_currency_from_destination
            currency = get_currency_from_destination(from_location) if from_location else '$'
            
            # Extract travel dates
            start_date = group_preferences.get('start_date', '') if group_preferences else ''
            end_date = group_preferences.get('end_date', '') if group_preferences else ''
            
            # Get user's accommodation preferences
            accommodation_preferences = self._extract_accommodation_preferences(answers)
            print(f"✓ Extracted preferences: {accommodation_preferences}")
            
            # Get historical data for better suggestions
            historical_suggestions = self._get_historical_accommodation_data(destination, accommodation_preferences)
            
            # Search Google Places API for accommodations
            places_results = self._search_google_places(destination, accommodation_preferences)
            print(f"✓ Google Places returned {len(places_results)} results")
            
            # Filter and format results based on user preferences
            suggestions = self._format_places_results(places_results, destination, context, currency, start_date, end_date, accommodation_preferences)
            print(f"✓ Formatted {len(suggestions)} suggestions")
            
            if SKIP_FILTERING:
                print("⚠️ SKIPPING ALL FILTERS FOR DEBUGGING")
                return suggestions  # Return ALL suggestions, not just 12
            
            # Apply strict filtering based on user preferences
            print(f"Before preference filter: {len(suggestions)} suggestions")
            suggestions = self._filter_suggestions_by_preferences(suggestions, accommodation_preferences)
            print(f"After preference filter: {len(suggestions)} suggestions")
            
            # Apply budget-based filtering to ensure suggestions are within user's budget
            print(f"Before budget filter: {len(suggestions)} suggestions")
            suggestions = self._filter_suggestions_by_budget(suggestions, accommodation_preferences, currency)
            print(f"After budget filter: {len(suggestions)} suggestions")
            
            # Combine with historical data if available
            if historical_suggestions:
                suggestions = self._combine_with_historical_data(suggestions, historical_suggestions)
            
            # Store suggestions in database for future reference and analytics
            self._store_accommodation_suggestions(suggestions, destination, answers, group_preferences)
            
            # Return ALL suggestions (no pagination limit)
            print(f"✓ Returning all {len(suggestions)} suggestions")
            
            return suggestions
            
        except Exception as e:
            print(f"Error generating accommodation suggestions: {e}")
            return self._get_fallback_accommodation_suggestions(destination)
    
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
    
    def _search_google_places(self, destination: str, preferences: Dict) -> List[Dict]:
        """Search Google Places API for accommodations with AI-optimized queries"""
        try:
            import urllib.parse
            
            print(f"🔍 _search_google_places called with destination: '{destination}'")
            
            # Create multiple search queries for better coverage
            queries = self._create_multiple_search_queries(destination, preferences)
            print(f"🔍 Generated {len(queries)} queries: {queries}")
            
            all_results = []
            seen_place_ids = set()
            
            for query in queries:
                try:
                    print(f"🔍 Searching Google Places with query: '{query}'")
                    
                    # Google Places API Text Search
                    places_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json"
                    
                    params = {
                        'query': f"{query}",
                        'key': self.maps_api_key
                    }
                    
                    print(f"🔍 API params: {params}")
                    response = requests.get(places_url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'OK':
                            for place in data.get('results', []):
                                place_id = place.get('place_id')
                                place_name = place.get('name')
                                place_location = place.get('formatted_address', 'Unknown location')
                                if place_id and place_id not in seen_place_ids:
                                    print(f"✓ Found: {place_name} in {place_location}")
                                    all_results.append(place)
                                    seen_place_ids.add(place_id)
                        else:
                            print(f"⚠️ Google Places API returned status: {data.get('status')}")
                    
                    # Limit to avoid too many API calls
                    if len(all_results) >= 30:
                        break
                        
                except Exception as e:
                    print(f"Error with query '{query}': {e}")
                    continue
            
            print(f"Google Places API returned {len(all_results)} results")
            return all_results
                
        except Exception as e:
            print(f"Error searching Google Places: {e}")
            return []
    
    def _get_real_price_range(self, place_details: Dict, place: Dict, currency: str, destination: str = None) -> str:
        """Use AI to estimate approximate property-specific pricing"""
        try:
            price_level = place.get('price_level', 2)
            name = place.get('name', '')
            vicinity = place.get('vicinity', destination or '')
            rating = place.get('rating', 0)
            
            # Get additional context from place details
            address_components = place_details.get('address_components', [])
            overview = place_details.get('editorial_summary', {}).get('overview', '')
            
            # Build context for AI
            location_context = f"{destination}, {vicinity}" if destination else vicinity
            hotel_type = self._get_hotel_type_from_name(name)
            
            # Use AI to estimate realistic approximate prices for THIS specific property
            prompt = f"""
Estimate realistic approximate nightly rates for this specific property:

PROPERTY: {name}
LOCATION: {location_context}
RATING: {rating}/5 stars
GOOGLE PRICE LEVEL: {price_level} (0=Free, 1=Inexpensive, 2=Moderate, 3=Expensive, 4=Very Expensive)
PROPERTY TYPE: {hotel_type}
ADDITIONAL INFO: {overview[:200] if overview else 'Well-reviewed accommodation'}

Consider:
1. The actual property name and its brand positioning
2. The specific location and neighborhood
3. The rating (higher ratings often mean higher prices)
4. Google's price level indicator
5. Typical market prices for similar properties in this location

CURRENCY: {currency}

Return a realistic price range in JSON format:
{{"min_price": number, "max_price": number, "note": "approximate nightly rate"}}

IMPORTANT: Provide realistic numbers, not generic ranges. Base it on the specific property characteristics.
"""

            try:
                response = self.model.generate_content(prompt)
                result = response.text.strip()
                
                # Parse JSON from response
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    pricing = json.loads(json_match.group())
                    min_price = pricing.get('min_price')
                    max_price = pricing.get('max_price')
                    
                    if min_price and max_price:
                        return f"{currency}{int(min_price):,}-{currency}{int(max_price):,}"
                    elif min_price:
                        return f"{currency}{int(min_price):,}+"
                
            except Exception as e:
                print(f"AI pricing estimation failed: {e}")
            
            # Fallback to price level-based estimation if AI fails
            return self._estimate_price_from_level(price_level, currency, vicinity, name)
                
        except Exception as e:
            print(f"Error getting price range: {e}")
            return "Check booking site for current prices"
    
    def _get_hotel_type_from_name(self, name: str) -> str:
        """Infer hotel type from name"""
        name_lower = name.lower()
        
        if any(term in name_lower for term in ['citizenm', 'moxy', 'aloft', 'sleeper']):
            return "Boutique Modern Hotel"
        elif any(term in name_lower for term in ['easyhotel', 'ibis', 'premier inn']):
            return "Budget Hotel Chain"
        elif any(term in name_lower for term in ['hilton', 'marriott', 'hyatt', 'radisson', 'sheraton']):
            return "International Chain Hotel"
        elif any(term in name_lower for term in ['resident', 'aparthotel', 'apartment']):
            return "Serviced Apartment"
        else:
            return "Hotel"
    
    def _estimate_price_from_level(self, price_level: int, currency: str, location: str, name: str) -> str:
        """Fallback price estimation based on price level and location"""
        # Location-based multipliers (approximate only)
        location = location.lower() if location else ''
        
        # High-cost cities
        high_cost_cities = ['london', 'tokyo', 'new york', 'paris', 'singapore', 'zurich', 'geneva']
        is_expensive = any(city in location for city in high_cost_cities)
        
        # Indian cities
        indian_cities = ['mumbai', 'delhi', 'bangalore', 'chennai', 'hyderabad']
        is_indian = any(city in location for city in indian_cities)
        
        # Low-cost destinations
        budget_destinations = ['bangkok', 'phuket', 'bali', 'ho chi minh', 'chiang mai']
        is_budget = any(dest in location for dest in budget_destinations)
        
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
        # These are fallback prices based on standard accommodation pricing
        base_prices = self._calculate_dynamic_fallback_prices(currency, price_level)
        
        if price_level in base_prices:
            min_price, max_price = base_prices[price_level]
            return f"{currency}{int(min_price * multiplier):,}-{currency}{int(max_price * multiplier):,}"
        else:
            return "Check booking site for pricing"
    
    def _get_dynamic_price_fallback(self, price_level: int, currency: str, hotel_name: str, vicinity: str) -> str:
        """Dynamic fallback pricing when AI fails"""
        try:
            # Use AI to determine currency-appropriate pricing multipliers
            prompt = f"""
            Determine appropriate pricing multipliers for this currency and price level.
            
            CURRENCY: {currency}
            PRICE LEVEL: {price_level} (0=Free, 1=Inexpensive, 2=Moderate, 3=Expensive, 4=Very Expensive)
            LOCATION: {vicinity}
            
            REQUIREMENTS:
            1. Consider the currency and its typical pricing scale
            2. Consider the price level (0-4) and what it represents
            3. Consider the location and its economic context
            4. Provide realistic multipliers for this currency and price level
            
            Return ONLY a JSON object with:
            {{"min_multiplier": number, "max_multiplier": number}}
            """
            
            try:
                response = self.model.generate_content(prompt)
                result = response.text.strip()
                import json
                multipliers = json.loads(result)
                min_mult = multipliers.get('min_multiplier', 1.0)
                max_mult = multipliers.get('max_multiplier', 3.0)
            except:
                # Ultimate fallback - use generic multipliers
                min_mult = 1.0
                max_mult = 3.0
            
            # Calculate prices dynamically
            min_price = int(min_mult * 1000)  # Base unit
            max_price = int(max_mult * 1000)
            
            if price_level == 0:
                return "Free"
            else:
                return f"{currency}{min_price}-{currency}{max_price}"
                
        except Exception as e:
            print(f"Error in dynamic price fallback: {e}")
            return "Price on request"
    
    def _get_real_description(self, place_details: Dict, place: Dict, name: str) -> str:
        """Get real description from Google Places data using AI"""
        try:
            hotel_name = name
            rating = place.get('rating', 0)
            vicinity = place.get('vicinity', '')
            price_level = place.get('price_level', 0)
            
            # Get additional context from place details
            editorial_summary = place_details.get('editorial_summary', {}) if place_details else {}
            overview = editorial_summary.get('overview', '')
            
            reviews = place_details.get('reviews', []) if place_details else []
            review_text = ""
            if reviews:
                best_review = max(reviews, key=lambda x: x.get('rating', 0))
                review_text = best_review.get('text', '')
            
            # Use AI to create a meaningful description
            prompt = f"""
            Create a compelling description for this accommodation based on available data.
            
            ACCOMMODATION DETAILS:
            Name: {hotel_name}
            Location: {vicinity}
            Rating: {rating}/5
            Google Price Level: {price_level} (0=Free, 1=Inexpensive, 2=Moderate, 3=Expensive, 4=Very Expensive)
            
            GOOGLE PLACES OVERVIEW: {overview}
            
            GUEST REVIEW SAMPLE: {review_text[:200] if review_text else 'No reviews available'}
            
            REQUIREMENTS:
            1. Create an engaging, informative description
            2. Highlight key features and benefits
            3. Mention location advantages
            4. Include rating information naturally
            5. Keep it concise but compelling (2-3 sentences)
            6. Use professional, marketing-friendly language
            7. Do NOT include pricing information
            
            Return ONLY the description text, no additional formatting.
            """
            
            response = self.model.generate_content(prompt)
            description = response.text.strip()
            
            # Validate the description
            if description and len(description) > 20:
                return description
            else:
                # Fallback: Use Google Places overview if available
                if overview and len(overview) > 20:
                    return overview.strip()
                else:
                    return f"{hotel_name} - Quality accommodation option in {vicinity}."
            
        except Exception as e:
            print(f"Error getting real description: {e}")
            return f"{name} - Accommodation option found via Google Places API."
    
    def _create_multiple_search_queries(self, destination: str, preferences: Dict) -> List[str]:
        """Create multiple targeted search queries - one per accommodation type"""
        try:
            queries = []
            accommodation_types = preferences.get('accommodation_types', ['Hotel'])  # Default to 'Hotel' if none provided
            location_prefs = preferences.get('LOCATION_PREFERENCES', [destination])  # Default to destination
            location = location_prefs[0]  # Use the first location preference
            
            # Generate one query per accommodation type
            for acc_type in accommodation_types:
                query = self._create_ai_optimized_search_query(destination, preferences, acc_type)
                queries.append(query)
            
            # Add queries for well-known properties (if applicable)
            known_properties = self._get_known_properties(destination, preferences)
            for property_name, acc_type in known_properties:
                if acc_type in accommodation_types and location.lower() in property_name.lower():
                    queries.append(f"{property_name} {destination}")
            
            # Remove duplicates and limit to a reasonable number (e.g., 5)
            unique_queries = list(dict.fromkeys(queries))[:5]
            return unique_queries if unique_queries else [self._create_basic_search_query(destination, preferences)]
            
        except Exception as e:
            print(f"Error creating multiple search queries: {e}")
            return [self._create_basic_search_query(destination, preferences)]
    
    def _get_known_properties(self, destination: str, preferences: Dict) -> List[Tuple[str, str]]:
        """Retrieve well-known properties from Firebase with AI fallback"""
        properties = []
        try:
            # Try Firebase database first
            docs = firebase_service.db.collection('known_properties').where('destination', '==', destination).stream()
            for doc in docs:
                data = doc.to_dict()
                properties.append((data.get('name'), data.get('type')))
            
            if properties:
                return self._filter_properties_by_preferences(properties, preferences)
            
            # Fallback to AI if database is empty
            prompt = f"""
            List well-known accommodations in {destination} that match these preferences:
            {json.dumps(preferences, indent=2)}
            
            Return a JSON array of objects with name and type. If no well-known properties exist, return an empty array [].
            Example format:
            [
                {{"name": "Hotel Name", "type": "Hotel"}},
                {{"name": "Resort Name", "type": "Resort"}}
            ]
            """
            try:
                response = self.model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Handle empty or invalid responses
                if not response_text or response_text == "[]" or response_text.startswith("No"):
                    return []
                
                ai_properties = json.loads(response_text)
                if isinstance(ai_properties, list):
                    return [(p.get('name', ''), p.get('type', 'Hotel')) for p in ai_properties if p.get('name')]
                else:
                    return []
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing AI response for known properties: {e}")
                return []
            except Exception as e:
                print(f"Error getting AI properties: {e}")
                return []
            
        except Exception as e:
            print(f"Error fetching known properties: {e}")
            return []
    
    def _filter_properties_by_preferences(self, properties: List[Tuple[str, str]], preferences: Dict) -> List[Tuple[str, str]]:
        """Filter properties based on user preferences"""
        try:
            location_prefs = preferences.get('LOCATION_PREFERENCES', [])
            location = location_prefs[0].lower() if location_prefs else ''
            accommodation_types = preferences.get('accommodation_types', [])
            
            filtered_properties = []
            for name, acc_type in properties:
                # Check if property matches accommodation type and location preference
                if (not accommodation_types or acc_type in accommodation_types) and \
                   (not location or location in name.lower()):
                    filtered_properties.append((name, acc_type))
            
            return filtered_properties
            
        except Exception as e:
            print(f"Error filtering properties: {e}")
            return properties
    
    def _extract_departure_date(self, answers: List[Dict]) -> str:
        """Extract departure date with environment variable fallback"""
        for answer in answers:
            if 'departure' in answer.get('question_text', '').lower() and 'date' in answer.get('question_text', '').lower():
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
        return os.getenv('DEFAULT_DEPARTURE_DATE', datetime.now(UTC).strftime('%Y-%m-%d'))
    
    def _extract_return_date(self, answers: List[Dict]) -> str:
        """Extract return date with environment variable fallback"""
        for answer in answers:
            if 'return' in answer.get('question_text', '').lower() and 'date' in answer.get('question_text', '').lower():
                date_value = answer.get('answer_value')
                if date_value:
                    return str(date_value)
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
    
    def _generate_destination_specific_queries(self, destination: str, preferences: Dict) -> List[str]:
        """Use AI to generate destination-specific premium hotel queries"""
        try:
            accommodation_types = preferences.get('accommodation_types', [])
            budget_info = preferences.get('budget_range', {})
            
            prompt = f"""
            Generate specific Google Places search queries for premium accommodations in this destination.
            
            DESTINATION: {destination}
            ACCOMMODATION TYPES: {accommodation_types}
            BUDGET INFO: {budget_info}
            
            REQUIREMENTS:
            1. Generate 3-5 specific search queries for this destination
            2. Include well-known hotel chains and premium properties by name
            3. Include luxury and premium accommodation terms
            4. Include business and upscale hotel terms
            5. Make queries specific to this destination
            6. Use terms that Google Places API will recognize
            7. Consider the destination's characteristics (beach, mountain, city, etc.)
            8. Consider the accommodation types requested
            9. Consider the budget range for appropriate property levels
            
            Return ONLY the search queries, one per line, no explanations or formatting.
            """
            
            response = self.model.generate_content(prompt)
            queries_text = response.text.strip()
            
            # Parse the response into individual queries
            queries = []
            for line in queries_text.split('\n'):
                query = line.strip().strip('"').strip("'")
                if query and len(query) > 5:
                    queries.append(query)
            
            return queries[:5]  # Limit to 5 queries
            
        except Exception as e:
            print(f"Error generating destination-specific queries: {e}")
            return []
    
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
    
    def _create_ai_optimized_search_query(self, destination: str, preferences: Dict, accommodation_type: str = None) -> str:
        """Create a dynamic search query based on preferences, using AI only when needed"""
        try:
            # Extract preferences dynamically
            location_prefs = preferences.get('LOCATION_PREFERENCES', [])
            accommodation_types = preferences.get('accommodation_types', [])
            
            # Use provided accommodation_type or select the first one
            selected_type = accommodation_type or (accommodation_types[0] if accommodation_types else 'Hotel')
            
            # CRITICAL: Always include the destination in the query, even if we have location preferences
            # Location preferences (like "beachside") are additional keywords, not replacements for destination
            
            # Build query with destination and location preferences
            if location_prefs:
                # Combine destination with location keywords (e.g., "Airbnb beachside Udupi")
                location_keywords = ' '.join(location_prefs[:2])  # Take first 2 location keywords
                query = f"{selected_type} {location_keywords} {destination}"
            else:
                # Just accommodation type + destination
                query = f"{selected_type} {destination}"
            
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
                
                # If no match found and we have location info, be lenient but cautious
                if not has_destination_match and vicinity:
                    # Use AI to check if this property is in the destination city
                    try:
                        prompt = f"""Is this property located in {destination}?
                        
                        Property Name: {name}
                        Location/Vicinity: {vicinity}
                        Destination: {destination}
                        
                        Respond with only "YES" if the property is in or near {destination}, or "NO" if it's clearly in a different city.
                        Be lenient - if unsure, respond "YES".
                        """
                        response = self.model.generate_content(prompt)
                        result = response.text.strip().upper()
                        
                        if result == "NO":
                            print(f"✗ AI confirmed different city: {name} in {vicinity}")
                            continue
                    except Exception as e:
                        # If AI check fails, be lenient and include the property
                        pass
                
                # Get place details for more information
                place_details = self._get_place_details(place.get('place_id'))
                
                # Build features list dynamically from Google Places data
                features = self._extract_dynamic_features(place_details, place)
                
                # Get pricing information from Google Places
                price_indicator = self._get_real_price_range(place_details, place, currency, destination)
                
                # Get real description from Google Places
                real_description = self._get_real_description(place_details, place, name)
                
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
                    'maps_url': f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}",
                    'maps_embed_url': self._create_maps_embed_url({'place_id': place.get('place_id'), 'name': name, 'location': vicinity}, destination),
                    'external_url': f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}",
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
        """Extract features from text using AI"""
        try:
            if not text or len(text) < 10:
                return []
            
            # Use AI to extract key features from text
            prompt = f"""
            Extract 2-3 key accommodation features from this text. Return only the feature names, separated by commas.
            
            Text: {text[:200]}...
            
            Examples of features: "Free WiFi", "Swimming pool", "Pet friendly", "Beachfront", "Restaurant", "Parking"
            
            Return only the feature names, no explanations.
            """
            
            response = self.model.generate_content(prompt)
            features_text = response.text.strip()
            
            # Parse features
            features = [f.strip() for f in features_text.split(',') if f.strip()]
            return features[:3]  # Limit to 3 features
            
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
    
    def _get_historical_accommodation_data(self, destination: str, preferences: Dict) -> List[Dict]:
        """Retrieve historical accommodation data from database for better suggestions"""
        try:
            # Query database for similar searches
            query = firebase_service.db.collection('accommodation_searches').where('destination', '==', destination)
            docs = query.stream()
            
            historical_data = []
            for doc in docs:
                data = doc.to_dict()
                # Check if preferences match
                if self._preferences_match(data.get('user_preferences', {}), preferences):
                    historical_data.extend(data.get('suggestions', []))
            
            return historical_data[:5]  # Return top 5 historical suggestions
            
        except Exception as e:
            print(f"Error retrieving historical data: {e}")
            return []
    
    def _preferences_match(self, stored_prefs: Dict, current_prefs: Dict) -> bool:
        """Check if stored preferences match current preferences dynamically"""
        try:
            # Use AI to determine if preferences match
            prompt = f"""
            Compare these two sets of accommodation preferences and determine if they are similar enough to be considered matching.
            
            STORED PREFERENCES:
            {json.dumps(stored_prefs, indent=2)}
            
            CURRENT PREFERENCES:
            {json.dumps(current_prefs, indent=2)}
            
            ANALYSIS CRITERIA:
            - Compare accommodation types (if specified)
            - Compare specific requirements (pet-friendly, beachfront, etc.)
            - Compare amenities and features
            - Compare budget ranges (if specified)
            - Consider preferences as matching if they have similar accommodation types and key requirements
            
            Respond with only "MATCH" if the preferences are similar enough, or "NO MATCH" if they are too different.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip().upper()
            
            return result == "MATCH"
            
        except Exception as e:
            print(f"Error comparing preferences with AI: {e}")
            # Fallback to dynamic comparison without hardcoded categories
            return self._dynamic_preference_comparison(stored_prefs, current_prefs)
    
    def _dynamic_preference_comparison(self, stored_prefs: Dict, current_prefs: Dict) -> bool:
        """Dynamic preference comparison without hardcoded categories"""
        try:
            # Compare all non-empty preference fields dynamically
            for key, current_value in current_prefs.items():
                if current_value:  # Only compare non-empty values
                    stored_value = stored_prefs.get(key)
                    
                    # Handle different data types
                    if isinstance(current_value, list) and isinstance(stored_value, list):
                        # Compare lists - check if they have any common elements
                        if not any(item in stored_value for item in current_value):
                            return False
                    elif isinstance(current_value, bool) and isinstance(stored_value, bool):
                        # Compare booleans - must match exactly
                        if current_value != stored_value:
                            return False
                    elif isinstance(current_value, (int, float)) and isinstance(stored_value, (int, float)):
                        # Compare numbers - allow some tolerance for budget ranges
                        if abs(current_value - stored_value) > (current_value * 0.2):  # 20% tolerance
                            return False
                    elif isinstance(current_value, str) and isinstance(stored_value, str):
                        # Compare strings - case insensitive partial match
                        if current_value.lower() not in stored_value.lower() and stored_value.lower() not in current_value.lower():
                            return False
            
            return True
            
        except Exception as e:
            print(f"Error in dynamic preference comparison: {e}")
            return False
    
    def _combine_with_historical_data(self, current_suggestions: List[Dict], historical_suggestions: List[Dict]) -> List[Dict]:
        """Combine current Google Places results with historical data"""
        try:
            # Remove duplicates based on place_id or name
            seen_places = set()
            combined_suggestions = []
            
            # Add current suggestions first (more recent)
            for suggestion in current_suggestions:
                place_id = suggestion.get('place_id')
                name = suggestion.get('name')
                key = place_id or name
                
                if key and key not in seen_places:
                    seen_places.add(key)
                    combined_suggestions.append(suggestion)
            
            # Add historical suggestions if not already present
            for suggestion in historical_suggestions:
                place_id = suggestion.get('place_id')
                name = suggestion.get('name')
                key = place_id or name
                
                if key and key not in seen_places:
                    seen_places.add(key)
                    # Mark as historical data
                    suggestion['source'] = 'historical'
                    combined_suggestions.append(suggestion)
            
            return combined_suggestions  # Return all suggestions
            
        except Exception as e:
            print(f"Error combining historical data: {e}")
            return current_suggestions
    
    def _filter_suggestions_by_budget(self, suggestions: List[Dict], preferences: Dict, currency: str) -> List[Dict]:
        """Filter suggestions to ensure they are within user's budget range (including below budget)"""
        try:
            # Extract user's budget range
            budget_info = self._extract_budget_from_preferences(preferences)
            
            if not budget_info:
                print("No budget information found, skipping budget filtering")
                return suggestions
            
            # Parse budget range for display
            budget_min, budget_max = self._parse_budget_range(budget_info)
            print(f"Filtering suggestions by budget: {budget_min}-{budget_max} {currency}")
            
            filtered_suggestions = []
            
            for suggestion in suggestions:
                if self._suggestion_within_budget(suggestion, budget_info, currency):
                    filtered_suggestions.append(suggestion)
                    print(f"✓ Budget OK: {suggestion.get('name')}")
                else:
                    print(f"✗ Budget exceeded: {suggestion.get('name')}")
            
            print(f"Budget filtering: {len(suggestions)} → {len(filtered_suggestions)} suggestions")
            return filtered_suggestions
            
        except Exception as e:
            print(f"Error filtering suggestions by budget: {e}")
            return suggestions
    
    def _suggestion_within_budget(self, suggestion: Dict, budget_info: any, currency: str) -> bool:
        """Use AI to determine if suggestion is within user's budget range (including below budget)"""
        try:
            suggestion_data = {
                'name': suggestion.get('name', ''),
                'description': suggestion.get('description', ''),
                'features': suggestion.get('features', []),
                'location': suggestion.get('location', ''),
                'rating': suggestion.get('rating', 0),
                'current_price_range': suggestion.get('price_range', '')
            }
            
            # Parse budget range
            budget_min, budget_max = self._parse_budget_range(budget_info)
            
            # Get real-time pricing estimate
            pricing_data = self._get_real_time_pricing(suggestion_data['name'], suggestion_data['location'])
            
            # Create AI prompt for budget analysis with real pricing data
            prompt = f"""
            Analyze this accommodation suggestion and determine if it fits within the user's budget range.
            
            ACCOMMODATION SUGGESTION:
            Name: {suggestion_data['name']}
            Description: {suggestion_data['description']}
            Features: {', '.join(suggestion_data['features'])}
            Location: {suggestion_data['location']}
            Rating: {suggestion_data['rating']}
            Current Price Range: {suggestion_data['current_price_range']}
            
            ESTIMATED PRICING DATA:
            Min Price: ₹{pricing_data.get('estimated_min_price', 'N/A')}
            Max Price: ₹{pricing_data.get('estimated_max_price', 'N/A')}
            Confidence: {pricing_data.get('confidence', 'low')}
            
            USER BUDGET REQUIREMENT: ₹{budget_min} - ₹{budget_max}
            
            IMPORTANT BUDGET LOGIC:
            - Hotels BELOW the budget range are ACCEPTABLE (user can save money)
            - Hotels ABOVE the budget range are NOT ACCEPTABLE (user cannot afford)
            - Hotels WITHIN the budget range are ACCEPTABLE
            
            ANALYSIS CRITERIA:
            1. Use the estimated pricing data as primary reference
            2. Consider the accommodation's name, description, and features
            3. Consider the location and its typical pricing
            4. Consider the rating (higher ratings often mean higher prices)
            5. Consider any luxury indicators in the name or description
            6. Be conservative - if unsure, prefer to include the suggestion
            
            Examples:
            - Hotel estimated ₹4,000-₹7,000 with budget ₹10,000-₹25,000 → WITHIN_BUDGET (below budget is fine)
            - Hotel estimated ₹12,000-₹18,000 with budget ₹10,000-₹25,000 → WITHIN_BUDGET (within range)
            - Hotel estimated ₹30,000-₹50,000 with budget ₹10,000-₹25,000 → OVER_BUDGET (above budget)
            
            Respond with only "WITHIN_BUDGET" if it fits the budget (including below budget), or "OVER_BUDGET" if it exceeds the budget.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip().upper()
            
            return result == "WITHIN_BUDGET"
            
        except Exception as e:
            print(f"Error in AI budget analysis: {e}")
            return True  # Fallback to avoid filtering out all suggestions
    
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
    
    def _get_real_time_pricing(self, hotel_name: str, destination: str) -> Dict:
        """Get real-time pricing information for a hotel (placeholder for future API integration)"""
        try:
            # Get currency dynamically from destination
            currency = self._get_currency_from_destination(destination)
            
            # This is a placeholder for future integration with booking APIs
            # For now, we'll use AI to estimate pricing based on hotel characteristics
            
            prompt = f"""
            Estimate the typical price range for this hotel based on its characteristics.
            
            HOTEL NAME: {hotel_name}
            DESTINATION: {destination}
            CURRENCY: {currency}
            
            Consider:
            1. Hotel name and brand recognition
            2. Destination pricing levels
            3. Typical hotel categories
            4. Local currency and pricing norms
            
            Return a JSON object with:
            {{
                "estimated_min_price": number,
                "estimated_max_price": number,
                "confidence": "high/medium/low",
                "currency": "{currency}"
            }}
            
            Be conservative in estimates. If unsure, provide a wide range.
            Use the appropriate currency for the destination.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            # Try to parse JSON response
            try:
                import json
                pricing_data = json.loads(result)
                return pricing_data
            except:
                # Fallback if JSON parsing fails - use AI to estimate
                try:
                    fallback_prompt = f"""
                    Estimate pricing for {hotel_name} in {destination}.
                    Return JSON: {{"estimated_min_price": number, "estimated_max_price": number, "confidence": "low", "currency": "{currency}"}}
                    """
                    fallback_response = self.model.generate_content(fallback_prompt)
                    fallback_result = fallback_response.text.strip()
                    import json
                    return json.loads(fallback_result)
                except:
                    return {
                        "estimated_min_price": 0,
                        "estimated_max_price": 0,
                        "confidence": "low",
                        "currency": currency
                    }
                
        except Exception as e:
            print(f"Error getting real-time pricing: {e}")
            # Get currency dynamically even in error case
            try:
                currency = self._get_currency_from_destination(destination)
            except:
                currency = "USD"  # Ultimate fallback
            return {
                "estimated_min_price": 0,
                "estimated_max_price": 0,
                "confidence": "low",
                "currency": currency
            }
    
    def _filter_suggestions_by_preferences(self, suggestions: List[Dict], preferences: Dict) -> List[Dict]:
        """Apply flexible filtering based on user preferences using AI - OPTIMIZED WITH BATCHING"""
        try:
            print(f"Filtering {len(suggestions)} suggestions based on preferences: {preferences}")
            
            # If we have many suggestions, use batch filtering (1 API call instead of N)
            if len(suggestions) > 5:
                print(f"📦 Using BATCH filtering for {len(suggestions)} suggestions (1 AI call instead of {len(suggestions)})")
                filtered_suggestions = self._batch_filter_suggestions(suggestions, preferences)
            else:
                # For small batches, use individual calls
                filtered_suggestions = []
                for suggestion in suggestions:
                    if self._suggestion_matches_preferences_ai(suggestion, preferences):
                        filtered_suggestions.append(suggestion)
                        print(f"✓ Kept suggestion: {suggestion.get('name')}")
                    else:
                        print(f"✗ Filtered out suggestion: {suggestion.get('name')}")
            
            # Apply lenient fallback if too many filtered
            has_meals_requirement = False
            if 'AMENITIES' in preferences:
                amenities = preferences['AMENITIES']
                if isinstance(amenities, list) and any('meal' in str(amenity).lower() for amenity in amenities):
                    has_meals_requirement = True
            
            if has_meals_requirement and len(filtered_suggestions) < len(suggestions) * 0.3:
                print("⚠️ Too many suggestions filtered out - applying lenient fallback")
                filtered_suggestions = []
                for suggestion in suggestions:
                    suggestion_name = suggestion.get('name', '').lower()
                    if any(type_word in suggestion_name for type_word in ['hotel', 'resort', 'retreat', 'homestay', 'guesthouse', 'cottage', 'inn', 'villa', 'residency']):
                        filtered_suggestions.append(suggestion)
            
            print(f"Filtered to {len(filtered_suggestions)} matching suggestions")
            return filtered_suggestions
            
        except Exception as e:
            print(f"Error filtering suggestions: {e}")
            return suggestions
    
    def _batch_filter_suggestions(self, suggestions: List[Dict], preferences: Dict) -> List[Dict]:
        """Batch filter suggestions in one AI call instead of N individual calls"""
        try:
            # Prepare batch data for AI
            suggestions_data = []
            for suggestion in suggestions:
                suggestions_data.append({
                    'name': suggestion.get('name', ''),
                    'description': suggestion.get('description', ''),
                    'features': suggestion.get('features', []),
                    'location': suggestion.get('location', ''),
                    'rating': suggestion.get('rating', 0)
                })
            
            prompt = f"""
            Filter these {len(suggestions_data)} accommodation suggestions based on user preferences.
            BE EXTREMELY LENIENT AND FLEXIBLE.
            
            USER PREFERENCES:
            {json.dumps(preferences, indent=2)}
            
            SUGGESTIONS TO FILTER:
            {json.dumps(suggestions_data, indent=2)}
            
            MATCHING RULES:
            1. If user wants "hotel", accept: Hotel, Resort, Inn, Lodge, Retreat
            2. If user wants "airbnb", accept: Homestay, Cottage, Villa, Apartment
            3. If meals required, accept any with restaurant/kitchen/dining mentions OR any resort/homestay
            4. When in doubt, MATCH
            
            Return ONLY a JSON array of matched suggestion names:
            ["Hotel Name 1", "Hotel Name 2", ...]
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse AI response to get matched suggestion names
            try:
                matched_names = json.loads(response.text.strip())
                filtered = [s for s in suggestions if s.get('name') in matched_names]
                print(f"✓ Batch filtering kept {len(filtered)}/{len(suggestions)} suggestions")
                return filtered
            except:
                # Fallback: use lenient filtering
                print("⚠️ AI parsing failed, using lenient fallback")
                return suggestions
                
        except Exception as e:
            print(f"Error in batch filtering: {e}")
            return suggestions
    
    def _suggestion_matches_preferences_ai(self, suggestion: Dict, preferences: Dict) -> bool:
        """Use AI to dynamically check if a suggestion matches user preferences - BE REASONABLE"""
        try:
            suggestion_data = {
                'name': suggestion.get('name', ''),
                'description': suggestion.get('description', ''),
                'features': suggestion.get('features', []),
                'location': suggestion.get('location', ''),
                'rating': suggestion.get('rating', 0)
            }
            
            prompt = f"""
            Determine if this accommodation suggestion matches the user's preferences. BE EXTREMELY LENIENT AND FLEXIBLE.
            
            SUGGESTION:
            {json.dumps(suggestion_data, indent=2)}
            
            USER PREFERENCES:
            {json.dumps(preferences, indent=2)}
            
            CRITICAL MATCHING RULES (BE VERY FLEXIBLE):
            
            1. ACCOMMODATION TYPE MATCHING:
               - If user wants "hotel", accept: Hotel, Resort, Inn, Lodge, Retreat, Residency
               - If user wants "airbnb", accept: Homestay, Cottage, Villa, Apartment, Entire Villa, Entire Floor
               - If user wants "guesthouse", accept: Guesthouse, Homestay, Inn, Cottage
               - BE FLEXIBLE with synonyms and variations
            
            2. MEALS/AMENITIES MATCHING (MOST IMPORTANT):
               - If user wants "meals included", accept if:
                 * The name/description mentions: Restaurant, Dining, Food, Kitchen, Meals, Breakfast, Lunch, Dinner
                 * It's a Resort/Retreat (they typically provide meals)
                 * It's a Homestay (they often provide meals)
                 * ANY mention of food services
               - DO NOT require explicit "all 3 meals" language
               - Assume resorts and homestays can provide meals even if not explicitly stated
            
            3. BUDGET MATCHING:
               - DO NOT filter by budget in this step
               - Budget filtering happens separately
            
            4. LOCATION MATCHING:
               - Accept ANY accommodation in the same city/area
            
            IMPORTANT DECISION LOGIC:
            - If accommodation TYPE matches (hotel/airbnb/guesthouse) → MATCH
            - If it's a resort/retreat/homestay → MATCH (they typically provide meals)
            - Only reject if it's completely the wrong type (e.g., a standalone restaurant)
            - When in doubt, return MATCH
            
            Return ONLY "MATCH" or "NO MATCH"
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip().upper()
            
            # Log the decision for debugging
            print(f"AI Decision for '{suggestion_data['name']}': {result}")
            
            return result == "MATCH"
            
        except Exception as e:
            print(f"Error in dynamic AI preference matching: {e}")
            return True  # Fallback to INCLUDE suggestions when AI fails
    
    def _basic_preference_match(self, suggestion: Dict, preferences: Dict) -> bool:
        """Fallback basic preference matching using AI to avoid hardcoded terms"""
        try:
            suggestion_text = f"{suggestion.get('name', '')} {suggestion.get('description', '')} {', '.join(suggestion.get('features', []))}"
            
            # Use AI to check if suggestion matches preferences dynamically
            prompt = f"""
            Check if this accommodation suggestion matches the user's preferences using basic text analysis.
            
            SUGGESTION TEXT: "{suggestion_text}"
            
            USER PREFERENCES: {json.dumps(preferences, indent=2)}
            
            Check each preference requirement:
            1. If accommodation types are specified, check if the suggestion matches any of those types
            2. If pet_friendly is true, check if the text mentions pet-friendly services
            3. If beachfront is true, check if the text mentions beachfront/waterfront access
            4. If amenities are specified, check if the text mentions any of those amenities
            5. If budget is specified, check if the suggestion appears to be within that range
            
            Respond with only "MATCH" if the suggestion meets the requirements, or "NO MATCH" if it doesn't.
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip().upper()
            
            return result == "MATCH"
            
        except Exception as e:
            print(f"Error in AI-based basic preference matching: {e}")
            # Ultimate fallback - return True to avoid filtering out all suggestions
            return True
    
    def _determine_user_budget_range(self, preferences: Dict, currency: str, destination: str = None) -> str:
        """Determine price range based on user's actual budget preferences dynamically"""
        try:
            # Use AI to find budget information in preferences
            budget_info = self._extract_budget_from_preferences(preferences)
            
            if budget_info:
                if isinstance(budget_info, dict) and 'min' in budget_info and 'max' in budget_info:
                    return f"{currency}{budget_info['min']}-{currency}{budget_info['max']}"
                elif isinstance(budget_info, str) and '-' in budget_info:
                    return f"{currency}{budget_info}"
            
            # If no user budget specified, use AI to determine appropriate range based on location and preferences
            return self._determine_ai_budget_range(preferences, currency, destination)
            
        except Exception as e:
            print(f"Error determining user budget range: {e}")
            return f"{currency}1000-{currency}5000"  # Fallback range
    
    def _extract_budget_from_preferences(self, preferences: Dict) -> any:
        """Use AI to extract budget information from dynamic preferences"""
        try:
            prompt = f"""
            Extract budget/price information from these accommodation preferences.
            
            PREFERENCES: {json.dumps(preferences, indent=2)}
            
            Look for any budget, price, or cost-related information in the preferences.
            Return the budget information in format "min-max" (e.g., "10000-25000") or "NONE" if no budget found.
            
            Return only the budget range or "NONE", no explanations.
            """
            
            response = self.model.generate_content(prompt)
            budget_result = response.text.strip()
            
            if budget_result != "NONE" and budget_result:
                return budget_result
            
            return None
            
        except Exception as e:
            print(f"Error extracting budget from preferences: {e}")
            return None
    
    def _determine_ai_budget_range(self, preferences: Dict, currency: str, destination: str = None) -> str:
        """Use AI to determine appropriate budget range based on location and preferences"""
        try:
            prompt = f"""
            Determine an appropriate budget range for accommodations based on these factors:
            
            DESTINATION: {destination}
            CURRENCY: {currency}
            ACCOMMODATION TYPES: {preferences.get('types', [])}
            LOCATION PREFERENCES: {preferences.get('location_preferences', [])}
            SPECIFIC REQUIREMENTS: {preferences.get('specific_requirements', [])}
            
            Consider:
            1. The destination's typical accommodation costs
            2. The accommodation types requested
            3. Any specific location requirements (near consulate, city center, etc.)
            4. Any special requirements that might affect pricing
            
            Return the budget range in format: "{currency}X-{currency}Y"
            Examples: "{currency}5000-{currency}15000", "{currency}2000-{currency}8000"
            
            Return only the budget range, no explanations.
            """
            
            response = self.model.generate_content(prompt)
            budget_range = response.text.strip()
            
            # Validate the format
            if currency in budget_range and '-' in budget_range:
                return budget_range
            
            # Fallback to destination-based pricing
            return self._determine_price_range(2, currency, destination)  # Use mid-range as default
            
        except Exception as e:
            print(f"Error determining AI budget range: {e}")
            return self._determine_price_range(2, currency, destination)
    
    def _get_place_details(self, place_id: str) -> Dict:
        """Get detailed information about a place"""
        try:
            if not place_id:
                return {}
            
            places_url = f"https://maps.googleapis.com/maps/api/place/details/json"
            
            params = {
                'place_id': place_id,
                'fields': 'formatted_phone_number,website,opening_hours,editorial_summary,amenities',
                'key': self.maps_api_key
            }
            
            response = requests.get(places_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', {})
            else:
                return {}
                
        except Exception as e:
            print(f"Error getting place details: {e}")
            return {}
    
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
