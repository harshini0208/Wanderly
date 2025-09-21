import { useState } from 'react';
import './CreateGroup.css';
import apiService from './api';

function CreateGroup({ onCancel, onGroupCreated }) {
  const [groupName, setGroupName] = useState('');
  const [fromLocation, setFromLocation] = useState('');
  const [toLocation, setToLocation] = useState('');
  const [totalMembers, setTotalMembers] = useState(2);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [description, setDescription] = useState('');
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Create group
      const groupData = {
        name: groupName,
        destination: toLocation, // Railway backend expects destination
        from_location: fromLocation, // Keep for future use
        to_location: toLocation, // Keep for future use
        total_members: totalMembers,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        description: description
      };

      const result = await apiService.createGroup(groupData);
      
      // Set user data in API service for future requests
      const userId = result.user_id || 'demo_user_123'; // Use returned user_id or fallback
      apiService.setUser(userId, userName, userEmail);
      
      // Create rooms for the group
      try {
        await apiService.createRoomsForGroup(result.group_id);
        console.log('Rooms created successfully');
      } catch (roomError) {
        console.error('Failed to create rooms:', roomError);
        // Continue anyway - rooms can be created later
      }
      
      alert(`Group "${groupName}" created successfully!\nInvite Code: ${result.invite_code}`);
      
      if (onGroupCreated) {
        onGroupCreated(result);
      }
    } catch (error) {
      console.error('Error creating group:', error);
      
      // Handle different error formats
      let errorMessage = 'Failed to create group. Please try again.';
      
      if (error.message) {
        errorMessage = error.message;
      } else if (error.detail) {
        // Handle validation errors from backend
        if (Array.isArray(error.detail)) {
          errorMessage = error.detail.map(err => err.msg).join(', ');
        } else {
          errorMessage = error.detail;
        }
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
      
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="create-group-container">
      <h2 className="create-title">Create New Trip Group</h2>
      
      {error && (
        <div className="error-message" style={{ color: 'red', marginBottom: '1rem' }}>
          {error}
        </div>
      )}
      
      <form className="create-form" onSubmit={handleSubmit}>
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

        <label>Group Name</label>
        <input
          type="text"
          value={groupName}
          onChange={(e) => setGroupName(e.target.value)}
          placeholder="Enter group name"
          required
        />

        <label>From Location</label>
        <input
          type="text"
          value={fromLocation}
          onChange={(e) => setFromLocation(e.target.value)}
          placeholder="Where are you starting from?"
          required
        />

        <label>To Location</label>
        <input
          type="text"
          value={toLocation}
          onChange={(e) => setToLocation(e.target.value)}
          placeholder="Where are you going?"
          required
        />

        <label>Number of Members</label>
        <input
          type="number"
          value={totalMembers}
          onChange={(e) => setTotalMembers(parseInt(e.target.value) || 2)}
          placeholder="How many people?"
          min="2"
          max="20"
          required
        />

        <label>Travel Dates</label>
        <div className="date-picker">
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
          <span>to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            required
          />
        </div>

        <label>Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Tell us the vibe of your trip..."
          rows="4"
        />

        <div className="form-buttons">
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={isLoading}
          >
            {isLoading ? 'Creating...' : 'Create Group'}
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

export default CreateGroup;
