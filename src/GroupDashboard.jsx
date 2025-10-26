import { useState, useEffect } from 'react';
import './GroupDashboard.css';
import apiService from './api';
import PlanningRoom from './PlanningRoom';
import ResultsDashboard from './ResultsDashboard';
import LoadingProgress from './components/LoadingProgress';

// Import SVG icons
import hotelIcon from './assets/stay.jpeg';
import planeIcon from './assets/travel.jpeg';
import calendarIcon from './assets/activities.jpeg';
import utensilsIcon from './assets/eat.jpeg';

function GroupDashboard({ groupId, userData, onBack }) {
  const [group, setGroup] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);  // For initial page load
  const [drawerLoading, setDrawerLoading] = useState(false);  // For drawer operations
  const [error, setError] = useState('');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerContent, setDrawerContent] = useState('form'); // 'form', 'suggestions', or 'results'
  const [currentRoomType, setCurrentRoomType] = useState(null);
  const [drawerRoom, setDrawerRoom] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedSuggestions, setSelectedSuggestions] = useState([]);
  const [consolidatedResults, setConsolidatedResults] = useState({});
  
  // Edit group state
  const [isEditingGroup, setIsEditingGroup] = useState(false);
  const [editingGroupData, setEditingGroupData] = useState({});
  
  // Inline results state
  const [showInlineResults, setShowInlineResults] = useState(false);

  // Maps popup state
  const [mapsModalOpen, setMapsModalOpen] = useState(false);
  const [selectedMapUrl, setSelectedMapUrl] = useState('');
  const [selectedSuggestion, setSelectedSuggestion] = useState(null);

  // Pagination state for suggestions display
  const [displayCount, setDisplayCount] = useState(1000); // Show all suggestions by default

  useEffect(() => {
    loadGroupData();
  }, [groupId]);

  // Save all session state to localStorage
  useEffect(() => {
    if (group) {
      localStorage.setItem(`wanderly_group_${groupId}`, JSON.stringify(group));
    }
    if (rooms.length > 0) {
      localStorage.setItem(`wanderly_rooms_${groupId}`, JSON.stringify(rooms));
    }
    if (selectedRoom) {
      localStorage.setItem(`wanderly_selectedRoom_${groupId}`, JSON.stringify(selectedRoom));
    }
    // Save drawer state
    if (drawerOpen) {
      localStorage.setItem(`wanderly_drawerState_${groupId}`, JSON.stringify({
        drawerOpen,
        drawerContent,
        currentRoomType,
        suggestions,
        selectedSuggestions
      }));
    }
  }, [group, rooms, selectedRoom, drawerOpen, drawerContent, currentRoomType, suggestions, selectedSuggestions, groupId]);

  // Load saved data from localStorage on mount (including drawer state)
  useEffect(() => {
    const savedDrawerState = localStorage.getItem(`wanderly_drawerState_${groupId}`);
    if (savedDrawerState) {
      try {
        const drawerState = JSON.parse(savedDrawerState);
        if (drawerState.drawerOpen) {
          setDrawerOpen(true);
          setDrawerContent(drawerState.drawerContent || 'form');
          setCurrentRoomType(drawerState.currentRoomType);
          setSuggestions(drawerState.suggestions || []);
          setSelectedSuggestions(drawerState.selectedSuggestions || []);
        }
      } catch (error) {
        console.error('Error loading saved drawer state:', error);
      }
    }
  }, [groupId]);

  const loadGroupData = async () => {
    try {
      setPageLoading(true);
      
      // Try to load from localStorage first for faster loading
      const savedGroup = localStorage.getItem(`wanderly_group_${groupId}`);
      const savedRooms = localStorage.getItem(`wanderly_rooms_${groupId}`);
      
      if (savedGroup && savedRooms) {
        try {
          setGroup(JSON.parse(savedGroup));
          setRooms(JSON.parse(savedRooms));
          setPageLoading(false);
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
      
      // If total_members is missing, try to fix it
      if (!groupData?.total_members && groupData?.members?.length) {
        try {
          await apiService.updateGroupTotalMembers(groupId, groupData.members.length);
          // Reload group data after update
          const updatedGroupData = await apiService.getGroup(groupId);
          setGroup(updatedGroupData);
        } catch (error) {
          console.error('Failed to update total_members:', error);
        }
      }
      
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
      setPageLoading(false);
    }
  };

  const handleRoomSelect = (room) => {
    setDrawerRoom(room); 
    setCurrentRoomType(room.room_type);
    setDrawerContent('form');
    setDrawerOpen(true);
    setSuggestions([]);
    setSelectedSuggestions([]);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setCurrentRoomType(null);
    setDrawerRoom(null);
    setDrawerContent('form');
    setSuggestions([]);
    setSelectedSuggestions([]);
  };

  const handleFormSubmit = async (formData) => {
    try {
      setDrawerLoading(true);
      
      // Use the real room ID from drawerRoom instead of 'drawer-room'
      if (!drawerRoom || !drawerRoom.id) {
        console.error('No room selected for suggestions');
        const mockSuggestions = generateMockSuggestions(currentRoomType);
        setSuggestions(mockSuggestions);
        setDrawerContent('suggestions');
        return;
      }
      
      console.log('Generating suggestions for room:', drawerRoom.id);
      console.log('Form data:', formData);
      
      // Generate real AI suggestions using the existing AI service
      const aiSuggestions = await apiService.generateSuggestions({
        room_id: drawerRoom.id,
        preferences: formData
      });
      
      console.log('AI suggestions received:', aiSuggestions);
      setSuggestions(aiSuggestions);
      setDrawerContent('suggestions');
    } catch (error) {
      console.error('Error generating suggestions:', error);
      // Fallback to mock suggestions if AI fails
      const mockSuggestions = generateMockSuggestions(currentRoomType);
      setSuggestions(mockSuggestions);
      setDrawerContent('suggestions');
    } finally {
      setDrawerLoading(false);
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
    } else {
      setSelectedSuggestions(prev => [...prev, suggestionId]);
    }
  };

  const handleFinalSubmit = async () => {
    try {
      if (!drawerRoom || selectedSuggestions.length === 0) return;
      
      // 1. Save the selected suggestions to consolidated results
      console.log('Saving selected suggestions:', selectedSuggestions);
      console.log('Available suggestions:', suggestions);
      
      // Get the actual suggestion objects from the selected IDs
      const selectedSuggestionObjects = selectedSuggestions.map(id => 
        suggestions.find(suggestion => suggestion.id === id || suggestions.indexOf(suggestion) === id)
      ).filter(Boolean);
      console.log('Selected suggestion objects:', selectedSuggestionObjects);
      
      // Call API to save selections to consolidated results
      const saveResponse = await apiService.saveRoomSelections(drawerRoom.id, selectedSuggestionObjects);
      
      if (saveResponse.success) {
        console.log('Selections saved successfully');
      } else {
        console.error('Failed to save selections:', saveResponse.error);
      }
      
      // 2. Mark room as completed by current user
      const completionResponse = await apiService.markRoomCompleted(drawerRoom.id, userData?.email);
      
      if (completionResponse.success) {
        console.log('Room marked as completed');
      } else {
        console.error('Failed to mark room as completed:', completionResponse.error);
      }
      
      // 3. Refresh group and rooms data to show updated completion count and selections
      const updatedRoomsData = await apiService.getGroupRooms(groupId);
      setRooms(updatedRoomsData);
      
      // 4. Refresh consolidated results if they're visible
      if (showInlineResults) {
        await loadConsolidatedResults();
      }
      
      // 5. Close drawer
      handleDrawerClose();
      
    } catch (error) {
      console.error('Error in final submit:', error);
    }
  };

  const handleBackToDashboard = () => {
    setSelectedRoom(null);
    setShowResults(false);
    loadGroupData(); // Refresh data
  };

  const loadConsolidatedResults = async () => {
    try {
      setDrawerLoading(true);
      const results = await apiService.getGroupConsolidatedResults(groupId);
      setConsolidatedResults(results.room_results || {});
      
      // Also load room selections directly from rooms
      const roomSelections = {};
      for (const room of rooms) {
        try {
          const roomData = await apiService.getRoom(room.id);
          if (roomData && roomData.user_selections) {
            roomSelections[room.id] = {
              selections: roomData.user_selections,
              completed: roomData.completed_by || []
            };
          }
        } catch (e) {
          console.error(`Error loading selections for room ${room.id}:`, e);
        }
      }
      console.log('Room selections:', roomSelections);
    } catch (error) {
      console.error('Error loading consolidated results:', error);
    } finally {
      setDrawerLoading(false);
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
    if (!showInlineResults) {
      await loadConsolidatedResults();
    } else {
      // Always refresh results when showing to get latest votes
      await loadConsolidatedResults();
    }
    setShowInlineResults(!showInlineResults);
  };

  // Maps popup handlers
  const handleOpenMaps = (suggestion) => {
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

  if (pageLoading && !group) {
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                {/* Back Home Button - Leftmost */}
                <button 
                  onClick={onBack}
                  className="btn btn-secondary"
                  style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem', marginRight: 'auto' }}
                >
                  🏠 Home
                </button>
                
                {/* Centered Trip Details */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
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

                {/* Edit Group Button - Right */}
                <div style={{ marginRight: '15%' }}>
                <button 
                  onClick={() => setIsEditingGroup(true)}
                  className="btn btn-secondary"
                  style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem' }}
                >
                  Edit Group
                </button>
                </div>
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
              <div className="room-completion">
                {room.completed_by ? `${room.completed_by.length}/${group?.total_members || group?.members?.length || 2} completed` : `0/${group?.total_members || group?.members?.length || 2} completed`}
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
                  {showInlineResults ? 'HIDE RESULTS' : 'VIEW RESULTS'}
        </button>
              </div>
            </div>
          </div>
          
          {/* Inline Consolidated Results */}
          {showInlineResults && (
            <div className="results-container">
                <div className="results-content">
                  <div className="results-header">
                    <h4>Live Voting Results</h4>
                    <p>Current consensus for {group?.name}</p>
                  </div>
                  
                  {rooms.length === 0 ? (
                    <div className="no-results">
                      <p>Loading rooms...</p>
                    </div>
                  ) : (
                    <div className="results-sections">
                      {rooms.map((room) => {
                        const selections = room.user_selections || [];
                        const completedCount = room.completed_by?.length || 0;
                        
                        return (
                          <div key={room.id} className="room-results-section">
                            <div className="room-results-header">
                              <span className="room-icon">{getRoomIcon(room.room_type)}</span>
                              <h5 className="room-title">{getRoomTitle(room.room_type)}</h5>
                              <div className="room-status">
                                {completedCount}/{group?.total_members || 2} completed
                              </div>
                            </div>
                            
                            {selections.length > 0 ? (
                              <div className="voting-results">
                                <h6>Selected Options ({selections.length})</h6>
                                <div className="suggestions-grid">
                                  {selections.map((suggestion, idx) => (
                                    <div key={idx} className="suggestion-card">
                                      <div className="suggestion-header">
                                        <h5 className="suggestion-title">
                                          {suggestion.name || suggestion.title || suggestion.airline || suggestion.operator || suggestion.train_name || 'Selection'}
                                        </h5>
                                        <div className="suggestion-rating">
                                          {suggestion.rating || '4.5'}
                                        </div>
                                      </div>
                                      <p className="suggestion-description">
                                        {suggestion.description || suggestion.suggestion_description || suggestion.details || 
                                         (suggestion.airline ? `${suggestion.airline} flight` :
                                          suggestion.train_name ? `${suggestion.train_name} ${suggestion.class || ''}` :
                                          suggestion.operator ? `${suggestion.operator} ${suggestion.bus_type || ''}` :
                                          'Selected option')}
                                      </p>
                                      <div className="suggestion-details">
                                        <span className="suggestion-price">
                                          {suggestion.price ? `₹${suggestion.price}` : suggestion.price_range || 'N/A'}
                                        </span>
                                        {suggestion.duration && <span className="suggestion-duration">{suggestion.duration}</span>}
                                        {suggestion.departure_time && suggestion.arrival_time && (
                                          <span className="suggestion-times">
                                            {suggestion.departure_time} - {suggestion.arrival_time}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <div className="no-suggestions">
                                <p>No selections made yet</p>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
            </div>
          )}
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
            {drawerContent === 'form' && drawerRoom && (
              <div className="form-content">
                {drawerLoading ? (
                  <LoadingProgress isLoading={drawerLoading} />
                ) : (
                  <PlanningRoom 
                    room={drawerRoom}
                    group={group}
                    userData={userData}
                    onBack={handleDrawerClose}
                    onSubmit={handleFormSubmit}
                    isDrawer={true}
                  />
                )}
              </div>
            )}

            {drawerContent === 'suggestions' && (
              <div className="suggestions-content">
                <div className="suggestions-header">
                  <h4>AI-Generated Suggestions</h4>
                  <p>Showing all {suggestions.length} suggestions</p>
                  <p>Select your preferred options:</p>
                </div>
                
                <div className="suggestions-grid">
                  {suggestions.map((suggestion, index) => (
                    <div 
                      key={suggestion.id || index}
                      className={`suggestion-card ${selectedSuggestions.includes(suggestion.id || index) ? 'selected' : ''}`}
                      onClick={() => handleSuggestionSelect(suggestion)}
                    >
                      <div className="suggestion-header">
                        <h5>
                          {suggestion.name || suggestion.title || suggestion.suggestion_name || 
                           (suggestion.airline && suggestion.flight_number ? 
                            `${suggestion.airline} ${suggestion.flight_number}` : 
                           suggestion.train_name && suggestion.train_number ?
                            `${suggestion.train_name} (${suggestion.train_number})` :
                           suggestion.operator && suggestion.bus_type ?
                            `${suggestion.operator} ${suggestion.bus_type}` :
                            suggestion.airline || suggestion.train_name || suggestion.operator || 'Transport Option')}
                        </h5>
                        <div className="suggestion-rating">
                          ⭐ {suggestion.rating || suggestion.star_rating || '4.5'}
                        </div>
                      </div>
                      <p className="suggestion-description">
                        {suggestion.description || suggestion.suggestion_description || suggestion.details ||
                         (suggestion.airline ? 
                          `${suggestion.airline} flight from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                         suggestion.train_name ?
                          `${suggestion.train_name} ${suggestion.class || ''} from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                         suggestion.operator ?
                          `${suggestion.operator} ${suggestion.bus_type || ''} from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                          'Transport option')}
                      </p>
                      <div className="suggestion-details">
                        <span className="suggestion-price">
                          {suggestion.price ? `₹${suggestion.price}` : 
                           suggestion.price_range || suggestion.cost || '$50'}
                        </span>
                        {suggestion.duration && <span className="suggestion-duration">{suggestion.duration}</span>}
                        {suggestion.departure_time && suggestion.arrival_time && (
                          <span className="suggestion-times">
                            {suggestion.departure_time} - {suggestion.arrival_time}
                          </span>
                        )}
                        {suggestion.class && <span className="suggestion-class">{suggestion.class}</span>}
                        {suggestion.bus_type && <span className="suggestion-bus-type">{suggestion.bus_type}</span>}
                        {suggestion.cuisine && <span className="suggestion-cuisine">{suggestion.cuisine}</span>}
                        {suggestion.location && <span className="suggestion-location">{suggestion.location}</span>}
                      </div>
                      {suggestion.amenities && suggestion.amenities.length > 0 && (
                        <div className="suggestion-amenities">
                          <small>Includes: {suggestion.amenities.join(', ')}</small>
                        </div>
                      )}
                      
                      {/* Maps button */}
                      {(suggestion.maps_embed_url || suggestion.maps_url || suggestion.external_url) && (
                        <div className="suggestion-actions">
                          <button 
                            className="maps-button"
                            onClick={(e) => {
                              e.stopPropagation(); // Prevent card selection
                              handleOpenMaps(suggestion);
                            }}
                          >
                            🗺️ View on Maps
                          </button>
                        </div>
                      )}
                      
                      {selectedSuggestions.includes(suggestion.id || index) && (
                        <div className="selection-indicator">✓ Selected</div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Load More Button */}
                {/* All suggestions are now displayed by default */}

                <div className="suggestions-footer">
                  <p className="selection-count">
                    {selectedSuggestions.length} selected
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

      {/* Maps Modal */}
      {mapsModalOpen && (
        <div className="maps-modal-overlay" onClick={handleCloseMaps}>
          <div className="maps-modal" onClick={(e) => e.stopPropagation()}>
            <div className="maps-modal-header">
              <h3>{selectedSuggestion?.name || 'Location'}</h3>
              <button className="maps-modal-close" onClick={handleCloseMaps}>
                ×
              </button>
            </div>
            <div className="maps-modal-body">
              <div className="maps-modal-layout">
                {/* Left sidebar with details */}
                <div className="maps-modal-details">
                  <div className="maps-modal-section">
                    <h4>Details</h4>
                    {selectedSuggestion?.description && (
                      <p className="maps-description">{selectedSuggestion.description}</p>
                    )}
                    {selectedSuggestion?.location && (
                      <p className="maps-location">📍 {selectedSuggestion.location}</p>
                    )}
                    {selectedSuggestion?.rating && (
                      <div className="maps-rating">
                        <span className="rating-stars">
                          {'⭐'.repeat(Math.floor(selectedSuggestion.rating))}☆
                        </span>
                        <span className="rating-value">{selectedSuggestion.rating}/5</span>
                      </div>
                    )}
                    {selectedSuggestion?.price_range && (
                      <p className="maps-price">💰 {selectedSuggestion.price_range}</p>
                    )}
                    {selectedSuggestion?.features && selectedSuggestion.features.length > 0 && (
                      <div className="maps-features">
                        <h5>Features:</h5>
                        <div className="features-list">
                          {selectedSuggestion.features.map((feature, idx) => (
                            <span key={idx} className="feature-tag">{feature}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Photos section */}
                  <div className="maps-modal-section">
                    <h4>Photos</h4>
                    {selectedSuggestion?.photos && selectedSuggestion.photos.length > 0 ? (
                      <div className="maps-photos-gallery">
                        <div className="photos-grid">
                          {selectedSuggestion.photos.slice(0, 6).map((photo_reference, idx) => {
                            const photoUrl = `https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference=${photo_reference}&key=AIzaSyBVR-c133yJG7wtpGOqYFBALI3-CH8BiR4`;
                            return (
                              <img 
                                key={idx}
                                src={photoUrl}
                                alt={`${selectedSuggestion?.name} - Photo ${idx + 1}`}
                                className="photo-thumbnail"
                                loading="lazy"
                                onError={(e) => {
                                  e.target.style.display = 'none';
                                }}
                              />
                            );
                          })}
                        </div>
                        <p className="photos-note">
                          {selectedSuggestion.photos.length} photos available
                        </p>
                        <a 
                          href={`https://www.google.com/maps/search/?api=1&query=place_id:${selectedSuggestion.place_id || selectedSuggestion.name}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="view-photos-btn"
                          style={{ display: 'block', textAlign: 'center', marginTop: '0.5rem' }}
                        >
                          View all photos on Google Maps →
                        </a>
                      </div>
                    ) : selectedSuggestion?.place_id ? (
                      <div className="maps-photos">
                        <a 
                          href={`https://www.google.com/maps/search/?api=1&query=place_id:${selectedSuggestion.place_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="view-photos-btn"
                          style={{ display: 'block', textAlign: 'center', width: '100%' }}
                        >
                          View Photos on Google Maps →
                        </a>
                        <p className="photos-note" style={{ marginTop: '0.5rem', textAlign: 'center' }}>
                          Click to see property photos
                        </p>
                      </div>
                    ) : null}
                  </div>
                  
                  {/* External link */}
                  <div className="maps-modal-section">
                    {selectedSuggestion?.maps_url && (
                      <a 
                        href={selectedSuggestion.maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="view-maps-btn"
                      >
                        🗺️ View on Google Maps
                      </a>
                    )}
                  </div>
                </div>
                
                {/* Right side with map */}
                <div className="maps-modal-map">
                  {selectedMapUrl && (
                    <iframe
                      src={selectedMapUrl}
                      width="100%"
                      height="100%"
                      style={{ border: 0 }}
                      allowFullScreen
                      loading="lazy"
                      referrerPolicy="no-referrer-when-downgrade"
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Group Modal */}
      {isEditingGroup && (
        <div className="edit-group-modal-overlay" onClick={() => setIsEditingGroup(false)}>
          <div className="edit-group-modal" onClick={(e) => e.stopPropagation()}>
            <div className="edit-group-header">
              <h3>Edit Group Details</h3>
              <button className="edit-group-close" onClick={() => setIsEditingGroup(false)}>×</button>
            </div>
            <div className="edit-group-body">
              <div className="edit-group-field">
                <label>Group Name</label>
                <input 
                  type="text" 
                  value={editingGroupData.name || group.name}
                  onChange={(e) => setEditingGroupData({...editingGroupData, name: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>From Location</label>
                <input 
                  type="text" 
                  value={editingGroupData.from_location || group.from_location || ''}
                  onChange={(e) => setEditingGroupData({...editingGroupData, from_location: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>Destination (To Location)</label>
                <input 
                  type="text" 
                  value={editingGroupData.destination || group.destination}
                  onChange={(e) => setEditingGroupData({...editingGroupData, destination: e.target.value})}
                />
                <small style={{color: '#666', fontSize: '0.85rem', display: 'block', marginTop: '0.5rem'}}>
                  ⚠️ Changing destination will refresh all votes
                </small>
              </div>
              <div className="edit-group-field">
                <label>Start Date</label>
                <input 
                  type="date" 
                  value={editingGroupData.start_date || group.start_date.split('T')[0]}
                  onChange={(e) => setEditingGroupData({...editingGroupData, start_date: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>End Date</label>
                <input 
                  type="date" 
                  value={editingGroupData.end_date || group.end_date.split('T')[0]}
                  onChange={(e) => setEditingGroupData({...editingGroupData, end_date: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>Number of Members</label>
                <input 
                  type="number" 
                  min="2"
                  value={editingGroupData.total_members || group.total_members || 2}
                  onChange={(e) => setEditingGroupData({...editingGroupData, total_members: parseInt(e.target.value)})}
                />
              </div>
              <div className="edit-group-actions">
                <button 
                  className="btn btn-primary"
                  onClick={async () => {
                    try {
                      const newDestination = editingGroupData.destination || group.destination;
                      const oldDestination = group.destination;
                      const destinationChanged = newDestination !== oldDestination;
                      
                      const updateData = {
                        name: editingGroupData.name || group.name,
                        from_location: editingGroupData.from_location || group.from_location,
                        destination: newDestination,
                        start_date: editingGroupData.start_date || group.start_date,
                        end_date: editingGroupData.end_date || group.end_date,
                        total_members: editingGroupData.total_members || group.total_members
                      };
                      
                      // Show confirmation if destination changed
                      if (destinationChanged) {
                        const confirmReset = window.confirm(
                          '⚠️ Changing the destination will reset all votes and suggestions.\n\n' +
                          'Do you want to continue?'
                        );
                        if (!confirmReset) {
                          return;
                        }
                      }
                      
                      await apiService.updateGroup(groupId, updateData);
                      
                      // If destination changed, reset votes by clearing room answers and suggestions
                      if (destinationChanged) {
                        // Clear all room voting data
                        for (const room of rooms) {
                          try {
                            await apiService.clearRoomData(room.id);
                          } catch (e) {
                            console.error(`Error clearing room ${room.id}:`, e);
                          }
                        }
                        // If destination changed, reload all data
                        await loadGroupData();
                      } else {
                        // If destination didn't change, only update the group data (preserve votes)
                        const updatedGroupData = await apiService.getGroup(groupId);
                        setGroup(updatedGroupData);
                      }
                      
                      setIsEditingGroup(false);
                      setEditingGroupData({});
                      
                      // Show success message
                      if (destinationChanged) {
                        alert('Group updated! All votes have been reset due to destination change.');
                      } else {
                        console.log('Group updated successfully! Voting data preserved.');
                      }
                    } catch (error) {
                      console.error('Error updating group:', error);
                      alert('Error updating group. Please try again.');
                    }
                  }}
                >
                  Save Changes
                </button>
                <button 
                  className="btn btn-secondary"
                  onClick={() => {
                    setIsEditingGroup(false);
                    setEditingGroupData({});
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

export default GroupDashboard;
