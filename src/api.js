// API service for connecting to Python Flask backend
const getApiBaseUrl = () => {
  // If environment variable is defined, use that (for production)
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL + '/api';
  }

  // Development mode → use local backend
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:8000/api';
  }

  // This ensures Vercel-deployed frontend can connect to Cloud Run backend
  if (window.location.hostname.includes('vercel.app') || window.location.hostname.includes('wanderly-ai')) {
    return 'https://wanderly-323958238334.us-central1.run.app/api';
  }

  // Default fallback (same origin)
  return `${window.location.origin}/api`;
};

const API_BASE_URL = getApiBaseUrl();

// Debug logging (remove in production if needed)
console.log('🔧 API Configuration:', {
  VITE_API_URL: import.meta.env.VITE_API_URL || 'NOT SET',
  hostname: typeof window !== 'undefined' ? window.location.hostname : 'N/A',
  API_BASE_URL: API_BASE_URL
});

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
      },
      mode: 'cors',
      credentials: 'omit'
    };

    if (options.body) {
      config.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }

    // Enhanced debug logging
    console.log('🔧 API Request Debug:', {
      url,
      method: config.method,
      hostname: typeof window !== 'undefined' ? window.location.hostname : 'N/A',
      VITE_API_URL: import.meta.env.VITE_API_URL || 'NOT SET',
      API_BASE_URL: API_BASE_URL,
      headers: config.headers,
      hasBody: !!config.body
    });

    try {
      console.log(`📡 API call: ${config.method} ${url}`);
      console.log(`   Environment: VITE_API_URL=${import.meta.env.VITE_API_URL || 'NOT SET'}`);
      console.log(`   API_BASE_URL: ${API_BASE_URL}`);
      console.log(`   Full URL: ${url}`);
      
      const response = await fetch(url, config);
      
      console.log('✅ Response received:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries())
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('❌ API request failed:', error);
      console.error('   Error name:', error.name);
      console.error('   Error message:', error.message);
      console.error('   Error stack:', error.stack);

      // Provide more helpful error messages
      if (
        error.message === 'Load failed' ||
        error.message === 'Failed to fetch' ||
        error.message === 'NetworkError when attempting to fetch resource.' ||
        (error.name === 'TypeError' && error.message.includes('fetch'))
      ) {
        // Network/CORS error
        const debugInfo = `Debug info: API_BASE_URL=${API_BASE_URL}, VITE_API_URL=${import.meta.env.VITE_API_URL || 'NOT SET'}, Hostname=${window.location.hostname}`;
        console.error(debugInfo);
        throw new Error(
          `Cannot connect to server. Please ensure the backend server is running at ${API_BASE_URL}. Error: ${error.message}. ${debugInfo}`
        );
      }

      // Re-throw if message is descriptive
      if (error.message && !error.message.includes('Load failed')) {
        throw error;
      }

      // Generic fallback
      throw new Error(error.message || 'Unknown error occurred. Please check your connection and try again.');
    }
  }

  // Groups API
  async createGroup(groupData, userName, userEmail) {
    const userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

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
    return this.request(`/groups/${groupId}`);
  }

  async getGroupMembers(groupId) {
    return this.request(`/groups/${groupId}/members`);
  }

  async getUserGroups() {
    return [];
  }

  async createRoomsForGroup(groupId) {
    return this.request(`/groups/${groupId}/rooms`, {
      method: 'POST',
    });
  }

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

  async getUserAnswers(roomId, userId) {
    if (!userId) {
      throw new Error('User ID is required to get user answers');
    }
    return this.request(`/rooms/${roomId}/answers/${userId}`);
  }

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

  async getBatchPreferences(groupId) {
    return this.request(`/groups/${groupId}/batch-preferences`);
  }

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

  async consolidateGroupPreferences(groupId, roomType = null) {
    const url = `/groups/${groupId}/consolidate-preferences${roomType ? `?room_type=${encodeURIComponent(roomType)}` : ''}`;
    return this.request(url, {
      method: 'POST',
    });
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
    const url = `/voting/room/${roomId}/complete?user_name=${encodeURIComponent(
      userName
    )}&user_email=${encodeURIComponent(userEmail)}`;
    return this.request(url, {
      method: 'POST',
    });
  }

  async getRoomStatus(roomId) {
    return this.request(`/rooms/${roomId}/status`);
  }

  async getGroupDashboard(groupId) {
    return this.request(`/analytics/group/${groupId}/dashboard`);
  }

  async exportGroupItinerary(groupId) {
    return this.request(`/analytics/group/${groupId}/export`);
  }

  async getItineraryWeather(destination, startDate, endDate) {
    const params = new URLSearchParams({
      location: destination,
      start_date: startDate,
      end_date: endDate
    });
    return this.request(`/itinerary/weather?${params.toString()}`);
  }

  async getGroupWeatherAnalysis(groupId) {
    const response = await this.request(`/groups/${groupId}/weather-analysis`);
    return response;
  }

  async saveGroupWeatherAnalysis(groupId, weatherAnalysis) {
    const response = await this.request(`/groups/${groupId}/weather-analysis`, {
      method: 'POST',
      body: { weather_analysis: weatherAnalysis }
    });
    return response;
  }

  async analyzeWeatherActivities(destination, weatherData, existingActivities = [], groupPreferences = {}) {
    return this.request('/weather/analyze-activities', {
      method: 'POST',
      body: JSON.stringify({
        destination,
        weather_data: weatherData,
        existing_activities: existingActivities,
        group_preferences: groupPreferences
      })
    });
  }

  async checkWeatherChanges(destination, startDate, endDate, oldWeather = []) {
    return this.request('/weather/check-changes', {
      method: 'POST',
      body: JSON.stringify({
        destination,
        start_date: startDate,
        end_date: endDate,
        old_weather: oldWeather
      })
    });
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

  async getAIStatus() {
    return this.request('/ai/status');
  }

  getDestinationFunFacts(destination) {
    return fetch(`${API_BASE_URL}/destinations/${encodeURIComponent(destination)}/fun-facts`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    }).then(res => res.json());
  }

  async getPlacesAutocomplete(input) {
    if (!input || input.length < 2) {
      return { predictions: [] };
    }
    return this.request(`/places/autocomplete?input=${encodeURIComponent(input)}`);
  }
}

// Create and export a singleton instance
const apiService = new ApiService();
export default apiService;
