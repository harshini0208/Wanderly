import google.generativeai as genai
from app.config import settings
from typing import Dict, List, Any
import json
from .maps_service import maps_service

class AIService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
    
    def generate_suggestions(self, room_type: str, preferences: Dict[str, Any], destination: str, group_context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate AI-powered suggestions based on room type and preferences"""
        
        # First, try to get real suggestions from Google Places API
        real_suggestions = maps_service.get_real_suggestions(destination, room_type, preferences)
        
        if real_suggestions:
            # Enhance real suggestions with AI descriptions
            enhanced_suggestions = []
            for suggestion in real_suggestions:
                enhanced = self._enhance_suggestion_with_ai(suggestion, room_type, preferences, destination)
                enhanced_suggestions.append(enhanced)
            return enhanced_suggestions
        
        # Fallback to AI-generated suggestions if no real data
        prompt = self._build_suggestion_prompt(room_type, preferences, destination, group_context)
        
        try:
            response = self.model.generate_content(prompt)
            suggestions = self._parse_suggestions(response.text, room_type)
            return suggestions
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return self._get_fallback_suggestions(room_type, destination)
    
    def _build_suggestion_prompt(self, room_type: str, preferences: Dict[str, Any], destination: str, group_context: Dict[str, Any] = None) -> str:
        """Build prompt for AI suggestion generation"""
        
        # Build group context string
        context_info = f"Destination: {destination}"
        if group_context:
            context_info += f"\nTrip Dates: {group_context.get('start_date', 'Not specified')} to {group_context.get('end_date', 'Not specified')}"
            context_info += f"\nGroup Size: {group_context.get('group_size', 'Not specified')} people"
            context_info += f"\nGroup Name: {group_context.get('group_name', 'Not specified')}"
        
        base_prompt = f"""
        You are a travel planning AI assistant. Generate 10-12 high-quality suggestions for a group trip.
        
        {context_info}
        Room Type: {room_type}
        Group Preferences: {json.dumps(preferences, indent=2)}
        
        Please provide suggestions in the following JSON format:
        {{
            "suggestions": [
                {{
                    "title": "Suggestion Name",
                    "description": "Detailed description",
                    "price": 2500,
                    "currency": "INR",
                    "highlights": ["Highlight 1", "Highlight 2", "Highlight 3"],
                    "location": {{
                        "address": "Full address",
                        "coordinates": {{"lat": 12.9716, "lng": 77.5946}},
                        "landmarks": ["Nearby landmark 1", "Nearby landmark 2"]
                    }},
                    "image_url": "https://example.com/image.jpg",
                    "external_url": "https://booking.com/example",
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
        """
        
        if room_type == "stay":
            base_prompt += f"""
            Focus on REAL accommodations in {destination}:
            - Use actual hotel/resort names and locations
            - Include real neighborhoods and areas
            - Provide realistic prices in local currency
            - Mention actual amenities and features
            - Include real landmarks and attractions nearby
            - Use authentic descriptions and highlights
            - Make suggestions bookable on platforms like Booking.com, Airbnb, etc.
            """
        elif room_type == "travel":
            base_prompt += f"""
            Focus on REAL transportation options to/from {destination}:
            - Use actual airlines, train routes, bus services
            - Include real departure times and durations
            - Provide realistic prices and booking options
            - Mention actual airports, stations, and terminals
            - Include real amenities and services
            """
        elif room_type == "itinerary":
            base_prompt += f"""
            Focus on REAL activities and attractions in {destination}:
            - Use actual tourist spots, monuments, and attractions
            - Include real tour operators and experiences
            - Provide realistic timings and durations
            - Mention actual entry fees and booking requirements
            - Include real local insights and recommendations
            - Suggest authentic cultural experiences
            """
        elif room_type == "eat":
            base_prompt += f"""
            Focus on REAL restaurants and food experiences in {destination}:
            - Use actual restaurant names and locations
            - Include real local dishes and specialties
            - Provide realistic prices and timings
            - Mention actual ambiance and atmosphere
            - Include real reviews and ratings
            - Suggest authentic local food experiences
            """
        
        return base_prompt
    
    def _parse_suggestions(self, response_text: str, room_type: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured suggestions"""
        try:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)
            
            return data.get('suggestions', [])
        except Exception as e:
            print(f"Error parsing suggestions: {e}")
            return self._get_fallback_suggestions(room_type, "Unknown")
    
    def _get_fallback_suggestions(self, room_type: str, destination: str) -> List[Dict[str, Any]]:
        """Fallback suggestions if AI generation fails"""
        fallback_suggestions = {
            "stay": [
                {
                    "title": f"Budget Hotel in {destination}",
                    "description": "Clean and comfortable budget accommodation",
                    "price": 1500,
                    "currency": "INR",
                    "highlights": ["Free WiFi", "24/7 Reception", "Central Location"],
                    "location": {
                        "address": f"Central {destination}",
                        "coordinates": {"lat": 0, "lng": 0},
                        "landmarks": ["City Center", "Public Transport"]
                    },
                    "image_url": None,
                    "external_url": None,
                    "metadata": {"rating": 4.0, "reviews_count": 50}
                }
            ],
            "travel": [
                {
                    "title": f"Flight to {destination}",
                    "description": "Direct flight with good timing",
                    "price": 5000,
                    "currency": "INR",
                    "highlights": ["Direct Flight", "Meal Included", "Free Check-in"],
                    "location": {
                        "address": "Airport",
                        "coordinates": {"lat": 0, "lng": 0},
                        "landmarks": ["Airport", "City Center"]
                    },
                    "image_url": None,
                    "external_url": None,
                    "metadata": {"rating": 4.2, "reviews_count": 100}
                }
            ],
            "itinerary": [
                {
                    "title": f"City Tour of {destination}",
                    "description": "Comprehensive city tour covering major attractions",
                    "price": 800,
                    "currency": "INR",
                    "highlights": ["Guided Tour", "All Major Attractions", "Local Guide"],
                    "location": {
                        "address": f"Various locations in {destination}",
                        "coordinates": {"lat": 0, "lng": 0},
                        "landmarks": ["City Center", "Historic Sites"]
                    },
                    "image_url": None,
                    "external_url": None,
                    "metadata": {"rating": 4.5, "reviews_count": 200}
                }
            ],
            "eat": [
                {
                    "title": f"Local Restaurant in {destination}",
                    "description": "Authentic local cuisine experience",
                    "price": 500,
                    "currency": "INR",
                    "highlights": ["Local Cuisine", "Vegetarian Options", "Good Ambiance"],
                    "location": {
                        "address": f"Local area in {destination}",
                        "coordinates": {"lat": 0, "lng": 0},
                        "landmarks": ["City Center", "Local Market"]
                    },
                    "image_url": None,
                    "external_url": None,
                    "metadata": {"rating": 4.3, "reviews_count": 75}
                }
            ]
        }
        
        return fallback_suggestions.get(room_type, [])
    
    def _enhance_suggestion_with_ai(self, suggestion: Dict[str, Any], room_type: str, preferences: Dict[str, Any], destination: str) -> Dict[str, Any]:
        """Enhance real Google Places data with AI-generated descriptions"""
        
        prompt = f"""
        Enhance this real place suggestion with compelling descriptions:
        
        Place: {suggestion.get('title', '')}
        Address: {suggestion.get('address', '')}
        Rating: {suggestion.get('rating', 0)}/5
        Price Level: {suggestion.get('price_level', 0)}
        Types: {', '.join(suggestion.get('types', []))}
        
        Room Type: {room_type}
        Destination: {destination}
        Preferences: {json.dumps(preferences, indent=2)}
        
        Please enhance with:
        1. Compelling description (2-3 sentences)
        2. Key highlights based on the place type
        3. Why it's perfect for this group
        4. Best time to visit (if applicable)
        
        Return as JSON with keys: enhanced_description, highlights, perfect_for_group, best_time
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Parse AI enhancement
            start_idx = response.text.find('{')
            end_idx = response.text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > 0:
                json_str = response.text[start_idx:end_idx]
                ai_enhancement = json.loads(json_str)
                
                # Merge with original suggestion
                enhanced = suggestion.copy()
                enhanced.update({
                    'description': ai_enhancement.get('enhanced_description', suggestion.get('description', '')),
                    'highlights': ai_enhancement.get('highlights', []),
                    'perfect_for_group': ai_enhancement.get('perfect_for_group', ''),
                    'best_time': ai_enhancement.get('best_time', ''),
                    'price': self._estimate_price(suggestion.get('price_level', 0), room_type),
                    'currency': 'INR',
                    'external_url': f"https://www.google.com/maps/place/?q=place_id:{suggestion.get('id', '')}"
                })
                
                return enhanced
        except Exception as e:
            print(f"Error enhancing suggestion with AI: {e}")
        
        # Return original suggestion with basic enhancements
        return {
            **suggestion,
            'price': self._estimate_price(suggestion.get('price_level', 0), room_type),
            'currency': 'INR',
            'external_url': f"https://www.google.com/maps/place/?q=place_id:{suggestion.get('id', '')}"
        }
    
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
            return json.loads(response.text)
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

