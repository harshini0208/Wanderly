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
        console.log('No rooms found, creating default rooms...');
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
    setSelectedRoom(room);
  };

  const handleBackToDashboard = () => {
    setSelectedRoom(null);
    setShowResults(false);
    loadGroupData(); // Refresh data
  };

  const handleShowResults = () => {
    setShowResults(true);
  };


  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading">Loading group data...</div>
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <div className="error">{error}</div>
        <button onClick={onBack} className="btn btn-secondary">Back to Home</button>
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
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
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
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
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <div className="header-top">
          <h1 className="group-title">{group.name}</h1>
        </div>
        <p className="group-destination">📍 {group.destination}</p>
        <p className="group-dates">
          {new Date(group.start_date).toLocaleDateString()} - {new Date(group.end_date).toLocaleDateString()}
        </p>
        <div className="invite-code">
          <span className="invite-label">Invite Code:</span>
          <span className="invite-value">{group.invite_code}</span>
        </div>
      </div>

      <div className="rooms-grid">
        <h2 className="rooms-title">Plan Your Trip</h2>
        <div className="rooms-container">
          {rooms.map((room) => (
            <div 
              key={room.id} 
              className={`room-card ${room.status}`}
              onClick={() => handleRoomSelect(room)}
            >
              <div className="room-icon">
                {room.room_type === 'stay' && <img src={hotelIcon} alt="Hotel" />}
                {room.room_type === 'travel' && <img src={planeIcon} alt="Travel" />}
                {room.room_type === 'itinerary' && <img src={calendarIcon} alt="Calendar" />}
                {room.room_type === 'eat' && <img src={utensilsIcon} alt="Utensils" />}
              </div>
              <h3 className="room-title">
                {room.room_type === 'stay' && 'Plan Stay'}
                {room.room_type === 'travel' && 'Plan Travel'}
                {room.room_type === 'itinerary' && 'Plan Activities'}
                {room.room_type === 'eat' && 'Plan Eat'}
              </h3>
              <p className="room-description">
                {room.room_type === 'stay' && 'Find the perfect accommodation'}
                {room.room_type === 'travel' && 'Book your transportation'}
                {room.room_type === 'itinerary' && 'Plan activities and attractions'}
                {room.room_type === 'eat' && 'Discover local cuisine'}
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

      <div className="dashboard-actions">
        <button onClick={handleShowResults} className="btn btn-primary">
          View Results
        </button>
        <button onClick={onBack} className="btn btn-secondary">
          Back to Home
        </button>
      </div>
      <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
    </div>
  );
}

export default GroupDashboard;
