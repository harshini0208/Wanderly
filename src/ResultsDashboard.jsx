import { useState, useEffect } from 'react';
import './ResultsDashboard.css';
import apiService from './api';

function ResultsDashboard({ groupId, onBack }) {
  const [group, setGroup] = useState(null);
  const [consolidatedResults, setConsolidatedResults] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [suggestionIdMapByRoom, setSuggestionIdMapByRoom] = useState({}); // { [roomId]: { [nameKey]: suggestionId } }
  const [countsBySuggestionByRoom, setCountsBySuggestionByRoom] = useState({}); // { [roomId]: { [suggestionId]: count } }
  const [userVotesBySuggestion, setUserVotesBySuggestion] = useState({}); // { [suggestionId]: 'up' | 'down' | null }
  
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
          currency: bookingData.suggestion.currency || 'USD',
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
      
      // Build suggestion id maps and counts per room
      try {
        const rooms = Object.values(results.room_results || {}).map(r => r.room) || [];
        // Build name->id maps
        const suggPairs = await Promise.all(rooms.map(async (room) => {
          try {
            const list = await apiService.getRoomSuggestions(room.id);
            const map = {};
            (list || []).forEach((s) => {
              const key = (s.name || s.title || '').toString().trim().toLowerCase();
              if (key && s.id) map[key] = s.id;
            });
            return [room.id, map];
          } catch (e) {
            return [room.id, {}];
          }
        }));
        setSuggestionIdMapByRoom(Object.fromEntries(suggPairs));

        // Fetch vote counts using top-preferences endpoint (returns counts map)
        const countPairs = await Promise.all(rooms.map(async (room) => {
          try {
            const pref = await apiService.getRoomTopPreferences(room.id);
            return [room.id, pref.counts_by_suggestion || {}];
          } catch (e) {
            return [room.id, {}];
          }
        }));
        setCountsBySuggestionByRoom(Object.fromEntries(countPairs));

        // Load user votes for all suggestions
        const userId = apiService.userId;
        if (userId) {
          try {
            const userVotesMap = {};
            const allSuggestions = [];
            for (const room of rooms) {
              try {
                const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                if (roomSuggestions && Array.isArray(roomSuggestions)) {
                  allSuggestions.push(...roomSuggestions);
                }
              } catch (e) {
                console.error(`Failed to fetch suggestions for room ${room.id}:`, e);
              }
            }
            
            await Promise.all(
              allSuggestions.map(async (suggestion) => {
                if (suggestion.id) {
                  try {
                    const votes = await apiService.getSuggestionVotes(suggestion.id);
                    const userVote = votes.find(v => v.user_id === userId && v.vote_type === 'up');
                    if (userVote) {
                      userVotesMap[suggestion.id] = 'up';
                    }
                  } catch (e) {
                    // Silently fail
                  }
                }
              })
            );
            
            setUserVotesBySuggestion(userVotesMap);
          } catch (e) {
            console.error('Failed to load user votes:', e);
          }
        }
      } catch (e) {
        console.error('Failed to prepare id maps or counts:', e);
      }
      
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

  const renderSuggestionCard = (suggestionData, roomType = null, roomId = null) => {
    const suggestion = suggestionData.suggestion;
    const idMap = roomId ? (suggestionIdMapByRoom[roomId] || {}) : {};
    const countsMap = roomId ? (countsBySuggestionByRoom[roomId] || {}) : {};
    const displayName = (suggestion.name || suggestion.title || 'Option').toString();
    const sid = idMap[displayName.trim().toLowerCase()] || suggestion.id;
    const likeCount = sid ? (countsMap[sid] || 0) : 0;
    
    // Check if current user has already liked this suggestion
    const userId = apiService.userId;
    const userVote = userId && sid ? (userVotesBySuggestion[sid] || null) : null;
    const isUserLiked = userVote === 'up';
    
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
        
        <div className="suggestion-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
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

          {/* Heart/Like button */}
          {roomId && (
            <button
              onClick={async (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                try {
                  if (!sid) {
                    console.error('Cannot vote: missing suggestion ID');
                    return;
                  }
                  
                  const userId = apiService.userId;
                  if (!userId) {
                    alert('Please join or create a group first to like suggestions.');
                    return;
                  }
                  
                  // Toggle: if already liked, unlike; otherwise, like
                  const newVoteType = isUserLiked ? 'down' : 'up';
                  
                  // Submit vote
                  await apiService.submitVote({
                    suggestion_id: sid,
                    user_id: userId,
                    vote_type: newVoteType
                  });
                  
                  // Update local state immediately for better UX
                  setUserVotesBySuggestion(prev => {
                    const updated = { ...prev };
                    if (newVoteType === 'up') {
                      updated[sid] = 'up';
                    } else {
                      delete updated[sid];
                    }
                    return updated;
                  });
                  
                  // Refresh to get updated counts
                  await loadConsolidatedResults();
                } catch (e) {
                  console.error('Failed to like:', e);
                  alert('Failed to submit vote. Please try again.');
                }
              }}
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                color: isUserLiked ? '#e74c3c' : '#999',
                opacity: isUserLiked ? 1 : 0.7
              }}
              title={isUserLiked ? 'Unlike' : 'Like'}
            >
              <span style={{ fontSize: '1.1rem' }}>❤</span>
              <span style={{ color: '#555', fontWeight: 600 }}>{likeCount}</span>
            </button>
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
              
              {(() => {
                // For transportation, always show two subsections (departure and return)
                const isTransportation = room.room_type === 'transportation';
                
                if (consensus.final_decision) {
                  const finalSuggestions = Array.isArray(consensus.final_decision) 
                    ? consensus.final_decision 
                    : [consensus.final_decision];
                  
                  if (isTransportation) {
                    // Separate into departure and return
                    const departureItems = finalSuggestions.filter(s => 
                      (s.trip_leg === 'departure' || s.leg_type === 'departure') || 
                      (!s.trip_leg && !s.leg_type)
                    );
                    const returnItems = finalSuggestions.filter(s => 
                      s.trip_leg === 'return' || s.leg_type === 'return'
                    );
                    
                    return (
                      <div className="final-decision">
                        <h3>Final Decision</h3>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '1rem' }}>
                          <div>
                            <h6 style={{ marginBottom: '1rem', color: '#3498db' }}>Departure Travel</h6>
                            {departureItems.length > 0 ? (
                              <div className="suggestions-grid">
                                {departureItems.map((suggestion) => 
                                  renderSuggestionCard(
                                    { suggestion: suggestion, votes: { up_votes: 0, down_votes: 0 } },
                                    room.room_type,
                                    roomId
                                  )
                                )}
                              </div>
                            ) : (
                              <p style={{ color: '#999', fontStyle: 'italic' }}>No departure preferences yet</p>
                            )}
                          </div>
                          <div>
                            <h6 style={{ marginBottom: '1rem', color: '#e67e22' }}>Return Travel</h6>
                            {returnItems.length > 0 ? (
                              <div className="suggestions-grid">
                                {returnItems.map((suggestion) => 
                                  renderSuggestionCard(
                                    { suggestion: suggestion, votes: { up_votes: 0, down_votes: 0 } },
                                    room.room_type,
                                    roomId
                                  )
                                )}
                              </div>
                            ) : (
                              <p style={{ color: '#999', fontStyle: 'italic' }}>No return preferences yet</p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  }
                  
                  // Non-transportation final decision
                  return (
                    <div className="final-decision">
                      <h3>Final Decision</h3>
                      {Array.isArray(consensus.final_decision) ? (
                        <div className="suggestions-grid">
                          {consensus.final_decision.map((suggestion) => 
                            renderSuggestionCard(
                              { suggestion: suggestion, votes: { up_votes: 0, down_votes: 0 } },
                              room.room_type,
                              roomId
                            )
                          )}
                        </div>
                      ) : (
                        renderSuggestionCard(
                          { suggestion: consensus.final_decision, votes: { up_votes: 0, down_votes: 0 } },
                          room.room_type,
                          roomId
                        )
                      )}
                    </div>
                  );
                }
                
                // Consolidated suggestions
                if (isTransportation) {
                  // Separate into departure and return
                  const departureItems = likedSuggestions.filter(([, suggestionData]) => {
                    const s = suggestionData.suggestion || suggestionData;
                    return (s.trip_leg === 'departure' || s.leg_type === 'departure') || 
                           (!s.trip_leg && !s.leg_type);
                  });
                  const returnItems = likedSuggestions.filter(([, suggestionData]) => {
                    const s = suggestionData.suggestion || suggestionData;
                    return s.trip_leg === 'return' || s.leg_type === 'return';
                  });
                  
                  return (
                    <div className="consolidated-suggestions">
                      <h3>Top Consolidated Results ({consensus.consolidated_count || likedSuggestions.length})</h3>
                      <p className="consolidation-info">
                        Based on all members' preferences • {consensus.total_liked || likedSuggestions.length} total liked options
                      </p>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '1rem' }}>
                        <div>
                          <h6 style={{ marginBottom: '1rem', color: '#3498db' }}>Departure Travel</h6>
                          {departureItems.length > 0 ? (
                            <div className="suggestions-grid">
                              {departureItems.map(([, suggestionData]) => 
                                renderSuggestionCard(suggestionData, room.room_type, roomId)
                              )}
                            </div>
                          ) : (
                            <p className="no-suggestions">No departure preferences yet</p>
                          )}
                        </div>
                        <div>
                          <h6 style={{ marginBottom: '1rem', color: '#e67e22' }}>Return Travel</h6>
                          {returnItems.length > 0 ? (
                            <div className="suggestions-grid">
                              {returnItems.map(([, suggestionData]) => 
                                renderSuggestionCard(suggestionData, room.room_type, roomId)
                              )}
                            </div>
                          ) : (
                            <p className="no-suggestions">No return preferences yet</p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                }
                
                // Non-transportation consolidated suggestions
                return (
                  <div className="consolidated-suggestions">
                    <h3>Top Consolidated Results ({consensus.consolidated_count || likedSuggestions.length})</h3>
                    <p className="consolidation-info">
                      Based on all members' preferences • {consensus.total_liked || likedSuggestions.length} total liked options
                    </p>
                    {likedSuggestions.length > 0 ? (
                      <div className="suggestions-grid">
                        {likedSuggestions.map(([, suggestionData]) => 
                          renderSuggestionCard(suggestionData, room.room_type, roomId)
                        )}
                      </div>
                    ) : (
                      <p className="no-suggestions">No liked suggestions yet. Start voting to see consolidated results!</p>
                    )}
                  </div>
                );
              })()}
              
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
                  <h5 style={{ margin: 0 }}>Price: {bookingData.suggestion.price}</h5>
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
      
    </div>
  );
}

export default ResultsDashboard;