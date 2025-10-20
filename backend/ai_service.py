import os
import json
import requests
from typing import List, Dict, Any
import google.generativeai as genai
from datetime import datetime
from easemytrip_service import EaseMyTripService

class AIService:
    def __init__(self):
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
    
    def generate_suggestions(self, room_type: str, destination: str, answers: List[Dict], group_preferences: Dict = None) -> List[Dict]:
        """Generate AI-powered suggestions based on user answers and preferences"""
        
        # For transportation, use real EaseMyTrip data instead of AI
        if room_type == 'transportation':
            return self._generate_transportation_suggestions(destination, answers, group_preferences)
        
        # Get currency based on room type and user preference
        from utils import get_currency_from_destination
        
        # For stay and transportation, use FROM location currency (home currency)
        # For dining and activities, use destination currency (local currency)
        if room_type in ['accommodation', 'transportation']:
            # Use from location currency for planning purposes (user's home currency)
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            currency = get_currency_from_destination(from_location) if from_location else '$'
            currency_source = f"from location ({from_location})"
        else:
            # Use destination currency for local services
            currency = get_currency_from_destination(destination)
            currency_source = f"destination ({destination})"
        
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
                else:
                    # Handle text questions - emphasize accommodation type
                    if "accommodation" in question_text.lower() and "type" in question_text.lower():
                        context_parts.append(f"ACCOMMODATION TYPE PREFERENCE: {answer_value}")
                    else:
                        context_parts.append(f"{question_text}: {answer_value}")
        
        return "; ".join(context_parts)
    
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

IMPORTANT: Pay special attention to accommodation type preferences:
- If user selected "Airbnb" → Suggest actual Airbnb properties and vacation rentals
- If user selected "Hotel" → Suggest actual hotels and resorts
- If user selected "Hostel" → Suggest actual hostels and budget accommodations
- If user selected "Resort" → Suggest actual resorts and luxury properties
- If user selected "Guesthouse" → Suggest actual guesthouses and B&Bs

Format your response as a JSON array with this structure:
[
  {{
    "name": "REAL Hotel/Property Name",
    "description": "Brief description of this real place and why it matches their preferences...",
    "price_range": "{currency}X-Y (from location currency)",
    "rating": 4.5,
    "features": ["Real Feature 1", "Real Feature 2", "Real Feature 3"],
    "location": "Actual area/neighborhood in {destination}",
    "why_recommended": "Why this real place matches their specific preferences"
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
4. Focus on well-known, searchable establishments
5. Provide 5-12 REAL dining suggestions

Format your response as a JSON array with this structure:
[
  {{
    "name": "REAL Restaurant Name",
    "description": "Brief description of cuisine and atmosphere...",
    "price_range": "{currency}X-Y",
    "rating": 4.5,
    "features": ["Outdoor seating", "Vegetarian options", "Live music"],
    "location": "Actual area/neighborhood in {destination}",
    "why_recommended": "Why this restaurant matches their specific preferences"
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
                suggestion['external_url'] = maps_url
                suggestion['link_type'] = 'maps'
            
            return suggestion
            
        except Exception as e:
            pass
    
    def _create_flight_booking_url(self, suggestion: Dict, destination: str, answers: List[Dict] = None, group_preferences: Dict = None) -> str:
        """Create a flight booking search URL with specific travel details"""
        try:
            import urllib.parse
            from datetime import datetime
            
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
        
        
        for answer in answers:
            question_text = answer.get('question_text', '').lower()
            
            if 'transportation' in question_text or 'travel' in question_text:
                selected_options = answer.get('answer_value')
                
                if isinstance(selected_options, list) and selected_options:
                    result = selected_options[0]
                    return result
                elif isinstance(selected_options, str):
                    return selected_options
        
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
            from_location = group_preferences.get('from_location', '') if group_preferences else ''
            departure_date = self._extract_departure_date(answers)
            
            # Get user's transportation preference
            transport_type = self._get_user_transportation_preference(answers)
            
            suggestions = []
            
            # Get real data based on transport type
            if transport_type and transport_type.lower() == 'bus':
                suggestions = self.easemytrip_service.get_bus_options(from_location, destination, departure_date)
            elif transport_type and transport_type.lower() == 'train':
                suggestions = self.easemytrip_service.get_train_options(from_location, destination, departure_date)
            elif transport_type and transport_type.lower() == 'flight':
                # For flights, still use AI but with better prompts
                suggestions = self._generate_flight_suggestions_ai(destination, answers, group_preferences)
            else:
                # Mixed or unknown - ONLY show bus options (2 options: government + private)
                suggestions = self.easemytrip_service.get_bus_options(from_location, destination, departure_date)
            
            return suggestions
            
        except Exception as e:
            return self._get_fallback_transportation_suggestions(destination, answers)
    
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
