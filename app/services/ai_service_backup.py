import google.generativeai as genai
from app.config import settings
from typing import Dict, List, Any
import json
from .maps_service import maps_service

class AIService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
    
    def generate_suggestions(self, room_type: str, preferences: Dict[str, Any], from_location: str, to_location: str, group_context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate AI-powered suggestions based on room type and preferences"""
        
        # First, try to get real suggestions from Google Places API
        real_suggestions = maps_service.get_real_suggestions(to_location, room_type, preferences, from_location)
        
        if real_suggestions and len(real_suggestions) > 0:
            # Enhance real suggestions with AI descriptions
            enhanced_suggestions = []
            for suggestion in real_suggestions:
                try:
                    enhanced = self._enhance_suggestion_with_ai(suggestion, room_type, preferences, to_location, from_location)
                    # Ensure external URL is present
                    if not enhanced.get('external_url'):
                        enhanced['external_url'] = f"https://www.google.com/search?q={enhanced.get('title', '').replace(' ', '+')}+{to_location.replace(' ', '+')}"
                    enhanced_suggestions.append(enhanced)
                except Exception as e:
                    print(f"Failed to enhance suggestion {suggestion.get('title', '')}: {e}")
                    # Don't add failed suggestions, let the error propagate
                    raise e
            return enhanced_suggestions
        
        print(f"No real suggestions found, using fallback suggestions with external URLs for {room_type} from {from_location} to {to_location}")
        # Use fallback suggestions which have guaranteed external URLs
        return self._get_fallback_suggestions(room_type, from_location, to_location, preferences)
    
    def _build_suggestion_prompt(self, room_type: str, preferences: Dict[str, Any], from_location: str, to_location: str, group_context: Dict[str, Any] = None) -> str:
        """Build prompt for AI suggestion generation"""
        
        # Build group context string
        context_info = f"From: {from_location} to {to_location}"
        if group_context:
            context_info += f"\nTrip Dates: {group_context.get('start_date', 'Not specified')} to {group_context.get('end_date', 'Not specified')}"
            context_info += f"\nGroup Size: {group_context.get('group_size', 'Not specified')} people"
            context_info += f"\nGroup Name: {group_context.get('group_name', 'Not specified')}"
        
        base_prompt = f"""
        You are a travel planning AI assistant. Generate 15 high-quality suggestions for a group trip.
        
        {context_info}
        Room Type: {room_type}
        Group Preferences: {json.dumps(preferences, indent=2)}
        
        IMPORTANT: Return ONLY valid JSON in this exact format. Do not include any text before or after the JSON.
        
        {{
            "suggestions": [
                {{
                    "title": "Suggestion Name",
                    "description": "Detailed description",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Highlight 1", "Highlight 2", "Highlight 3"],
                    "location": {{
                        "address": "Full address",
                        "coordinates": {{"lat": 12.9716, "lng": 77.5946}},
                        "landmarks": ["Nearby landmark 1", "Nearby landmark 2"]
                    }},
                    "image_url": "https://example.com/image.jpg",
                    "external_url": "https://www.google.com/search?q=hotels+in+{to_location}",
                    "metadata": {{
                        "rating": 4.5,
                        "reviews_count": 150,
                        "amenities": ["WiFi", "Pool", "Gym"]
                    }}
                }}
            ]
        }}
        
        Requirements:
        - Make suggestions realistic and bookable
        - Include diverse price ranges based on budget preferences
        - Highlight unique features and benefits
        - Include accurate location information
        - Provide compelling descriptions
        - Ensure suggestions match the group's preferences
        - Return ONLY the JSON object, no other text
        """
        
        if room_type == "stay":
            base_prompt += f"""
            Focus on REAL accommodations in {to_location}:
            - Use actual hotel/resort names and locations
            - Include real neighborhoods and areas based on user preferences
            - Provide realistic prices in local currency
            - Mention actual amenities and features
            - Include real landmarks and attractions nearby
            - Use authentic descriptions and highlights
            - Make suggestions bookable on platforms like Booking.com, Airbnb, etc.
            - Consider specific accommodation types (hotel, homestay, resort, etc.)
            - Consider specific areas (beachside, city center, near market, etc.)
            - Consider specific requirements (pet-friendly, wifi, pool, etc.)
            - Match the exact location preferences provided by users
            """
        elif room_type == "travel":
            base_prompt += f"""
            Focus on REAL transportation options from {from_location} to {to_location}:
            - Use actual airlines, train routes, bus services, car rental companies
            - Include real departure times and durations
            - Provide realistic prices and booking options
            - Mention actual airports, stations, and terminals
            - Include real amenities and services
            - Match the exact vehicle type preference (flight, bus, train, car rental)
            - If user chooses "Bus", suggest only bus services, not flights
            - If user chooses "Flight", suggest only airline options, not buses
            - If user chooses "Car Rental", suggest specific rental companies and vehicle types
            - Include specific vehicle names, routes, and operators
            - Provide exact departure times and journey durations
            """
        elif room_type == "itinerary":
            base_prompt += f"""
            Focus on REAL activities and attractions in {to_location}:
            - Use actual tourist spots, monuments, and attractions
            - Include real tour operators and experiences
            - Provide realistic timings and durations
            - Include real local insights and recommendations
            - Suggest authentic cultural experiences
            - Do NOT include price information
            """
        elif room_type == "eat":
            meal_type = preferences.get('meal_type', 'Any')
            cuisine_type = preferences.get('cuisine_type', 'Any')
            
            base_prompt += f"""
            Focus EXCLUSIVELY on RESTAURANTS and FOOD ESTABLISHMENTS in {to_location} for {meal_type}:
            - ONLY suggest dining options specifically suitable for {meal_type}
            - For BREAKFAST: Suggest cafes, breakfast spots, bakeries, and morning eateries
            - For LUNCH: Suggest full-service restaurants, lunch spots, and casual dining
            - For DINNER: Suggest fine dining, dinner restaurants, and evening establishments
            - For SNACKS/CAFES: Suggest cafes, snack bars, tea shops, and light food places
            - For ANY: Suggest a variety of dining options for all meal types
            - Match the cuisine preference: {cuisine_type}
            - Use actual restaurant names and locations
            - Include real local dishes and specialties appropriate for {meal_type}
            - Provide realistic prices and timings for {meal_type}
            - Mention actual ambiance and atmosphere suitable for {meal_type}
            - Include real reviews and ratings
            - Suggest authentic local food experiences for {meal_type}
            - DO NOT suggest activities, attractions, or non-food related places
            - Focus on dining experiences, food quality, and restaurant atmosphere appropriate for {meal_type}
            """
        
        return base_prompt
    
    def _get_fallback_suggestions(self, room_type: str, from_location: str, to_location: str, preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate dynamic fallback suggestions using AI when real suggestions fail"""
        try:
            # Use AI to generate dynamic fallback suggestions
            ai_suggestions = self._generate_ai_fallback_suggestions(room_type, from_location, to_location, preferences)
            if ai_suggestions:
                return ai_suggestions
        except Exception as e:
            print(f"AI fallback generation failed: {e}")
        
        # If AI fails, use basic dynamic fallbacks
        return self._get_basic_dynamic_fallbacks(room_type, from_location, to_location, preferences)
    
    def _generate_ai_fallback_suggestions(self, room_type: str, from_location: str, to_location: str, preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate dynamic fallback suggestions using AI based on destination and preferences"""
        
        # Build dynamic prompt based on actual preferences
        preference_text = ""
        if preferences:
            for key, value in preferences.items():
                if value and value != 'Any':
                    preference_text += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        prompt = f"""
        Generate 8 realistic, bookable suggestions for {room_type} in {to_location}.
        
        Context:
        - Destination: {to_location}
        - From: {from_location} (for travel suggestions)
        - Room Type: {room_type}
        
        User Preferences:
        {preference_text if preference_text else "- No specific preferences"}
        
        Requirements:
        1. Make suggestions realistic and actually available in {to_location}
        2. Use local names, brands, and services that exist in {to_location}
        3. Include diverse price ranges and options
        4. Generate appropriate external URLs for booking
        5. Use local landmarks and addresses specific to {to_location}
        6. Include relevant highlights based on {to_location}'s characteristics
        
        Return ONLY valid JSON in this format:
        {{
            "suggestions": [
                {{
                    "title": "Realistic Name",
                    "description": "Detailed description mentioning {to_location} specifics",
                    "price": null,
                    "currency": "INR",
                    "highlights": ["Relevant highlight 1", "Relevant highlight 2", "Relevant highlight 3"],
                    "location": {{
                        "address": "Realistic address in {to_location}",
                        "coordinates": {{"lat": 0, "lng": 0}},
                        "landmarks": ["Actual landmarks near {to_location}"]
                    }},
                    "image_url": null,
                    "external_url": "Realistic booking URL",
                    "metadata": {{"rating": 4.2, "reviews_count": 150}}
                }}
            ]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            start_idx = response.text.find('{')
            end_idx = response.text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > 0:
                json_str = response.text[start_idx:end_idx]
                result = json.loads(json_str)
                return result.get('suggestions', [])
            
        except Exception as e:
            print(f"AI fallback generation error: {e}")
        
        return []
    
    def _get_basic_dynamic_fallbacks(self, room_type: str, from_location: str, to_location: str, preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Basic dynamic fallbacks when AI fails - uses destination-specific data"""
        
        # Get destination-specific information
        dest_info = self._get_destination_info(to_location)
        
        if room_type == "stay":
            return self._get_dynamic_stay_suggestions(to_location, dest_info, preferences)
        elif room_type == "travel":
            return self._get_dynamic_travel_suggestions(from_location, to_location, dest_info, preferences)
        elif room_type == "eat":
            return self._get_dynamic_eat_suggestions(to_location, dest_info, preferences)
        elif room_type == "itinerary":
            return self._get_dynamic_itinerary_suggestions(to_location, dest_info, preferences)
        
        return []
    
    def _get_destination_info(self, destination: str) -> Dict[str, Any]:
        """Get destination-specific information for dynamic suggestions"""
        
        # This could be enhanced with a real API call to get destination data
        # For now, we'll use a basic mapping
        destination_lower = destination.lower()
        
        # Common Indian destinations with their characteristics
        dest_info = {
            "mumbai": {
                "type": "metro",
                "landmarks": ["Gateway of India", "Marine Drive", "Bandra-Worli Sea Link"],
                "areas": ["Bandra", "Andheri", "Powai", "Malad"],
                "transport": ["Local Trains", "Metro", "Buses", "Taxis"],
                "cuisine": ["Street Food", "Seafood", "Maharashtrian", "International"]
            },
            "delhi": {
                "type": "metro", 
                "landmarks": ["Red Fort", "India Gate", "Qutub Minar", "Lotus Temple"],
                "areas": ["Connaught Place", "Karol Bagh", "Paharganj", "South Delhi"],
                "transport": ["Metro", "Buses", "Auto Rickshaws", "Taxis"],
                "cuisine": ["Street Food", "North Indian", "Mughlai", "International"]
            },
            "bangalore": {
                "type": "metro",
                "landmarks": ["Cubbon Park", "Lalbagh", "Vidhana Soudha", "UB City"],
                "areas": ["Koramangala", "Indiranagar", "Whitefield", "Electronic City"],
                "transport": ["Metro", "Buses", "Auto Rickshaws", "Taxis"],
                "cuisine": ["South Indian", "Street Food", "International", "Cafes"]
            },
            "goa": {
                "type": "beach",
                "landmarks": ["Calangute Beach", "Baga Beach", "Fort Aguada", "Basilica of Bom Jesus"],
                "areas": ["Calangute", "Baga", "Anjuna", "Panjim"],
                "transport": ["Bikes", "Taxis", "Buses", "Rental Cars"],
                "cuisine": ["Seafood", "Goan", "Portuguese", "Beach Shacks"]
            }
        }
        
        # Find matching destination
        for key, info in dest_info.items():
            if key in destination_lower:
                return info
        
        # Default info for unknown destinations
        return {
            "type": "city",
            "landmarks": ["City Center", "Local Market", "Public Park"],
            "areas": ["Downtown", "Market Area", "Residential Area"],
            "transport": ["Buses", "Taxis", "Auto Rickshaws"],
            "cuisine": ["Local Cuisine", "Street Food", "Restaurants"]
        }
    
    def _get_dynamic_stay_suggestions(self, destination: str, dest_info: Dict[str, Any], preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate dynamic stay suggestions based on destination characteristics"""
        
        budget = preferences.get('budget', 'mid-range') if preferences else 'mid-range'
        accommodation_type = preferences.get('accommodation_type', 'Hotel') if preferences else 'Hotel'
        
        suggestions = []
        dest_encoded = destination.replace(' ', '+')
        
        # Generate suggestions based on destination type and budget
        if dest_info["type"] == "beach":
            suggestions.extend([
                {
                    "title": f"Beachside {accommodation_type} {destination}",
                    "description": f"Perfect beachfront {accommodation_type.lower()} in {destination} with stunning ocean views and beach access",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Beach Access", "Ocean Views", "Beach Activities", "Seafood Restaurant"],
                    "location": {
                        "address": f"{dest_info['areas'][0]}, {destination}",
                        "coordinates": {"lat": 0, "lng": 0},
                        "landmarks": dest_info["landmarks"][:2]
                    },
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q={accommodation_type.lower()}+{dest_encoded}",
                    "metadata": {"rating": 4.3, "reviews_count": 200}
                }
            ])
        
        if dest_info["type"] == "metro":
            suggestions.extend([
                {
                    "title": f"Business {accommodation_type} {destination}",
                    "description": f"Modern business {accommodation_type.lower()} in {destination} with excellent connectivity and amenities",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["City Center", "Business Facilities", "Metro Access", "WiFi"],
                    "location": {
                        "address": f"{dest_info['areas'][0]}, {destination}",
                        "coordinates": {"lat": 0, "lng": 0},
                        "landmarks": dest_info["landmarks"][:2]
                    },
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q={accommodation_type.lower()}+{dest_encoded}",
                    "metadata": {"rating": 4.2, "reviews_count": 180}
                }
            ])
        
        # Add budget-appropriate suggestions
        if budget in ['budget', 'economical']:
            suggestions.append({
                "title": f"Budget {accommodation_type} {destination}",
                "description": f"Affordable {accommodation_type.lower()} in {destination} offering great value for money",
                "price": None,
                "currency": "INR",
                "highlights": ["Budget Friendly", "Clean Rooms", "Basic Amenities", "Good Location"],
                "location": {
                    "address": f"{dest_info['areas'][1] if len(dest_info['areas']) > 1 else dest_info['areas'][0]}, {destination}",
                    "coordinates": {"lat": 0, "lng": 0},
                    "landmarks": dest_info["landmarks"][:1]
                },
                "image_url": None,
                "external_url": f"https://www.google.com/search?q=budget+{accommodation_type.lower()}+{dest_encoded}",
                "metadata": {"rating": 3.8, "reviews_count": 120}
            })
        
        return suggestions[:4]  # Return up to 4 suggestions
    
    def _get_dynamic_travel_suggestions(self, from_location: str, to_location: str, dest_info: Dict[str, Any], preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate dynamic travel suggestions based on route and destination"""
        
        travel_type = preferences.get('travel_type', 'Bus') if preferences else 'Bus'
        vehicle_type = preferences.get('vehicle_type', 'Sleeper Bus') if preferences else 'Sleeper Bus'
        
        suggestions = []
        from_encoded = from_location.replace(' ', '+')
        to_encoded = to_location.replace(' ', '+')
        
        # Generate URLs based on actual services available for the route
        if travel_type == 'Bus':
            suggestions.append({
                "title": f"{vehicle_type} {from_location} to {to_location}",
                "description": f"Comfortable {vehicle_type.lower()} service from {from_location} to {to_location}",
                "price": None,
                "currency": "INR",
                "highlights": ["Comfortable Journey", "Online Booking", "Reliable Service", "Good Connectivity"],
                "location": {"address": f"Bus Stand, {from_location}"},
                "image_url": None,
                "external_url": f"https://www.google.com/search?q={vehicle_type.lower().replace(' ', '+')}+{from_encoded}+to+{to_encoded}",
                "metadata": {"rating": 4.1, "reviews_count": 150}
            })
        
        elif travel_type == 'Train':
            suggestions.append({
                "title": f"Train {from_location} to {to_location}",
                "description": f"Indian Railways train service from {from_location} to {to_location}",
                "price": None,
                "currency": "INR",
                "highlights": ["Scenic Route", "Comfortable", "Online Booking", "Reliable"],
                "location": {"address": f"Railway Station, {from_location}"},
                "image_url": None,
                "external_url": f"https://www.google.com/search?q=train+{from_encoded}+to+{to_encoded}",
                "metadata": {"rating": 4.0, "reviews_count": 200}
            })
        
        elif travel_type == 'Flight':
            suggestions.append({
                "title": f"Flight {from_location} to {to_location}",
                "description": f"Domestic flight service from {from_location} to {to_location}",
                "price": None,
                "currency": "INR",
                "highlights": ["Fast Travel", "Comfortable", "Online Booking", "Time Saving"],
                "location": {"address": f"Airport, {from_location}"},
                "image_url": None,
                "external_url": f"https://www.google.com/search?q=flight+{from_encoded}+to+{to_encoded}",
                "metadata": {"rating": 4.2, "reviews_count": 300}
            })
        
        return suggestions[:3]  # Return up to 3 suggestions
    
    def _get_dynamic_eat_suggestions(self, destination: str, dest_info: Dict[str, Any], preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate dynamic eat suggestions based on destination cuisine"""
        
        meal_type = preferences.get('meal_type', 'Any') if preferences else 'Any'
        cuisine_type = preferences.get('cuisine_type', 'Local') if preferences else 'Local'
        
        suggestions = []
        dest_encoded = destination.replace(' ', '+')
        
        # Generate suggestions based on destination cuisine
        for cuisine in dest_info["cuisine"][:2]:  # Take first 2 cuisines
            suggestions.append({
                "title": f"{cuisine} Restaurant {destination}",
                "description": f"Authentic {cuisine.lower()} restaurant in {destination} serving traditional flavors",
                "price": None,
                "currency": "INR",
                "highlights": [f"{cuisine} Cuisine", "Traditional Recipes", "Local Ingredients", "Authentic Taste"],
                "location": {"address": f"{dest_info['areas'][0]}, {destination}"},
                "image_url": None,
                "external_url": f"https://www.google.com/search?q={cuisine.lower().replace(' ', '+')}+restaurant+{dest_encoded}",
                "metadata": {"rating": 4.2, "reviews_count": 100}
            })
        
        return suggestions[:3]  # Return up to 3 suggestions
    
    def _get_dynamic_itinerary_suggestions(self, destination: str, dest_info: Dict[str, Any], preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate dynamic itinerary suggestions based on destination landmarks"""
        
        activity_type = preferences.get('activity_type', 'Sightseeing') if preferences else 'Sightseeing'
        
        suggestions = []
        dest_encoded = destination.replace(' ', '+')
        
        # Generate suggestions based on destination landmarks
        for landmark in dest_info["landmarks"][:2]:  # Take first 2 landmarks
            suggestions.append({
                "title": f"{landmark} Tour {destination}",
                "description": f"Guided tour of {landmark} and surrounding areas in {destination}",
                "price": None,
                "currency": "INR",
                "highlights": ["Guided Tour", landmark, "Local Guide", "Historical Information"],
                "location": {
                    "address": f"{landmark}, {destination}",
                    "coordinates": {"lat": 0, "lng": 0},
                    "landmarks": [landmark]
                },
                "image_url": None,
                "external_url": f"https://www.google.com/search?q={landmark.replace(' ', '+')}+tour+{dest_encoded}",
                "metadata": {"rating": 4.3, "reviews_count": 150}
            })
        
        return suggestions[:2]  # Return up to 2 suggestions
    
    def _get_meal_specific_suggestions(self, to_location: str, preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get meal-specific fallback suggestions based on user preferences"""
        dest_encoded = to_location.replace(' ', '+')
        meal_type = preferences.get('meal_type', 'Any') if preferences else 'Any'
        
        suggestions = []
        
        if meal_type in ['Breakfast', 'Any']:
            suggestions.extend([
                {
                    "title": f"Morning Cafe {to_location}",
                    "description": f"Perfect breakfast spot serving fresh coffee, pastries, and morning meals in {to_location}",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Fresh Coffee", "Pastries", "Morning Meals", "Cozy Atmosphere"],
                    "location": {"address": f"Main Street, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=breakfast+{dest_encoded}",
                    "metadata": {"rating": 4.2, "reviews_count": 85}
                },
                {
                    "title": f"Local Bakery {to_location}",
                    "description": f"Traditional bakery offering fresh bread, cakes, and breakfast items",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Fresh Bread", "Local Cakes", "Traditional Recipes", "Budget Friendly"],
                    "location": {"address": f"Market Area, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=bakery+{dest_encoded}",
                    "metadata": {"rating": 4.0, "reviews_count": 120}
                }
            ])
        
        if meal_type in ['Lunch', 'Any']:
            suggestions.extend([
                {
                    "title": f"Local Restaurant {to_location}",
                    "description": f"Authentic local cuisine perfect for lunch with traditional flavors and warm hospitality",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Local Cuisine", "Traditional Recipes", "Family Owned", "Fresh Ingredients"],
                    "location": {"address": f"Main Street, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=lunch+restaurants+{dest_encoded}",
                    "metadata": {"rating": 4.2, "reviews_count": 120}
                },
                {
                    "title": f"Quick Bites {to_location}",
                    "description": f"Fast-casual dining spot perfect for a quick lunch with local and international options",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Quick Service", "Varied Menu", "Good Value", "Central Location"],
                    "location": {"address": f"Commercial Area, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=quick+lunch+{dest_encoded}",
                    "metadata": {"rating": 4.1, "reviews_count": 95}
                }
            ])
        
        if meal_type in ['Dinner', 'Any']:
            suggestions.extend([
                {
                    "title": f"Fine Dining Restaurant {to_location}",
                    "description": f"Upscale restaurant offering contemporary cuisine with stunning views and excellent service",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Fine Dining", "Contemporary Cuisine", "Great Views", "Wine Selection"],
                    "location": {"address": f"Business District, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=fine+dining+{dest_encoded}",
                    "metadata": {"rating": 4.5, "reviews_count": 85}
                },
                {
                    "title": f"Traditional Dinner House {to_location}",
                    "description": f"Classic restaurant serving traditional dinner specialties in a warm, family-friendly atmosphere",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Traditional Cuisine", "Family Friendly", "Cozy Atmosphere", "Local Specialties"],
                    "location": {"address": f"Heritage Area, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=dinner+restaurants+{dest_encoded}",
                    "metadata": {"rating": 4.3, "reviews_count": 110}
                }
            ])
        
        if meal_type in ['Snacks/Cafes', 'Any']:
            suggestions.extend([
                {
                    "title": f"Cafe & Bakery {to_location}",
                    "description": f"Cozy cafe offering fresh baked goods, coffee, and light meals in a relaxed atmosphere",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Fresh Baked Goods", "Coffee", "Light Meals", "WiFi Available"],
                    "location": {"address": f"Commercial Street, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=cafe+{dest_encoded}",
                    "metadata": {"rating": 4.1, "reviews_count": 95}
                },
                {
                    "title": f"Street Food Corner {to_location}",
                    "description": f"Popular local street food spot serving authentic regional delicacies and snacks",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Street Food", "Local Delicacies", "Budget Friendly", "Quick Service"],
                    "location": {"address": f"Market Area, {to_location}"},
                    "image_url": None,
                    "external_url": f"https://www.google.com/search?q=street+food+{dest_encoded}",
                    "metadata": {"rating": 4.0, "reviews_count": 200}
                }
            ])
        
        return suggestions[:6]  # Return maximum 6 suggestions
    
    def _get_travel_specific_suggestions(self, from_location: str, to_location: str, preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get travel-specific fallback suggestions based on route and preferences"""
        from_encoded = from_location.replace(' ', '+')
        to_encoded = to_location.replace(' ', '+')
        
        travel_type = preferences.get('travel_type', 'Bus') if preferences else 'Bus'
        vehicle_type = preferences.get('vehicle_type', 'Sleeper Bus') if preferences else 'Sleeper Bus'
        travel_time = preferences.get('travel_time', 'Night') if preferences else 'Night'
        
        # Handle special cases where vehicle_type indicates the travel type
        if vehicle_type in ['Budget Flight', 'Premium Flight']:
            travel_type = 'Flight'
        elif vehicle_type in ['Express Train', 'Local Train']:
            travel_type = 'Train'
        elif vehicle_type in ['Private Car', 'Shared Taxi']:
            travel_type = 'Car Rental'
        elif vehicle_type in ['Sleeper Bus', 'Semi-Sleeper', 'AC Seater', 'Non-AC']:
            travel_type = 'Bus'
        
        suggestions = []
        
        if travel_type == 'Bus':
            if vehicle_type == 'Sleeper Bus':
                suggestions.extend([
                    {
                        "title": f"KSRTC Sleeper Bus {from_location} to {to_location}",
                        "description": f"Government sleeper bus service from {from_location} to {to_location} with comfortable berths and {travel_time.lower()} departure",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["Government Service", "Sleeper Berths", f"{travel_time} Departure", "Online Booking", "Reliable Service"],
                        "location": {"address": f"KSRTC Bus Stand, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.ksrtc.in/oprs-web/",
                        "metadata": {"rating": 4.2, "reviews_count": 150}
                    },
                    {
                        "title": f"Private Sleeper Bus {from_location} to {to_location}",
                        "description": f"Premium private sleeper bus service with AC berths and {travel_time.lower()} departure from {from_location} to {to_location}",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["AC Sleeper", "Premium Service", f"{travel_time} Departure", "Online Booking", "Comfortable Berths"],
                        "location": {"address": f"Private Bus Stand, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.redbus.in/bus-tickets/{from_encoded}-to-{to_encoded}",
                        "metadata": {"rating": 4.4, "reviews_count": 200}
                    }
                ])
            else:
                suggestions.extend([
                    {
                        "title": f"KSRTC AC Seater {from_location} to {to_location}",
                        "description": f"Government AC seater bus service from {from_location} to {to_location} with {travel_time.lower()} departure",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["Government Service", "AC Seater", f"{travel_time} Departure", "Online Booking", "Economical"],
                        "location": {"address": f"KSRTC Bus Stand, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.ksrtc.in/oprs-web/",
                        "metadata": {"rating": 4.1, "reviews_count": 180}
                    }
                ])
        
        elif travel_type == 'Train':
            suggestions.extend([
                {
                    "title": f"Express Train {from_location} to {to_location}",
                    "description": f"Indian Railways express train service from {from_location} to {to_location} with {travel_time.lower()} departure",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Indian Railways", "Express Service", f"{travel_time} Departure", "Online Booking", "Scenic Route"],
                    "location": {"address": f"Railway Station, {from_location}"},
                    "image_url": None,
                    "external_url": f"https://www.irctc.co.in/nget/train-search",
                    "metadata": {"rating": 4.0, "reviews_count": 120}
                }
            ])
        
        elif travel_type == 'Flight':
            if vehicle_type == 'Budget Flight':
                suggestions.extend([
                    {
                        "title": f"Budget Flight {from_location} to {to_location}",
                        "description": f"Economical domestic flight service from {from_location} to {to_location} with {travel_time.lower()} departure. Perfect for budget-conscious travelers.",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["Budget Friendly", "Economical", f"{travel_time} Departure", "Online Booking", "Value for Money"],
                        "location": {"address": f"Airport, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.makemytrip.com/flights/{from_encoded}-{to_encoded}",
                        "metadata": {"rating": 4.1, "reviews_count": 250}
                    },
                    {
                        "title": f"Low-Cost Carrier {from_location} to {to_location}",
                        "description": f"Affordable flight options with low-cost carriers from {from_location} to {to_location}, ideal for budget travel",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["Low Cost", "No Frills", f"{travel_time} Departure", "Online Booking", "Affordable"],
                        "location": {"address": f"Airport, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.goibibo.com/flights/{from_encoded}-{to_encoded}",
                        "metadata": {"rating": 3.9, "reviews_count": 200}
                    }
                ])
            elif vehicle_type == 'Premium Flight':
                suggestions.extend([
                    {
                        "title": f"Premium Flight {from_location} to {to_location}",
                        "description": f"Luxury domestic flight service from {from_location} to {to_location} with premium amenities and {travel_time.lower()} departure",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["Premium Service", "Luxury Amenities", f"{travel_time} Departure", "Priority Booking", "Comfort"],
                        "location": {"address": f"Airport, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.makemytrip.com/flights/{from_encoded}-{to_encoded}",
                        "metadata": {"rating": 4.5, "reviews_count": 180}
                    }
                ])
            else:
                suggestions.extend([
                    {
                        "title": f"Domestic Flight {from_location} to {to_location}",
                        "description": f"Domestic flight service from {from_location} to {to_location} with {travel_time.lower()} departure",
                        "price": None,
                        "currency": "INR",
                        "highlights": ["Fastest Option", "Comfortable", f"{travel_time} Departure", "Online Booking", "Time Saving"],
                        "location": {"address": f"Airport, {from_location}"},
                        "image_url": None,
                        "external_url": f"https://www.makemytrip.com/flights/{from_encoded}-{to_encoded}",
                        "metadata": {"rating": 4.3, "reviews_count": 300}
                    }
                ])
        
        elif travel_type == 'Car Rental':
            suggestions.extend([
                {
                    "title": f"Private Car Rental {from_location} to {to_location}",
                    "description": f"Private car rental service from {from_location} to {to_location} with experienced driver and {travel_time.lower()} departure",
                    "price": None,
                    "currency": "INR",
                    "highlights": ["Private Vehicle", "Experienced Driver", f"{travel_time} Departure", "Flexible Timing", "Door to Door"],
                    "location": {"address": f"Car Rental Office, {from_location}"},
                    "image_url": None,
                    "external_url": f"https://www.zoomcar.com/",
                    "metadata": {"rating": 4.5, "reviews_count": 250}
                }
            ])
        
        return suggestions[:4]  # Return maximum 4 travel suggestions
    
    def _enhance_suggestion_with_ai(self, suggestion: Dict[str, Any], room_type: str, preferences: Dict[str, Any], to_location: str, from_location: str = None) -> Dict[str, Any]:
        """Enhance real Google Places data with AI-generated descriptions"""
        
        # Room-specific prompts for Gen AI hackathon
        room_prompts = {
            'stay': f"""
            You are a travel accommodation expert. Enhance this hotel/resort suggestion:
            
            Place: {suggestion.get('title', '')}
            Address: {suggestion.get('address', '')}
            Rating: {suggestion.get('rating', 0)}/5
            Price Level: {suggestion.get('price_level', 0)}
            
            Focus on:
            - Accommodation quality and amenities
            - Location advantages for tourists
            - Value for money
            - Group-friendly features
            - Local area benefits
            
            Destination: {to_location}
            Group Preferences: {json.dumps(preferences, indent=2)}
            """,
            
            'travel': f"""
            You are a transportation expert. Enhance this travel option for {from_location or 'Unknown'} to {to_location}:
            
            Service: {suggestion.get('title', '')}
            Route: {from_location or 'Unknown'} → {to_location}
            Rating: {suggestion.get('rating', 0)}/5
            
            Focus on:
            - Specific route details and timings
            - Vehicle type and comfort level
            - Booking process and availability
            - Cost-effectiveness for groups
            - Real operator names and services
            - Departure/arrival times
            - Booking links and contact information
            
            Travel Preferences: {json.dumps(preferences, indent=2)}
            """,
            
            'activities': f"""
            You are a local tourism expert. Enhance this attraction/activity:
            
            Place: {suggestion.get('title', '')}
            Address: {suggestion.get('address', '')}
            Rating: {suggestion.get('rating', 0)}/5
            
            Focus on:
            - Cultural and entertainment value
            - Group activity suitability
            - Local significance and history
            - Timing and duration recommendations
            - Photo opportunities and experiences
            
            Destination: {to_location}
            Group Preferences: {json.dumps(preferences, indent=2)}
            """,
            
            'dining': f"""
            You are a food and dining expert. Enhance this restaurant suggestion:
            
            Place: {suggestion.get('title', '')}
            Address: {suggestion.get('address', '')}
            Rating: {suggestion.get('rating', 0)}/5
            Price Level: {suggestion.get('price_level', 0)}
            
            Focus on:
            - Local cuisine and specialties
            - Ambiance and atmosphere
            - Group dining suitability
            - Dietary options and preferences
            - Local dining culture and customs
            
            Destination: {to_location}
            Group Preferences: {json.dumps(preferences, indent=2)}
            """
        }
        
        base_prompt = room_prompts.get(room_type, room_prompts['activities'])
        
        prompt = f"""
        {base_prompt}
        
        Please enhance with:
        1. Compelling description (2-3 sentences)
        2. Key highlights specific to this room type
        3. Why it's perfect for this group's preferences
        4. Best time to visit/use (if applicable)
        5. Local insider tips
        
        Return as JSON with keys: enhanced_description, highlights, perfect_for_group, best_time, insider_tips
        """
        
        try:
            print(f"=== AI ENHANCEMENT DEBUG ===")
            print(f"Enhancing: {suggestion.get('title', '')}")
            print(f"Google AI API Key present: {bool(settings.google_api_key)}")
            print(f"Model: {self.model}")
            
            response = self.model.generate_content(prompt)
            print(f"AI Response: {response.text[:300]}...")
            
            # Parse AI enhancement
            start_idx = response.text.find('{')
            end_idx = response.text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > 0:
                json_str = response.text[start_idx:end_idx]
                print(f"Extracted JSON: {json_str}")
                
                try:
                    ai_enhancement = json.loads(json_str)
                    print(f"Parsed enhancement: {ai_enhancement}")
                    
                    # Merge with original suggestion
                    enhanced = suggestion.copy()
                    enhanced.update({
                        'description': ai_enhancement.get('enhanced_description', suggestion.get('description', '')),
                        'highlights': ai_enhancement.get('highlights', []),
                        'perfect_for_group': ai_enhancement.get('perfect_for_group', ''),
                        'best_time': ai_enhancement.get('best_time', ''),
                        'insider_tips': ai_enhancement.get('insider_tips', ''),
                        'price': None,  # Remove all prices
                        'currency': 'INR',
                        'external_url': f"https://www.google.com/maps/place/?q=place_id:{suggestion.get('id', '')}"
                    })
                    
                    print(f"Enhanced description: {enhanced.get('description', '')[:100]}...")
                    return enhanced
                    
                except json.JSONDecodeError as e:
                    print(f"JSON parsing error: {e}")
                    print(f"Malformed JSON: {json_str}")
                    # Return original suggestion with basic enhancement
                    enhanced = suggestion.copy()
                    enhanced.update({
                        'description': suggestion.get('description', '') or f"Great {room_type} option in {to_location}",
                        'highlights': ['Quality service', 'Good location', 'Recommended'],
                        'perfect_for_group': 'Suitable for group travel',
                        'best_time': 'Available year-round',
                        'insider_tips': 'Book in advance for best rates',
                        'price': None,  # Remove all prices
                        'currency': 'INR',
                        'external_url': f"https://www.google.com/maps/place/?q=place_id:{suggestion.get('id', '')}"
                    })
                    return enhanced
            else:
                print("No valid JSON found in AI response")
                raise Exception("AI response does not contain valid JSON")
        except Exception as e:
            print(f"Error enhancing suggestion with AI: {e}")
            print(f"Response was: {response.text if 'response' in locals() else 'No response'}")
            raise e  # Re-raise to see the actual error
        
        # Return original suggestion with basic enhancements
        return {
            **suggestion,
            'price': None if room_type == 'stay' else self._estimate_price(suggestion.get('price_level', 0), room_type),
            'currency': 'INR' if room_type != 'stay' else 'INR',
            'external_url': f"https://www.google.com/maps/place/?q=place_id:{suggestion.get('id', '')}"
        }
    
    def _generate_external_url(self, suggestion: Dict[str, Any], room_type: str, to_location: str) -> str:
        """Generate external URL for a suggestion based on room type and to_location"""
        title = suggestion.get('title', '').replace(' ', '+')
        dest = to_location.replace(' ', '+')
        
        if room_type == 'stay':
            return f"https://www.google.com/search?q={title}+{dest}+hotel+booking"
        elif room_type == 'travel':
            return f"https://www.google.com/search?q={title}+{dest}+transportation"
        elif room_type == 'eat':
            return f"https://www.google.com/search?q={title}+{dest}+restaurant"
        elif room_type == 'itinerary':
            return f"https://www.google.com/search?q={title}+{dest}+activities"
        else:
            return f"https://www.google.com/search?q={title}+{dest}"
    
    def _estimate_price(self, price_level: int, room_type: str) -> int:
        """Estimate price based on Google Places price level"""
        base_prices = {
            'stay': {0: 1000, 1: 2000, 2: 4000, 3: 8000, 4: 15000},
            'dining': {0: 200, 1: 500, 2: 1000, 3: 2000, 4: 4000},
            'activities': {0: 100, 1: 300, 2: 600, 3: 1200, 4: 2500},
            'transportation': {0: 50, 1: 150, 2: 300, 3: 600, 4: 1200}
        }
        
        return base_prices.get(room_type, {0: 500, 1: 1000, 2: 2000, 3: 4000, 4: 8000}).get(price_level, 1000)
    
    def analyze_group_preferences(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze group answers to generate preference summary"""
        
        prompt = f"""
        Analyze the following group travel preferences and provide a summary:
        
        Answers: {json.dumps(answers, indent=2)}
        
        Please provide:
        1. Most popular choices
        2. Budget ranges
        3. Common themes
        4. Conflicting preferences
        5. Recommendations for consensus
        
        Format as JSON with keys: popular_choices, budget_ranges, common_themes, conflicts, recommendations
        """
        
        try:
            response = self.model.generate_content(prompt)
            try:
                return json.loads(response.text)
            except json.JSONDecodeError as e:
                print(f"JSON parsing error in analyze_group_preferences: {e}")
                print(f"Malformed JSON: {response.text[:200]}...")
                return {
                    "popular_choices": {},
                    "budget_ranges": {},
                    "common_themes": [],
                    "conflicts": [],
                    "recommendations": []
                }
        except Exception as e:
            print(f"Error analyzing preferences: {e}")
            return {
                "popular_choices": {},
                "budget_ranges": {},
                "common_themes": [],
                "conflicts": [],
                "recommendations": []
            }
    
    def _filter_suggestions(self, suggestions: List[Dict[str, Any]], room_type: str, to_location: str) -> List[Dict[str, Any]]:
        """Filter out generic, unknown, or low-quality suggestions"""
        filtered = []
        generic_keywords = ['unknown', 'generic', 'sample', 'test', 'example', 'placeholder', 'tbd', 'n/a']
        
        for suggestion in suggestions:
            title = suggestion.get('title', '').lower()
            description = suggestion.get('description', '').lower()
            
            # Skip if title or description contains generic keywords
            if any(keyword in title or keyword in description for keyword in generic_keywords):
                continue
            
            # Skip if title is too generic
            if title in ['hotel', 'restaurant', 'activity', 'place', 'location', 'accommodation']:
                continue
            
            # Skip if description is too short or generic
            if len(description) < 20:
                continue
            
            # For stay suggestions, ensure they have proper accommodation terms
            if room_type == 'stay':
                if not any(term in title.lower() for term in ['hotel', 'resort', 'hostel', 'guest', 'inn', 'lodge', 'villa', 'apartment', 'homestay']):
                    continue
            
            # For travel suggestions, ensure they have proper transport terms
            if room_type == 'travel':
                if not any(term in title.lower() for term in ['flight', 'bus', 'train', 'taxi', 'car', 'transport', 'airline', 'railway']):
                    continue
            
            # For eat suggestions, ensure they have proper food terms
            if room_type == 'eat':
                if not any(term in title.lower() for term in ['restaurant', 'cafe', 'dining', 'food', 'kitchen', 'bistro', 'eatery', 'bar']):
                    continue
            
            # For itinerary suggestions, ensure they have proper activity terms
            if room_type == 'itinerary':
                if not any(term in title.lower() for term in ['tour', 'visit', 'explore', 'activity', 'attraction', 'sight', 'monument', 'museum', 'park']):
                    continue
            
            filtered.append(suggestion)
        
        return filtered
    
    def generate_consensus_summary(self, votes: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> str:
        """Generate AI summary of group consensus"""
        
        prompt = f"""
        Based on the voting results and suggestions, provide a consensus summary:
        
        Votes: {json.dumps(votes, indent=2)}
        Suggestions: {json.dumps(suggestions, indent=2)}
        
        Provide a clear summary of:
        1. Most popular choice
        2. Group agreement level
        3. Next steps recommendation
        4. Any concerns or alternatives
        
        Keep it concise and actionable.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating consensus: {e}")
            return "Group preferences have been collected. Please review the options and vote."

# Global AI service instance
ai_service = AIService()
