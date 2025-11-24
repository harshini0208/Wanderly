import { useState } from 'react';
import './CreateGroup.css';
import apiService from './api';
import LocationAutocomplete from './components/LocationAutocomplete';

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
        group_name: groupName,
        destination: toLocation,
        from_location: fromLocation,
        to_location: toLocation,
        total_members: totalMembers,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        description: description
      };

      const result = await apiService.createGroup(groupData, userName, userEmail);
      
      // Set user data in API service for future requests
      const userId = result.user_id;
      apiService.setUser(userId, userName, userEmail);
      
      // Create rooms for the group
      try {
        await apiService.createRoomsForGroup(result.id);
        // Rooms created successfully
      } catch (roomError) {
        console.error('Failed to create rooms:', roomError);
        // Continue anyway - rooms can be created later
      }
      
      alert(`Group "${groupName}" created successfully!\nGroup ID: ${result.id}`);
      
      if (onGroupCreated) {
        // Include user data in the result
        onGroupCreated({
          ...result,
          user_name: userName,
          user_email: userEmail
        });
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
        {/* Row 1: User Name and Email */}
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

        {/* Row 2: From Location, To Location, Group Name, Members */}
        <div className="form-row">
          <div className="form-section">
            <label className="form-label">FROM LOCATION</label>
            <LocationAutocomplete
              value={fromLocation}
              onChange={setFromLocation}
              placeholder="Where are you starting from?"
              className="form-input"
              required
            />
          </div>

          <div className="form-section">
            <label className="form-label">TO LOCATION</label>
            <LocationAutocomplete
              value={toLocation}
              onChange={setToLocation}
              placeholder="Where are you going?"
              className="form-input"
              required
            />
          </div>

          <div className="form-section">
            <label className="form-label">GROUP NAME</label>
            <input
              type="text"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="Enter group name"
              className="form-input"
              required
            />
          </div>

          <div className="form-section">
            <label className="form-label">MEMBERS</label>
            <input
              type="number"
              value={totalMembers}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                // Allow values from 1 to 20
                if (!isNaN(val) && val >= 1 && val <= 20) {
                  setTotalMembers(val);
                }
                // If empty or invalid, keep previous value (don't update)
              }}
              placeholder="How many people?"
              className="form-input"
              min="1"
              max="20"
              required
            />
          </div>
        </div>

        {/* Row 3: Travel Dates */}
        <div className="form-row">
          <div className="form-section-full">
            <label className="form-label">TRAVEL DATES</label>
            <div className="date-inputs">
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  // If end date is before new start date, update it
                  if (endDate && e.target.value && new Date(endDate) < new Date(e.target.value)) {
                    setEndDate(e.target.value);
                  }
                }}
                min={new Date().toISOString().split('T')[0]}
                className="form-input date-input"
                required
              />
              <span className="date-separator">to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                min={startDate || new Date().toISOString().split('T')[0]}
                className="form-input date-input"
                required
              />
            </div>
          </div>
        </div>

        <div className="form-buttons">
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={isLoading}
          >
            {isLoading ? 'CREATING...' : 'CREATE GROUP'}
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

export default CreateGroup;
