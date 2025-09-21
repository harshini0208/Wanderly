// API service for connecting to Wanderly backend
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://wanderly-production-7e36.up.railway.app/api'
  : 'http://localhost:8000/api';

class ApiService {
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        // Handle validation errors properly
        let errorMessage = `HTTP error! status: ${response.status}`;
        
        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            // Handle validation errors array
            errorMessage = errorData.detail.map(err => err.msg || err.message || JSON.stringify(err)).join(', ');
          } else {
            errorMessage = errorData.detail;
          }
        }
        
        throw new Error(errorMessage);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Groups API
  async createGroup(groupData) {
    return this.request('/groups/', {
      method: 'POST',
      body: JSON.stringify(groupData),
    });
  }

  async joinGroup(inviteData) {
    return this.request('/groups/join', {
      method: 'POST',
      body: JSON.stringify(inviteData),
    });
  }

  async getGroup(groupId) {
    return this.request(`/groups/${groupId}`);
  }

  async getUserGroups() {
    return this.request('/groups/');
  }

  async createRoomsForGroup(groupId) {
    return this.request(`/groups/${groupId}/rooms`, {
      method: 'POST',
    });
  }

  // Rooms API
  async getGroupRooms(groupId) {
    return this.request(`/rooms/group/${groupId}`);
  }

  async getGroupRoomsUserStatus(groupId) {
    return this.request(`/rooms/group/${groupId}/user-status`);
  }

  async getRoom(roomId) {
    return this.request(`/rooms/${roomId}`);
  }

  async createQuestionsForRoom(roomId) {
    return this.request(`/rooms/${roomId}/questions`, {
      method: 'POST',
    });
  }

  async getRoomQuestions(roomId) {
    return this.request(`/rooms/${roomId}/questions`);
  }

  async submitAnswer(roomId, answerData) {
    return this.request(`/rooms/${roomId}/answers`, {
      method: 'POST',
      body: JSON.stringify(answerData),
    });
  }

  async getRoomAnswers(roomId) {
    return this.request(`/rooms/${roomId}/answers`);
  }

  // Suggestions API
  async generateSuggestions(requestData) {
    return this.request('/suggestions/generate', {
      method: 'POST',
      body: JSON.stringify(requestData),
    });
  }

  async getRoomSuggestions(roomId) {
    return this.request(`/suggestions/room/${roomId}`);
  }

  async getSuggestion(suggestionId) {
    return this.request(`/suggestions/${suggestionId}`);
  }

  async getTestSuggestions() {
    return this.request('/suggestions/test-suggestions');
  }

  // Voting API
  async submitVote(voteData) {
    return this.request('/voting/vote', {
      method: 'POST',
      body: JSON.stringify(voteData),
    });
  }

  async getSuggestionVotes(suggestionId) {
    return this.request(`/voting/suggestion/${suggestionId}/votes`);
  }

  async getRoomConsensus(roomId) {
    return this.request(`/voting/room/${roomId}/consensus`);
  }

  async getGroupConsolidatedResults(groupId) {
    return this.request(`/voting/group/${groupId}/consolidated`);
  }

  async lockRoomDecision(roomId, suggestionId) {
    return this.request(`/voting/room/${roomId}/lock?suggestion_id=${suggestionId}`, {
      method: 'POST',
    });
  }

  async lockRoomDecisionMultiple(roomId, suggestionIds) {
    return this.request(`/voting/room/${roomId}/lock-multiple`, {
      method: 'POST',
      body: JSON.stringify(suggestionIds),
    });
  }

  // Analytics API
  async getGroupDashboard(groupId) {
    return this.request(`/analytics/group/${groupId}/dashboard`);
  }

  async exportGroupItinerary(groupId) {
    return this.request(`/analytics/group/${groupId}/export`);
  }
}

// Create and export a singleton instance
const apiService = new ApiService();
export default apiService;

