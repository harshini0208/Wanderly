import { useState } from 'react';
import './JoinGroup.css';
import apiService from './api';

function JoinGroup({ onCancel, onGroupJoined }) {
  const [inviteCode, setInviteCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const joinData = {
        invite_code: inviteCode
      };

      const result = await apiService.joinGroup(joinData);
      
      alert(`Successfully joined group!`);
      
      if (onGroupJoined) {
        onGroupJoined(result);
      }
    } catch (error) {
      console.error('Error joining group:', error);
      setError(error.message || 'Failed to join group. Please check your invite code.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="join-group-container">
      <h2 className="join-title">Join Existing Group</h2>
      
      {error && (
        <div className="error-message" style={{ color: 'red', marginBottom: '1rem' }}>
          {error}
        </div>
      )}
      
      <form className="join-form" onSubmit={handleSubmit}>
        <label>Invite Code</label>
        <input
          type="text"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
          placeholder="Enter the invite code"
          required
        />

        <div className="form-buttons">
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={isLoading}
          >
            {isLoading ? 'Joining...' : 'Join Group'}
          </button>
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancel
          </button>
        </div>
      </form>
      <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
    </div>
  );
}

export default JoinGroup;




