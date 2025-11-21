import { useState, useEffect } from 'react';
import './GroupDashboard.css';
import apiService from './api';
import PlanningRoom from './PlanningRoom';
import ResultsDashboard from './ResultsDashboard';
import LoadingProgress from './components/LoadingProgress';
import { normalizeAndValidateSuggestions } from './utils/apiHelpers';

// Import SVG icons
import hotelIcon from './assets/stay.jpeg';
import planeIcon from './assets/travel.jpeg';
import calendarIcon from './assets/activities.jpeg';
import utensilsIcon from './assets/eat.jpeg';
import planePng from './assets/plane.png';
import createBg from './assets/create_bg_large.png';

const deduplicateSelections = (selections = []) => {
  const unique = [];
  const seenIds = new Set();
  const seenNames = new Set();

  selections.forEach((selection) => {
    const id = selection?.id || selection?.suggestion_id;
    const name = (selection?.name || selection?.title || selection?.airline || selection?.operator || selection?.train_name || '')
      .toString()
      .trim()
      .toLowerCase();

    if (id) {
      if (seenIds.has(id)) {
        return;
      }
      seenIds.add(id);
    } else if (name) {
      if (seenNames.has(name)) {
        return;
      }
      seenNames.add(name);
    } else {
      if (seenNames.has('unknown')) {
        return;
      }
      seenNames.add('unknown');
    }

    unique.push(selection);
  });

  return unique;
};

const mapSelectionToOption = (selection = {}) => {
  const name = (selection.name || selection.title || selection.airline || selection.operator || selection.train_name || 'Selection').toString();
  return {
    suggestion_id: selection.suggestion_id || selection.id || selection.place_id || name.toLowerCase(),
    name,
    source: selection.source || 'selection',
  };
};

const deduplicateOptions = (options = []) => {
  const unique = [];
  const seenIds = new Set();
  const seenNames = new Set();

  options.forEach((option) => {
    if (!option) return;
    const id = option.suggestion_id || option.id;
    const name = (option.name || '').toString().trim().toLowerCase();

    if (id) {
      if (seenIds.has(id)) {
        return;
      }
      seenIds.add(id);
    } else if (name) {
      if (seenNames.has(name)) {
        return;
      }
      seenNames.add(name);
    }

    unique.push(option);
  });

  return unique;
};

const shuffleArray = (arr = []) => arr.slice().sort(() => Math.random() - 0.5);

function GroupDashboard({ groupId, userData, onBack }) {
  const [group, setGroup] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);  // For initial page load
  const [drawerLoading, setDrawerLoading] = useState(false);  // For drawer operations
  const [error, setError] = useState('');

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerContent, setDrawerContent] = useState('form'); // 'form', 'suggestions', or 'results'
  const [currentRoomType, setCurrentRoomType] = useState(null);
  const [drawerRoom, setDrawerRoom] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedSuggestions, setSelectedSuggestions] = useState([]);
  const [consolidatedResults, setConsolidatedResults] = useState({});
  
  // Edit group state
  const [isEditingGroup, setIsEditingGroup] = useState(false);
  const [editingGroupData, setEditingGroupData] = useState({});
  
  // Inline results state
  const [showInlineResults, setShowInlineResults] = useState(false);

  // Maps popup state
  const [mapsModalOpen, setMapsModalOpen] = useState(false);
  const [selectedMapUrl, setSelectedMapUrl] = useState('');
  const [selectedSuggestion, setSelectedSuggestion] = useState(null);
  
  // Booking modal state
  const [bookingModalOpen, setBookingModalOpen] = useState(false);
  const [bookingData, setBookingData] = useState(null);
  const [bookingStep, setBookingStep] = useState(1); // 1: details, 2: confirmation
  const [bookingForm, setBookingForm] = useState({
    title: '',
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    contactEmail: '',
    contactPhone: ''
  });
  const [termsAccepted, setTermsAccepted] = useState(false);

  // Pagination state for suggestions display
  const [displayCount, setDisplayCount] = useState(1000); // Show all suggestions by default
  const [topPreferencesByRoom, setTopPreferencesByRoom] = useState({});
  const [suggestionIdMapByRoom, setSuggestionIdMapByRoom] = useState({}); // { [roomId]: { [nameKey]: suggestionId } }
  const [fullSuggestionsByRoom, setFullSuggestionsByRoom] = useState({}); // { [roomId]: [fullSuggestionData] }
  const [groupMembers, setGroupMembers] = useState([]);
  const [userVotesBySuggestion, setUserVotesBySuggestion] = useState({}); // { [suggestionId]: 'up' | 'down' | null }
  const [isConfirming, setIsConfirming] = useState(false);

  // Stable ordering for rooms: Stay, Travel, Dining, Activities
  const sortRoomsByDesiredOrder = (roomsArray) => {
    const order = { accommodation: 0, transportation: 1, dining: 2, activities: 3 };
    return (roomsArray || []).slice().sort((a, b) => {
      const ai = order[a?.room_type] ?? 999;
      const bi = order[b?.room_type] ?? 999;
      if (ai !== bi) return ai - bi;
      return (a?.id || '').localeCompare(b?.id || '');
    });
  };

  useEffect(() => {
    loadGroupData();
  }, [groupId]);
  
  // Real-time polling for group members and rooms data
  useEffect(() => {
    if (!groupId) return;

    const refreshGroupData = async () => {
      try {
        const membersData = await apiService.getGroupMembers(groupId).catch(() => ({ members: [], total_count: 0 }));
        if (membersData && membersData.members) {
          setGroupMembers(prevMembers => {
            const prevIds = new Set(prevMembers.map(m => m.id || m.user_id || m));
            const newIds = new Set(membersData.members.map(m => m.id || m.user_id || m));
            if (prevIds.size !== newIds.size || ![...prevIds].every(id => newIds.has(id))) {
              return membersData.members;
            }
            return prevMembers;
          });
        }

        const roomsData = await apiService.getGroupRooms(groupId);
        if (roomsData && roomsData.length > 0) {
          setRooms(prevRooms => {
            const sortedNew = sortRoomsByDesiredOrder(roomsData);
            if (JSON.stringify(sortedNew) !== JSON.stringify(prevRooms)) {
              return sortedNew;
            }
            return prevRooms;
          });
        }

        const groupData = await apiService.getGroup(groupId);
        if (groupData) {
          setGroup(prevGroup => {
            if (JSON.stringify(prevGroup) !== JSON.stringify(groupData)) {
              return groupData;
            }
            return prevGroup;
          });
        }
      } catch (error) {
        console.error('Error in real-time refresh:', error);
      }
    };

    const initialTimeout = setTimeout(refreshGroupData, 1000);
    
    if (!drawerOpen && !showInlineResults) {
      return () => clearTimeout(initialTimeout);
    }

    const interval = setInterval(refreshGroupData, 15000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [groupId, drawerOpen, showInlineResults]);

  // Real-time polling for votes, top preferences, and AI consolidation
  useEffect(() => {
    if (!groupId || rooms.length === 0) return;
    if (!drawerOpen && !showInlineResults) {
      console.log('⏸️ Vote polling paused - user not viewing');
      return;
    }

    const refreshVotesAndPreferences = async () => {
      try {
        let prefsMap = {};
        try {
          const batchPrefs = await apiService.getBatchPreferences(groupId);
          prefsMap = batchPrefs || {};
        } catch (batchError) {
          console.error('Batch preference fetch failed, falling back to per-room calls:', batchError);
        const prefsResponses = await Promise.all(
          rooms.map(async (room) => {
            try {
              const res = await apiService.getRoomTopPreferences(room.id);
              return [room.id, res];
            } catch (e) {
              return [room.id, { top_preferences: [], counts_by_suggestion: {} }];
            }
          })
        );
          prefsMap = Object.fromEntries(prefsResponses);
        }

        setTopPreferencesByRoom(prev => {
          if (JSON.stringify(prev) !== JSON.stringify(prefsMap)) {
            return prefsMap;
          }
          return prev;
        });

        // Refresh user votes for all suggestions
        const userId = apiService.userId || userData?.id || userData?.email;
        if (userId) {
          try {
            const userVotesMap = {};
            const allSuggestions = [];
            for (const room of rooms) {
              try {
                const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                if (roomSuggestions && Array.isArray(roomSuggestions)) {
                  allSuggestions.push(...roomSuggestions);
                }
              } catch (e) {
                console.error(`Failed to fetch suggestions for room ${room.id}:`, e);
              }
            }
            
            await Promise.all(
              allSuggestions.map(async (suggestion) => {
                if (suggestion.id) {
                  try {
                    const votes = await apiService.getSuggestionVotes(suggestion.id);
                    const userVote = votes.find(v => v.user_id === userId && v.vote_type === 'up');
                    if (userVote) {
                      userVotesMap[suggestion.id] = 'up';
                    }
                  } catch (e) {
                    console.error(`Failed to fetch votes for suggestion ${suggestion.id}:`, e);
                  }
                }
              })
            );
            
            setUserVotesBySuggestion(prev => {
              if (JSON.stringify(prev) !== JSON.stringify(userVotesMap)) {
                return userVotesMap;
              }
              return prev;
            });
          } catch (e) {
            console.error('Failed to refresh user votes:', e);
          }
        }

        // Refresh suggestion ID maps
        const suggResponses = await Promise.all(
          rooms.map(async (room) => {
            try {
              const list = await apiService.getRoomSuggestions(room.id);
              const map = {};
              (list || []).forEach((s) => {
                const key = (s.name || s.title || '').toString().trim().toLowerCase();
                if (key && s.id) map[key] = s.id;
              });
              return [room.id, map];
            } catch (e) {
              return [room.id, {}];
            }
          })
        );
        setSuggestionIdMapByRoom(Object.fromEntries(suggResponses));
      } catch (error) {
        console.error('Error refreshing votes and preferences:', error);
      }
    };

    const initialTimeout = setTimeout(refreshVotesAndPreferences, 1500);
    const interval = setInterval(refreshVotesAndPreferences, 15000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [groupId, rooms.length, userData, drawerOpen, showInlineResults]);

  // Real-time polling for AI consolidation (less frequent to avoid excessive AI calls)
  useEffect(() => {
    if (!groupId || rooms.length === 0) return;
    // Only poll when results are visible (not when drawer is open, to avoid conflicts)
    if (!showInlineResults) {
      return;
    }

    const refreshAIConsolidation = async () => {
      try {
        // Only refresh if results are visible
        if (showInlineResults) {
          await loadConsolidatedResults();
        }
      } catch (error) {
        console.error('Error refreshing AI consolidation:', error);
      }
    };

    // Initial load
    const initialTimeout = setTimeout(refreshAIConsolidation, 2000);
    // Poll every 30 seconds (less frequent than vote polling since AI calls are expensive)
    const interval = setInterval(refreshAIConsolidation, 30000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [groupId, rooms.length, showInlineResults]);

  // Real-time updates for suggestions in the drawer
  useEffect(() => {
    if (!drawerOpen || drawerContent !== 'suggestions' || !drawerRoom || suggestions.length === 0) {
      return;
    }

    const refreshDrawerSuggestions = async () => {
      try {
        // Refresh suggestions for the current room
        const roomSuggestions = await apiService.getRoomSuggestions(drawerRoom.id);
        if (roomSuggestions && Array.isArray(roomSuggestions)) {
          const normalizedSuggestions = normalizeAndValidateSuggestions(roomSuggestions);
          
          // Only update if suggestions changed
          setSuggestions(prevSuggestions => {
            // Compare by IDs to avoid unnecessary updates
            const prevIds = new Set(prevSuggestions.map(s => s.id || s.suggestion?.id));
            const newIds = new Set(normalizedSuggestions.map(s => s.id || s.suggestion?.id));
            
            if (prevIds.size !== newIds.size || ![...prevIds].every(id => newIds.has(id))) {
              return normalizedSuggestions;
            }
            
            // Also check if vote counts changed
            const hasChanges = normalizedSuggestions.some(newS => {
              const prevS = prevSuggestions.find(p => (p.id || p.suggestion?.id) === (newS.id || newS.suggestion?.id));
              if (!prevS) return true;
              
              const newVoteCount = newS.vote_count || newS.suggestion?.vote_count || 0;
              const prevVoteCount = prevS.vote_count || prevS.suggestion?.vote_count || 0;
              return newVoteCount !== prevVoteCount;
            });
            
            if (hasChanges) {
              return normalizedSuggestions;
            }
            
            return prevSuggestions;
          });

          // Refresh user votes for these suggestions
          const userId = apiService.userId || userData?.id || userData?.email;
          if (userId) {
            const userVotesMap = {};
            await Promise.all(
              normalizedSuggestions.map(async (suggestion) => {
                const sid = suggestion.id || suggestion.suggestion?.id;
                if (sid) {
                  try {
                    const votes = await apiService.getSuggestionVotes(sid);
                    const userVote = votes.find(v => v.user_id === userId && v.vote_type === 'up');
                    if (userVote) {
                      userVotesMap[sid] = 'up';
                    }
                  } catch (e) {
                    // Silently fail
                  }
                }
              })
            );
            
            setUserVotesBySuggestion(prev => {
              const updated = { ...prev, ...userVotesMap };
              if (JSON.stringify(prev) !== JSON.stringify(updated)) {
                return updated;
              }
              return prev;
            });

            // Refresh top preferences for all room types
            try {
              const topPrefs = await apiService.getRoomTopPreferences(drawerRoom.id);
              setTopPreferencesByRoom(prev => {
                const updated = { ...prev, [drawerRoom.id]: topPrefs };
                if (JSON.stringify(prev[drawerRoom.id]) !== JSON.stringify(topPrefs)) {
                  return updated;
                }
                return prev;
              });
            } catch (e) {
              // Silently fail
            }
          }
        }
      } catch (error) {
        console.error('Error refreshing drawer suggestions:', error);
      }
    };

    // Initial refresh after 1 second
    const initialTimeout = setTimeout(refreshDrawerSuggestions, 1000);
    
    // Then refresh every 10 seconds
    const interval = setInterval(refreshDrawerSuggestions, 10000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
    };
  }, [drawerOpen, drawerContent, drawerRoom, suggestions.length, userData]);

  // Load consolidated results when inline view opens (manual refresh afterwards)
  useEffect(() => {
    if (showInlineResults) {
      loadConsolidatedResults();
    }
  }, [showInlineResults]);

  // Save all session state to localStorage
  useEffect(() => {
    if (group) {
      localStorage.setItem(`wanderly_group_${groupId}`, JSON.stringify(group));
    }
    if (rooms.length > 0) {
      localStorage.setItem(`wanderly_rooms_${groupId}`, JSON.stringify(rooms));
    }
    if (selectedRoom) {
      localStorage.setItem(`wanderly_selectedRoom_${groupId}`, JSON.stringify(selectedRoom));
    }
    // Save drawer state
    if (drawerOpen) {
      localStorage.setItem(`wanderly_drawerState_${groupId}`, JSON.stringify({
        drawerOpen,
        drawerContent,
        currentRoomType,
        suggestions,
        selectedSuggestions
      }));
    }
  }, [group, rooms, selectedRoom, drawerOpen, drawerContent, currentRoomType, suggestions, selectedSuggestions, groupId]);

  // Load saved data from localStorage on mount (including drawer state)
  useEffect(() => {
    const savedDrawerState = localStorage.getItem(`wanderly_drawerState_${groupId}`);
    if (savedDrawerState) {
      try {
        const drawerState = JSON.parse(savedDrawerState);
        if (drawerState.drawerOpen) {
          setDrawerOpen(true);
          setDrawerContent(drawerState.drawerContent || 'form');
          setCurrentRoomType(drawerState.currentRoomType);
          setSuggestions(drawerState.suggestions || []);
          setSelectedSuggestions(drawerState.selectedSuggestions || []);
        }
      } catch (error) {
        console.error('Error loading saved drawer state:', error);
      }
    }
  }, [groupId]);

  const loadGroupData = async () => {
    try {
      setPageLoading(true);
      
      // Try to load from localStorage first for faster loading
      const savedGroup = localStorage.getItem(`wanderly_group_${groupId}`);
      const savedRooms = localStorage.getItem(`wanderly_rooms_${groupId}`);
      
      if (savedGroup && savedRooms) {
        try {
          setGroup(JSON.parse(savedGroup));
          setRooms(sortRoomsByDesiredOrder(JSON.parse(savedRooms)));
          setPageLoading(false);
        } catch (parseError) {
          console.error('Error parsing saved data:', parseError);
        }
      }
      
      // Always fetch fresh data in background
      const [groupData, roomsData, membersData] = await Promise.all([
        apiService.getGroup(groupId),
        apiService.getGroupRooms(groupId),
        apiService.getGroupMembers(groupId).catch(() => ({ members: [], total_count: 0 }))
      ]);
      
      setGroup(groupData);
      
      // Load group members
      if (membersData && membersData.members) {
        setGroupMembers(membersData.members);
      }
      
      // If total_members is missing, try to fix it
      if (!groupData?.total_members && groupData?.members?.length) {
        try {
          await apiService.updateGroupTotalMembers(groupId, groupData.members.length);
          // Reload group data after update
          const updatedGroupData = await apiService.getGroup(groupId);
          setGroup(updatedGroupData);
        } catch (error) {
          console.error('Failed to update total_members:', error);
        }
      }
      
      // If no rooms exist, create them
      if (roomsData.length === 0) {
        // No rooms found, creating defaults
        try {
          await apiService.createRoomsForGroup(groupId);
          // Reload rooms after creating them
          const newRoomsData = await apiService.getGroupRooms(groupId);
          setRooms(sortRoomsByDesiredOrder(newRoomsData));
        } catch (roomError) {
          console.error('Failed to create rooms:', roomError);
          setRooms([]);
        }
      } else {
        setRooms(sortRoomsByDesiredOrder(roomsData));
      }
    } catch (error) {
      console.error('Error loading group data:', error);
      console.error('Group ID:', groupId);
      console.error('Error details:', error.message || error);
      setError(`Failed to load group data: ${error.message || 'Unknown error'}`);
    } finally {
      setPageLoading(false);
    }
  };

  const handleRoomSelect = (room) => {
    setDrawerRoom(room); 
    setCurrentRoomType(room.room_type);
    setDrawerContent('form');
    setDrawerOpen(true);
    setSuggestions([]);
    setSelectedSuggestions([]);
    setDrawerLoading(false); // Ensure loading is off when opening form
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setCurrentRoomType(null);
    setDrawerRoom(null);
    setDrawerContent('form');
    setSuggestions([]);
    setSelectedSuggestions([]);
    setDrawerLoading(false); // Reset loading state when closing drawer
  };

  const handleFormSubmit = async (formData) => {
    try {
      // Set drawer to suggestions view and show loading screen FIRST
      setDrawerContent('suggestions');
      setDrawerOpen(true);
      setDrawerLoading(true);
      setSuggestions([]); // Clear any old suggestions
      
      // Use the real room ID from drawerRoom instead of 'drawer-room'
      if (!drawerRoom || !drawerRoom.id) {
        console.error('No room selected for suggestions');
        const mockSuggestions = generateMockSuggestions(currentRoomType, formData, group);
        setSuggestions(mockSuggestions);
        setDrawerLoading(false);
        return;
      }
      
      console.log('=== FORM SUBMISSION DEBUG ===');
      console.log('Room:', drawerRoom.room_type, drawerRoom.id);
      console.log('Form data type:', Array.isArray(formData) ? 'array' : typeof formData);
      console.log('Form data:', formData);
      
      // For transportation, ensure we're sending the answers array (not preferences object)
      // The backend expects an array of answer objects with trip_leg/section fields
      let requestPayload = {
        room_id: drawerRoom.id,
        preferences: formData
      };
      
      // If formData is already an array of answers (from PlanningRoom), use it directly
      if (Array.isArray(formData)) {
        console.log('Using form data as answers array:', formData);
        // Log sample answer to verify metadata
        if (formData.length > 0) {
          console.log('Sample answer object:', formData[0]);
          console.log('Has trip_leg:', formData[0].trip_leg || formData[0].leg_type);
          console.log('Has section:', formData[0].section);
          console.log('Has question_key:', formData[0].question_key);
        }
        // Note: Backend fetches answers from Firebase, but we can still pass them for reference
        // The backend will use Firebase answers which should have the metadata
        requestPayload = {
          room_id: drawerRoom.id,
          answers: formData // Send as 'answers' for consistency (backend will still fetch from Firebase)
        };
      }
      
      console.log('Request payload:', requestPayload);
      
      // Generate real AI suggestions using the existing AI service
      const aiSuggestions = await apiService.generateSuggestions(requestPayload);
      
      console.log('AI suggestions received:', aiSuggestions);
      
      // Check if response is an error about missing API keys or temporary API issues
      if (aiSuggestions.error || (aiSuggestions.setup_required === true)) {
        const errorMessage = aiSuggestions.error || 'AI service not configured';
        const errorDetails = aiSuggestions.details || '';
        
        // Handle temporary API issues (503 errors)
        if (aiSuggestions.error_type === 'temporary_api_issue' || errorMessage.includes('temporarily unavailable')) {
          setError(`❌ ${errorMessage}\n\n${errorDetails || 'The Google Gemini API is currently experiencing issues. Please try again in a few moments.'}`);
        } else if (aiSuggestions.setup_required === true) {
          setError(`❌ ${errorMessage}\n\nPlease ensure GEMINI_API_KEY is set in your backend environment variables.\n\nThe system cannot generate real suggestions without proper API configuration.\n\nFor deployment, add GEMINI_API_KEY to your environment variables.`);
        } else {
          setError(`❌ ${errorMessage}\n\n${errorDetails || 'Please try again or check your backend configuration.'}`);
        }
        
        setSuggestions([]);
        setDrawerLoading(false);
        return;
      }
      
      // Normalize API response using utility function (handles different response formats)
      const suggestionsArray = normalizeAndValidateSuggestions(aiSuggestions);
      
      // CRITICAL: Check trip_leg preservation
      console.log('=== CHECKING TRIP_LEG FIELDS ===');
      suggestionsArray.forEach((s, i) => {
        console.log(`Suggestion ${i}:`, {
          name: s.name || s.title,
          trip_leg: s.trip_leg,
          leg_type: s.leg_type
        });
      });
      
      console.log('Processed suggestions array:', suggestionsArray.length, 'suggestions');
      
      if (suggestionsArray.length === 0) {
        console.warn('No valid suggestions received from API');
        setError('No suggestions were generated. Please try again or check your API configuration.');
        setDrawerLoading(false);
        return;
      }
      
      // Update suggestions and stop loading
      setSuggestions(suggestionsArray);
      setDrawerLoading(false);
    } catch (error) {
      console.error('Error generating suggestions:', error);
      console.error('Error details:', error.message, error.stack);
      
      // Check if it's an API configuration error
      const errorMessage = error.message || error.toString() || 'Unknown error';
      
      // Avoid duplicating "Failed to generate suggestions" prefix if it's already in the message
      const hasPrefix = errorMessage.includes('Failed to generate suggestions') || 
                        errorMessage.includes('AI service temporarily unavailable') ||
                        errorMessage.includes('AI service not available');
      
      if (errorMessage.includes('temporarily unavailable') || errorMessage.includes('ServiceUnavailable')) {
        setError(`❌ ${errorMessage}\n\nThe Google Gemini API is currently experiencing issues. Please try again in a few moments.`);
      } else if (errorMessage.includes('AI service not available') || 
          errorMessage.includes('API keys') || 
          errorMessage.includes('GEMINI_API_KEY') ||
          errorMessage.includes('setup_required')) {
        setError(`❌ AI service not configured: ${errorMessage}\n\nPlease ensure GEMINI_API_KEY is set in your backend environment variables.\n\nFor deployment, check your environment variables configuration.`);
      } else if (errorMessage.includes('Load failed') || errorMessage.includes('Failed to fetch')) {
        setError(`❌ Cannot connect to backend server.\n\nPlease ensure your backend server is running and accessible.\n\nError: ${errorMessage}`);
      } else if (hasPrefix) {
        // Error message already has a proper prefix, use it as-is
        setError(`❌ ${errorMessage}`);
      } else {
        setError(`❌ Failed to generate suggestions: ${errorMessage}\n\nPlease try again or check your backend configuration.`);
      }
      
      setSuggestions([]);
      setDrawerLoading(false);
    }
  };

  const generateMockSuggestions = (roomType, formData = {}, group = null) => {
    // Get currency from group or default
    const currency = group?.currency || '₹';
    
    // For transportation, generate based on user's selected transport type
    if (roomType === 'transportation') {
      // Extract transport type from formData (which could be answers object or preferences object)
      let transportType = null;
      
      // Handle case where formData is answers object (from PlanningRoom)
      if (formData && typeof formData === 'object') {
        // Try to find transport type preference
        // First, check if it's already in preferences format (question_text: answer_value)
        const transportTypeKeys = Object.keys(formData).filter(key => {
          const keyStr = String(key).toLowerCase();
          const value = formData[key];
          
          // Check if key contains transport-related words
          if (keyStr.includes('transport') || keyStr.includes('travel') || keyStr.includes('mode')) {
            return true;
          }
          
          // Check if value is an answer object with question_text
          if (value && typeof value === 'object' && value.question_text) {
            const questionText = String(value.question_text).toLowerCase();
            return questionText.includes('transport') || questionText.includes('travel') || questionText.includes('mode');
          }
          
          return false;
        });
        
        if (transportTypeKeys.length > 0) {
          const transportValue = formData[transportTypeKeys[0]];
          
          // Extract value from answer object if needed
          let actualValue = transportValue;
          if (transportValue && typeof transportValue === 'object' && transportValue.answer_value !== undefined) {
            actualValue = transportValue.answer_value;
          } else if (transportValue && typeof transportValue === 'object' && transportValue.question_text) {
            // This is a preferences format (question_text: value)
            actualValue = transportValue;
          }
          
          // Get the actual string value
          if (typeof actualValue === 'string') {
            transportType = actualValue.toLowerCase();
          } else if (Array.isArray(actualValue) && actualValue.length > 0) {
            transportType = String(actualValue[0]).toLowerCase();
          }
        }
      }
      
      // Generate mock suggestions based on selected transport type
      const mockSuggestions = [];
      
      if (!transportType || transportType.includes('bus')) {
        // Bus options
        mockSuggestions.push(
          {
            id: 1,
            name: 'Orange Tours Semi-Sleeper',
            description: 'Comfortable semi-sleeper journey with Orange Tours',
            price: `${currency}642`,
            duration: '8h 23m',
            rating: 4.5,
            type: 'Semi-Sleeper',
            operator: 'Orange Tours',
            times: '23:45 - 07:08',
            inclusions: ['Water Bottle', 'Blanket', 'Sleeper Berth', 'Pillow', 'Reclining Seats', 'Footrest']
          },
          {
            id: 2,
            name: 'Comfort Coach Semi-Sleeper',
            description: 'Semi-sleeper bus with comfortable seating',
            price: `${currency}939`,
            duration: '12h 23m',
            rating: 4.3,
            type: 'Semi-Sleeper',
            operator: 'Comfort Coach',
            times: '08:15 - 20:38',
            inclusions: ['Water Bottle', 'Blanket', 'Sleeper Berth', 'Pillow', 'Reclining Seats', 'Footrest']
          },
          {
            id: 3,
            name: 'Orange Tours Semi-Sleeper',
            description: 'Comfortable semi-sleeper journey with Orange Tours',
            price: `${currency}1,012`,
            duration: '12h 36m',
            rating: 4.5,
            type: 'Semi-Sleeper',
            operator: 'Orange Tours',
            times: '09:30 - 21:06',
            inclusions: ['Water Bottle', 'Blanket', 'Sleeper Berth', 'Pillow', 'Reclining Seats', 'Footrest']
          },
          {
            id: 4,
            name: 'Neeta Travels AC Seater',
            description: 'Comfortable ac seater journey with Neeta Travels',
            price: `${currency}1,246`,
            duration: '8h 47m',
            rating: 3.8,
            type: 'AC Seater',
            operator: 'Neeta Travels',
            times: '10:00 - 18:47',
            inclusions: ['Water Bottle', 'Blanket', 'AC', 'Charging Point']
          }
        );
      }
      
      if (!transportType || transportType.includes('train')) {
        // Train options
        mockSuggestions.push(
          {
            id: 5,
            name: 'Express Train AC',
            description: 'Fast and comfortable AC train service',
            price: `${currency}850`,
            duration: '5h 30m',
            rating: 4.6,
            type: 'Train AC',
            operator: 'Indian Railways',
            times: '08:00 - 13:30',
            inclusions: ['AC', 'Berth', 'Food Service', 'Water']
          }
        );
      }
      
      if (!transportType || transportType.includes('flight') || transportType.includes('plane')) {
        // Flight options
        mockSuggestions.push(
          {
            id: 6,
            name: 'Direct Flight Economy',
            description: 'Non-stop flight to destination',
            price: `${currency}8,500`,
            duration: '2h 30m',
            rating: 4.5,
            type: 'Flight',
            operator: 'Airline',
            times: '10:00 - 12:30',
            inclusions: ['In-flight Meal', 'Entertainment', 'Baggage Allowance']
          }
        );
      }
      
      // If no specific type selected, return all options (limit to 5)
      return mockSuggestions.slice(0, 5);
    }
    
    // For other room types, use default mock data (can be enhanced later)
    const suggestionsByType = {
      'accommodation': [
        { id: 1, name: 'Luxury Resort', description: '5-star beachfront resort', price: `${currency}200/night`, rating: 4.8 },
        { id: 2, name: 'Boutique Hotel', description: 'Charming city center hotel', price: `${currency}120/night`, rating: 4.6 },
        { id: 3, name: 'Eco Lodge', description: 'Sustainable mountain retreat', price: `${currency}80/night`, rating: 4.7 },
        { id: 4, name: 'Business Hotel', description: 'Modern business district hotel', price: `${currency}150/night`, rating: 4.5 },
        { id: 5, name: 'Historic Inn', description: 'Heritage building with character', price: `${currency}90/night`, rating: 4.4 },
        { id: 6, name: 'Budget Hostel', description: 'Affordable shared accommodation', price: `${currency}25/night`, rating: 4.2 }
      ],
      'activities': [
        { id: 1, name: 'City Walking Tour', description: 'Explore historic downtown', price: `${currency}25`, duration: '3h', rating: 4.6 },
        { id: 2, name: 'Museum Visit', description: 'Cultural and art exhibitions', price: `${currency}15`, duration: '2h', rating: 4.4 },
        { id: 3, name: 'Nature Hike', description: 'Scenic mountain trails', price: `${currency}30`, duration: '4h', rating: 4.8 },
        { id: 4, name: 'Food Tour', description: 'Local cuisine tasting', price: `${currency}45`, duration: '2.5h', rating: 4.7 },
        { id: 5, name: 'Boat Cruise', description: 'Relaxing water excursion', price: `${currency}55`, duration: '3h', rating: 4.5 },
        { id: 6, name: 'Adventure Sports', description: 'Thrilling outdoor activities', price: `${currency}80`, duration: '5h', rating: 4.9 }
      ],
      'dining': [
        { id: 1, name: 'Fine Dining Restaurant', description: 'Michelin-starred cuisine', price: `${currency}120/person`, cuisine: 'International', rating: 4.8 },
        { id: 2, name: 'Local Street Food', description: 'Authentic local flavors', price: `${currency}8/person`, cuisine: 'Local', rating: 4.6 },
        { id: 3, name: 'Seafood Speciality', description: 'Fresh catch of the day', price: `${currency}45/person`, cuisine: 'Seafood', rating: 4.7 },
        { id: 4, name: 'Vegetarian Cafe', description: 'Healthy plant-based options', price: `${currency}20/person`, cuisine: 'Vegetarian', rating: 4.5 },
        { id: 5, name: 'Traditional Tavern', description: 'Historic local pub', price: `${currency}25/person`, cuisine: 'Traditional', rating: 4.4 },
        { id: 6, name: 'Rooftop Bar', description: 'Cocktails with city views', price: `${currency}35/person`, cuisine: 'Bar Food', rating: 4.6 }
      ]
    };
    
    return suggestionsByType[roomType] || [];
  };

  const handleSuggestionSelect = (suggestion) => {
    const suggestionId = suggestion.id || suggestions.indexOf(suggestion);
    if (selectedSuggestions.includes(suggestionId)) {
      setSelectedSuggestions(prev => prev.filter(id => id !== suggestionId));
    } else {
      setSelectedSuggestions(prev => [...prev, suggestionId]);
    }
  };

  const handleFinalSubmit = async () => {
    try {
      if (!drawerRoom || selectedSuggestions.length === 0 || isConfirming) return;
      
      setIsConfirming(true);
      
      // Get the actual suggestion objects from the selected IDs
      const selectedSuggestionObjects = selectedSuggestions.map(id => {
        const suggestion = suggestions.find(s => s.id === id || suggestions.indexOf(s) === id);
        if (!suggestion) return null;
        
        // CRITICAL: Preserve trip_leg/leg_type when saving
        return {
          ...suggestion,
          trip_leg: suggestion.trip_leg || suggestion.leg_type || 'departure',
          leg_type: suggestion.leg_type || suggestion.trip_leg || 'departure'
        };
      }).filter(Boolean);
      
      // Close drawer immediately for better UX (optimistic update)
      handleDrawerClose();
      
      // Run API calls in parallel for faster execution
      const [saveResponse, completionResponse] = await Promise.all([
        // 1. Save the selected suggestions to consolidated results
        apiService.saveRoomSelections(drawerRoom.id, selectedSuggestionObjects).catch(err => {
          console.error('Failed to save selections:', err);
          return { success: false, error: err };
        }),
        
        // 2. Mark room as completed by current user
        apiService.markRoomCompleted(drawerRoom.id, userData?.email).catch(err => {
          console.error('Failed to mark room as completed:', err);
          return { success: false, error: err };
        })
      ]);
      
      // Log results (non-blocking)
      if (saveResponse.success) {
        console.log('Selections saved successfully');
      }
      if (completionResponse.success) {
        console.log('Room marked as completed');
      }
      
      // Refresh data in background (non-blocking)
      Promise.all([
        // 3. Refresh group and rooms data to show updated completion count and selections
        apiService.getGroupRooms(groupId).then(updatedRoomsData => {
          setRooms(sortRoomsByDesiredOrder(updatedRoomsData));
        }).catch(err => console.error('Failed to refresh rooms:', err)),
        
        // 4. Always refresh AI-consolidated results when a user completes voting (real-time update)
        loadConsolidatedResults().catch(err => {
          console.error('Failed to refresh consolidated results:', err);
        })
      ]).catch(err => console.error('Error refreshing data:', err));
      
      setIsConfirming(false);
      
    } catch (error) {
      console.error('Error in final submit:', error);
      setIsConfirming(false);
      // Only show alert if drawer is still open (if user hasn't seen the drawer close)
      if (drawerOpen) {
        alert('Failed to confirm selections. Please try again.');
      }
    }
  };

  const handleBackToDashboard = () => {
    setSelectedRoom(null);
    setShowResults(false);
    loadGroupData(); // Refresh data
  };

  const loadConsolidatedResults = async () => {
    try {
      // Don't set drawerLoading here - it blocks the form
      // Only set loading state for inline results if needed
      
      // First, call AI consolidation endpoint to get smart recommendations
      try {
        const response = await fetch(`/api/groups/${groupId}/consolidate-preferences`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          const aiConsolidated = await response.json();
          console.log('AI Consolidated Preferences:', aiConsolidated);
          
          // Store AI consolidation data
          setConsolidatedResults({
            ...aiConsolidated,
            ai_analyzed: true,
            common_preferences: aiConsolidated.common_preferences,
            recommendation: aiConsolidated.recommendation
          });
        } else {
          console.log('AI consolidation not available, using standard results');
          const results = await apiService.getGroupConsolidatedResults(groupId);
          setConsolidatedResults(results.room_results || {});
        }
      } catch (aiError) {
        console.log('AI consolidation failed, using standard results:', aiError);
        const results = await apiService.getGroupConsolidatedResults(groupId);
        setConsolidatedResults(results.room_results || {});
      }
      
      // Refresh rooms data to get latest selections
      const updatedRoomsData = await apiService.getGroupRooms(groupId);
      setRooms(updatedRoomsData);

      // Build suggestionId maps (by normalized name/title) for each room
      try {
        const suggResponses = await Promise.all(
          (updatedRoomsData || []).map(async (room) => {
            try {
              const list = await apiService.getRoomSuggestions(room.id);
              const map = {};
              (list || []).forEach((s) => {
                const key = (s.name || s.title || '').toString().trim().toLowerCase();
                if (key && s.id) map[key] = s.id;
              });
              return [room.id, map];
            } catch (e) {
              return [room.id, {}];
            }
          })
        );
        setSuggestionIdMapByRoom(Object.fromEntries(suggResponses));
      } catch (e) {
        console.error('Failed to load room suggestions for id mapping:', e);
      }

      // Fetch top preferences for each room in parallel
      try {
        const prefsResponses = await Promise.all(
          (updatedRoomsData || []).map(async (room) => {
            try {
              const res = await apiService.getRoomTopPreferences(room.id);
              console.log(`Top preferences for room ${room.id}:`, res);
              console.log(`Counts by suggestion for room ${room.id}:`, res.counts_by_suggestion);
              return [room.id, res];
            } catch (e) {
              console.error(`Failed to load top preferences for room ${room.id}:`, e);
              return [room.id, { top_preferences: [], counts_by_suggestion: {} }];
            }
          })
        );
        const prefsMap = Object.fromEntries(prefsResponses);
        console.log('All top preferences map:', prefsMap);
        setTopPreferencesByRoom(prefsMap);
      } catch (e) {
        console.error('Failed to load top preferences:', e);
      }
      
      // Load user votes for all suggestions
      const userId = apiService.userId || userData?.id || userData?.email;
      if (userId) {
        try {
          const userVotesMap = {};
          // Get all suggestions from all rooms
          const allSuggestions = [];
          for (const room of updatedRoomsData) {
            try {
              const roomSuggestions = await apiService.getRoomSuggestions(room.id);
              if (roomSuggestions && Array.isArray(roomSuggestions)) {
                allSuggestions.push(...roomSuggestions);
              }
            } catch (e) {
              console.error(`Failed to load suggestions for room ${room.id}:`, e);
            }
          }
          
          // Check user votes for each suggestion
          await Promise.all(
            allSuggestions.map(async (suggestion) => {
              if (suggestion.id) {
                try {
                  const votes = await apiService.getSuggestionVotes(suggestion.id);
                  const userVote = votes.find(v => v.user_id === userId && v.vote_type === 'up');
                  if (userVote) {
                    userVotesMap[suggestion.id] = 'up';
                  }
                } catch (e) {
                  // Silently fail - just means we can't check this vote
                }
              }
            })
          );
          
          setUserVotesBySuggestion(userVotesMap);
        } catch (e) {
          console.error('Failed to load user votes:', e);
        }
      }
      
      // Also load room selections directly from rooms for itinerary
      const roomSelections = {};
      for (const room of updatedRoomsData) {
        try {
          const roomData = await apiService.getRoom(room.id);
          if (roomData && roomData.user_selections) {
            roomSelections[room.id] = {
              selections: roomData.user_selections,
              completed: roomData.completed_by || []
            };
          }
        } catch (e) {
          console.error(`Error loading selections for room ${room.id}:`, e);
        }
      }
      console.log('Room selections:', roomSelections);
    } catch (error) {
      console.error('Error loading consolidated results:', error);
    }
    // Removed finally block that was setting drawerLoading to false
  };

  const getRoomTitle = (roomType) => {
    switch (roomType) {
      case 'accommodation': return 'Accommodation';
      case 'transportation': return 'Transportation';
      case 'activities': return 'Activities';
      case 'dining': return 'Dining';
      default: return 'Plan';
    }
  };

  const getRoomIcon = (roomType) => {
    switch (roomType) {
      case 'accommodation': return '🏨';
      case 'transportation': return '✈️';
      case 'activities': return '📅';
      case 'dining': return '🍽️';
      default: return '📋';
    }
  };

  const renderSuggestionCard = (suggestionData) => {
    const suggestion = suggestionData.suggestion;
    
    return (
      <div key={suggestion.id} className="suggestion-card">
        <div className="suggestion-header">
          <h5 className="suggestion-title">{suggestion.title || suggestion.name}</h5>
          <div className="suggestion-rating">⭐ {suggestion.rating || '4.5'}</div>
        </div>
        
        <p className="suggestion-description">{suggestion.description}</p>
        
        {suggestion.highlights && suggestion.highlights.length > 0 && (
          <div className="suggestion-highlights">
            {suggestion.highlights.map((highlight, index) => (
              <span key={index} className="highlight-tag">
                {highlight}
              </span>
            ))}
          </div>
        )}
        
        {suggestion.external_url && (
          <div className="suggestion-actions">
            <a 
              href={suggestion.external_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="explore-button"
            >
              🔗 Explore More
            </a>
          </div>
        )}
      </div>
    );
  };

  const renderResultItemCard = (
    item,
    idx,
    room,
    countsMap,
    idMap,
    hasAIConsolidation
  ) => {
    const displayName = (item.name || item.title || item.airline || item.operator || item.train_name || 'Selection').toString();
    const whySelected = item.why_selected || item.conflict_resolution || null;
    const matchesPrefs = item.matches_preferences || [];

    let sid = idMap[displayName.trim().toLowerCase()];
    if (!sid) {
      sid = item.id || item.suggestion_id;
    }
    if (!sid) {
      console.warn('No suggestion ID found for:', displayName, 'item:', item);
    }

    const likeCount = sid ? (countsMap[sid] || 0) : 0;
    const userId = apiService.userId || userData?.id || userData?.email;
    const userVote = userId && sid ? (userVotesBySuggestion[sid] || null) : null;
    const isUserLiked = userVote === 'up';

    const handleLike = async (e) => {
      e.preventDefault();
      e.stopPropagation();

      if (!userId) {
        alert('Please join or create a group first to like suggestions.');
        return;
      }

      if (!sid) {
        console.error('Cannot vote: missing suggestion ID for:', displayName);
        alert(`Cannot vote: Unable to find suggestion ID for "${displayName}".`);
        return;
      }

      const newVoteType = isUserLiked ? 'down' : 'up';
      const countChange = isUserLiked ? -1 : 1;

      setUserVotesBySuggestion(prev => ({
        ...prev,
        [sid]: newVoteType === 'up' ? 'up' : null
      }));

      if (sid) {
        const currentCount = countsMap[sid] || 0;
        const newCount = Math.max(0, currentCount + countChange);

        setTopPreferencesByRoom(prev => {
          const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
          const newCountsMap = { ...roomPrefs.counts_by_suggestion, [sid]: newCount };
          const updatedTopPrefs = [...(roomPrefs.top_preferences || [])];
          const prefIndex = updatedTopPrefs.findIndex(p => p.suggestion_id === sid);
          if (prefIndex >= 0) {
            updatedTopPrefs[prefIndex] = { ...updatedTopPrefs[prefIndex], count: newCount };
          } else {
            updatedTopPrefs.push({
              suggestion_id: sid,
              name: displayName,
              count: newCount
            });
          }
          updatedTopPrefs.sort((a, b) => b.count - a.count);

          return {
            ...prev,
            [room.id]: {
              ...roomPrefs,
              counts_by_suggestion: newCountsMap,
              top_preferences: updatedTopPrefs
            }
          };
        });
      }

      try {
        await apiService.submitVote({
          suggestion_id: sid,
          user_id: userId,
          vote_type: newVoteType
        });
      } catch (voteErr) {
        console.error('Failed to submit vote:', voteErr);
        alert('Failed to submit vote. Please try again.');
      } finally {
        await refreshVotesAndPreferences();
      }
    };

    return (
      <div
        key={`${room.id}-${sid || idx}-${displayName}`}
        className={`suggestion-card ${isUserLiked ? 'liked' : ''}`}
      >
        <div className="suggestion-card-header">
          <div>
            <h5>{displayName}</h5>
            {item.operator && item.operator !== displayName && (
              <p className="suggestion-subtitle">{item.operator}</p>
            )}
            {item.destination && (
              <p className="suggestion-subtitle">{item.destination}</p>
            )}
          </div>
          <button
            className={`like-button ${isUserLiked ? 'active' : ''}`}
            onClick={handleLike}
            title={isUserLiked ? 'Remove like' : 'Like this option'}
          >
            ❤️ <span>{likeCount}</span>
          </button>
        </div>

        {item.description && <p className="suggestion-description">{item.description}</p>}
        {item.summary && <p className="suggestion-summary">{item.summary}</p>}

        <div className="suggestion-meta-grid">
          {item.price && (
            <div className="suggestion-meta-item">
              <label>Price</label>
              <span>{item.price}</span>
            </div>
          )}
          {item.duration && (
            <div className="suggestion-meta-item">
              <label>Duration</label>
              <span>{item.duration}</span>
            </div>
          )}
          {item.departure_time && (
            <div className="suggestion-meta-item">
              <label>Departure</label>
              <span>{item.departure_time}</span>
            </div>
          )}
          {item.arrival_time && (
            <div className="suggestion-meta-item">
              <label>Arrival</label>
              <span>{item.arrival_time}</span>
            </div>
          )}
          {item.start_time && (
            <div className="suggestion-meta-item">
              <label>Start</label>
              <span>{item.start_time}</span>
            </div>
          )}
          {item.end_time && (
            <div className="suggestion-meta-item">
              <label>End</label>
              <span>{item.end_time}</span>
            </div>
          )}
          {item.rating && (
            <div className="suggestion-meta-item">
              <label>Rating</label>
              <span>{item.rating}</span>
            </div>
          )}
        </div>

        {matchesPrefs.length > 0 && (
          <div className="matches-preferences">
            <strong>Matches:</strong> {matchesPrefs.join(', ')}
          </div>
        )}

        {whySelected && (
          <div className="why-selected">
            <strong>{hasAIConsolidation ? 'AI Reasoning' : 'Why selected'}:</strong> {whySelected}
          </div>
        )}

        {(item.trip_leg || item.leg_type) && (
          <div className="trip-leg-badge">
            {(item.trip_leg || item.leg_type) === 'return' ? 'Return leg' : 'Departure leg'}
          </div>
        )}
      </div>
    );
  };

  const handleShowResults = async () => {
    if (!showInlineResults) {
      await loadConsolidatedResults();
    } else {
      // Always refresh results when showing to get latest votes
      await loadConsolidatedResults();
    }
    setShowInlineResults(!showInlineResults);
  };

  // Maps popup handlers
  const handleOpenMaps = (suggestion) => {
    const mapUrl = suggestion.maps_embed_url || suggestion.maps_url || suggestion.external_url;
    if (mapUrl) {
      setSelectedMapUrl(mapUrl);
      setSelectedSuggestion(suggestion);
      setMapsModalOpen(true);
    }
  };

  const handleCloseMaps = () => {
    setMapsModalOpen(false);
    setSelectedMapUrl('');
    setSelectedSuggestion(null);
  };
  
  // Booking popup functions
  const handleOpenBooking = (suggestion, roomType) => {
    setBookingData({
      suggestion,
      roomType,
      groupId,
      group
    });
    setBookingModalOpen(true);
  };
  
  const handleCloseBooking = () => {
    setBookingModalOpen(false);
    setBookingData(null);
    setBookingStep(1);
    setBookingForm({
      title: '',
      firstName: '',
      lastName: '',
      email: '',
      phone: '',
      contactEmail: '',
      contactPhone: ''
    });
    setTermsAccepted(false);
  };
  
  const handleSubmitBooking = () => {
    // Validate form
    if (!bookingForm.title || !bookingForm.firstName || !bookingForm.lastName || 
        !bookingForm.contactEmail || !bookingForm.contactPhone || !termsAccepted) {
      alert('Please fill in all required fields and accept the terms.');
      return;
    }
    
    // Move to confirmation step
    setBookingStep(2);
  };
  
  const handleConfirmBooking = async () => {
    // Simulate booking success
    const bookingId = `BOOK${Date.now()}`;
    
    alert(`Booking confirmed successfully!\n\nBooking ID: ${bookingId}\nYou will receive a confirmation email shortly.`);
    handleCloseBooking();
  };
  
  const handleBookNow = () => {
    // Open booking modal directly
    // No API call yet - user will fill form and confirm
  };
  
  // Generate itinerary function
  const generateItinerary = () => {
    if (!group || !group.start_date || !group.end_date) {
      return <p>Please enter trip dates to generate itinerary</p>;
    }
    
    // Calculate number of days
    const startDate = new Date(group.start_date);
    const endDate = new Date(group.end_date);
    const diffTime = Math.abs(endDate - startDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1; // +1 to include both start and end days
    
    // Build sources for each room type using all selections (top + user picks)
    const roomTypeOptions = {};
    rooms.forEach((room) => {
      const topPrefs = topPreferencesByRoom[room.id]?.top_preferences || [];
      const mappedSelections = deduplicateSelections(room.user_selections || []).map(sel => mapSelectionToOption(sel));
      const combined = [...topPrefs, ...mappedSelections];
      const deduped = deduplicateOptions(combined);
      if (deduped.length > 0) {
        roomTypeOptions[room.room_type] = deduped;
      }
    });
    
    // If nothing to plan
    if (Object.keys(roomTypeOptions).length === 0) {
      return <p>Make selections to see your itinerary</p>;
    }
    
    const activitiesPool = shuffleArray(roomTypeOptions['activities'] || []);
    const diningPool = shuffleArray(roomTypeOptions['dining'] || []);
    const travelPool = roomTypeOptions['transportation'] || [];
    const stayPool = roomTypeOptions['accommodation'] || [];

    const getOptionForDay = (pool, dayIndex, offset = 0) => {
      if (!pool || pool.length === 0) return null;
      const index = (dayIndex + offset) % pool.length;
      return pool[index];
    };
    
    // Generate day-by-day itinerary
    const itinerary = [];
    for (let day = 1; day <= diffDays; day++) {
      const currentDate = new Date(startDate);
      currentDate.setDate(startDate.getDate() + (day - 1));
      
      const dateStr = currentDate.toLocaleDateString('en-US', { 
        weekday: 'short', 
        month: 'short', 
        day: 'numeric' 
      });
      
      itinerary.push(
        <div key={day} style={{ 
          border: '1px solid #e0e0e0', 
          borderRadius: '8px', 
          marginBottom: '1rem', 
          padding: '1.5rem',
          backgroundColor: '#f9f9f9'
        }}>
          <h4 style={{ marginTop: 0, color: '#2c3e50' }}>
            Day {day} - {dateStr}
          </h4>
          
          {/* Show transportation if available */}
          {travelPool.length > 0 && day === 1 && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: 'white', borderRadius: '6px' }}>
              <strong style={{ color: '#27ae60' }}>Travel:</strong> {travelPool[0]?.name || 'Transportation booked'}
            </div>
          )}
          
          {/* Show accommodation if available */}
          {stayPool.length > 0 && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: 'white', borderRadius: '6px' }}>
              <strong style={{ color: '#3498db' }}>Stay:</strong> {stayPool[0]?.name || 'Accommodation booked'}
            </div>
          )}
          
          {/* Show activities if available */}
          {activitiesPool.length > 0 && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: 'white', borderRadius: '6px' }}>
              <strong style={{ color: '#9b59b6' }}>Activities:</strong>
              <ul style={{ margin: '0.5rem 0 0 1.5rem', padding: 0 }}>
                {(() => {
                  const picks = [];
                  const first = getOptionForDay(activitiesPool, (day - 1) * 2);
                  const second = getOptionForDay(activitiesPool, (day - 1) * 2 + 1);
                  [first, second].forEach((activity) => {
                    if (
                      activity &&
                      !picks.some(
                        (existing) =>
                          existing?.suggestion_id === activity?.suggestion_id ||
                          existing?.name === activity?.name
                      )
                    ) {
                      picks.push(activity);
                    }
                  });
                  return picks.map((p, idx) => (
                  <li key={idx} style={{ marginBottom: '0.25rem' }}>
                      {p.name}
                  </li>
                  ));
                })()}
              </ul>
            </div>
          )}
          
          {/* Show dining if available */}
          {diningPool.length > 0 && (
            <div style={{ padding: '0.75rem', backgroundColor: 'white', borderRadius: '6px' }}>
              <strong style={{ color: '#e67e22' }}>Dining:</strong>
              <ul style={{ margin: '0.5rem 0 0 1.5rem', padding: 0 }}>
                {(() => {
                  const pick = getOptionForDay(diningPool, day - 1);
                  return pick ? (
                    <li style={{ marginBottom: '0.25rem' }}>{pick.name}</li>
                  ) : null;
                })()}
              </ul>
            </div>
          )}
        </div>
      );
    }
    
    return (
      <div>
        <p style={{ marginBottom: '1.5rem', color: '#666' }}>
          Your {diffDays}-day trip to {group.destination}
        </p>
        {itinerary}
      </div>
    );
  };

  if (pageLoading && !group) {
    return (
      <div className="dashboard-container">
        <div className="loading">Loading group data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <div className="error">{error}</div>
        <button onClick={onBack} className="btn btn-secondary">Back to Home</button>
      </div>
    );
  }

  if (showResults) {
    return (
      <div className="dashboard-container">
        <ResultsDashboard 
          groupId={groupId}
          onBack={handleBackToDashboard}
        />
      </div>
    );
  }

  if (selectedRoom) {
    return (
      <div className="dashboard-container">
        <PlanningRoom 
          room={selectedRoom} 
          group={group}
          userData={userData}
          onBack={handleBackToDashboard}
        />
      </div>
    );
  }

  return (
    <div className="dashboard-layout">
      {/* Main Dashboard */}
      <div className={`dashboard-main ${drawerOpen ? 'drawer-open' : ''}`}>
    <div className="dashboard-container">
          {/* Group Info Row */}
          <div className="form-row">
            <div className="form-section-full">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                {/* Left plane image button aligned middle (always visible) */}
                <img
                  src={planePng}
                  alt="Go Home"
                  onClick={onBack}
                  style={{
                    height: '120px',
                    width: '120px',
                    objectFit: 'contain',
                    cursor: 'pointer',
                    marginRight: 'auto',
                    alignSelf: 'center',
                    marginTop: '2.5rem'
                  }}
                />
                
                {/* Centered Trip Details (nudged slightly right) */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', marginLeft: '3rem' }}>
          <h1 className="group-title">{group.name}</h1>
        <p className="group-destination">{group.destination}</p>
        <p className="group-dates">
          {new Date(group.start_date).toLocaleDateString()} - {new Date(group.end_date).toLocaleDateString()}
        </p>
        <div className="invite-code">
          <span className="invite-label">Invite Code:</span>
          <span className="invite-value">{group.id}</span>
        </div>
      </div>

                {/* Edit Group Button - Right */}
                <div style={{ marginRight: '13%', alignSelf: 'center', marginTop: '1rem' }}>
                <button 
                  onClick={() => setIsEditingGroup(true)}
                  className="btn btn-secondary"
                  style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem' }}
                >
                  Edit Details
                </button>
                </div>
              </div>
        </div>
      </div>

          {/* Plan Your Trip Section */}
          <div className="form-row">
            <div className="form-section-full">
        <h2 className="rooms-title">Plan Your Trip</h2>
        <div className="rooms-container">
          {rooms.map((room) => (
            <div 
              key={room.id} 
              className={`room-card room-${room.room_type} ${room.status}`}
              onClick={() => handleRoomSelect(room)}
            >
              <div className="room-icon">
                {room.room_type === 'accommodation' && <img src={hotelIcon} alt="Hotel" />}
                {room.room_type === 'transportation' && <img src={planeIcon} alt="Travel" />}
                {room.room_type === 'activities' && <img src={calendarIcon} alt="Calendar" />}
                {room.room_type === 'dining' && <img src={utensilsIcon} alt="Utensils" />}
              </div>
              <h3 className="room-title">
                {room.room_type === 'accommodation' && 'Stay'}
                {room.room_type === 'transportation' && 'Travel'}
                {room.room_type === 'dining' && 'Dining'}
                {room.room_type === 'activities' && 'Activities'}
              </h3>
              <p className="room-description">
                {room.room_type === 'accommodation' && 'Find the perfect accommodation'}
                {room.room_type === 'transportation' && 'Book your transportation'}
                {room.room_type === 'activities' && 'Plan activities and attractions'}
                {room.room_type === 'dining' && 'Discover local cuisine'}
              </p>
              <div className="room-status">
                {room.status === 'active' && 'Ready to plan'}
                {room.status === 'locked' && 'Decision made'}
                {room.status === 'completed' && 'Completed'}
                {!room.status && 'Ready to plan'}
              </div>
              <div className="room-completion">
                {room.completed_by ? `${room.completed_by.length}/${group?.total_members || group?.members?.length || 2} completed` : `0/${group?.total_members || group?.members?.length || 2} completed`}
              </div>
            </div>
          ))}
              </div>
        </div>
      </div>

          {/* Group Members Section */}
          <div className="form-row" style={{ overflow: 'hidden', width: '100%', boxSizing: 'border-box' }}>
            <div className="form-section-full" style={{ width: '100%', maxWidth: '100%', overflow: 'hidden', boxSizing: 'border-box' }}>
              <div style={{
                backgroundImage: `url(${createBg})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
                borderRadius: '12px',
                padding: '1.5rem',
                marginBottom: '1.5rem',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                overflow: 'hidden',
                position: 'relative',
                width: '100%',
                maxWidth: '100%',
                boxSizing: 'border-box'
              }}>
                <h3 style={{
                  color: 'white',
                  marginTop: 0,
                  marginBottom: '1rem',
                  fontSize: '1.25rem',
                  fontWeight: '600',
                  textShadow: '0 2px 4px rgba(0, 0, 0, 0.3)',
                  wordBreak: 'break-word'
                }}>
                  👥 Group Members ({groupMembers.length || 0})
                </h3>
                {groupMembers.length > 0 ? (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: '0.75rem',
                    overflow: 'hidden',
                    width: '100%',
                    maxWidth: '100%',
                    boxSizing: 'border-box'
                  }}>
                    {groupMembers.map((member) => (
                      <div
                        key={member.id}
                        style={{
                          background: 'rgba(255, 255, 255, 0.95)',
                          borderRadius: '6px',
                          padding: '0.75rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.25rem',
                          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                          minWidth: 0,
                          maxWidth: '100%',
                          width: '100%',
                          boxSizing: 'border-box',
                          overflow: 'hidden',
                          flexShrink: 1
                        }}
                      >
                        <div style={{
                          fontWeight: '600',
                          color: '#333',
                          fontSize: '0.875rem',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          wordBreak: 'break-word',
                          lineHeight: '1.2'
                        }}>
                          {member.name}
                        </div>
                        <div style={{
                          color: '#666',
                          fontSize: '0.75rem',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          wordBreak: 'break-word',
                          lineHeight: '1.2'
                        }}>
                          {member.email}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{
                    color: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '0.9rem',
                    textShadow: '0 1px 2px rgba(0, 0, 0, 0.3)'
                  }}>
                    No members yet. Share the invite code to add members!
                  </div>
                )}
              </div>
        </div>
      </div>

          {/* Action Buttons Row */}
          <div className="form-row">
            <div className="form-section-full">
      <div className="dashboard-actions">
        <button onClick={handleShowResults} className="btn btn-primary">
                  {showInlineResults ? 'HIDE RESULTS' : 'VIEW RESULTS'}
        </button>
              </div>
            </div>
          </div>
          
          {/* Inline Consolidated Results */}
          {showInlineResults && (
            <div className="results-container">
                <div className="results-content">
                  <div className="results-header">
                    <h4>Live Voting Results</h4>
                    <p>Current consensus for {group?.name}</p>
                    <button 
                      onClick={() => loadConsolidatedResults()}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '0.5rem 1rem' }}
                    >
                      Refresh Results
                    </button>
                    {consolidatedResults.ai_analyzed ? (
                      <div style={{ 
                        marginTop: '1rem', 
                        padding: '1rem', 
                        backgroundColor: 'rgba(76, 175, 80, 0.1)', 
                        border: '2px solid #4caf50',
                        borderRadius: '8px',
                        fontSize: '0.9rem'
                      }}>
                        <strong>AI Analysis Active:</strong> Showing only common preferences across all members
                        {consolidatedResults.recommendation && (
                          <p style={{ marginTop: '0.5rem', marginBottom: 0 }}>
                            {consolidatedResults.recommendation}
                          </p>
                        )}
                      </div>
                    ) : (
                      <div style={{ 
                        marginTop: '1rem', 
                        padding: '1rem', 
                        backgroundColor: 'rgba(255, 152, 0, 0.1)', 
                        border: '2px solid #ff9800',
                        borderRadius: '8px',
                        fontSize: '0.9rem'
                      }}>
                        <strong>Analyzing...</strong> AI consolidation will activate once multiple members complete voting
                      </div>
                    )}
                  </div>
                  
                  {rooms.length === 0 ? (
                    <div className="no-results">
                      <p>Loading rooms...</p>
                    </div>
                  ) : (
                    <div className="results-sections">
                      {rooms.map((room) => {
                        const completedCount = room.completed_by?.length || 0;
                        const countsMap = topPreferencesByRoom[room.id]?.counts_by_suggestion || {};
                        const idMap = suggestionIdMapByRoom[room.id] || {};
                        
                        // Check if we have AI-consolidated preferences
                        const hasAIConsolidation = consolidatedResults?.ai_analyzed && 
                                                  consolidatedResults?.consolidated_selections;
                        
                        // Use AI-consolidated selections if available, otherwise fall back to raw selections
                        let displayItems = [];
                        
                        if (hasAIConsolidation) {
                          // Get AI-selected common preferences for this room type
                          const aiSelections = consolidatedResults.consolidated_selections[room.room_type] || [];
                          
                          console.log(`Using AI-consolidated selections for ${room.room_type}:`, aiSelections);
                          
                          // AI already filtered to common preferences, use those
                          displayItems = aiSelections.map(aiSelection => ({
                            ...aiSelection,
                            // Ensure we preserve AI reasoning
                            ai_selected: true,
                            why_selected: aiSelection.why_selected || aiSelection.conflict_resolution,
                            matches_preferences: aiSelection.matches_preferences || []
                          }));
                        } else {
                          // Fallback: No AI analysis yet - show raw selections
                          console.warn(`No AI consolidation for ${room.room_type}, showing raw selections`);
                          
                          const rawSelections = room.user_selections || [];
                          const selections = deduplicateSelections(rawSelections);
                          
                          // Enrich selections with full suggestion data
                          const fullSuggestions = fullSuggestionsByRoom[room.id] || [];
                          displayItems = selections.map(selection => {
                            // Try to find full suggestion data by ID first
                          let fullData = fullSuggestions.find(s => 
                            s.id === selection.id || 
                            s.id === selection.suggestion_id ||
                            s.suggestion_id === selection.id ||
                            s.suggestion_id === selection.suggestion_id
                          );
                          
                          // If not found by ID, try to match by name
                          if (!fullData) {
                            const selectionName = (selection.name || selection.title || selection.airline || selection.operator || selection.train_name || '').toString().trim().toLowerCase();
                            fullData = fullSuggestions.find(s => {
                              const sName = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                              return sName === selectionName && sName !== '';
                            });
                          }
                          
                          // CRITICAL: Preserve trip_leg/leg_type from original selection
                          // Priority: selection > fullData > default to departure
                          const preservedTripLeg = selection.trip_leg || selection.leg_type || fullData?.trip_leg || fullData?.leg_type;
                          const preservedLegType = selection.leg_type || selection.trip_leg || fullData?.leg_type || fullData?.trip_leg;
                          
                          // Merge full data with selection data, but preserve trip_leg/leg_type from selection
                          return fullData ? { 
                            ...selection,  // Keep original selection data first (includes trip_leg)
                            ...fullData,   // Merge with full data
                            // Ensure trip_leg/leg_type are preserved from selection
                            trip_leg: preservedTripLeg || 'departure',
                            leg_type: preservedLegType || preservedTripLeg || 'departure'
                          } : {
                            ...selection,
                            // Ensure trip_leg/leg_type are set even if not in selection
                            trip_leg: preservedTripLeg || 'departure',
                            leg_type: preservedLegType || preservedTripLeg || 'departure'
                          };
                          });
                        }
                        
                        // For transportation, always render two-column layout
                        if (isTransportation) {
                          // Separate into departure and return
                          // Items without trip_leg/leg_type default to departure (for one-way trips)
                          const departureItems = displayItems.filter(item => {
                            const leg = item.trip_leg || item.leg_type;
                            return leg === 'departure' || !leg; // Default to departure if not specified
                          });
                          const returnItems = displayItems.filter(item => {
                            const leg = item.trip_leg || item.leg_type;
                            return leg === 'return';
                          });
                          
                          console.log('Transportation - Departure items:', departureItems.length, 'Return items:', returnItems.length);
                          
                          // Always render transportation with two sections
                        return (
                          <div key={room.id} className="room-results-section">
                            <div className="room-results-header">
                              <span className="room-icon">{getRoomIcon(room.room_type)}</span>
                              <h5 className="room-title">{getRoomTitle(room.room_type)}</h5>
                              <div className="room-status">
                                {completedCount}/{group?.total_members || 2} completed
                              </div>
                            </div>
                            
                            {/* Show AI analysis indicator */}
                            {hasAIConsolidation && (
                              <div style={{
                                background: '#e3f2fd',
                                padding: '0.75rem',
                                borderRadius: '6px',
                                marginBottom: '1rem',
                                fontSize: '0.9rem',
                                color: '#1565c0'
                              }}>
                                <strong>AI Analysis:</strong> Showing {displayItems.length} options that match most members' preferences
                                {consolidatedResults.recommendation && (
                                  <p style={{ marginTop: '0.5rem', marginBottom: 0 }}>
                                    {consolidatedResults.recommendation}
                                  </p>
                                )}
                              </div>
                            )}
                            
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1.5rem', marginTop: '1rem' }}>
                                  {/* Departure Section */}
                                  <div>
                                    <h6 style={{ marginBottom: '1rem', color: '#3498db' }}>Departure Travel</h6>
                                    {departureItems.length > 0 ? (
                                      <div className="suggestions-grid">
                                        {departureItems.map((item, idx) => {
                                          const displayName = (item.name || item.title || item.airline || item.operator || item.train_name || 'Selection').toString();
                                          const whySelected = item.why_selected || item.conflict_resolution || null;
                                          const matchesPrefs = item.matches_preferences || [];
                                          
                                          let sid = idMap[displayName.trim().toLowerCase()] || item.id || item.suggestion_id;
                                          const likeCount = sid ? (countsMap[sid] || 0) : 0;
                                          const userId = apiService.userId || userData?.id || userData?.email;
                                          const userVote = userId && sid ? (userVotesBySuggestion[sid] || null) : null;
                                          const isLiked = userVote === 'up';
                                          
                                          // HandleLike function for transportation - same as accommodation
                                          const handleLike = async (e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            
                                            if (!userId) {
                                              alert('Please join or create a group first to like suggestions.');
                                              return;
                                            }
                                            
                                            if (!sid) {
                                              console.error('Cannot vote: missing suggestion ID for:', displayName);
                                              alert(`Cannot vote: Unable to find suggestion ID for "${displayName}".`);
                                              return;
                                            }
                                            
                                            // Toggle: if already liked, unlike; otherwise, like
                                            const newVoteType = isLiked ? 'down' : 'up';
                                            const countChange = isLiked ? -1 : 1;
                                            
                                            // OPTIMISTIC UPDATE: Update UI immediately before API call
                                            setUserVotesBySuggestion(prev => ({
                                              ...prev,
                                              [sid]: newVoteType === 'up' ? 'up' : null
                                            }));
                                            
                                            // Update counts map immediately
                                            if (sid) {
                                              const currentCount = countsMap[sid] || 0;
                                              const newCount = Math.max(0, currentCount + countChange);
                                              
                                              setTopPreferencesByRoom(prev => {
                                                const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                                const newCountsMap = { ...roomPrefs.counts_by_suggestion, [sid]: newCount };
                                                
                                                // Update top preferences list with new count
                                                const updatedTopPrefs = [...(roomPrefs.top_preferences || [])];
                                                const prefIndex = updatedTopPrefs.findIndex(p => p.suggestion_id === sid);
                                                if (prefIndex >= 0) {
                                                  updatedTopPrefs[prefIndex] = { ...updatedTopPrefs[prefIndex], count: newCount };
                                                } else {
                                                  updatedTopPrefs.push({
                                                    suggestion_id: sid,
                                                    name: displayName,
                                                    count: newCount
                                                  });
                                                }
                                                updatedTopPrefs.sort((a, b) => b.count - a.count);
                                                
                                                return {
                                                  ...prev,
                                                  [room.id]: {
                                                    ...roomPrefs,
                                                    top_preferences: updatedTopPrefs,
                                                    counts_by_suggestion: newCountsMap
                                                  }
                                                };
                                              });
                                            }
                                            
                                            try {
                                              // Try to get the correct suggestion ID from the suggestions collection
                                              let voteSuggestionId = sid;
                                              
                                              try {
                                                const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                                                const found = roomSuggestions?.find(s => {
                                                  const sName = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                                                  const dName = displayName.trim().toLowerCase();
                                                  return sName === dName;
                                                });
                                                
                                                if (found && found.id) {
                                                  voteSuggestionId = found.id;
                                                }
                                              } catch (fetchErr) {
                                                console.error('Failed to fetch room suggestions for ID lookup:', fetchErr);
                                              }
                                              
                                              await apiService.submitVote({
                                                suggestion_id: voteSuggestionId,
                                                user_id: userId,
                                                vote_type: newVoteType
                                              });
                                              
                                              // Refresh top preferences after a short delay (non-blocking to prevent glitch)
                                              setTimeout(async () => {
                                                try {
                                                  const topPrefs = await apiService.getRoomTopPreferences(room.id);
                                                  setTopPreferencesByRoom(prev => ({
                                                    ...prev,
                                                    [room.id]: topPrefs
                                                  }));
                                                  
                                                  // Update suggestion ID map
                                                  try {
                                                    const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                                                    const newIdMap = {};
                                                    roomSuggestions?.forEach(s => {
                                                      const nameKey = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                                                      if (nameKey && s.id) {
                                                        newIdMap[nameKey] = s.id;
                                                      }
                                                    });
                                                    setSuggestionIdMapByRoom(prev => ({
                                                      ...prev,
                                                      [room.id]: newIdMap
                                                    }));
                                                  } catch (mapErr) {
                                                    console.error('Failed to update ID map:', mapErr);
                                                  }
                                                } catch (prefErr) {
                                                  console.error('Failed to refresh top preferences:', prefErr);
                                                }
                                              }, 500);
                                            } catch (err) {
                                              console.error('Failed to submit vote:', err);
                                              // Revert optimistic updates
                                              setUserVotesBySuggestion(prev => {
                                                const newState = { ...prev };
                                                if (isLiked) {
                                                  newState[sid] = 'up';
                                                } else {
                                                  delete newState[sid];
                                                }
                                                return newState;
                                              });
                                              if (sid) {
                                                setTopPreferencesByRoom(prev => {
                                                  const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                                  const newCountsMap = { ...roomPrefs.counts_by_suggestion };
                                                  if (isLiked) {
                                                    newCountsMap[sid] = (newCountsMap[sid] || 0) + 1;
                                                  } else {
                                                    newCountsMap[sid] = Math.max(0, (newCountsMap[sid] || 0) - 1);
                                                  }
                                                  return {
                                                    ...prev,
                                                    [room.id]: {
                                                      ...roomPrefs,
                                                      counts_by_suggestion: newCountsMap
                                                    }
                                                  };
                                                });
                                              }
                                              alert('Failed to submit vote. Please try again.');
                                            }
                                          };
                                          
                                          return (
                                            <div 
                                              key={idx} 
                                              className={`suggestion-card ${isLiked ? 'selected' : ''}`}
                                              onClick={handleLike}
                                              style={{ cursor: 'pointer' }}
                                            >
                                              <div className="suggestion-header">
                                                <h5 className="suggestion-title">{displayName}</h5>
                                                <div className="suggestion-rating">⭐ {item.rating || '4.5'}</div>
                                              </div>
                                              {whySelected && (
                                                <div style={{
                                                  marginBottom: '0.5rem',
                                                  padding: '0.5rem',
                                                  backgroundColor: '#e3f2fd',
                                                  borderRadius: '4px',
                                                  fontSize: '0.85rem',
                                                  fontStyle: 'italic',
                                                  color: '#1565c0'
                                                }}>
                                                  <strong>Why selected:</strong> {whySelected}
                                                </div>
                                              )}
                                              <p className="suggestion-description">
                                                {item.description || item.suggestion_description || item.details || 
                                                 (item.airline ? `${item.airline} flight` :
                                                  item.train_name ? `${item.train_name} ${item.class || ''}` :
                                                  item.operator ? `${item.operator} ${item.bus_type || ''}` :
                                                  'Selected option')}
                                              </p>
                                              <div className="suggestion-details">
                                                <span className="suggestion-price">{item.price_range || item.price || item.price_estimate || (item.price_min && item.price_max ? `₹${item.price_min}-₹${item.price_max}` : 'N/A')}</span>
                                                {item.duration && <span className="suggestion-duration">{item.duration}</span>}
                                                {item.departure_time && item.arrival_time && (
                                                  <span className="suggestion-times">
                                                    {item.departure_time} - {item.arrival_time}
                                                  </span>
                                                )}
                                              </div>
                                              <div className="suggestion-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                <button 
                                                  onClick={async (e) => {
                                                    e.stopPropagation();
                                                    if (item.external_url) {
                                                      window.open(item.external_url, '_blank');
                                                    }
                                                  }}
                                                  className="book-button"
                                                  style={{
                                                    background: '#2196F3',
                                                    color: 'white',
                                                    border: '2px solid #2196F3',
                                                    padding: '0.5rem 1rem',
                                                    fontWeight: '600',
                                                    letterSpacing: '0.5px',
                                                    textTransform: 'uppercase',
                                                    cursor: 'pointer',
                                                    margin: '0.5rem 0.5rem 0.5rem 0',
                                                    borderRadius: '4px',
                                                    fontSize: '0.85rem'
                                                  }}
                                                >
                                                  BOOK NOW
                                                </button>
                                                {/* Heart/Like button - matches accommodation section style */}
                                                <div
                                                  onClick={handleLike}
                                                  onMouseDown={(e) => {
                                                    e.stopPropagation();
                                                  }}
                                                  style={{
                                                    background: 'transparent',
                                                    border: 'none',
                                                    cursor: 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.25rem',
                                                    color: '#e74c3c',
                                                    padding: '0.25rem',
                                                    position: 'relative',
                                                    zIndex: 2,
                                                    userSelect: 'none'
                                                  }}
                                                  title="Click to like"
                                                >
                                                  <span style={{ fontSize: '1.1rem', color: isLiked ? '#e74c3c' : '#999' }}>❤️</span>
                                                  <span style={{ color: '#555', fontWeight: 600 }}>{likeCount}</span>
                                                </div>
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    ) : (
                                      <p style={{ color: '#999', fontStyle: 'italic' }}>No departure preferences yet</p>
                                    )}
                                  </div>
                                  
                                  {/* Return Section */}
                                  <div>
                                    <h6 style={{ marginBottom: '1rem', color: '#e67e22' }}>Return Travel</h6>
                                    {returnItems.length > 0 ? (
                                      <div className="suggestions-grid">
                                        {returnItems.map((item, idx) => {
                                          const displayName = (item.name || item.title || item.airline || item.operator || item.train_name || 'Selection').toString();
                                          const whySelected = item.why_selected || item.conflict_resolution || null;
                                          const matchesPrefs = item.matches_preferences || [];
                                          
                                          let sid = idMap[displayName.trim().toLowerCase()] || item.id || item.suggestion_id;
                                          const likeCount = sid ? (countsMap[sid] || 0) : 0;
                                          const userId = apiService.userId || userData?.id || userData?.email;
                                          const userVote = userId && sid ? (userVotesBySuggestion[sid] || null) : null;
                                          const isLiked = userVote === 'up';
                                          
                                          // HandleLike function for return section - same as accommodation
                                          const handleLike = async (e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            
                                            if (!userId) {
                                              alert('Please join or create a group first to like suggestions.');
                                              return;
                                            }
                                            
                                            if (!sid) {
                                              console.error('Cannot vote: missing suggestion ID for:', displayName);
                                              alert(`Cannot vote: Unable to find suggestion ID for "${displayName}".`);
                                              return;
                                            }
                                            
                                            // Toggle: if already liked, unlike; otherwise, like
                                            const newVoteType = isLiked ? 'down' : 'up';
                                            const countChange = isLiked ? -1 : 1;
                                            
                                            // OPTIMISTIC UPDATE: Update UI immediately before API call
                                            setUserVotesBySuggestion(prev => ({
                                              ...prev,
                                              [sid]: newVoteType === 'up' ? 'up' : null
                                            }));
                                            
                                            // Update counts map immediately
                                            if (sid) {
                                              const currentCount = countsMap[sid] || 0;
                                              const newCount = Math.max(0, currentCount + countChange);
                                              
                                              setTopPreferencesByRoom(prev => {
                                                const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                                const newCountsMap = { ...roomPrefs.counts_by_suggestion, [sid]: newCount };
                                                
                                                // Update top preferences list with new count
                                                const updatedTopPrefs = [...(roomPrefs.top_preferences || [])];
                                                const prefIndex = updatedTopPrefs.findIndex(p => p.suggestion_id === sid);
                                                if (prefIndex >= 0) {
                                                  updatedTopPrefs[prefIndex] = { ...updatedTopPrefs[prefIndex], count: newCount };
                                                } else {
                                                  updatedTopPrefs.push({
                                                    suggestion_id: sid,
                                                    name: displayName,
                                                    count: newCount
                                                  });
                                                }
                                                updatedTopPrefs.sort((a, b) => b.count - a.count);
                                                
                                                return {
                                                  ...prev,
                                                  [room.id]: {
                                                    ...roomPrefs,
                                                    top_preferences: updatedTopPrefs,
                                                    counts_by_suggestion: newCountsMap
                                                  }
                                                };
                                              });
                                            }
                                            
                                            try {
                                              // Try to get the correct suggestion ID from the suggestions collection
                                              let voteSuggestionId = sid;
                                              
                                              try {
                                                const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                                                const found = roomSuggestions?.find(s => {
                                                  const sName = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                                                  const dName = displayName.trim().toLowerCase();
                                                  return sName === dName;
                                                });
                                                
                                                if (found && found.id) {
                                                  voteSuggestionId = found.id;
                                                }
                                              } catch (fetchErr) {
                                                console.error('Failed to fetch room suggestions for ID lookup:', fetchErr);
                                              }
                                              
                                              await apiService.submitVote({
                                                suggestion_id: voteSuggestionId,
                                                user_id: userId,
                                                vote_type: newVoteType
                                              });
                                              
                                              // Refresh top preferences after a short delay (non-blocking to prevent glitch)
                                              setTimeout(async () => {
                                                try {
                                                  const topPrefs = await apiService.getRoomTopPreferences(room.id);
                                                  setTopPreferencesByRoom(prev => ({
                                                    ...prev,
                                                    [room.id]: topPrefs
                                                  }));
                                                  
                                                  // Update suggestion ID map
                                                  try {
                                                    const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                                                    const newIdMap = {};
                                                    roomSuggestions?.forEach(s => {
                                                      const nameKey = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                                                      if (nameKey && s.id) {
                                                        newIdMap[nameKey] = s.id;
                                                      }
                                                    });
                                                    setSuggestionIdMapByRoom(prev => ({
                                                      ...prev,
                                                      [room.id]: newIdMap
                                                    }));
                                                  } catch (mapErr) {
                                                    console.error('Failed to update ID map:', mapErr);
                                                  }
                                                } catch (prefErr) {
                                                  console.error('Failed to refresh top preferences:', prefErr);
                                                }
                                              }, 500);
                                            } catch (err) {
                                              console.error('Failed to submit vote:', err);
                                              // Revert optimistic updates
                                              setUserVotesBySuggestion(prev => {
                                                const newState = { ...prev };
                                                if (isLiked) {
                                                  newState[sid] = 'up';
                                                } else {
                                                  delete newState[sid];
                                                }
                                                return newState;
                                              });
                                              if (sid) {
                                                setTopPreferencesByRoom(prev => {
                                                  const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                                  const newCountsMap = { ...roomPrefs.counts_by_suggestion };
                                                  if (isLiked) {
                                                    newCountsMap[sid] = (newCountsMap[sid] || 0) + 1;
                                                  } else {
                                                    newCountsMap[sid] = Math.max(0, (newCountsMap[sid] || 0) - 1);
                                                  }
                                                  return {
                                                    ...prev,
                                                    [room.id]: {
                                                      ...roomPrefs,
                                                      counts_by_suggestion: newCountsMap
                                                    }
                                                  };
                                                });
                                              }
                                              alert('Failed to submit vote. Please try again.');
                                            }
                                          };
                                          
                                          return (
                                            <div 
                                              key={idx} 
                                              className={`suggestion-card ${isLiked ? 'selected' : ''}`}
                                              onClick={handleLike}
                                              style={{ cursor: 'pointer' }}
                                            >
                                              <div className="suggestion-header">
                                                <h5 className="suggestion-title">{displayName}</h5>
                                                <div className="suggestion-rating">⭐ {item.rating || '4.5'}</div>
                                              </div>
                                              {whySelected && (
                                                <div style={{
                                                  marginBottom: '0.5rem',
                                                  padding: '0.5rem',
                                                  backgroundColor: '#e3f2fd',
                                                  borderRadius: '4px',
                                                  fontSize: '0.85rem',
                                                  fontStyle: 'italic',
                                                  color: '#1565c0'
                                                }}>
                                                  <strong>Why selected:</strong> {whySelected}
                                                </div>
                                              )}
                                              <p className="suggestion-description">
                                                {item.description || item.suggestion_description || item.details || 
                                                 (item.airline ? `${item.airline} flight` :
                                                  item.train_name ? `${item.train_name} ${item.class || ''}` :
                                                  item.operator ? `${item.operator} ${item.bus_type || ''}` :
                                                  'Selected option')}
                                              </p>
                                              <div className="suggestion-details">
                                                <span className="suggestion-price">{item.price_range || item.price || item.price_estimate || (item.price_min && item.price_max ? `₹${item.price_min}-₹${item.price_max}` : 'N/A')}</span>
                                                {item.duration && <span className="suggestion-duration">{item.duration}</span>}
                                                {item.departure_time && item.arrival_time && (
                                                  <span className="suggestion-times">
                                                    {item.departure_time} - {item.arrival_time}
                                                  </span>
                                                )}
                                              </div>
                                              <div className="suggestion-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                <button 
                                                  onClick={async (e) => {
                                                    e.stopPropagation();
                                                    if (item.external_url) {
                                                      window.open(item.external_url, '_blank');
                                                    }
                                                  }}
                                                  className="book-button"
                                                  style={{
                                                    background: '#2196F3',
                                                    color: 'white',
                                                    border: '2px solid #2196F3',
                                                    padding: '0.5rem 1rem',
                                                    fontWeight: '600',
                                                    letterSpacing: '0.5px',
                                                    textTransform: 'uppercase',
                                                    cursor: 'pointer',
                                                    margin: '0.5rem 0.5rem 0.5rem 0',
                                                    borderRadius: '4px',
                                                    fontSize: '0.85rem'
                                                  }}
                                                >
                                                  BOOK NOW
                                                </button>
                                                {/* Heart/Like button - matches accommodation section style */}
                                                <div
                                                  onClick={handleLike}
                                                  onMouseDown={(e) => {
                                                    e.stopPropagation();
                                                  }}
                                                  style={{
                                                    background: 'transparent',
                                                    border: 'none',
                                                    cursor: 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.25rem',
                                                    color: '#e74c3c',
                                                    padding: '0.25rem',
                                                    position: 'relative',
                                                    zIndex: 2,
                                                    userSelect: 'none'
                                                  }}
                                                  title="Click to like"
                                                >
                                                  <span style={{ fontSize: '1.1rem', color: isLiked ? '#e74c3c' : '#999' }}>❤️</span>
                                                  <span style={{ color: '#555', fontWeight: 600 }}>{likeCount}</span>
                                                </div>
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    ) : (
                                      <p style={{ color: '#999', fontStyle: 'italic' }}>No common preferences yet</p>
                                    )}
                                  </div>
                                  
                                  {/* Top Preferences Sidebar */}
                                  <div style={{ background: '#f8f9fa', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '0.75rem' }}>
                                    <div style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Top Preferences</div>
                                    {(() => {
                                      const topPrefs = topPreferencesByRoom[room.id]?.top_preferences || [];
                                      const filteredPrefs = topPrefs.filter(p => (p.count || 0) > 0);
                                      if (filteredPrefs.length === 0) {
                                        return <div style={{ fontSize: '0.85rem', color: '#888' }}>No likes yet</div>;
                                      }
                                      
                                      // Get top count
                                      const topCount = filteredPrefs[0]?.count || 0;
                                      // Show all items with top count (handles ties)
                                      const topItems = filteredPrefs.filter(p => p.count === topCount);
                                      
                                      return (
                                        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                          {topItems.map((p, i) => (
                                            <li key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
                                              <span>{p.name}</span>
                                              <span style={{ color: '#666' }}>❤ {p.count}</span>
                                            </li>
                                          ))}
                                        </ul>
                                      );
                                    })()}
                                  </div>
                              </div>
                            </div>
                          );
                        }
                        
                        // Always show "Selected Options" - only user selections
                        const displayTitle = `Selected Options (${displayItems.length})`;
                        
                        return (
                          <div key={room.id} className="room-results-section">
                            <div className="room-results-header">
                              <span className="room-icon">{getRoomIcon(room.room_type)}</span>
                              <h5 className="room-title">{getRoomTitle(room.room_type)}</h5>
                              <div className="room-status">
                                {completedCount}/{group?.total_members || 2} completed
                              </div>
                            </div>
                            
                            {displayItems.length > 0 ? (
                              <div className="voting-results" style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '1rem' }}>
                                <div>
                                <h6>{displayTitle}</h6>
                                <div className="suggestions-grid">
                                    {displayItems.map((item, idx) => {
                                      // Handle different data structures: AI-consolidated vs regular selections
                                      const displayName = (item.name || item.title || item.airline || item.operator || item.train_name || 'Selection').toString();
                                      const whySelected = item.why_selected || item.conflict_resolution || null;
                                      const matchesPrefs = item.matches_preferences || [];
                                      
                                      // Try to get suggestion ID from idMap first (mapped by name), then from item fields
                                      let sid = idMap[displayName.trim().toLowerCase()];
                                      
                                      // If not found in idMap, try item.id or suggestion_id
                                      if (!sid) {
                                        sid = item.id || item.suggestion_id;
                                      }
                                      
                                      // If still not found, log it
                                      if (!sid) {
                                        console.warn('No suggestion ID found for:', displayName, 'item:', item);
                                      }
                                      
                                      const likeCount = sid ? (countsMap[sid] || 0) : 0;
                                      
                                      // Check if current user has already liked this suggestion
                                      const userId = apiService.userId || userData?.id || userData?.email;
                                      const userVote = userId && sid ? (userVotesBySuggestion[sid] || null) : null;
                                      const isUserLiked = userVote === 'up';
                                      
                                      // Handler for clicking the card or heart button
                                      const handleLike = async (e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        
                                        if (!userId) {
                                          alert('Please join or create a group first to like suggestions.');
                                          return;
                                        }
                                        
                                        if (!sid) {
                                          console.error('Cannot vote: missing suggestion ID for:', displayName);
                                          alert(`Cannot vote: Unable to find suggestion ID for "${displayName}".`);
                                          return;
                                        }
                                        
                                        // Toggle: if already liked, unlike; otherwise, like
                                        const newVoteType = isUserLiked ? 'down' : 'up';
                                        const countChange = isUserLiked ? -1 : 1;
                                        
                                        console.log('=== LIKE CLICKED ===');
                                        console.log('Toggling vote:', isUserLiked ? 'unlike' : 'like');
                                        console.log('Current user vote:', userVote);
                                        console.log('New vote type:', newVoteType);
                                        
                                        // OPTIMISTIC UPDATE: Update UI immediately before API call
                                        // Update user vote state
                                        setUserVotesBySuggestion(prev => ({
                                          ...prev,
                                          [sid]: newVoteType === 'up' ? 'up' : null
                                        }));
                                        
                                        // Update top preferences for all room types
                                        if (sid) {
                                          const currentCount = countsMap[sid] || 0;
                                          const newCount = Math.max(0, currentCount + countChange);
                                          
                                          // Update counts map immediately
                                          setTopPreferencesByRoom(prev => {
                                            const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                            const newCountsMap = { ...roomPrefs.counts_by_suggestion, [sid]: newCount };
                                            
                                            // Update top preferences list with new count
                                            const updatedTopPrefs = [...(roomPrefs.top_preferences || [])];
                                            const prefIndex = updatedTopPrefs.findIndex(p => p.suggestion_id === sid);
                                            if (prefIndex >= 0) {
                                              updatedTopPrefs[prefIndex] = { ...updatedTopPrefs[prefIndex], count: newCount };
                                            } else {
                                              // Add to top prefs if not there
                                              updatedTopPrefs.push({
                                                suggestion_id: sid,
                                                name: displayName,
                                                count: newCount
                                              });
                                            }
                                            
                                            // Sort by count descending
                                            updatedTopPrefs.sort((a, b) => b.count - a.count);
                                            
                                            return {
                                              ...prev,
                                              [room.id]: {
                                                ...roomPrefs,
                                                top_preferences: updatedTopPrefs,
                                                counts_by_suggestion: newCountsMap
                                              }
                                            };
                                          });
                                        }
                                        
                                        try {
                                          // First, try to get the correct suggestion ID from the suggestions collection
                                          let voteSuggestionId = sid;
                                          
                                          // Always try to fetch from suggestions collection to ensure we have the right ID
                                          try {
                                            console.log('Fetching room suggestions for ID lookup...');
                                            const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                                            console.log('Room suggestions:', roomSuggestions);
                                            
                                            const found = roomSuggestions?.find(s => {
                                              const sName = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                                              const dName = displayName.trim().toLowerCase();
                                              console.log(`Comparing "${sName}" with "${dName}"`);
                                              return sName === dName;
                                            });
                                            
                                            if (found && found.id) {
                                              voteSuggestionId = found.id;
                                              console.log('Found suggestion ID:', voteSuggestionId);
                                            } else {
                                              console.warn('Suggestion not found in room suggestions by name');
                                              // Try to match by other fields
                                              const foundById = roomSuggestions?.find(s => s.id === suggestion.id);
                                              if (foundById && foundById.id) {
                                                voteSuggestionId = foundById.id;
                                                console.log('Found suggestion ID by matching existing ID:', voteSuggestionId);
                                              }
                                            }
                                          } catch (fetchErr) {
                                            console.error('Failed to fetch room suggestions for ID lookup:', fetchErr);
                                          }
                                          
                                          if (!voteSuggestionId) {
                                            console.error('Cannot vote: missing suggestion ID for:', displayName);
                                            // Revert optimistic updates
                                            setUserVotesBySuggestion(prev => {
                                              const newState = { ...prev };
                                              if (isUserLiked) {
                                                newState[sid] = 'up';
                                              } else {
                                                delete newState[sid];
                                              }
                                              return newState;
                                            });
                                            if (sid) {
                                              setTopPreferencesByRoom(prev => {
                                                const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                                const newCountsMap = { ...roomPrefs.counts_by_suggestion };
                                                if (isUserLiked) {
                                                  newCountsMap[sid] = (newCountsMap[sid] || 0) + 1;
                                                } else {
                                                  newCountsMap[sid] = Math.max(0, (newCountsMap[sid] || 0) - 1);
                                                }
                                                return {
                                                  ...prev,
                                                  [room.id]: {
                                                    ...roomPrefs,
                                                    counts_by_suggestion: newCountsMap
                                                  }
                                                };
                                              });
                                            }
                                            alert(`Cannot vote: Unable to find suggestion ID for "${displayName}".\n\nThis suggestion may not be in the database. Please refresh the page or regenerate suggestions.`);
                                            return;
                                          }
                                          
                                          console.log('Submitting vote with:', { 
                                            suggestion_id: voteSuggestionId, 
                                            user_id: userId, 
                                            vote_type: newVoteType 
                                          });
                                          
                                          const voteResponse = await apiService.submitVote({
                                            suggestion_id: voteSuggestionId,
                                            user_id: userId,
                                            vote_type: newVoteType
                                          });
                                          
                                          console.log('Vote response:', voteResponse);
                                          console.log('Vote submitted successfully, refreshing results...');
                                          
                                          // Wait a moment before refreshing to ensure vote is saved
                                          await new Promise(resolve => setTimeout(resolve, 300));
                                          
                                          // Refresh top preferences for this room to get updated vote counts
                                          try {
                                            console.log('Refreshing top preferences for room:', room.id);
                                            const topPrefs = await apiService.getRoomTopPreferences(room.id);
                                            console.log('Updated top preferences:', topPrefs);
                                            
                                            // Update state with new vote counts
                                            setTopPreferencesByRoom(prev => ({
                                              ...prev,
                                              [room.id]: topPrefs
                                            }));
                                              
                                              // Also update suggestion ID map if we have room suggestions
                                              try {
                                                const roomSuggestions = await apiService.getRoomSuggestions(room.id);
                                                const newIdMap = {};
                                                roomSuggestions?.forEach(s => {
                                                  const nameKey = (s.name || s.title || s.airline || s.operator || s.train_name || '').toString().trim().toLowerCase();
                                                  if (nameKey && s.id) {
                                                    newIdMap[nameKey] = s.id;
                                                  }
                                                });
                                                setSuggestionIdMapByRoom(prev => ({
                                                  ...prev,
                                                  [room.id]: newIdMap
                                                }));
                                              } catch (mapErr) {
                                                console.error('Failed to update ID map:', mapErr);
                                              }
                                              
                                              // Also refresh consolidated results if available
                                              await loadConsolidatedResults();
                                            } catch (prefErr) {
                                              console.error('Failed to refresh top preferences:', prefErr);
                                              // Still try to refresh consolidated results
                                              await loadConsolidatedResults();
                                            }
                                          
                                          console.log('Results refreshed');
                                        } catch (err) {
                                          console.error('Failed to like suggestion:', err);
                                          console.error('Error details:', {
                                            message: err.message,
                                            error: err.error,
                                            response: err.response,
                                            stack: err.stack
                                          });
                                          // Revert optimistic update on error
                                          setUserVotesBySuggestion(prev => {
                                            const newState = { ...prev };
                                            if (isUserLiked) {
                                              newState[sid] = 'up';
                                            } else {
                                              delete newState[sid];
                                            }
                                            return newState;
                                          });
                                          if (sid) {
                                            setTopPreferencesByRoom(prev => {
                                              const roomPrefs = prev[room.id] || { top_preferences: [], counts_by_suggestion: {} };
                                              const newCountsMap = { ...roomPrefs.counts_by_suggestion };
                                              if (isUserLiked) {
                                                newCountsMap[sid] = (newCountsMap[sid] || 0) + 1;
                                              } else {
                                                newCountsMap[sid] = Math.max(0, (newCountsMap[sid] || 0) - 1);
                                              }
                                              return {
                                                ...prev,
                                                [room.id]: {
                                                  ...roomPrefs,
                                                  counts_by_suggestion: newCountsMap
                                                }
                                              };
                                            });
                                          }
                                          const errorMessage = err.message || err.error || err.toString() || 'Unknown error';
                                          alert(`Failed to like suggestion: ${errorMessage}\n\nCheck console for details.`);
                                        }
                                      };
                                      
                                      // Check if this card is liked by current user (similar to selected state)
                                      const isLiked = isUserLiked;
                                      
                                      return (
                                      <div 
                                        key={idx} 
                                        className={`suggestion-card ${isLiked ? 'selected' : ''}`}
                                        onClick={(e) => handleLike(e)}
                                        onMouseDown={(e) => {
                                          // Ensure clicks work even if there are overlapping elements
                                          e.stopPropagation();
                                        }}
                                        style={{ 
                                          cursor: 'pointer',
                                          position: 'relative',
                                          zIndex: 1,
                                          userSelect: 'none'
                                        }}
                                      >
                                      <div className="suggestion-header">
                                        <h5 className="suggestion-title">
                                            {displayName}
                                        </h5>
                                        <div className="suggestion-rating">
                                          {item.rating || '4.5'}
                                        </div>
                                      </div>
                                      {whySelected && (
                                        <div style={{
                                          marginBottom: '0.5rem',
                                          padding: '0.5rem',
                                          backgroundColor: '#e3f2fd',
                                          borderRadius: '4px',
                                          fontSize: '0.85rem',
                                          fontStyle: 'italic',
                                          color: '#1565c0'
                                        }}>
                                          <strong>Why selected:</strong> {whySelected}
                                        </div>
                                      )}
                                      {matchesPrefs.length > 0 && (
                                        <div style={{
                                          marginBottom: '0.5rem',
                                          fontSize: '0.8rem',
                                          color: '#666'
                                        }}>
                                          <strong>Matches:</strong> {matchesPrefs.join(', ')}
                                        </div>
                                      )}
                                      <p className="suggestion-description">
                                        {item.description || item.suggestion_description || item.details || 
                                         (item.airline ? `${item.airline} flight` :
                                          item.train_name ? `${item.train_name} ${item.class || ''}` :
                                          item.operator ? `${item.operator} ${item.bus_type || ''}` :
                                          'Selected option')}
                                      </p>
                                      <div className="suggestion-details">
                                        <span className="suggestion-price">
                                            {item.price_range || item.price || item.price_estimate || (item.price_min && item.price_max ? `₹${item.price_min}-₹${item.price_max}` : 'N/A')}
                                        </span>
                                        {item.duration && <span className="suggestion-duration">{item.duration}</span>}
                                        {item.departure_time && item.arrival_time && (
                                          <span className="suggestion-times">
                                            {item.departure_time} - {item.arrival_time}
                                          </span>
                                        )}
                                      </div>
                                      
                                        <div className="suggestion-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        {/* View on Maps button - show for stay, eat, activities (not travel) */}
                                        {room.room_type !== 'transportation' && (item.maps_embed_url || item.maps_url || item.external_url) && (
                                          <button 
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleOpenMaps(item);
                                            }}
                                            className="maps-button"
                                            style={{
                                              background: '#27ae60',
                                              color: 'white',
                                              border: '2px solid #27ae60',
                                              padding: '0.5rem 1rem',
                                              fontWeight: '600',
                                              letterSpacing: '0.5px',
                                              textTransform: 'uppercase',
                                              cursor: 'pointer',
                                              margin: '0.5rem 0.5rem 0.5rem 0',
                                              borderRadius: '4px',
                                              fontSize: '0.85rem'
                                            }}
                                          >
                                            View on Maps
                                          </button>
                                        )}
                                        
                                        {/* Book Now button - ONLY for transportation, stay, and accommodation */}
                                        {(room.room_type === 'transportation' || room.room_type === 'stay' || room.room_type === 'accommodation') && (
                                          <button 
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleOpenBooking(item, room.room_type);
                                            }}
                                            className="book-button"
                                            style={{
                                              background: '#2196F3',
                                              color: 'white',
                                              border: '2px solid #2196F3',
                                              padding: '0.5rem 1rem',
                                              fontWeight: '600',
                                              letterSpacing: '0.5px',
                                              textTransform: 'uppercase',
                                              cursor: 'pointer',
                                              margin: '0.5rem 0.5rem 0.5rem 0',
                                              borderRadius: '4px',
                                              fontSize: '0.85rem'
                                            }}
                                          >
                                            Book Now
                                          </button>
                                        )}

                                          {/* Heart/Like button - also triggers like, but visual indicator */}
                                          <div
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              handleLike(e);
                                            }}
                                            onMouseDown={(e) => {
                                              e.stopPropagation();
                                            }}
                                            style={{
                                              background: 'transparent',
                                              border: 'none',
                                              cursor: 'pointer',
                                              display: 'flex',
                                              alignItems: 'center',
                                              gap: '0.25rem',
                                              color: '#e74c3c',
                                              padding: '0.25rem',
                                              position: 'relative',
                                              zIndex: 2,
                                              userSelect: 'none'
                                            }}
                                            title="Click to like"
                                          >
                                            <span style={{ fontSize: '1.1rem', color: isLiked ? '#e74c3c' : '#999' }}>❤️</span>
                                            <span style={{ color: '#555', fontWeight: 600 }}>{likeCount}</span>
                                      </div>
                                    </div>
                                      </div>
                                      );
                                    })}
                                  </div>
                                </div>
                                {/* Show Top Preferences for all room types */}
                                <div style={{ background: '#f8f9fa', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '0.75rem' }}>
                                  <div style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Top Preferences</div>
                                    {(() => {
                                      // Filter out items with 0 hearts and get top most liked
                                      const topPrefs = topPreferencesByRoom[room.id]?.top_preferences || [];
                                      const filteredPrefs = topPrefs.filter(p => (p.count || 0) > 0);
                                      if (filteredPrefs.length === 0) {
                                        return <div style={{ fontSize: '0.85rem', color: '#888' }}>No likes yet</div>;
                                      }
                                      
                                      // Get top count
                                      const topCount = filteredPrefs[0]?.count || 0;
                                      // Show all items with top count (handles ties)
                                      const topItems = filteredPrefs.filter(p => p.count === topCount);
                                      
                                      return (
                                        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                          {topItems.map((p, i) => (
                                            <li key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
                                              <span>{p.name}</span>
                                              <span style={{ color: '#666' }}>❤ {p.count}</span>
                                            </li>
                                          ))}
                                        </ul>
                                      );
                                    })()}
                                  </div>
                              </div>
                            ) : (
                              <div className="no-suggestions">
                                <p>No selections made yet</p>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                
                {/* Itinerary Section */}
                <div className="itinerary-section">
                  <h3>What your itinerary could look like:</h3>
                  {generateItinerary()}
                </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Drawer */}
      <div className={`drawer ${drawerOpen ? 'drawer-open' : ''} ${drawerContent === 'suggestions' ? 'suggestions-mode' : ''}`}>
        <div className="drawer-content">
          <div className="drawer-header">
            <h3 className="drawer-title">
              {drawerContent === 'form' && !drawerLoading && (
                <>
                  {currentRoomType === 'accommodation' && '🏨 Find Accommodation'}
                  {currentRoomType === 'transportation' && '✈️ Book Transportation'}
                  {currentRoomType === 'activities' && '📅 Plan Activities'}
                  {currentRoomType === 'dining' && '🍽️ Discover Dining'}
                </>
              )}
              {drawerContent === 'suggestions' && ''}
              {drawerContent === 'results' && '📊 Live Results'}
            </h3>
            <button onClick={handleDrawerClose} className="drawer-close">
              ×
            </button>
          </div>

          <div className="drawer-body">
            {drawerContent === 'form' && drawerRoom && (
              <div className="form-content">
                {/* Never show loading screen when form is displayed - user needs to fill it */}
                  <PlanningRoom 
                    room={drawerRoom}
                    group={group}
                    userData={userData}
                    onBack={handleDrawerClose}
                    onSubmit={handleFormSubmit}
                    isDrawer={true}
                  />
              </div>
            )}

            {drawerContent === 'suggestions' && drawerRoom && (
              <div className="suggestions-content">
                {drawerLoading ? (
                  // Show loading only when generating suggestions (after form submit)
                  <LoadingProgress isLoading={drawerLoading} destination={group?.destination} />
                ) : suggestions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '3rem', color: 'white' }}>
                    <p style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>No suggestions found</p>
                    <p style={{ fontSize: '0.9rem', opacity: 0.8 }}>
                      Please try again or check your preferences.
                    </p>
                    <button 
                      onClick={() => {
                        setDrawerContent('form');
                        setDrawerLoading(false);
                      }}
                      className="btn btn-secondary"
                      style={{ marginTop: '1rem' }}
                    >
                      Go Back
                    </button>
                  </div>
                ) : (
                  <>
                    {/* CRITICAL: Split transportation suggestions into departure and return */}
                    {drawerRoom.room_type === 'transportation' ? (
                  <>
                <div className="suggestions-header">
                          <h4>AI-Generated Transportation Suggestions</h4>
                          <p>Showing {suggestions.length} total suggestions</p>
                          <p>Select your preferred options for each trip leg:</p>
                </div>
                
                        {/* Two-column layout for departure and return */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1rem', marginTop: '1rem' }}>
                          {/* Departure Section */}
                          <div style={{
                            border: '1px solid rgba(255, 255, 255, 0.2)',
                            borderRadius: '8px',
                            padding: '1rem',
                            backgroundColor: 'rgba(255, 255, 255, 0.05)'
                          }}>
                            <h5 style={{ color: 'white', marginBottom: '1rem', fontSize: '1.1rem' }}>
                              🛫 Departure Travel
                            </h5>
                            <div className="suggestions-grid" style={{ gridTemplateColumns: '1fr' }}>
                              {suggestions
                                .filter(s => {
                                  const leg = s.trip_leg || s.leg_type;
                                  return leg === 'departure' || !leg; // Default to departure if not specified
                                })
                                .map((suggestion, index) => (
                    <div 
                      key={suggestion.id || index}
                      className={`suggestion-card ${selectedSuggestions.includes(suggestion.id || index) ? 'selected' : ''}`}
                      onClick={() => handleSuggestionSelect(suggestion)}
                    >
                      <div className="suggestion-header">
                        <h5>
                          {suggestion.name || suggestion.title || suggestion.suggestion_name || 
                           (suggestion.airline && suggestion.flight_number ? 
                            `${suggestion.airline} ${suggestion.flight_number}` : 
                           suggestion.train_name && suggestion.train_number ?
                            `${suggestion.train_name} (${suggestion.train_number})` :
                           suggestion.operator && suggestion.bus_type ?
                            `${suggestion.operator} ${suggestion.bus_type}` :
                            suggestion.airline || suggestion.train_name || suggestion.operator || 'Transport Option')}
                        </h5>
                        <div className="suggestion-rating">
                          ⭐ {suggestion.rating || suggestion.star_rating || '4.5'}
                        </div>
                      </div>
                      <p className="suggestion-description">
                        {suggestion.description || suggestion.suggestion_description || suggestion.details ||
                         (suggestion.airline ? 
                          `${suggestion.airline} flight from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                         suggestion.train_name ?
                          `${suggestion.train_name} ${suggestion.class || ''} from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                         suggestion.operator ?
                          `${suggestion.operator} ${suggestion.bus_type || ''} from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                          'Transport option')}
                      </p>
                      <div className="suggestion-details">
                        <span className="suggestion-price">
                          {suggestion.price_range || (suggestion.price != null ? `${suggestion.price}` : (suggestion.cost || '$50'))}
                        </span>
                        {suggestion.duration && <span className="suggestion-duration">{suggestion.duration}</span>}
                        {suggestion.departure_time && suggestion.arrival_time && (
                          <span className="suggestion-times">
                            {suggestion.departure_time} - {suggestion.arrival_time}
                          </span>
                        )}
                                    </div>
                                    {selectedSuggestions.includes(suggestion.id || index) && (
                                      <div className="selection-indicator">✓ Selected</div>
                                    )}
                                  </div>
                                ))}
                            </div>
                          </div>
                          
                          {/* Return Section */}
                          <div style={{
                            border: '1px solid rgba(255, 255, 255, 0.2)',
                            borderRadius: '8px',
                            padding: '1rem',
                            backgroundColor: 'rgba(255, 255, 255, 0.05)'
                          }}>
                            <h5 style={{ color: 'white', marginBottom: '1rem', fontSize: '1.1rem' }}>
                              🛬 Return Travel
                            </h5>
                            <div className="suggestions-grid" style={{ gridTemplateColumns: '1fr' }}>
                              {suggestions
                                .filter(s => {
                                  const leg = s.trip_leg || s.leg_type;
                                  return leg === 'return';
                                })
                                .map((suggestion, index) => (
                                  <div 
                                    key={suggestion.id || index}
                                    className={`suggestion-card ${selectedSuggestions.includes(suggestion.id || index) ? 'selected' : ''}`}
                                    onClick={() => handleSuggestionSelect(suggestion)}
                                  >
                                    <div className="suggestion-header">
                                      <h5>
                                        {suggestion.name || suggestion.title || suggestion.suggestion_name || 
                                         (suggestion.airline && suggestion.flight_number ? 
                                          `${suggestion.airline} ${suggestion.flight_number}` : 
                                         suggestion.train_name && suggestion.train_number ?
                                          `${suggestion.train_name} (${suggestion.train_number})` :
                                         suggestion.operator && suggestion.bus_type ?
                                          `${suggestion.operator} ${suggestion.bus_type}` :
                                          suggestion.airline || suggestion.train_name || suggestion.operator || 'Transport Option')}
                                      </h5>
                                      <div className="suggestion-rating">
                                        ⭐ {suggestion.rating || suggestion.star_rating || '4.5'}
                                      </div>
                                    </div>
                                    <p className="suggestion-description">
                                      {suggestion.description || suggestion.suggestion_description || suggestion.details ||
                                       (suggestion.airline ? 
                                        `${suggestion.airline} flight from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                                       suggestion.train_name ?
                                        `${suggestion.train_name} ${suggestion.class || ''} from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                                       suggestion.operator ?
                                        `${suggestion.operator} ${suggestion.bus_type || ''} from ${suggestion.origin || 'Origin'} to ${suggestion.destination || 'Destination'}` :
                                        'Transport option')}
                                    </p>
                                    <div className="suggestion-details">
                                      <span className="suggestion-price">
                                        {suggestion.price_range || (suggestion.price != null ? `${suggestion.price}` : (suggestion.cost || '$50'))}
                                      </span>
                                      {suggestion.duration && <span className="suggestion-duration">{suggestion.duration}</span>}
                                      {suggestion.departure_time && suggestion.arrival_time && (
                                        <span className="suggestion-times">
                                          {suggestion.departure_time} - {suggestion.arrival_time}
                                        </span>
                                      )}
                                    </div>
                                    {selectedSuggestions.includes(suggestion.id || index) && (
                                      <div className="selection-indicator">✓ Selected</div>
                                    )}
                                  </div>
                                ))}
                            </div>
                          </div>
                        </div>
                      </>
                    ) : (
                      /* NON-TRANSPORTATION: Standard single-column view */
                      <>
                        <div className="suggestions-header">
                          <h4>AI-Generated Suggestions</h4>
                          <p>Showing all {suggestions.length} suggestions</p>
                          <p>Select your preferred options:</p>
                        </div>
                        
                        <div className="suggestions-grid">
                          {suggestions.map((suggestion, index) => (
                            <div 
                              key={suggestion.id || index}
                              className={`suggestion-card ${selectedSuggestions.includes(suggestion.id || index) ? 'selected' : ''}`}
                              onClick={() => handleSuggestionSelect(suggestion)}
                            >
                              <div className="suggestion-header">
                                <h5>
                                  {suggestion.name || suggestion.title || suggestion.suggestion_name || 'Option'}
                                </h5>
                                <div className="suggestion-rating">
                                  ⭐ {suggestion.rating || suggestion.star_rating || '4.5'}
                                </div>
                              </div>
                              <p className="suggestion-description">
                                {suggestion.description || suggestion.suggestion_description || suggestion.details || 'Description'}
                              </p>
                              <div className="suggestion-details">
                                <span className="suggestion-price">
                                  {suggestion.price_range || (suggestion.price != null ? `${suggestion.price}` : (suggestion.cost || '$50'))}
                                </span>
                                {suggestion.duration && <span className="suggestion-duration">{suggestion.duration}</span>}
                        {suggestion.cuisine && <span className="suggestion-cuisine">{suggestion.cuisine}</span>}
                        {suggestion.location && <span className="suggestion-location">{suggestion.location}</span>}
                      </div>
                      {suggestion.amenities && suggestion.amenities.length > 0 && (
                        <div className="suggestion-amenities">
                          <small>Includes: {suggestion.amenities.join(', ')}</small>
                        </div>
                      )}
                      
                      {drawerRoom && drawerRoom.room_type !== 'transportation' && (suggestion.maps_embed_url || suggestion.maps_url) && (
                        <div className="suggestion-actions">
                          <button 
                            className="maps-button"
                            onClick={(e) => {
                                      e.stopPropagation();
                              handleOpenMaps(suggestion);
                            }}
                          >
                            🗺️ View on Maps
                          </button>
                        </div>
                      )}
                      
                      {selectedSuggestions.includes(suggestion.id || index) && (
                        <div className="selection-indicator">✓ Selected</div>
                      )}
                    </div>
                  ))}
                </div>
                      </>
                    )}

                <div className="suggestions-footer">
                  <p className="selection-count">
                    {selectedSuggestions.length} selected
                  </p>
                  <button 
                    onClick={handleFinalSubmit}
                    className="btn btn-primary"
                    disabled={selectedSuggestions.length === 0 || isConfirming}
                  >
                    {isConfirming ? 'CONFIRMING SUGGESTIONS...' : 'CONFIRM SELECTIONS'}
                  </button>
                </div>
                  </>
                )}
              </div>
            )}

            {drawerContent === 'results' && (
              <div className="results-content">
                <div className="results-header">
                  <h4>Live Voting Results</h4>
                  <p>Current consensus for {group?.name}</p>
                </div>
                
                {Object.keys(consolidatedResults).length === 0 ? (
                  <div className="no-results">
                    <p>No voting results available yet. Start planning to see live results!</p>
                  </div>
                ) : (
                  <div className="results-sections">
                    {Object.entries(consolidatedResults).map(([roomId, roomData]) => {
                      const room = roomData.room;
                      const consensus = roomData.consensus;
                      const likedSuggestions = consensus?.liked_suggestions || [];
                      
                      return (
                        <div key={roomId} className="room-results-section">
                          <div className="room-results-header">
                            <span className="room-icon">{getRoomIcon(room.room_type)}</span>
                            <h5 className="room-title">{getRoomTitle(room.room_type)}</h5>
                            <div className="room-status">
                              {consensus?.is_locked ? '🔒 Locked' : '🗳️ Voting Open'}
                            </div>
                          </div>
                          
                          {consensus?.final_decision ? (
                            <div className="final-decision">
                              <h6>Final Decision</h6>
                              <div className="suggestions-grid">
                                {Array.isArray(consensus.final_decision) ? (
                                  consensus.final_decision.map((suggestion) => 
                                    renderSuggestionCard({ suggestion })
                                  )
                                ) : (
                                  renderSuggestionCard({ suggestion: consensus.final_decision })
                                )}
                              </div>
                            </div>
                          ) : likedSuggestions.length > 0 ? (
                            <div className="voting-results">
                              <h6>Top Suggestions</h6>
                              <div className="suggestions-grid">
                                {likedSuggestions.slice(0, 3).map((suggestionData) => 
                                  renderSuggestionCard(suggestionData)
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="no-suggestions">
                              <p>No suggestions available yet</p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                
                <div className="results-footer">
                  <button 
                    onClick={handleDrawerClose}
                    className="btn btn-secondary"
                  >
                    CLOSE RESULTS
        </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drawer Overlay */}
      {drawerOpen && <div className="drawer-overlay" onClick={handleDrawerClose}></div>}

      {/* Maps Modal */}
      {mapsModalOpen && (
        <div className="maps-modal-overlay" onClick={handleCloseMaps}>
          <div className="maps-modal" onClick={(e) => e.stopPropagation()}>
            <div className="maps-modal-header">
              <h3>{selectedSuggestion?.name || 'Location'}</h3>
              <button className="maps-modal-close" onClick={handleCloseMaps}>
                ×
              </button>
            </div>
            <div className="maps-modal-body">
              <div className="maps-modal-layout">
                {/* Left sidebar with details */}
                <div className="maps-modal-details">
                  <div className="maps-modal-section">
                    <h4>Details</h4>
                    {selectedSuggestion?.description && (
                      <p className="maps-description">{selectedSuggestion.description}</p>
                    )}
                    {selectedSuggestion?.location && (
                      <p className="maps-location">📍 {selectedSuggestion.location}</p>
                    )}
                    {selectedSuggestion?.rating && (
                      <div className="maps-rating">
                        <span className="rating-stars">
                          {'⭐'.repeat(Math.floor(selectedSuggestion.rating))}☆
                        </span>
                        <span className="rating-value">{selectedSuggestion.rating}/5</span>
                      </div>
                    )}
                    {selectedSuggestion?.price_range && (
                      <p className="maps-price">💰 {selectedSuggestion.price_range}</p>
                    )}
                    {selectedSuggestion?.features && selectedSuggestion.features.length > 0 && (
                      <div className="maps-features">
                        <h5>Features:</h5>
                        <div className="features-list">
                          {selectedSuggestion.features.map((feature, idx) => (
                            <span key={idx} className="feature-tag">{feature}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Photos section */}
                  <div className="maps-modal-section">
                    <h4>Photos</h4>
                    {selectedSuggestion?.photos && selectedSuggestion.photos.length > 0 ? (
                      <div className="maps-photos-gallery">
                        <div className="photos-grid">
                          {selectedSuggestion.photos.slice(0, 6).map((photo_reference, idx) => {
                            const photoUrl = `https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference=${photo_reference}&key=AIzaSyBVR-c133yJG7wtpGOqYFBALI3-CH8BiR4`;
                            return (
                              <img 
                                key={idx}
                                src={photoUrl}
                                alt={`${selectedSuggestion?.name} - Photo ${idx + 1}`}
                                className="photo-thumbnail"
                                loading="lazy"
                                onError={(e) => {
                                  e.target.style.display = 'none';
                                }}
                              />
                            );
                          })}
                        </div>
                        <p className="photos-note">
                          {selectedSuggestion.photos.length} photos available
                        </p>
                        <a 
                          href={selectedSuggestion?.maps_url || selectedSuggestion?.external_url || (() => {
                            // Create a search URL using name and location (more reliable than place_id)
                            const name = selectedSuggestion.name || selectedSuggestion.title || '';
                            const location = selectedSuggestion.location || selectedSuggestion.vicinity || '';
                            const searchQuery = `${name} ${location}`.trim();
                            return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(searchQuery)}`;
                          })()}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="view-photos-btn"
                          style={{ display: 'block', textAlign: 'center', marginTop: '0.5rem' }}
                        >
                          View all photos on Google Maps →
                        </a>
                      </div>
                    ) : selectedSuggestion?.place_id ? (
                      <div className="maps-photos">
                        <a 
                          href={selectedSuggestion?.maps_url || selectedSuggestion?.external_url || (() => {
                            // Create a search URL using name and location (more reliable than place_id)
                            const name = (selectedSuggestion.name || selectedSuggestion.title || '').trim();
                            const location = (selectedSuggestion.location || selectedSuggestion.vicinity || '').trim();
                            const searchQuery = `${name} ${location}`.trim();
                            return searchQuery ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(searchQuery)}` : '#';
                          })()}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="view-photos-btn"
                          style={{ display: 'block', textAlign: 'center', width: '100%' }}
                        >
                          View Photos on Google Maps →
                        </a>
                        <p className="photos-note" style={{ marginTop: '0.5rem', textAlign: 'center' }}>
                          Click to see property photos
                        </p>
                      </div>
                    ) : null}
                  </div>
                  
                  {/* External link */}
                  <div className="maps-modal-section">
                    {selectedSuggestion?.maps_url && (
                      <a 
                        href={selectedSuggestion.maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="view-maps-btn"
                      >
                        🗺️ View on Google Maps
                      </a>
                    )}
                  </div>
                </div>
                
                {/* Right side with map */}
                <div className="maps-modal-map">
                  {selectedMapUrl && (
                    <iframe
                      src={selectedMapUrl}
                      width="100%"
                      height="100%"
                      style={{ border: 0 }}
                      allowFullScreen
                      loading="lazy"
                      referrerPolicy="no-referrer-when-downgrade"
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Group Modal */}
      {isEditingGroup && (
        <div className="edit-group-modal-overlay" onClick={() => setIsEditingGroup(false)}>
          <div className="edit-group-modal" onClick={(e) => e.stopPropagation()}>
            <div className="edit-group-header">
              <h3>Edit Group Details</h3>
              <button className="edit-group-close" onClick={() => setIsEditingGroup(false)}>×</button>
            </div>
            <div className="edit-group-body">
              <div className="edit-group-field">
                <label>Group Name</label>
                <input 
                  type="text" 
                  value={editingGroupData.name || group.name}
                  onChange={(e) => setEditingGroupData({...editingGroupData, name: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>From Location</label>
                <input 
                  type="text" 
                  value={editingGroupData.from_location || group.from_location || ''}
                  onChange={(e) => setEditingGroupData({...editingGroupData, from_location: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>Destination (To Location)</label>
                <input 
                  type="text" 
                  value={editingGroupData.destination || group.destination}
                  onChange={(e) => setEditingGroupData({...editingGroupData, destination: e.target.value})}
                />
                <small style={{color: '#666', fontSize: '0.85rem', display: 'block', marginTop: '0.5rem'}}>
                  ⚠️ Changing destination will refresh all votes
                </small>
              </div>
              <div className="edit-group-field">
                <label>Start Date</label>
                <input 
                  type="date" 
                  value={editingGroupData.start_date || group.start_date.split('T')[0]}
                  onChange={(e) => setEditingGroupData({...editingGroupData, start_date: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>End Date</label>
                <input 
                  type="date" 
                  value={editingGroupData.end_date || group.end_date.split('T')[0]}
                  onChange={(e) => setEditingGroupData({...editingGroupData, end_date: e.target.value})}
                />
              </div>
              <div className="edit-group-field">
                <label>Number of Members</label>
                <input 
                  type="number" 
                  min="2"
                  value={editingGroupData.total_members || group.total_members || 2}
                  onChange={(e) => setEditingGroupData({...editingGroupData, total_members: parseInt(e.target.value)})}
                />
              </div>
              <div className="edit-group-actions">
                <button 
                  className="btn btn-primary"
                  onClick={async () => {
                    try {
                      const newDestination = editingGroupData.destination || group.destination;
                      const oldDestination = group.destination;
                      const destinationChanged = newDestination !== oldDestination;
                      
                      const updateData = {
                        name: editingGroupData.name || group.name,
                        from_location: editingGroupData.from_location || group.from_location,
                        destination: newDestination,
                        start_date: editingGroupData.start_date || group.start_date,
                        end_date: editingGroupData.end_date || group.end_date,
                        total_members: editingGroupData.total_members || group.total_members
                      };
                      
                      // Show confirmation if destination changed
                      if (destinationChanged) {
                        const confirmReset = window.confirm(
                          '⚠️ Changing the destination will reset all votes and suggestions.\n\n' +
                          'Do you want to continue?'
                        );
                        if (!confirmReset) {
                          return;
                        }
                      }
                      
                      await apiService.updateGroup(groupId, updateData);
                      
                      // If destination changed, reset votes by clearing room answers and suggestions
                      if (destinationChanged) {
                        // Clear all room voting data
                        for (const room of rooms) {
                          try {
                            await apiService.clearRoomData(room.id);
                          } catch (e) {
                            console.error(`Error clearing room ${room.id}:`, e);
                          }
                        }
                        // If destination changed, reload all data
                        await loadGroupData();
                      } else {
                        // If destination didn't change, refresh group and rooms to ensure all UI updates
                        // Clear localStorage cache to force fresh data
                        localStorage.removeItem(`wanderly_group_${groupId}`);
                        localStorage.removeItem(`wanderly_rooms_${groupId}`);
                        
                        // Reload group and rooms data
                        const [updatedGroupData, updatedRoomsData] = await Promise.all([
                          apiService.getGroup(groupId),
                          apiService.getGroupRooms(groupId)
                        ]);
                        
                        setGroup(updatedGroupData);
                        setRooms(sortRoomsByDesiredOrder(updatedRoomsData));
                        
                        // Also refresh top preferences to ensure vote counts are updated
                        await refreshVotesAndPreferences();
                      }
                      
                      setIsEditingGroup(false);
                      setEditingGroupData({});
                      
                      // Show success message
                      if (destinationChanged) {
                        alert('Group updated! All votes have been reset due to destination change.');
                      } else {
                        console.log('Group updated successfully! Voting data preserved.');
                      }
                    } catch (error) {
                      console.error('Error updating group:', error);
                      alert('Error updating group. Please try again.');
                    }
                  }}
                >
                  Save Changes
                </button>
                <button 
                  className="btn btn-secondary"
                  onClick={() => {
                    setIsEditingGroup(false);
                    setEditingGroupData({});
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Booking Modal - EaseMyTrip Style */}
      {bookingModalOpen && bookingData && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 10000
          }}
          onClick={handleCloseBooking}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '8px',
              width: '95%',
              maxWidth: '900px',
              maxHeight: '90vh',
              overflow: 'auto',
              boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {bookingStep === 1 ? (
              <>
                {/* Header with booking details */}
                <div style={{
                  background: 'white',
                  padding: '24px',
                  borderBottom: '2px solid #e5e7eb'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2 style={{ margin: 0, color: '#1f2937', fontSize: '24px' }}>
                      {bookingData.suggestion.name || bookingData.suggestion.title}
                    </h2>
                    <button
                      onClick={handleCloseBooking}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        fontSize: '24px',
                        cursor: 'pointer',
                        color: '#6b7280'
                      }}
                    >
                      ×
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: '2rem', marginTop: '16px', color: '#6b7280', fontSize: '14px' }}>
                    <div>
                      <strong style={{ color: '#374151' }}>Dates:</strong> {new Date(group?.start_date).toLocaleDateString()} - {new Date(group?.end_date).toLocaleDateString()}
                    </div>
                    {bookingData.suggestion.price && (
                      <div>
                        <strong style={{ color: '#374151' }}>Price:</strong> ₹{bookingData.suggestion.price}
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Travellers Details Section */}
                <div style={{ padding: '24px', backgroundColor: '#f9fafb' }}>
                  <h3 style={{ 
                    color: '#2563eb', 
                    fontSize: '18px', 
                    fontWeight: '600',
                    marginBottom: '16px',
                    padding: '12px',
                    background: 'white',
                    borderRadius: '6px'
                  }}>
                    Travellers Details
                  </h3>
                  
                  <div style={{ background: 'white', padding: '16px', borderRadius: '8px', marginBottom: '16px' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      marginBottom: '12px'
                    }}>
                      <label style={{ fontWeight: '600', color: '#374151' }}>ADULT</label>
                      <span style={{ color: '#6b7280', fontSize: '12px' }}>▼</span>
                    </div>
                    
                    <div style={{ backgroundColor: '#eff6ff', padding: '12px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px', color: '#1e40af' }}>
                      Name should be same as in Government ID proof
                    </div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', marginBottom: '16px' }}>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                          Title *
                        </label>
                        <select
                          value={bookingForm.title}
                          onChange={(e) => setBookingForm({...bookingForm, title: e.target.value})}
                          style={{
                            width: '100%',
                            padding: '10px',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            fontSize: '14px'
                          }}
                        >
                          <option value="">Title</option>
                          <option value="Mr">Mr</option>
                          <option value="Mrs">Mrs</option>
                          <option value="Ms">Ms</option>
                          <option value="Miss">Miss</option>
                        </select>
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                          (First Name & Middle name, if any) *
                        </label>
                        <input
                          type="text"
                          value={bookingForm.firstName}
                          onChange={(e) => setBookingForm({...bookingForm, firstName: e.target.value})}
                          placeholder="Enter First Name"
                          style={{
                            width: '100%',
                            padding: '10px',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            fontSize: '14px'
                          }}
                        />
                      </div>
                    </div>
                    
                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                        Last Name *
                      </label>
                      <input
                        type="text"
                        value={bookingForm.lastName}
                        onChange={(e) => setBookingForm({...bookingForm, lastName: e.target.value})}
                        placeholder="Enter Last Name"
                        style={{
                          width: '100%',
                          padding: '10px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          fontSize: '14px'
                        }}
                      />
                    </div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                          Email Id (Optional)
                        </label>
                        <input
                          type="email"
                          value={bookingForm.email}
                          onChange={(e) => setBookingForm({...bookingForm, email: e.target.value})}
                          placeholder="Enter Email Id"
                          style={{
                            width: '100%',
                            padding: '10px',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            fontSize: '14px'
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                          Contact Number (Optional)
                        </label>
                        <input
                          type="tel"
                          value={bookingForm.phone}
                          onChange={(e) => setBookingForm({...bookingForm, phone: e.target.value})}
                          placeholder="Enter Contact Number"
                          style={{
                            width: '100%',
                            padding: '10px',
                            border: '1px solid #d1d5db',
                            borderRadius: '6px',
                            fontSize: '14px'
                          }}
                        />
                      </div>
                    </div>
                    
                    <div style={{ marginTop: '12px', fontSize: '12px', color: '#059669' }}>
                      <a href="#" style={{ color: '#2563eb', textDecoration: 'none' }}>
                        (+) Frequent flyer number (optional)
                      </a>
                    </div>
                  </div>
                </div>
                
                {/* Contact Details Section */}
                <div style={{ padding: '24px', backgroundColor: '#f9fafb', borderTop: '1px solid #e5e7eb' }}>
                  <h3 style={{ 
                    color: '#2563eb', 
                    fontSize: '18px', 
                    fontWeight: '600',
                    marginBottom: '8px'
                  }}>
                    Contact Details
                  </h3>
                  <p style={{ color: '#6b7280', fontSize: '14px', marginBottom: '16px' }}>
                    Your ticket & details will be shared here
                  </p>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                        Email Address *
                      </label>
                      <input
                        type="email"
                        value={bookingForm.contactEmail}
                        onChange={(e) => setBookingForm({...bookingForm, contactEmail: e.target.value})}
                        placeholder="Enter a valid email address"
                        style={{
                          width: '100%',
                          padding: '10px',
                          border: '1px solid #d1d5db',
                          borderRadius: '6px',
                          fontSize: '14px'
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#374151' }}>
                        Phone Number *
                      </label>
                      <div style={{ display: 'flex' }}>
                        <select style={{
                          padding: '10px',
                          border: '1px solid #d1d5db',
                          borderRight: 'none',
                          borderTopLeftRadius: '6px',
                          borderBottomLeftRadius: '6px',
                          fontSize: '14px',
                          width: '80px'
                        }}>
                          <option>+91</option>
                        </select>
                        <input
                          type="tel"
                          value={bookingForm.contactPhone}
                          onChange={(e) => setBookingForm({...bookingForm, contactPhone: e.target.value})}
                          placeholder="Enter Mobile no."
                          style={{
                            flex: 1,
                            padding: '10px',
                            border: '1px solid #d1d5db',
                            borderTopRightRadius: '6px',
                            borderBottomRightRadius: '6px',
                            fontSize: '14px'
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Terms and Continue Button */}
                <div style={{ padding: '24px', background: 'white', borderTop: '1px solid #e5e7eb' }}>
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'flex', alignItems: 'flex-start', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={termsAccepted}
                        onChange={(e) => setTermsAccepted(e.target.checked)}
                        style={{ marginRight: '8px', marginTop: '2px' }}
                      />
                      <span style={{ fontSize: '14px', color: '#374151' }}>
                        I understand and agree to the rules, <a href="#" style={{ color: '#2563eb' }}>Privacy Policy</a>,{' '}
                        <a href="#" style={{ color: '#2563eb' }}>User Agreement</a> and{' '}
                        <a href="#" style={{ color: '#2563eb' }}>Terms & Conditions</a> of Wanderly
                      </span>
                    </label>
                  </div>
                  
                  <div>
                    <button
                      onClick={handleSubmitBooking}
                      style={{
                        background: '#f97316',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '14px 32px',
                        fontSize: '16px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        width: '100%'
                      }}
                    >
                      Continue Booking
                    </button>
                  </div>
                </div>
              </>
            ) : (
              /* Confirmation Screen */
              <div style={{ padding: '48px', textAlign: 'center' }}>
                <div style={{ 
                  width: '80px', 
                  height: '80px', 
                  background: '#10b981', 
                  borderRadius: '50%',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '24px'
                }}>
                  <span style={{ fontSize: '48px', color: 'white' }}>✓</span>
                </div>
                <h2 style={{ color: '#1f2937', marginBottom: '12px' }}>Booking Confirmed!</h2>
                <p style={{ color: '#6b7280', marginBottom: '32px' }}>
                  Your booking has been confirmed successfully
                </p>
                <button
                  onClick={handleCloseBooking}
                  style={{
                    background: '#2563eb',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '12px 32px',
                    fontSize: '16px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default GroupDashboard;
