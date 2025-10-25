import { useState, useEffect } from 'react';
import './GroupDashboard.css';
import apiService from './api';
import PlanningRoom from './PlanningRoom';
import ResultsDashboard from './ResultsDashboard';

// Import SVG icons
import hotelIcon from './assets/hotel-outline.svg';
import planeIcon from './assets/plane-outline.svg';
import calendarIcon from './assets/calendar-outline.svg';
import utensilsIcon from './assets/utensils-outline.svg';

function GroupDashboard({ groupId, userData, onBack }) {
  const [group, setGroup] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerContent, setDrawerContent] = useState('form'); // 'form', 'suggestions', or 'results'
  const [currentRoomType, setCurrentRoomType] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedSuggestions, setSelectedSuggestions] = useState([]);
  const [consolidatedResults, setConsolidatedResults] = useState({});

  useEffect(() => {
    loadGroupData();
  }, [groupId]);

  // Load saved data from localStorage on mount
  useEffect(() => {
    const savedGroup = localStorage.getItem(`wanderly_group_${groupId}`);
    const savedRooms = localStorage.getItem(`wanderly_rooms_${groupId}`);
    const savedSelectedRoom = localStorage.getItem(`wanderly_selectedRoom_${groupId}`);
    
    if (savedGroup) {
      try {
        setGroup(JSON.parse(savedGroup));
      } catch (error) {
        console.error('Error loading saved group:', error);
      }
    }
    
    if (savedRooms) {
      try {
        setRooms(JSON.parse(savedRooms));
      } catch (error) {
        console.error('Error loading saved rooms:', error);
      }
    }
    
    if (savedSelectedRoom) {
      try {
        setSelectedRoom(JSON.parse(savedSelectedRoom));
      } catch (error) {
        console.error('Error loading saved selected room:', error);
      }
    }
  }, [groupId]);

  // Save data to localStorage whenever it changes
  useEffect(() => {
    if (group) {
      localStorage.setItem(`wanderly_group_${groupId}`, JSON.stringify(group));
    }
  }, [group, groupId]);

  useEffect(() => {
    if (rooms.length > 0) {
      localStorage.setItem(`wanderly_rooms_${groupId}`, JSON.stringify(rooms));
    }
  }, [rooms, groupId]);

  useEffect(() => {
    if (selectedRoom) {
      localStorage.setItem(`wanderly_selectedRoom_${groupId}`, JSON.stringify(selectedRoom));
    }
  }, [selectedRoom, groupId]);

  const loadGroupData = async () => {
    try {
      setLoading(true);
      
      // Try to load from localStorage first for faster loading
      const savedGroup = localStorage.getItem(`wanderly_group_${groupId}`);
      const savedRooms = localStorage.getItem(`wanderly_rooms_${groupId}`);
      
      if (savedGroup && savedRooms) {
        try {
          setGroup(JSON.parse(savedGroup));
          setRooms(JSON.parse(savedRooms));
          setLoading(false);
        } catch (parseError) {
          console.error('Error parsing saved data:', parseError);
        }
      }
      
      // Always fetch fresh data in background
      const [groupData, roomsData] = await Promise.all([
        apiService.getGroup(groupId),
        apiService.getGroupRooms(groupId)
      ]);
      
      setGroup(groupData);
      
      // If no rooms exist, create them
      if (roomsData.length === 0) {
        // No rooms found, creating defaults
        try {
          await apiService.createRoomsForGroup(groupId);
          // Reload rooms after creating them
          const newRoomsData = await apiService.getGroupRooms(groupId);
          setRooms(newRoomsData);
        } catch (roomError) {
          console.error('Failed to create rooms:', roomError);
          setRooms([]);
        }
      } else {
        setRooms(roomsData);
      }
    } catch (error) {
      console.error('Error loading group data:', error);
      console.error('Group ID:', groupId);
      console.error('Error details:', error.message || error);
      setError(`Failed to load group data: ${error.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRoomSelect = (room) => {
    setSelectedRoom(room);  // Store the actual room object
    setCurrentRoomType(room.room_type);
    setDrawerContent('form');
    setDrawerOpen(true);
    setSuggestions([]);
    setSelectedSuggestions([]);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setCurrentRoomType(null);
    setSelectedRoom(null);
    setDrawerContent('form');
    setSuggestions([]);
    setSelectedSuggestions([]);
  };

  const handleFormSubmit = async (formData) => {
    try {
      setLoading(true);
      
      // Generate real AI suggestions using the existing AI service
      const aiSuggestions = await apiService.generateSuggestions({
        room_id: 'drawer-room',
        preferences: formData
      });
      
      setSuggestions(aiSuggestions);
      setDrawerContent('suggestions');
    } catch (error) {
      console.error('Error generating suggestions:', error);
      // Fallback to mock suggestions if AI fails
      const mockSuggestions = generateMockSuggestions(currentRoomType);
      setSuggestions(mockSuggestions);
      setDrawerContent('suggestions');
    } finally {
      setLoading(false);
    }
  };

  const generateMockSuggestions = (roomType) => {
    const suggestionsByType = {
      'accommodation': [
        { id: 1, name: 'Luxury Resort', description: '5-star beachfront resort', price: '$200/night', rating: 4.8 },
        { id: 2, name: 'Boutique Hotel', description: 'Charming city center hotel', price: '$120/night', rating: 4.6 },
        { id: 3, name: 'Eco Lodge', description: 'Sustainable mountain retreat', price: '$80/night', rating: 4.7 },
        { id: 4, name: 'Business Hotel', description: 'Modern business district hotel', price: '$150/night', rating: 4.5 },
        { id: 5, name: 'Historic Inn', description: 'Heritage building with character', price: '$90/night', rating: 4.4 },
        { id: 6, name: 'Budget Hostel', description: 'Affordable shared accommodation', price: '$25/night', rating: 4.2 }
      ],
      'transportation': [
        { id: 1, name: 'Direct Flight', description: 'Non-stop flight to destination', price: '$300', duration: '2h 30m', rating: 4.5 },
        { id: 2, name: 'Train Journey', description: 'Scenic train route', price: '$80', duration: '4h 15m', rating: 4.6 },
        { id: 3, name: 'Bus Service', description: 'Comfortable coach service', price: '$25', duration: '6h 30m', rating: 4.3 },
        { id: 4, name: 'Car Rental', description: 'Flexible self-drive option', price: '$60/day', duration: 'Flexible', rating: 4.4 },
        { id: 5, name: 'Private Transfer', description: 'Door-to-door service', price: '$120', duration: '3h 45m', rating: 4.7 },
        { id: 6, name: 'Shared Shuttle', description: 'Cost-effective shared transport', price: '$35', duration: '5h 20m', rating: 4.1 }
      ],
      'activities': [
        { id: 1, name: 'City Walking Tour', description: 'Explore historic downtown', price: '$25', duration: '3h', rating: 4.6 },
        { id: 2, name: 'Museum Visit', description: 'Cultural and art exhibitions', price: '$15', duration: '2h', rating: 4.4 },
        { id: 3, name: 'Nature Hike', description: 'Scenic mountain trails', price: '$30', duration: '4h', rating: 4.8 },
        { id: 4, name: 'Food Tour', description: 'Local cuisine tasting', price: '$45', duration: '2.5h', rating: 4.7 },
        { id: 5, name: 'Boat Cruise', description: 'Relaxing water excursion', price: '$55', duration: '3h', rating: 4.5 },
        { id: 6, name: 'Adventure Sports', description: 'Thrilling outdoor activities', price: '$80', duration: '5h', rating: 4.9 }
      ],
      'dining': [
        { id: 1, name: 'Fine Dining Restaurant', description: 'Michelin-starred cuisine', price: '$120/person', cuisine: 'International', rating: 4.8 },
        { id: 2, name: 'Local Street Food', description: 'Authentic local flavors', price: '$8/person', cuisine: 'Local', rating: 4.6 },
        { id: 3, name: 'Seafood Speciality', description: 'Fresh catch of the day', price: '$45/person', cuisine: 'Seafood', rating: 4.7 },
        { id: 4, name: 'Vegetarian Cafe', description: 'Healthy plant-based options', price: '$20/person', cuisine: 'Vegetarian', rating: 4.5 },
        { id: 5, name: 'Traditional Tavern', description: 'Historic local pub', price: '$25/person', cuisine: 'Traditional', rating: 4.4 },
        { id: 6, name: 'Rooftop Bar', description: 'Cocktails with city views', price: '$35/person', cuisine: 'Bar Food', rating: 4.6 }
      ]
    };
    return suggestionsByType[roomType] || [];
  };

  const handleSuggestionSelect = (suggestion) => {
    const suggestionId = suggestion.id || suggestions.indexOf(suggestion);
    if (selectedSuggestions.includes(suggestionId)) {
      setSelectedSuggestions(prev => prev.filter(id => id !== suggestionId));
    } else if (selectedSuggestions.length < 3) {
      setSelectedSuggestions(prev => [...prev, suggestionId]);
    }
  };

  const handleFinalSubmit = () => {
    // Handle final submission of selected suggestions
    console.log('Selected suggestions:', selectedSuggestions);
    // Here you would typically save the selections and close the drawer
    handleDrawerClose();
  };

  const handleBackToDashboard = () => {
    setSelectedRoom(null);
    setShowResults(false);
    loadGroupData(); // Refresh data
  };

  const loadConsolidatedResults = async () => {
    try {
      setLoading(true);
      const results = await apiService.getGroupConsolidatedResults(groupId);
      setConsolidatedResults(results.room_results || {});
    } catch (error) {
      console.error('Error loading consolidated results:', error);
    } finally {
      setLoading(false);
    }
  };

  const getRoomTitle = (roomType) => {
    switch (roomType) {
      case 'accommodation': return 'Accommodation';
      case 'transportation': return 'Transportation';
      case 'activities': return 'Activities';
      case 'dining': return 'Dining';
      default: return 'Plan';
    }
  };

  const getRoomIcon = (roomType) => {
    switch (roomType) {
      case 'accommodation': return '🏨';
      case 'transportation': return '✈️';
      case 'activities': return '📅';
      case 'dining': return '🍽️';
      default: return '📋';
    }
  };

  const renderSuggestionCard = (suggestionData) => {
    const suggestion = suggestionData.suggestion;
    
    return (
      <div key={suggestion.id} className="suggestion-card">
        <div className="suggestion-header">
          <h5 className="suggestion-title">{suggestion.title || suggestion.name}</h5>
          <div className="suggestion-rating">⭐ {suggestion.rating || '4.5'}</div>
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
        
        {suggestion.external_url && (
          <div className="suggestion-actions">
            <a 
              href={suggestion.external_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="explore-button"
            >
              🔗 Explore More
            </a>
          </div>
        )}
      </div>
    );
  };

  const handleShowResults = async () => {
    await loadConsolidatedResults();
    setDrawerContent('results');
    setDrawerOpen(true);
  };

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading">Loading group data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <div className="error">{error}</div>
        <button onClick={onBack} className="btn btn-secondary">Back to Home</button>
      </div>
    );
  }

  if (showResults) {
    return (
      <div className="dashboard-container">
        <ResultsDashboard 
          groupId={groupId}
          onBack={handleBackToDashboard}
        />
      </div>
    );
  }

  if (selectedRoom) {
    return (
      <div className="dashboard-container">
        <PlanningRoom 
          room={selectedRoom} 
          group={group}
          userData={userData}
          onBack={handleBackToDashboard}
        />
      </div>
    );
  }

  return (
    <div className="dashboard-layout">
      {/* Main Dashboard */}
      <div className={`dashboard-main ${drawerOpen ? 'drawer-open' : ''}`}>
        <div className="dashboard-container">
          {/* Group Info Row */}
          <div className="form-row">
            <div className="form-section-full">
              <h1 className="group-title">{group.name}</h1>
              <p className="group-destination">{group.destination}</p>
              <p className="group-dates">
                {new Date(group.start_date).toLocaleDateString()} - {new Date(group.end_date).toLocaleDateString()}
              </p>
              <div className="invite-code">
                <span className="invite-label">Invite Code:</span>
                <span className="invite-value">{group.id}</span>
              </div>
            </div>
          </div>

          {/* Plan Your Trip Section */}
          <div className="form-row">
            <div className="form-section-full">
              <h2 className="rooms-title">Plan Your Trip</h2>
              <div className="rooms-container">
                {rooms.map((room) => (
                  <div 
                    key={room.id} 
                    className={`room-card ${room.status}`}
                    onClick={() => handleRoomSelect(room)}
                  >
                    <div className="room-icon">
                      {room.room_type === 'accommodation' && <img src={hotelIcon} alt="Hotel" />}
                      {room.room_type === 'transportation' && <img src={planeIcon} alt="Travel" />}
                      {room.room_type === 'activities' && <img src={calendarIcon} alt="Calendar" />}
                      {room.room_type === 'dining' && <img src={utensilsIcon} alt="Utensils" />}
                    </div>
                    <h3 className="room-title">
                      {room.room_type === 'accommodation' && 'Stay'}
                      {room.room_type === 'transportation' && 'Travel'}
                      {room.room_type === 'activities' && 'Activities'}
                      {room.room_type === 'dining' && 'Eat'}
                    </h3>
                    <p className="room-description">
                      {room.room_type === 'accommodation' && 'Find the perfect accommodation'}
                      {room.room_type === 'transportation' && 'Book your transportation'}
                      {room.room_type === 'activities' && 'Plan activities and attractions'}
                      {room.room_type === 'dining' && 'Discover local cuisine'}
                    </p>
                    <div className="room-status">
                      {room.status === 'active' && 'Ready to plan'}
                      {room.status === 'locked' && 'Decision made'}
                      {room.status === 'completed' && 'Completed'}
                      {!room.status && 'Ready to plan'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Action Buttons Row */}
          <div className="form-row">
            <div className="form-section-full">
              <div className="dashboard-actions">
                <button onClick={handleShowResults} className="btn btn-primary">
                  VIEW RESULTS
                </button>
                <button onClick={onBack} className="btn btn-secondary">
                  BACK TO HOME
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Drawer */}
      <div className={`drawer ${drawerOpen ? 'drawer-open' : ''}`}>
        <div className="drawer-content">
          <div className="drawer-header">
            <h3 className="drawer-title">
              {drawerContent === 'form' && (
                <>
                  {currentRoomType === 'accommodation' && '🏨 Find Accommodation'}
                  {currentRoomType === 'transportation' && '✈️ Book Transportation'}
                  {currentRoomType === 'activities' && '📅 Plan Activities'}
                  {currentRoomType === 'dining' && '🍽️ Discover Dining'}
                </>
              )}
              {drawerContent === 'suggestions' && '✨ AI Suggestions'}
              {drawerContent === 'results' && '📊 Live Results'}
            </h3>
            <button onClick={handleDrawerClose} className="drawer-close">
              ×
            </button>
          </div>

          <div className="drawer-body">
            {drawerContent === 'form' && (
              <div className="form-content">
                <PlanningRoom 
                  room={selectedRoom}
                  group={group}
                  userData={userData}
                  onBack={handleDrawerClose}
                  onSubmit={handleFormSubmit}
                  isDrawer={true}
                />
              </div>
            )}

            {drawerContent === 'suggestions' && (
              <div className="suggestions-content">
                <div className="suggestions-header">
                  <h4>AI-Generated Suggestions</h4>
                  <p>Select your top 3 preferences:</p>
                </div>
                
                <div className="suggestions-grid">
                  {suggestions.map((suggestion, index) => (
                    <div 
                      key={suggestion.id || index}
                      className={`suggestion-card ${selectedSuggestions.includes(suggestion.id || index) ? 'selected' : ''}`}
                      onClick={() => handleSuggestionSelect(suggestion)}
                    >
                      <div className="suggestion-header">
                        <h5>{suggestion.name || suggestion.title || suggestion.suggestion_name}</h5>
                        <div className="suggestion-rating">
                          ⭐ {suggestion.rating || suggestion.star_rating || '4.5'}
                        </div>
                      </div>
                      <p className="suggestion-description">
                        {suggestion.description || suggestion.suggestion_description || suggestion.details}
                      </p>
                      <div className="suggestion-details">
                        <span className="suggestion-price">
                          {suggestion.price || suggestion.price_range || suggestion.cost || '$50'}
                        </span>
                        {suggestion.duration && <span className="suggestion-duration">{suggestion.duration}</span>}
                        {suggestion.cuisine && <span className="suggestion-cuisine">{suggestion.cuisine}</span>}
                        {suggestion.location && <span className="suggestion-location">{suggestion.location}</span>}
                      </div>
                      {selectedSuggestions.includes(suggestion.id || index) && (
                        <div className="selection-indicator">✓ Selected</div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="suggestions-footer">
                  <p className="selection-count">
                    {selectedSuggestions.length}/3 selected
                  </p>
                  <button 
                    onClick={handleFinalSubmit}
                    className="btn btn-primary"
                    disabled={selectedSuggestions.length === 0}
                  >
                    CONFIRM SELECTIONS
                  </button>
                </div>
              </div>
            )}

            {drawerContent === 'results' && (
              <div className="results-content">
                <div className="results-header">
                  <h4>Live Voting Results</h4>
                  <p>Current consensus for {group?.name}</p>
                </div>
                
                {Object.keys(consolidatedResults).length === 0 ? (
                  <div className="no-results">
                    <p>No voting results available yet. Start planning to see live results!</p>
                  </div>
                ) : (
                  <div className="results-sections">
                    {Object.entries(consolidatedResults).map(([roomId, roomData]) => {
                      const room = roomData.room;
                      const consensus = roomData.consensus;
                      const likedSuggestions = consensus?.liked_suggestions || [];
                      
                      return (
                        <div key={roomId} className="room-results-section">
                          <div className="room-results-header">
                            <span className="room-icon">{getRoomIcon(room.room_type)}</span>
                            <h5 className="room-title">{getRoomTitle(room.room_type)}</h5>
                            <div className="room-status">
                              {consensus?.is_locked ? '🔒 Locked' : '🗳️ Voting Open'}
                            </div>
                          </div>
                          
                          {consensus?.final_decision ? (
                            <div className="final-decision">
                              <h6>Final Decision</h6>
                              <div className="suggestions-grid">
                                {Array.isArray(consensus.final_decision) ? (
                                  consensus.final_decision.map((suggestion) => 
                                    renderSuggestionCard({ suggestion })
                                  )
                                ) : (
                                  renderSuggestionCard({ suggestion: consensus.final_decision })
                                )}
                              </div>
                            </div>
                          ) : likedSuggestions.length > 0 ? (
                            <div className="voting-results">
                              <h6>Top Suggestions</h6>
                              <div className="suggestions-grid">
                                {likedSuggestions.slice(0, 3).map((suggestionData) => 
                                  renderSuggestionCard(suggestionData)
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="no-suggestions">
                              <p>No suggestions available yet</p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                
                <div className="results-footer">
                  <button 
                    onClick={handleDrawerClose}
                    className="btn btn-secondary"
                  >
                    CLOSE RESULTS
        </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drawer Overlay */}
      {drawerOpen && <div className="drawer-overlay" onClick={handleDrawerClose}></div>}
    </div>
  );
}

export default GroupDashboard;
