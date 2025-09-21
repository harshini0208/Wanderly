// API service for connecting to Wanderly backend
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://wanderly-production-7e36.up.railway.app/api'
  : 'http://localhost:8000/api';

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
    console.log('API: Making request to:', url);
    
    // Add user authentication to the URL if available
    const separator = endpoint.includes('?') ? '&' : '?';
    const authUrl = this.userId ? `${url}${separator}user_id=${this.userId}` : url;
    
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(authUrl, config);
      console.log('API: Response status:', response.status);
      
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
    console.log('API: Getting group with ID:', groupId);
    const result = await this.request(`/groups/${groupId}`);
    console.log('API: Group result:', result);
    return result;
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
    console.log('API: submitAnswer called with:', { roomId, answerData });
    console.log('API: Current user ID:', this.userId);
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
    console.log('API: markRoomComplete called with:', { roomId, userName, userEmail });
    console.log('API: Full URL will be:', `${API_BASE_URL}${url}`);
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

