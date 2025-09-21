import { useState } from 'react';
import './JoinGroup.css';
import apiService from './api';
import { useUser } from './UserContext';

function JoinGroup({ onCancel, onGroupJoined }) {
  const { login } = useUser();
  const [inviteCode, setInviteCode] = useState('');
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Set user context
      const userData = {
        name: userName.trim(),
        email: userEmail.trim()
      };
      login(userData);
      apiService.setUser(userData);

      const joinData = {
        invite_code: inviteCode,
        user_name: userName,
        user_email: userEmail
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

        <label>Your Name</label>
        <input
          type="text"
          value={userName}
          onChange={(e) => setUserName(e.target.value)}
          placeholder="Enter your name"
          required
        />

        <label>Your Email</label>
        <input
          type="email"
          value={userEmail}
          onChange={(e) => setUserEmail(e.target.value)}
          placeholder="Enter your email"
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




