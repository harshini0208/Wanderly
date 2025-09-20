import googlemaps
from app.config import settings
from typing import Dict, List, Any, Optional
import json

class MapsService:
    def __init__(self):
        try:
            # Enable Google Maps API for external URLs
            self.gmaps = googlemaps.Client(key=settings.google_maps_api_key)
            print("Google Maps API initialized successfully")
        except Exception as e:
            print(f"Google Maps API initialization failed: {e}")
            self.gmaps = None
    
    def _is_disabled(self):
        """Check if Maps API is disabled"""
        if not self.gmaps:
            print("Google Maps API is disabled")
            return True
        return False
    
    def get_place_details(self, place_id: str) -> Dict[str, Any]:
        """Get detailed information about a place"""
        if self._is_disabled():
            return {}
        try:
            place = self.gmaps.place(place_id=place_id)
            return place.get('result', {})
        except Exception as e:
            print(f"Error getting place details: {e}")
            return {}
    
    def search_places(self, query: str, location: str = None, radius: int = 5000) -> List[Dict[str, Any]]:
        """Search for places near a location"""
        if self._is_disabled():
            return []
        try:
            if location:
                # Geocode the location first
                geocode_result = self.gmaps.geocode(location)
                if geocode_result:
                    lat_lng = geocode_result[0]['geometry']['location']
                    places = self.gmaps.places_nearby(
                        location=lat_lng,
                        radius=radius,
                        keyword=query
                    )
                else:
                    places = self.gmaps.places(query=query)
            else:
                places = self.gmaps.places(query=query)
            
            return places.get('results', [])
        except Exception as e:
            print(f"Error searching places: {e}")
            return []
    
    def get_place_photos(self, place_id: str, max_photos: int = 5) -> List[str]:
        """Get photos for a place"""
        if self._is_disabled():
            return []
        try:
            place_details = self.get_place_details(place_id)
            photos = place_details.get('photos', [])
            
            photo_urls = []
            for photo in photos[:max_photos]:
                photo_reference = photo.get('photo_reference')
                if photo_reference:
                    photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={settings.google_maps_api_key}"
                    photo_urls.append(photo_url)
            
            return photo_urls
        except Exception as e:
            print(f"Error getting photos: {e}")
            return []
    
    def get_directions(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        """Get directions between two points"""
        if self._is_disabled():
            return {}
        try:
            directions = self.gmaps.directions(origin, destination, mode=mode)
            return directions[0] if directions else {}
        except Exception as e:
            print(f"Error getting directions: {e}")
            return {}
    
    def geocode_address(self, address: str) -> Optional[Dict[str, float]]:
        """Convert address to coordinates"""
        if self._is_disabled():
            return None
        try:
            geocode_result = self.gmaps.geocode(address)
            if geocode_result:
                return geocode_result[0]['geometry']['location']
            return None
        except Exception as e:
            print(f"Error geocoding address: {e}")
            return None
    
    def get_nearby_places(self, location: str, place_type: str, radius: int = 5000) -> List[Dict[str, Any]]:
        """Get nearby places of a specific type"""
        if self._is_disabled():
            return []
        try:
            # Geocode the location
            geocode_result = self.gmaps.geocode(location)
            if not geocode_result:
                return []
            
            lat_lng = geocode_result[0]['geometry']['location']
            
            # Search for places
            places = self.gmaps.places_nearby(
                location=lat_lng,
                radius=radius,
                type=place_type
            )
            
            return places.get('results', [])
        except Exception as e:
            print(f"Error getting nearby places: {e}")
            return []
    
    def enhance_suggestion_with_maps_data(self, suggestion: Dict[str, Any], destination: str) -> Dict[str, Any]:
        """Enhance a suggestion with Google Maps data"""
        if self._is_disabled():
            return suggestion  # Return original suggestion if Maps is disabled
        try:
            # Search for the place
            query = f"{suggestion.get('title', '')} {destination}"
            places = self.search_places(query, destination)
            
            if places:
                place = places[0]
                place_id = place.get('place_id')
                
                # Get detailed information
                place_details = self.get_place_details(place_id)
                
                # Enhance suggestion with maps data
                enhanced = suggestion.copy()
                enhanced.update({
                    'place_id': place_id,
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'formatted_address': place.get('formatted_address', ''),
                    'geometry': place.get('geometry', {}),
                    'photos': self.get_place_photos(place_id),
                    'opening_hours': place_details.get('opening_hours', {}),
                    'price_level': place.get('price_level', 0),
                    'types': place.get('types', [])
                })
                
                return enhanced
            
            return suggestion
        except Exception as e:
            print(f"Error enhancing suggestion: {e}")
            return suggestion
    
    def get_route_optimization(self, waypoints: List[str], origin: str, destination: str) -> Dict[str, Any]:
        """Optimize route through multiple waypoints"""
        if self._is_disabled():
            return {}
        try:
            # Use Google Maps Directions API with waypoints
            directions = self.gmaps.directions(
                origin=origin,
                destination=destination,
                waypoints=waypoints,
                optimize_waypoints=True
            )
            
            if directions:
                route = directions[0]
                return {
                    'optimized_waypoints': route.get('waypoint_order', []),
                    'total_distance': route['legs'][0]['distance']['text'],
                    'total_duration': route['legs'][0]['duration']['text'],
                    'route': route
                }
            
            return {}
        except Exception as e:
            print(f"Error optimizing route: {e}")
            return {}
    
    def get_real_suggestions(self, destination: str, room_type: str, preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get real suggestions from Google Places API with room-specific filtering"""
        print(f"=== MAPS SERVICE DEBUG ===")
        print(f"Google Maps client: {self.gmaps}")
        print(f"Is disabled: {self._is_disabled()}")
        
        if self._is_disabled():
            print("Google Maps API is disabled - returning empty list")
            return []
        
        print(f"Getting real suggestions for {room_type} in {destination}")
        
        try:
            # Test Google Maps API with a simple search first
            print("Testing Google Maps API with simple search...")
            test_places = self.gmaps.places(query="hotel in Mumbai")
            print(f"Test search returned: {len(test_places.get('results', []))} results")
            
            # Room-specific search configuration
            room_configs = {
                'stay': {
                    'place_type': 'lodging',
                    'keywords': ['hotel', 'resort', 'accommodation', 'hostel', 'guesthouse'],
                    'exclude_types': ['restaurant', 'tourist_attraction', 'transit_station'],
                    'radius': 15000  # 15km for accommodations
                },
                'travel': {
                    'place_type': 'transit_station',
                    'keywords': ['airport', 'bus station', 'train station', 'taxi', 'car rental', 'metro', 'subway', 'ferry', 'transportation'],
                    'exclude_types': ['lodging', 'restaurant', 'tourist_attraction', 'shopping_mall', 'hospital', 'school'],
                    'radius': 50000  # 50km for transportation
                },
                'activities': {
                    'place_type': 'tourist_attraction',
                    'keywords': ['museum', 'park', 'beach', 'temple', 'monument', 'adventure', 'entertainment'],
                    'exclude_types': ['lodging', 'restaurant', 'transit_station'],
                    'radius': 20000  # 20km for activities
                },
                'dining': {
                    'place_type': 'restaurant',
                    'keywords': ['restaurant', 'cafe', 'bar', 'food', 'cuisine'],
                    'exclude_types': ['lodging', 'tourist_attraction', 'transit_station'],
                    'radius': 10000  # 10km for dining
                }
            }
            
            config = room_configs.get(room_type, room_configs['activities'])
            
            # Build specific search query for the room type
            query_parts = []
            
            # Add room-specific keywords
            if config['keywords']:
                query_parts.extend(config['keywords'][:2])  # Use first 2 keywords
            
            # Add preference-based keywords
            if preferences.get('type'):
                query_parts.append(preferences.get('type'))
            
            if preferences.get('budget'):
                budget = preferences.get('budget', 0)
                if budget < 100:
                    query_parts.append('budget')
                elif budget > 500:
                    query_parts.append('luxury')
            
            # Add destination-specific keywords
            if 'beach' in destination.lower():
                query_parts.append('beach')
            elif 'mountain' in destination.lower():
                query_parts.append('mountain')
            elif 'city' in destination.lower():
                query_parts.append('city')
            
            query = ' '.join(query_parts) if query_parts else config['place_type']
            
            # Search for places with room-specific parameters
            # Use text search for better results
            search_query = f"{query} in {destination}"
            print(f"Searching for: {search_query}")
            
            try:
                places = self.gmaps.places(
                    query=search_query
                )
                print(f"Found {len(places.get('results', []))} places")
            except Exception as e:
                print(f"Google Places API error: {e}")
                return []
            
            results = []
            for place in places.get('results', [])[:25]:  # Get more results for filtering
                # Basic filtering - just exclude obviously wrong types
                place_types = place.get('types', [])
                
                # Simple room-specific filtering
                if room_type == 'travel':
                    # For travel, prefer transportation-related places
                    if not any(transport_type in place_types for transport_type in 
                             ['airport', 'bus_station', 'train_station', 'subway_station', 'taxi_stand', 'car_rental', 'transit_station']):
                        continue
                elif room_type == 'stay':
                    # For stay, prefer lodging-related places
                    if not any(lodging_type in place_types for lodging_type in 
                             ['lodging', 'hotel', 'resort', 'hostel', 'guest_house']):
                        continue
                elif room_type == 'dining':
                    # For dining, prefer food-related places
                    if not any(food_type in place_types for food_type in 
                             ['restaurant', 'food', 'cafe', 'bar', 'meal_takeaway']):
                        continue
                elif room_type == 'activities':
                    # For activities, prefer attraction-related places
                    if not any(attraction_type in place_types for attraction_type in 
                             ['tourist_attraction', 'museum', 'park', 'amusement_park', 'zoo', 'aquarium']):
                        continue
                
                # Get detailed information
                place_details = self.get_place_details(place.get('place_id'))
                
                suggestion = {
                    'id': place.get('place_id'),
                    'title': place.get('name', ''),
                    'description': place.get('vicinity', ''),
                    'rating': place.get('rating', 0),
                    'price_level': place.get('price_level', 0),
                    'address': place.get('vicinity', ''),
                    'photos': self.get_place_photos(place.get('place_id')),
                    'opening_hours': place_details.get('opening_hours', {}),
                    'phone': place_details.get('formatted_phone_number', ''),
                    'website': place_details.get('website', ''),
                    'types': place.get('types', []),
                    'geometry': place.get('geometry', {}),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'external_url': f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}"
                }
                
                results.append(suggestion)
                
                # Limit to 15 results per room type
                if len(results) >= 15:
                    break
            
            return results
            
        except Exception as e:
            print(f"Error getting real suggestions: {e}")
            return []

# Global maps service instance
maps_service = MapsService()
