// Mock API service for frontend-only deployment
// This will be replaced with actual backend integration later
const API_BASE_URL = '/api'; // Placeholder for future backend integration

class ApiService {
  constructor() {
    // Load user data from localStorage on initialization
    const savedUser = localStorage.getItem('wanderly_user_data');
    if (savedUser) {
      try {
        const userData = JSON.parse(savedUser);
        this.userId = userData.userId;
        this.userName = userData.userName;
        this.userEmail = userData.userEmail;
      } catch (error) {
        console.error('Error loading saved user data:', error);
      }
    } else {
      this.userId = null;
      this.userName = null;
      this.userEmail = null;
    }
  }

  setUser(userId, userName, userEmail) {
    this.userId = userId;
    this.userName = userName;
    this.userEmail = userEmail;
    
    // Save user data to localStorage
    localStorage.setItem('wanderly_user_data', JSON.stringify({
      userId,
      userName,
      userEmail
    }));
  }

  clearUser() {
    this.userId = null;
    this.userName = null;
    this.userEmail = null;
    localStorage.removeItem('wanderly_user_data');
  }

  async request(endpoint, options = {}) {
    // Mock implementation for frontend-only deployment
    console.log(`Mock API call: ${endpoint}`, options);
    
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Return mock data based on endpoint
    if (endpoint.includes('/groups/') && options.method === 'POST') {
      return {
        group_id: 'mock-group-' + Date.now(),
        group_name: 'Mock Group',
        invite_code: 'MOCK123',
        created_at: new Date().toISOString()
      };
    }
    
    if (endpoint.includes('/groups/join')) {
      return {
        group_id: 'mock-group-123',
        message: 'Successfully joined group'
      };
    }
    
    if (endpoint.includes('/suggestions/generate')) {
      return {
        suggestions: [
          {
            id: 'mock-suggestion-1',
            type: 'hotel',
            name: 'Mock Hotel',
            description: 'A beautiful mock hotel for your trip',
            rating: 4.5,
            price_range: '$100-200'
          },
          {
            id: 'mock-suggestion-2',
            type: 'restaurant',
            name: 'Mock Restaurant',
            description: 'Delicious mock cuisine',
            rating: 4.2,
            price_range: '$20-50'
          }
        ]
      };
    }
    
    // Default mock response
    return {
      message: 'Mock API response',
      endpoint: endpoint,
      timestamp: new Date().toISOString()
    };
  }

  // Groups API
  async createGroup(groupData, userName, userEmail) {
    const url = `/groups/?user_name=${encodeURIComponent(userName)}&user_email=${encodeURIComponent(userEmail)}`;
    return this.request(url, {
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
    // Getting group data
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
    // Submitting answer
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

  async markRoomComplete(roomId, userName, userEmail) {
    // Add user_name and user_email as URL parameters
    const url = `/voting/room/${roomId}/complete?user_name=${encodeURIComponent(userName)}&user_email=${encodeURIComponent(userEmail)}`;
    // Marking room complete
    return this.request(url, {
      method: 'POST',
    });
  }

  async getRoomStatus(roomId) {
    return this.request(`/voting/room/${roomId}/status`);
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

