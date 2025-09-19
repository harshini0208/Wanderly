import { useState } from 'react';
import './CreateGroup.css';
import apiService from './api';

function CreateGroup({ onCancel, onGroupCreated }) {
  const [groupName, setGroupName] = useState('');
  const [destination, setDestination] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [description, setDescription] = useState('');
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
        destination: destination,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        description: description
      };

      const result = await apiService.createGroup(groupData);
      
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
      setError(error.message || 'Failed to create group. Please try again.');
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
        <label>Group Name</label>
        <input
          type="text"
          value={groupName}
          onChange={(e) => setGroupName(e.target.value)}
          placeholder="Enter group name"
          required
        />

        <label>Destination</label>
        <input
          type="text"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="Where are you going?"
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
    </div>
  );
}

export default CreateGroup;
