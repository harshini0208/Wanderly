import googlemaps
from app.config import settings
from typing import Dict, List, Any, Optional
import json

class MapsService:
    def __init__(self):
        try:
            self.gmaps = googlemaps.Client(key=settings.google_maps_api_key)
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
        """Get real suggestions from Google Places API"""
        if self._is_disabled():
            return []
        
        try:
            # Map room types to Google Places types
            place_type_mapping = {
                'stay': 'lodging',
                'activities': 'tourist_attraction',
                'dining': 'restaurant',
                'transportation': 'transit_station'
            }
            
            place_type = place_type_mapping.get(room_type, 'point_of_interest')
            
            # Build search query based on preferences
            query_parts = []
            if preferences.get('budget'):
                budget = preferences.get('budget', 0)
                if budget < 100:
                    query_parts.append('budget')
                elif budget > 500:
                    query_parts.append('luxury')
            
            if preferences.get('type'):
                query_parts.append(preferences.get('type'))
            
            query = ' '.join(query_parts) if query_parts else place_type
            
            # Search for places
            places = self.gmaps.places_nearby(
                location=destination,
                radius=10000,  # 10km radius
                type=place_type,
                keyword=query
            )
            
            results = []
            for place in places.get('results', [])[:10]:  # Limit to 10 results
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
                    'user_ratings_total': place.get('user_ratings_total', 0)
                }
                
                results.append(suggestion)
            
            return results
            
        except Exception as e:
            print(f"Error getting real suggestions: {e}")
            return []

# Global maps service instance
maps_service = MapsService()
