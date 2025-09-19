import { useState, useEffect } from 'react';
import './ResultsDashboard.css';
import apiService from './api';

function ResultsDashboard({ groupId, onBack }) {
  const [group, setGroup] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [lockedDecisions, setLockedDecisions] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadGroupData();
  }, [groupId]);

  const loadGroupData = async () => {
    try {
      setLoading(true);
      
      // Load group and rooms
      const [groupData, roomsData] = await Promise.all([
        apiService.getGroup(groupId),
        apiService.getGroupRooms(groupId)
      ]);
      
      setGroup(groupData);
      setRooms(roomsData);
      
      // Load locked decisions for each room
      const decisions = {};
      for (const room of roomsData) {
        try {
          const consensus = await apiService.getRoomConsensus(room.id);
          console.log(`Room ${room.id} consensus:`, consensus);
          
          // Check if room is locked and has a final decision
          if (consensus.is_locked && consensus.final_decision) {
            decisions[room.id] = consensus.final_decision;
            console.log(`Found locked decision for room ${room.id}:`, consensus.final_decision);
          } else if (room.status === 'locked' && consensus.top_suggestions && consensus.top_suggestions.length > 0) {
            // If room is locked but no final_decision, use the top suggestion
            const topSuggestion = consensus.top_suggestions[0][1].suggestion;
            decisions[room.id] = topSuggestion;
            console.log(`Using top suggestion for locked room ${room.id}:`, topSuggestion);
          }
        } catch (err) {
          console.log(`No consensus data for room ${room.id}:`, err);
        }
      }
      setLockedDecisions(decisions);
      
    } catch (error) {
      console.error('Error loading group data:', error);
      setError('Failed to load group data');
    } finally {
      setLoading(false);
    }
  };

  const getRoomTitle = (roomType) => {
    switch (roomType) {
      case 'stay': return '🏨 Accommodation';
      case 'travel': return '✈️ Transportation';
      case 'itinerary': return '📅 Activities';
      case 'eat': return '🍽️ Dining';
      default: return 'Plan';
    }
  };

  const getRoomIcon = (roomType) => {
    switch (roomType) {
      case 'stay': return '🏨';
      case 'travel': return '✈️';
      case 'itinerary': return '📅';
      case 'eat': return '🍽️';
      default: return '📋';
    }
  };

  if (loading) {
    return (
      <div className="results-container">
        <div className="loading">Loading results...</div>
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="results-container">
        <div className="error">{error}</div>
        <button onClick={onBack} className="btn btn-secondary">Back to Dashboard</button>
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

  const lockedRooms = rooms.filter(room => lockedDecisions[room.id]);
  const pendingRooms = rooms.filter(room => !lockedDecisions[room.id]);

  return (
    <div className="results-container">
      <div className="results-header">
        <button onClick={onBack} className="back-button">← Back to Dashboard</button>
        <h1 className="results-title">Trip Results</h1>
        <p className="results-subtitle">{group?.name} - {group?.destination}</p>
      </div>

      <div className="results-content">
        {/* Locked Decisions */}
        <div className="decisions-section">
          <h2 className="section-title">✅ Final Decisions</h2>
          {lockedRooms.length > 0 ? (
            <div className="decisions-grid">
              {lockedRooms.map(room => {
                const decision = lockedDecisions[room.id];
                return (
                  <div key={room.id} className="decision-card">
                    <div className="decision-header">
                      <span className="decision-icon">{getRoomIcon(room.room_type)}</span>
                      <h3 className="decision-title">{getRoomTitle(room.room_type)}</h3>
                    </div>
                    
                    <div className="decision-content">
                      <h4 className="decision-name">{decision.title}</h4>
                      {decision.price && (
                        <div className="decision-price">
                          ₹{decision.price} {decision.currency}
                        </div>
                      )}
                      <p className="decision-description">{decision.description}</p>
                      
                      {decision.highlights && decision.highlights.length > 0 && (
                        <div className="decision-highlights">
                          {decision.highlights.map((highlight, index) => (
                            <span key={index} className="highlight-tag">
                              {highlight}
                            </span>
                          ))}
                        </div>
                      )}
                      
                      {decision.location && (
                        <div className="decision-location">
                          📍 {decision.location.address}
                        </div>
                      )}
                      
                      {decision.external_url && (
                        <a 
                          href={decision.external_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="decision-link"
                        >
                          View Details →
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="no-decisions">
              <p>No decisions have been locked yet.</p>
              <p>Complete the planning in each room to see results here.</p>
            </div>
          )}
        </div>

        {/* Pending Rooms */}
        {pendingRooms.length > 0 && (
          <div className="pending-section">
            <h2 className="section-title">⏳ Pending Decisions</h2>
            <div className="pending-grid">
              {pendingRooms.map(room => (
                <div key={room.id} className="pending-card">
                  <span className="pending-icon">{getRoomIcon(room.room_type)}</span>
                  <h3 className="pending-title">{getRoomTitle(room.room_type)}</h3>
                  <p className="pending-status">Not yet decided</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Summary */}
        <div className="summary-section">
          <h2 className="section-title">📊 Trip Summary</h2>
          <div className="summary-stats">
            <div className="stat">
              <span className="stat-number">{lockedRooms.length}</span>
              <span className="stat-label">Decisions Made</span>
            </div>
            <div className="stat">
              <span className="stat-number">{pendingRooms.length}</span>
              <span className="stat-label">Pending</span>
            </div>
            <div className="stat">
              <span className="stat-number">{rooms.length}</span>
              <span className="stat-label">Total Rooms</span>
            </div>
          </div>
        </div>
      </div>
      <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
    </div>
  );
}

export default ResultsDashboard;
