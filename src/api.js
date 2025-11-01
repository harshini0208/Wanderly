// API service for connecting to Python Flask backend
const API_BASE_URL = 'http://localhost:8000/api'; // Firebase backend URL

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
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    };

    if (options.body) {
      config.body = options.body;
    }

    try {
      console.log(`API call: ${url}`, config);
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Groups API
  async createGroup(groupData, userName, userEmail) {
    // Generate a user ID for the user
    const userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Add user information to the group data
    const requestData = {
      ...groupData,
      user_id: userId,
      user_name: userName,
      user_email: userEmail
    };
    
    const result = await this.request('/groups/', {
      method: 'POST',
      body: JSON.stringify(requestData),
    });
    
    // Add the user_id to the result so the frontend can access it
    result.user_id = userId;
    
    return result;
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

  async getGroupMembers(groupId) {
    return this.request(`/groups/${groupId}/members`);
  }

  async getUserGroups() {
    // For now, return empty array since we need user_id
    // This will be implemented when we add user authentication
    return [];
  }

  async createRoomsForGroup(groupId) {
    return this.request(`/groups/${groupId}/rooms`, {
      method: 'POST',
    });
  }

  // Rooms API
  async getGroupRooms(groupId) {
    return this.request(`/groups/${groupId}/rooms`);
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
    if (!this.userId) {
      throw new Error('User not authenticated. Please create or join a group first.');
    }
    
    const requestData = {
      ...answerData,
      room_id: roomId,
      user_id: this.userId
    };
    return this.request('/answers/', {
      method: 'POST',
      body: JSON.stringify(requestData),
    });
  }

  async getRoomAnswers(roomId) {
    return this.request(`/rooms/${roomId}/answers`);
  }

  // Suggestions API
  async generateSuggestions(requestData) {
    return this.request('/suggestions/', {
      method: 'POST',
      body: JSON.stringify(requestData),
    });
  }

  async getRoomSuggestions(roomId) {
    return this.request(`/rooms/${roomId}/suggestions`);
  }

  async getSuggestion(suggestionId) {
    return this.request(`/suggestions/${suggestionId}`);
  }

  async getRoomTopPreferences(roomId) {
    return this.request(`/rooms/${roomId}/top-preferences`);
  }

  async getTestSuggestions() {
    return this.request('/suggestions/test-suggestions');
  }

  // Voting API
  async submitVote(voteData) {
    return this.request('/votes/', {
      method: 'POST',
      body: JSON.stringify(voteData),
    });
  }

  async getSuggestionVotes(suggestionId) {
    return this.request(`/suggestions/${suggestionId}/votes`);
  }

  async getRoomConsensus(roomId) {
    return this.request(`/voting/room/${roomId}/consensus`);
  }

  async getGroupConsolidatedResults(groupId) {
    return this.request(`/voting/group/${groupId}/consolidated`);
  }

  async lockRoomDecision(roomId, suggestionId) {
    return this.request(`/rooms/${roomId}/lock`, {
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
    return this.request(`/rooms/${roomId}/status`);
  }

  // Analytics API
  async getGroupDashboard(groupId) {
    return this.request(`/analytics/group/${groupId}/dashboard`);
  }

  async exportGroupItinerary(groupId) {
    return this.request(`/analytics/group/${groupId}/export`);
  }

  async markRoomCompleted(roomId, userEmail) {
    return this.request(`/rooms/${roomId}/mark-completed`, {
      method: 'POST',
      body: JSON.stringify({ user_email: userEmail })
    });
  }

  async updateGroupTotalMembers(groupId, totalMembers) {
    return this.request(`/groups/${groupId}/update-total-members`, {
      method: 'POST',
      body: JSON.stringify({ total_members: totalMembers })
    });
  }

  async saveRoomSelections(roomId, selections) {
    return this.request(`/rooms/${roomId}/save-selections`, {
      method: 'POST',
      body: JSON.stringify({ selections: selections })
    });
  }

  async searchFlights(searchData) {
    return this.request('/flights/search', {
      method: 'POST',
      body: JSON.stringify(searchData)
    });
  }

  async updateGroup(groupId, updateData) {
    return this.request(`/groups/${groupId}`, {
      method: 'PUT',
      body: JSON.stringify(updateData)
    });
  }

  async clearRoomData(roomId) {
    return this.request(`/rooms/${roomId}/clear-data`, {
      method: 'POST'
    });
  }

  getDestinationFunFacts(destination) {
    return fetch(`${API_BASE_URL}/destinations/${encodeURIComponent(destination)}/fun-facts`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    }).then(res => res.json());
  }
}

// Create and export a singleton instance
const apiService = new ApiService();
export default apiService;

