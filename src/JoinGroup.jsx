import { useState, useEffect } from 'react';
import './JoinGroup.css';
import apiService from './api';

function JoinGroup({ onCancel, onGroupJoined, initialInviteCode }) {
  const [inviteCode, setInviteCode] = useState(initialInviteCode || '');
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Update invite code if initialInviteCode prop changes
  useEffect(() => {
    if (initialInviteCode) {
      setInviteCode(initialInviteCode);
    }
  }, [initialInviteCode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Trim whitespace from invite code to avoid validation issues
      const trimmedInviteCode = inviteCode.trim();
      
      if (!trimmedInviteCode) {
        setError('Please enter an invite code.');
        setIsLoading(false);
        return;
      }

      const joinData = {
        invite_code: trimmedInviteCode,
        user_name: userName.trim(),
        user_email: userEmail.trim()
      };

      const result = await apiService.joinGroup(joinData);
      
      // Set user data in API service for future requests
      const userId = result.user_id;
      if (!userId) {
        throw new Error('Failed to get user ID from server response');
      }
      apiService.setUser(userId, userName, userEmail);
      
      alert(`Successfully joined group!`);
      
      if (onGroupJoined) {
        // Include user data in the result
        onGroupJoined({
          ...result,
          user_name: userName,
          user_email: userEmail
        });
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
        {/* Row 1: Invite Code */}
        <div className="form-row">
          <div className="form-section-full">
            <label className="form-label">INVITE CODE</label>
            <input
              type="text"
              value={inviteCode}
              onChange={(e) => {
                // Trim whitespace but preserve case (group IDs are case-sensitive)
                setInviteCode(e.target.value.trim());
              }}
              placeholder="Enter the invite code"
              className="form-input"
              required
            />
          </div>
        </div>

        {/* Row 2: User Name and Email */}
        <div className="form-row">
          <div className="form-section">
            <label className="form-label">YOUR NAME</label>
            <input
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="Enter your name"
              className="form-input"
              required
            />
          </div>

          <div className="form-section">
            <label className="form-label">YOUR EMAIL</label>
            <input
              type="email"
              value={userEmail}
              onChange={(e) => setUserEmail(e.target.value)}
              placeholder="Enter your email"
              className="form-input"
              required
            />
          </div>
        </div>

        <div className="form-buttons">
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={isLoading}
          >
            {isLoading ? 'JOINING...' : 'JOIN GROUP'}
          </button>
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={isLoading}
          >
            CANCEL
          </button>
        </div>
      </form>
    </div>
  );
}

export default JoinGroup;




