import { useState } from 'react';
import './CreateGroup.css';

function CreateGroup() {
  const [groupName, setGroupName] = useState('');
  const [destination, setDestination] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    alert(`Group "${groupName}" created!`);
    // You can add actual submission logic here
  }

  return (
    <div className="create-group-container">
      <h2 className="create-title">Create New Trip Group</h2>
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
          <button type="submit" className="btn btn-primary">Create Group</button>
          <button type="button" className="btn btn-secondary">Cancel</button>
        </div>
      </form>
    </div>
  );
}

export default CreateGroup;
