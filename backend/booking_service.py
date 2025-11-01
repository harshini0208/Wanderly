from firebase_service import firebase_service
from datetime import datetime
from typing import Dict, List, Optional

class BookingService:
    """Service to handle trip bookings"""
    
    def __init__(self):
        self.db = firebase_service.db
    
    def create_booking(self, booking_data: Dict) -> Dict:
        """
        Create a new booking
        
        Args:
            booking_data: Complete booking information including:
                - group_id: Group ID
                - user_id: User ID making the booking
                - selections: List of selected suggestions to book
                - total_amount: Total booking amount
                - currency: Currency code
                - booking_status: Status (pending, confirmed, cancelled)
        
        Returns:
            Dict containing booking confirmation
        """
        try:
            # Generate booking ID
            booking_id = f"BW{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create booking document
            booking_doc = {
                'id': booking_id,
                'group_id': booking_data.get('group_id'),
                'user_id': booking_data.get('user_id'),
                'selections': booking_data.get('selections', []),
                'total_amount': booking_data.get('total_amount', 0),
                'currency': booking_data.get('currency', '₹'),
                'booking_status': booking_data.get('booking_status', 'pending'),
                'payment_status': 'pending',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'trip_dates': booking_data.get('trip_dates', {}),
                'customer_details': booking_data.get('customer_details', {})
            }
            
            # Save to Firebase
            doc_ref = self.db.collection('bookings').document()
            booking_doc['firebase_id'] = doc_ref.id
            doc_ref.set(booking_doc)
            
            return {
                'success': True,
                'booking_id': booking_id,
                'booking': booking_doc,
                'message': 'Booking created successfully'
            }
            
        except Exception as e:
            print(f"Error creating booking: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_bookings(self, user_id: str) -> List[Dict]:
        """Get all bookings for a user"""
        try:
            bookings_ref = self.db.collection('bookings')
            query = bookings_ref.where('user_id', '==', user_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error getting user bookings: {e}")
            return []
    
    def get_group_bookings(self, group_id: str) -> List[Dict]:
        """Get all bookings for a group"""
        try:
            bookings_ref = self.db.collection('bookings')
            query = bookings_ref.where('group_id', '==', group_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error getting group bookings: {e}")
            return []
    
    def update_booking_status(self, booking_id: str, status: str, payment_status: str = None) -> Dict:
        """Update booking and payment status"""
        try:
            booking = self.db.collection('bookings').document(booking_id).get()
            if not booking.exists:
                return {'success': False, 'error': 'Booking not found'}
            
            update_data = {
                'booking_status': status,
                'updated_at': datetime.now().isoformat()
            }
            
            if payment_status:
                update_data['payment_status'] = payment_status
            
            self.db.collection('bookings').document(booking_id).update(update_data)
            
            return {
                'success': True,
                'message': f'Booking status updated to {status}'
            }
            
        except Exception as e:
            print(f"Error updating booking status: {e}")
            return {'success': False, 'error': str(e)}

# Global booking service instance
booking_service = BookingService()

