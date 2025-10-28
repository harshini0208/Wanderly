import { useState, useEffect } from 'react';
import './ResultsDashboard.css';
import apiService from './api';

function ResultsDashboard({ groupId, onBack }) {
  const [group, setGroup] = useState(null);
  const [consolidatedResults, setConsolidatedResults] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Maps popup state
  const [mapsModalOpen, setMapsModalOpen] = useState(false);
  const [selectedMapUrl, setSelectedMapUrl] = useState('');
  const [selectedSuggestion, setSelectedSuggestion] = useState(null);
  
  // Booking popup state
  const [bookingModalOpen, setBookingModalOpen] = useState(false);
  const [bookingData, setBookingData] = useState(null);

  useEffect(() => {
    loadConsolidatedResults();
  }, [groupId]);
  
  // Maps popup functions
  const handleOpenMaps = (suggestion) => {
    // Use maps_embed_url if available, otherwise fallback to maps_url
    const mapUrl = suggestion.maps_embed_url || suggestion.maps_url || suggestion.external_url;
    if (mapUrl) {
      setSelectedMapUrl(mapUrl);
      setSelectedSuggestion(suggestion);
      setMapsModalOpen(true);
    }
  };

  const handleCloseMaps = () => {
    setMapsModalOpen(false);
    setSelectedMapUrl('');
    setSelectedSuggestion(null);
  };
  
  // Booking popup functions
  const handleOpenBooking = (suggestion, roomType) => {
    setBookingData({
      suggestion,
      roomType,
      groupId
    });
    setBookingModalOpen(true);
  };
  
  const handleCloseBooking = () => {
    setBookingModalOpen(false);
    setBookingData(null);
  };
  
  const handleBookNow = async () => {
    try {
      // Create booking with selected suggestion
      const response = await fetch('/api/bookings/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          group_id: groupId,
          user_id: 'current_user', // TODO: Get from user context
          selections: [bookingData.suggestion],
          total_amount: bookingData.suggestion.price || 0,
          currency: '₹',
          trip_dates: {
            start: group?.start_date,
            end: group?.end_date
          },
          customer_details: {
            name: 'User Name', // TODO: Get from user context
            email: 'user@example.com'
          }
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        alert('Booking created successfully! Booking ID: ' + result.booking_id);
        handleCloseBooking();
      } else {
        alert('Booking failed: ' + result.error);
      }
    } catch (error) {
      console.error('Booking error:', error);
      alert('Error creating booking. Please try again.');
    }
  };

  const loadConsolidatedResults = async () => {
    try {
      setLoading(true);
      
      // Load consolidated results for all rooms
      const results = await apiService.getGroupConsolidatedResults(groupId);
      // Consolidated results loaded
      
      setGroup(results.group);
      setConsolidatedResults(results.room_results);
      
    } catch (error) {
      console.error('Error loading consolidated results:', error);
      setError('Failed to load consolidated results');
    } finally {
      setLoading(false);
    }
  };

  const getRoomTitle = (roomType) => {
    switch (roomType) {
      case 'stay': return 'Accommodation';
      case 'travel': return 'Transportation';
      case 'itinerary': return 'Activities';
      case 'eat': return 'Dining';
      default: return 'Plan';
    }
  };

  const getRoomIcon = (roomType) => {
    switch (roomType) {
      case 'stay': return '';
      case 'travel': return '';
      case 'itinerary': return '';
      case 'eat': return '';
      default: return '📋';
    }
  };

  const renderSuggestionCard = (suggestionData, roomType = null) => {
    const suggestion = suggestionData.suggestion;
    
    // Only show maps button for stay, eat, and itinerary (not travel)
    const showMapsButton = roomType !== 'travel' && (suggestion.maps_embed_url || suggestion.maps_url || suggestion.external_url);
    
    return (
      <div key={suggestion.id} className="suggestion-card">
        <div className="suggestion-header">
          <h4 className="suggestion-title">{suggestion.title || suggestion.name}</h4>
        </div>
        
        <p className="suggestion-description">{suggestion.description}</p>
        
        {suggestion.highlights && suggestion.highlights.length > 0 && (
          <div className="suggestion-highlights">
            {suggestion.highlights.map((highlight, index) => (
              <span key={index} className="highlight-tag">
                {highlight}
              </span>
            ))}
          </div>
        )}
        
        <div className="suggestion-actions">
          {showMapsButton && (
            <button 
              onClick={() => handleOpenMaps(suggestion)}
              className="explore-button"
              style={{
                background: '#27ae60',
                color: 'white',
                border: '2px solid #27ae60',
                padding: '0.5rem 1rem',
                fontWeight: '600',
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
                cursor: 'pointer',
                margin: '0.5rem 0.5rem 0.5rem 0',
                borderRadius: '4px'
              }}
            >
              View on Maps
            </button>
          )}
          
          {/* Book Now button - ONLY for transportation and accommodation */}
          {(roomType === 'travel' || roomType === 'stay') && (
            <button 
              onClick={() => handleOpenBooking(suggestion, roomType)}
              className="explore-button"
              style={{
                background: '#3498db',
                color: 'white',
                border: '2px solid #3498db',
                padding: '0.5rem 1rem',
                fontWeight: '600',
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
                cursor: 'pointer',
                margin: '0.5rem 0.5rem 0.5rem 0',
                borderRadius: '4px'
              }}
            >
              Book Now
            </button>
          )}
          
          {suggestion.external_url && (
            <a 
              href={suggestion.external_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="explore-button"
              style={{ textDecoration: 'none', marginLeft: '0.5rem' }}
            >
              Explore More
            </a>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="results-container">
        <div className="loading">Loading consolidated results...</div>
        <img src="dist/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="results-container">
        <div className="error">{error}</div>
        <button onClick={onBack} className="btn btn-secondary">Back to Dashboard</button>
        <img src="dist/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

  const roomEntries = Object.entries(consolidatedResults);
  const roomsWithResults = roomEntries.filter(([, data]) => data.consensus);
  const roomsWithoutResults = roomEntries.filter(([, data]) => !data.consensus);

  return (
    <div className="results-container">
      <div className="results-header">
        <button onClick={onBack} className="back-button">← Back to Dashboard</button>
        <h1 className="results-title">Consolidated Results</h1>
        <p className="results-subtitle">{group?.name} - {group?.destination}</p>
      </div>

      <div className="results-content">
        {/* Consolidated Results for each room */}
        {roomsWithResults.map(([roomId, roomData]) => {
          const room = roomData.room;
          const consensus = roomData.consensus;
          const likedSuggestions = consensus.liked_suggestions || [];
          
          return (
            <div key={roomId} className="room-section">
              <div className="room-header">
                <span className="room-icon">{getRoomIcon(room.room_type)}</span>
                <h2 className="room-title">{getRoomTitle(room.room_type)}</h2>
                <div className="room-status">
                  {consensus.is_locked ? 'Locked' : 'Voting Open'}
                </div>
              </div>
              
              {consensus.final_decision ? (
                <div className="final-decision">
                  <h3>Final Decision</h3>
                  {Array.isArray(consensus.final_decision) ? (
                    <div className="suggestions-grid">
                      {consensus.final_decision.map((suggestion) => 
                        renderSuggestionCard(
                          { suggestion: suggestion, votes: { up_votes: 0, down_votes: 0 } },
                          room.room_type
                        )
                      )}
                    </div>
                  ) : (
                    renderSuggestionCard(
                      { suggestion: consensus.final_decision, votes: { up_votes: 0, down_votes: 0 } },
                      room.room_type
                    )
                  )}
                </div>
              ) : (
                <div className="consolidated-suggestions">
                  <h3>Top Consolidated Results ({consensus.consolidated_count || likedSuggestions.length})</h3>
                  <p className="consolidation-info">
                    Based on all members' preferences • {consensus.total_liked || likedSuggestions.length} total liked options
                  </p>
                  {likedSuggestions.length > 0 ? (
                    <div className="suggestions-grid">
                      {likedSuggestions.map(([, suggestionData]) => 
                        renderSuggestionCard(suggestionData, room.room_type)
                      )}
                    </div>
                  ) : (
                    <p className="no-suggestions">No liked suggestions yet. Start voting to see consolidated results!</p>
                  )}
                </div>
              )}
              
              {consensus.consensus_summary && (
                <div className="consensus-summary">
                  <h4>AI Summary</h4>
                  <p>{consensus.consensus_summary}</p>
                </div>
              )}
            </div>
          );
        })}

        {/* Rooms without results */}
        {roomsWithoutResults.length > 0 && (
          <div className="pending-section">
            <h2 className="section-title">⏳ Pending Rooms</h2>
            <div className="pending-grid">
              {roomsWithoutResults.map(([roomId, roomData]) => (
                <div key={roomId} className="pending-card">
                  <span className="pending-icon">{getRoomIcon(roomData.room.room_type)}</span>
                  <h3 className="pending-title">{getRoomTitle(roomData.room.room_type)}</h3>
                  <p className="pending-status">No suggestions generated yet</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Summary */}
        <div className="summary-section">
          <h2 className="section-title">Trip Summary</h2>
          <div className="summary-stats">
            <div className="stat">
              <span className="stat-number">{roomsWithResults.length}</span>
              <span className="stat-label">Rooms with Results</span>
            </div>
            <div className="stat">
              <span className="stat-number">{roomsWithoutResults.length}</span>
              <span className="stat-label">Pending</span>
            </div>
            <div className="stat">
              <span className="stat-number">{roomEntries.length}</span>
              <span className="stat-label">Total Rooms</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Maps Modal */}
      {mapsModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
          onClick={handleCloseMaps}
        >
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '12px',
              width: '90%',
              height: '80%',
              maxWidth: '1200px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '20px',
                borderBottom: '1px solid #eee',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <h3 style={{ margin: 0, color: '#333' }}>
                {selectedSuggestion?.name || selectedSuggestion?.title || 'Location Map'}
              </h3>
              <button
                onClick={handleCloseMaps}
                style={{
                  background: '#ff4757',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                Close
              </button>
            </div>
            
            {/* Modal Content */}
            <div style={{ flex: 1, padding: '0' }}>
              <iframe
                src={selectedMapUrl}
                width="100%"
                height="100%"
                style={{ border: 'none', borderRadius: '0 0 12px 12px' }}
                allowFullScreen
                loading="lazy"
                title="Google Maps"
              />
            </div>
          </div>
        </div>
      )}
      
      {/* Booking Modal */}
      {bookingModalOpen && bookingData && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
          onClick={handleCloseBooking}
        >
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '12px',
              width: '90%',
              maxWidth: '600px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '80vh',
              overflow: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '20px',
                borderBottom: '1px solid #eee',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <h3 style={{ margin: 0, color: '#333' }}>
                Complete Your Booking
              </h3>
              <button
                onClick={handleCloseBooking}
                style={{
                  background: '#ff4757',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                Close
              </button>
            </div>
            
            {/* Modal Content */}
            <div style={{ padding: '20px' }}>
              <h4 style={{ marginTop: 0 }}>{bookingData.suggestion.name || bookingData.suggestion.title}</h4>
              <p>{bookingData.suggestion.description}</p>
              
              {bookingData.suggestion.price && (
                <div style={{ margin: '1rem 0', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                  <h5 style={{ margin: 0 }}>Price: ₹{bookingData.suggestion.price}</h5>
                </div>
              )}
              
              <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
                <button
                  onClick={handleBookNow}
                  style={{
                    background: '#27ae60',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '12px 24px',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '16px',
                    flex: 1
                  }}
                >
                  Confirm Booking
                </button>
                <button
                  onClick={handleCloseBooking}
                  style={{
                    background: '#ecf0f1',
                    color: '#333',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '12px 24px',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '16px',
                    flex: 1
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <img src="dist/plane.png" alt="Paper Plane" className="corner-plane" />
    </div>
  );
}

export default ResultsDashboard;