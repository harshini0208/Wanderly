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
        - Use local landmarks and addresses
        - Include relevant external booking URLs
        """
        
        # Add room-specific requirements
        if room_type == "stay":
            base_prompt += f"""
            - Focus on accommodation types: {preferences.get('accommodation_type', 'Hotel')}
            - Budget range: {preferences.get('budget', 'mid-range')}
            - Include amenities like WiFi, parking, breakfast
            """
        elif room_type == "travel":
            base_prompt += f"""
            - Focus on transportation: {preferences.get('travel_type', 'Bus')}
            - Vehicle type: {preferences.get('vehicle_type', 'Sleeper Bus')}
            - Travel time preference: {preferences.get('travel_time', 'Night')}
            """
        elif room_type == "eat":
            meal_type = preferences.get('meal_type', 'Any')
            base_prompt += f"""
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
    
    def _enhance_suggestion_with_ai(self, suggestion: Dict[str, Any], room_type: str, preferences: Dict[str, Any], to_location: str, from_location: str) -> Dict[str, Any]:
        """Enhance a suggestion with AI-generated content"""
        
        prompt = f"""
        Enhance this travel suggestion with detailed information:
        
        Original Suggestion: {suggestion.get('title', '')}
        Description: {suggestion.get('description', '')}
        Location: {to_location}
        Room Type: {room_type}
        Preferences: {json.dumps(preferences, indent=2)}
        
        Return ONLY valid JSON in this format:
        {{
            "enhanced_description": "Detailed, engaging description",
            "highlights": ["Highlight 1", "Highlight 2", "Highlight 3"],
            "perfect_for_group": "Why this is perfect for group travel",
            "best_time": "Best time to visit/use this service",
            "insider_tips": "Insider tips and recommendations"
        }}
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
    
    def analyze_group_preferences(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze group answers to generate preference summary"""
        
        prompt = f"""
        Analyze the following group travel preferences and provide a summary:
        
        Group Answers: {json.dumps(answers, indent=2)}
        
        Provide analysis in these areas:
        1. Popular choices across all questions
        2. Budget ranges and spending patterns
        3. Common themes and interests
        4. Potential conflicts or disagreements
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
    
    def generate_consensus_summary(self, votes: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> str:
        """Generate AI summary of group consensus"""
        
        prompt = f"""
        Analyze the group voting results and generate a consensus summary:
        
        Votes: {json.dumps(votes, indent=2)}
        Suggestions: {json.dumps(suggestions, indent=2)}
        
        Provide a clear summary of:
        1. Most popular choices
        2. Group consensus areas
        3. Areas needing discussion
        4. Final recommendations
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating consensus: {e}")
            return "Group preferences have been collected. Please review the options and vote."

# Global AI service instance
ai_service = AIService()
