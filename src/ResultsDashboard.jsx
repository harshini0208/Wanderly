import { useState, useEffect } from 'react';
import './ResultsDashboard.css';
import apiService from './api';

function ResultsDashboard({ groupId, onBack }) {
  const [group, setGroup] = useState(null);
  const [consolidatedResults, setConsolidatedResults] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadConsolidatedResults();
  }, [groupId]);

  const loadConsolidatedResults = async () => {
    try {
      setLoading(true);
      
      // Load consolidated results for all rooms
      const results = await apiService.getGroupConsolidatedResults(groupId);
      console.log('Consolidated results:', results);
      
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

  const renderSuggestionCard = (suggestionData, voteData) => {
    const suggestion = suggestionData.suggestion;
    const votes = suggestionData.votes;
    
    return (
      <div key={suggestion.id} className="suggestion-card">
        <div className="suggestion-header">
          <h4 className="suggestion-title">{suggestion.title}</h4>
          {suggestion.price && (
            <div className="suggestion-price">
              ₹{suggestion.price} {suggestion.currency}
            </div>
          )}
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
        
        <div className="suggestion-votes">
          <span className="vote-count">👍 {votes.up_votes} likes</span>
          <span className="vote-count">👎 {votes.down_votes} dislikes</span>
        </div>
        
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

  if (loading) {
    return (
      <div className="results-container">
        <div className="loading">Loading consolidated results...</div>
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

  const roomEntries = Object.entries(consolidatedResults);
  const roomsWithResults = roomEntries.filter(([_, data]) => data.consensus);
  const roomsWithoutResults = roomEntries.filter(([_, data]) => !data.consensus);

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
                  {consensus.is_locked ? '🔒 Locked' : '🗳️ Voting Open'}
                </div>
              </div>
              
              {consensus.final_decision ? (
                <div className="final-decision">
                  <h3>✅ Final Decision</h3>
                  {Array.isArray(consensus.final_decision) ? (
                    <div className="suggestions-grid">
                      {consensus.final_decision.map((suggestion, index) => 
                        renderSuggestionCard(
                          { suggestion: suggestion, votes: { up_votes: 0, down_votes: 0 } },
                          null
                        )
                      )}
                    </div>
                  ) : (
                    renderSuggestionCard(
                      { suggestion: consensus.final_decision, votes: { up_votes: 0, down_votes: 0 } },
                      null
                    )
                  )}
                </div>
              ) : (
                <div className="consolidated-suggestions">
                  <h3>📊 All Liked Options ({likedSuggestions.length})</h3>
                  {likedSuggestions.length > 0 ? (
                    <div className="suggestions-grid">
                      {likedSuggestions.map(([suggestionId, suggestionData]) => 
                        renderSuggestionCard(suggestionData, null)
                      )}
                    </div>
                  ) : (
                    <p className="no-suggestions">No liked suggestions yet. Start voting to see results!</p>
                  )}
                </div>
              )}
              
              {consensus.consensus_summary && (
                <div className="consensus-summary">
                  <h4>🤖 AI Summary</h4>
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
          <h2 className="section-title">📊 Trip Summary</h2>
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
      <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
    </div>
  );
}

export default ResultsDashboard;