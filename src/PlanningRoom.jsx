import { useState, useEffect } from 'react';
import './PlanningRoom.css';
import apiService from './api';
import { getCurrencyFromLocation } from './currencyUtils';

function PlanningRoom({ room, userData, onBack, onSubmit, isDrawer = false, group = null }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [suggestions, setSuggestions] = useState([]);
  const [currentStep, setCurrentStep] = useState('questions'); // questions, suggestions, voting
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [completionStatus, setCompletionStatus] = useState(null);
  const [userCompleted, setUserCompleted] = useState(false);
  const [userName] = useState(userData?.name || '');
  const [userEmail] = useState(userData?.email || '');
  
  // Maps popup state
  const [mapsModalOpen, setMapsModalOpen] = useState(false);
  const [selectedMapUrl, setSelectedMapUrl] = useState('');
  const [selectedSuggestion, setSelectedSuggestion] = useState(null);

  useEffect(() => {
    // PlanningRoom mounted
    loadRoomData();
    loadCompletionStatus();
  }, [room.id]);

  // Load saved data from localStorage on mount
  useEffect(() => {
    const savedAnswers = localStorage.getItem(`wanderly_answers_${room.id}`);
    const savedSuggestions = localStorage.getItem(`wanderly_suggestions_${room.id}`);
    const savedCurrentStep = localStorage.getItem(`wanderly_currentStep_${room.id}`);
    
    if (savedAnswers) {
      try {
        setAnswers(JSON.parse(savedAnswers));
      } catch (error) {
        console.error('Error loading saved answers:', error);
      }
    }
    
    if (savedSuggestions) {
      try {
        setSuggestions(JSON.parse(savedSuggestions));
      } catch (error) {
        console.error('Error loading saved suggestions:', error);
      }
    }
    
    if (savedCurrentStep) {
      try {
        setCurrentStep(savedCurrentStep);
      } catch (error) {
        console.error('Error loading saved current step:', error);
      }
    }
  }, [room.id]);

  // Save data to localStorage whenever it changes
  useEffect(() => {
    if (Object.keys(answers).length > 0) {
      localStorage.setItem(`wanderly_answers_${room.id}`, JSON.stringify(answers));
    }
  }, [answers, room.id]);

  useEffect(() => {
    if (suggestions.length > 0) {
      localStorage.setItem(`wanderly_suggestions_${room.id}`, JSON.stringify(suggestions));
    }
  }, [suggestions, room.id]);

  useEffect(() => {
    localStorage.setItem(`wanderly_currentStep_${room.id}`, currentStep);
  }, [currentStep, room.id]);

  const getDefaultQuestionsForRoomType = (roomType, currency = '$') => {
    // Match backend question structure exactly for instant loading
    const defaultQuestions = {
      'accommodation': [
        {
          id: 'acc-1',
          question_text: 'What is your accommodation budget range per night?',
          question_type: 'range',
          min_value: 0,
          max_value: 1000,
          step: 10,
          currency: currency,
          order: 0
        },
        {
          id: 'acc-2',
          question_text: 'What type of accommodation do you prefer?',
          question_type: 'buttons',
          options: ['Hotel', 'Hostel', 'Airbnb', 'Resort', 'Guesthouse', 'No preference'],
          order: 1
        },
        {
          id: 'acc-3',
          question_text: 'Any specific accommodation preferences or requirements?',
          question_type: 'text',
          placeholder: 'e.g., pet-friendly, pool, gym, near city center...',
          order: 2
        }
      ],
      'transportation': [
        {
          id: 'trans-1',
          question_text: 'What is your transportation budget range?',
          question_type: 'range',
          min_value: 0,
          max_value: 2000,
          step: 50,
          currency: currency,
          order: 0
        },
        {
          id: 'trans-2',
          question_text: 'What transportation methods do you prefer?',
          question_type: 'buttons',
          options: ['Flight', 'Train', 'Bus', 'Car Rental'],
          order: 1
        },
        {
          id: 'trans-3',
          question_text: 'What is your preferred departure date?',
          question_type: 'date',
          placeholder: 'Select your departure date',
          order: 2
        },
        {
          id: 'trans-4',
          question_text: 'What is your preferred return date? (Leave empty for one-way)',
          question_type: 'date',
          placeholder: 'Select your return date (optional)',
          order: 3
        },
        {
          id: 'trans-5',
          question_text: 'Any specific transportation preferences?',
          question_type: 'text',
          placeholder: 'e.g., direct flights only, eco-friendly options, luxury transport...',
          order: 4
        }
      ],
      'activities': [
        {
          id: 'act-1',
          question_text: 'What type of activities interest you?',
          question_type: 'buttons',
          options: ['Cultural', 'Adventure', 'Relaxation', 'Food & Drink', 'Nature', 'Nightlife', 'Mixed'],
          order: 0
        },
        {
          id: 'act-2',
          question_text: 'Any specific activities or experiences you want?',
          question_type: 'text',
          placeholder: 'e.g., museum visits, hiking trails, cooking classes, local festivals...',
          order: 1
        }
      ],
      'dining': [
        {
          id: 'eat-1',
          question_text: 'What kind of dining experiences are you most interested in during this trip?',
          question_type: 'buttons',
          options: ['Local specialties & authentic food spots', 'Trendy restaurants or fine dining', 'Hidden gems / street food experiences', 'Casual, budget-friendly meals', 'Cafés & brunch spots', 'Bars, pubs, or nightlife dining'],
          order: 0
        },
        {
          id: 'eat-2',
          question_text: 'What kind of cuisines or food styles do you want to explore?',
          question_type: 'buttons',
          options: ['Local cuisine', 'Asian', 'Mediterranean', 'Italian', 'American / Burgers', 'Vegetarian / Vegan', 'Seafood', 'Desserts / Coffee / Bakery', 'Open to anything'],
          order: 1
        },
        {
          id: 'eat-3',
          question_text: 'Do you have any dietary needs or food preferences?',
          question_type: 'text',
          placeholder: 'Type your dietary needs or preferences. Type "No restrictions" if none.',
          order: 2
        },
      ]
    };
    
    return defaultQuestions[roomType] || [];
  };

  const loadRoomData = async () => {
    try {
      setLoading(true);
      
      // FIRST: Get from_location for correct currency (use passed group prop or fetch)
      let currency = '$';
      try {
        let fromLocation = '';
        if (group?.from_location) {
          // Use group prop if available (faster, no API call needed)
          fromLocation = group.from_location;
        } else if (room.group_id) {
          // Fallback: fetch group data if not passed as prop
          const groupData = await apiService.getGroup(room.group_id);
          fromLocation = groupData?.from_location || '';
        }
        currency = getCurrencyFromLocation(fromLocation);
      } catch (groupErr) {
        console.error('Error getting currency:', groupErr);
        // Continue with default currency
      }
      
      // IMMEDIATE: Show preset default questions instantly with correct currency
      const defaultQuestions = getDefaultQuestionsForRoomType(room.room_type, currency);
      if (defaultQuestions.length > 0) {
        // Deduplicate default questions by ID and question_text
        const seen = new Set();
        const uniqueDefaults = defaultQuestions.filter((question) => {
          const id = question.id || '';
          const text = question.question_text || '';
          const key = `${id}|${text}`;
          if (seen.has(key)) {
            return false;
          }
          seen.add(key);
          return true;
        });
        setQuestions(uniqueDefaults);
        setLoading(false); // Stop loading immediately - questions are shown
      }
      
      // Load questions from API in background (non-blocking)
      let questionsData = [];
      try {
        // Fetching questions
        questionsData = await apiService.getRoomQuestions(room.id);
        
        // Check if dining questions are old format (need to be replaced)
        if (room.room_type === 'dining' && questionsData.length > 0) {
          const isOldFormat = questionsData.some(q => 
            q.question_text === 'What meal type are you interested in?' ||
            q.question_text === 'What dining preferences do you have?' ||
            q.question_text === 'Any dietary restrictions or food preferences?' ||
            q.question_text.includes('must-do" food experiences')
          );
          
          if (isOldFormat) {
            // Old format detected - ignore and recreate with new format
            questionsData = []; // Clear old questions
            apiService.createQuestionsForRoom(room.id).then(() => {
              apiService.getRoomQuestions(room.id).then(fetchedQuestions => {
                if (fetchedQuestions.length > 0) {
                  // STRICT deduplication by question_text first, then by ID
                  const seenTexts = new Set();
                  const seenIds = new Set();
                  const uniqueQuestions = fetchedQuestions.filter((question) => {
                    const text = (question.question_text || '').trim().toLowerCase();
                    const id = question.id || '';
                    if (seenTexts.has(text) || (id && seenIds.has(id))) {
                      return false;
                    }
                    seenTexts.add(text);
                    if (id) seenIds.add(id);
                    return true;
                  });
                  
                  // Filter out must-do question for dining
                  let finalQuestions = uniqueQuestions;
                  if (room.room_type === 'dining') {
                    finalQuestions = uniqueQuestions.filter(q => 
                      !q.question_text.includes('must-do" food experiences')
                    );
                  }
                  
                  const sorted = finalQuestions.slice().sort((a, b) => {
                    const orderA = a.order !== undefined ? a.order : 999;
                    const orderB = b.order !== undefined ? b.order : 999;
                    if (orderA !== orderB) return orderA - orderB;
                    return (a.id || '').localeCompare(b.id || '');
                  });
                  setQuestions(sorted);
                }
              }).catch(() => {}); // Silent fail - defaults already shown
            }).catch(() => {}); // Silent fail - defaults already shown
            return; // Don't process old questions
          }
        }
        
        // If no questions exist, create them in background (non-blocking)
        if (questionsData.length === 0) {
          apiService.createQuestionsForRoom(room.id).then(() => {
            apiService.getRoomQuestions(room.id).then(fetchedQuestions => {
              if (fetchedQuestions.length > 0) {
                // STRICT deduplication by question_text first, then by ID
                const seenTexts = new Set();
                const seenIds = new Set();
                const uniqueQuestions = fetchedQuestions.filter((question) => {
                  const text = (question.question_text || '').trim().toLowerCase();
                  const id = question.id || '';
                  if (seenTexts.has(text) || (id && seenIds.has(id))) {
                    return false;
                  }
                  seenTexts.add(text);
                  if (id) seenIds.add(id);
                  return true;
                });
                
                // Filter out must-do question for dining
                let finalQuestions = uniqueQuestions;
                if (room.room_type === 'dining') {
                  finalQuestions = uniqueQuestions.filter(q => 
                    !q.question_text.includes('must-do" food experiences')
                  );
                }
                
                const sorted = finalQuestions.slice().sort((a, b) => {
                  const orderA = a.order !== undefined ? a.order : 999;
                  const orderB = b.order !== undefined ? b.order : 999;
                  if (orderA !== orderB) return orderA - orderB;
                  return (a.id || '').localeCompare(b.id || '');
                });
                setQuestions(sorted);
              }
            }).catch(() => {}); // Silent fail - defaults already shown
          }).catch(() => {}); // Silent fail - defaults already shown
        } else {
          // Questions exist from API - check if they match new format for dining
          let shouldUseApiQuestions = true;
          if (room.room_type === 'dining') {
            // Verify API questions match new structure
            const hasNewQ1 = questionsData.some(q => q.question_text.includes('dining experiences are you most interested'));
            const hasNewQ2 = questionsData.some(q => q.question_text.includes('cuisines or food styles'));
            const hasNewQ3 = questionsData.some(q => q.question_text.includes('Do you have any dietary needs'));
            
            // Only use API questions if they match new format (3 questions, no must-do question)
            const hasOldQ4 = questionsData.some(q => q.question_text.includes('must-do" food experiences'));
            shouldUseApiQuestions = hasNewQ1 && hasNewQ2 && hasNewQ3 && !hasOldQ4;
            
            if (!shouldUseApiQuestions) {
              // Old format - recreate with new format
              apiService.createQuestionsForRoom(room.id).then(() => {
                apiService.getRoomQuestions(room.id).then(fetchedQuestions => {
                  if (fetchedQuestions.length > 0) {
                    // STRICT deduplication by question_text first, then by ID
                    const seenTexts = new Set();
                    const seenIds = new Set();
                    const uniqueQuestions = fetchedQuestions.filter((question) => {
                      const text = (question.question_text || '').trim().toLowerCase();
                      const id = question.id || '';
                      if (seenTexts.has(text) || (id && seenIds.has(id))) {
                        return false;
                      }
                      seenTexts.add(text);
                      if (id) seenIds.add(id);
                      return true;
                    });
                    
                    // Filter out must-do question for dining
                    let finalQuestions = uniqueQuestions;
                    if (room.room_type === 'dining') {
                      finalQuestions = uniqueQuestions.filter(q => 
                        !q.question_text.includes('must-do" food experiences')
                      );
                    }
                    
                    const sorted = finalQuestions.slice().sort((a, b) => {
                      const orderA = a.order !== undefined ? a.order : 999;
                      const orderB = b.order !== undefined ? b.order : 999;
                      if (orderA !== orderB) return orderA - orderB;
                      return (a.id || '').localeCompare(b.id || '');
                    });
                    setQuestions(sorted);
                  }
                }).catch(() => {}); // Silent fail - defaults already shown
              }).catch(() => {}); // Silent fail - defaults already shown
              return; // Don't process old questions
            }
          }
          
          if (shouldUseApiQuestions) {
            // Questions exist from API and are correct format - update with them (may have currency/dynamic options)
            // STRICT deduplication: First by question_text (most important), then by ID
            const seenTexts = new Set();
            const seenIds = new Set();
            const uniqueQuestions = questionsData.filter((question) => {
              const text = (question.question_text || '').trim().toLowerCase();
              const id = question.id || '';
              
              // If we've seen this exact text OR this ID before, skip it
              if (seenTexts.has(text) || (id && seenIds.has(id))) {
                return false;
              }
              seenTexts.add(text);
              if (id) seenIds.add(id);
              return true;
            });
            
            // Additional check: if dining room, ensure exactly 3 questions
            let finalQuestions = uniqueQuestions;
            if (room.room_type === 'dining') {
              finalQuestions = uniqueQuestions.filter(q => 
                !q.question_text.includes('must-do" food experiences')
              );
              // If we still have duplicates, take unique by question_text only
              const textMap = new Map();
              finalQuestions.forEach(q => {
                const text = (q.question_text || '').trim().toLowerCase();
                if (!textMap.has(text)) {
                  textMap.set(text, q);
                }
              });
              finalQuestions = Array.from(textMap.values());
            }
            
            const stableSorted = finalQuestions.slice().sort((a, b) => {
              const orderA = a.order !== undefined ? a.order : 999;
              const orderB = b.order !== undefined ? b.order : 999;
              if (orderA !== orderB) return orderA - orderB;
        const idCmp = (a.id || '').localeCompare(b.id || '');
        if (idCmp !== 0) return idCmp;
        return (a.question_text || '').localeCompare(b.question_text || '');
      });
            
            // Only update if we have valid questions and they're different from current
            if (stableSorted.length > 0) {
              // Compare with current questions to avoid unnecessary updates
              const currentTexts = questions.map(q => (q.question_text || '').trim().toLowerCase()).sort();
              const newTexts = stableSorted.map(q => (q.question_text || '').trim().toLowerCase()).sort();
              const textsEqual = currentTexts.length === newTexts.length && 
                currentTexts.every((text, idx) => text === newTexts[idx]);
              
              if (!textsEqual) {
                setQuestions(stableSorted); // Update with API questions (may have currency)
              }
            }
          }
        }
      } catch (fetchErr) {
        console.error('Error fetching questions:', fetchErr);
        // If fetch fails, defaults are already shown - create in background
        apiService.createQuestionsForRoom(room.id).catch(() => {}); // Silent fail
      }
      
      // Load answers and suggestions in parallel (non-blocking)
      Promise.all([
        apiService.getRoomAnswers(room.id).then(answersData => {
          const answersMap = {};
          answersData.forEach(answer => {
            answersMap[answer.question_id] = answer;
          });
          setAnswers(answersMap);
        }).catch(() => setAnswers({})),
        
        apiService.getRoomSuggestions(room.id).then(suggestionsData => {
          if (suggestionsData.length > 0) {
            setSuggestions(suggestionsData);
          }
        }).catch(() => {})
      ]);
      
      // Always start with questions step
      setCurrentStep('questions');
      
    } catch (error) {
      console.error('Error loading room data:', error);
      setError('Failed to load room data');
    } finally {
      setLoading(false);
    }
  };

  const loadCompletionStatus = async () => {
    try {
      const status = await apiService.getRoomStatus(room.id);
      setCompletionStatus(status);
      setUserCompleted(status.user_completed);
    } catch (error) {
      console.error('Error loading completion status:', error);
    }
  };

  const markRoomComplete = async () => {
    if (!userName || !userEmail) {
      setError('Please enter your name and email to mark room as complete');
      return;
    }

    try {
      setLoading(true);
      // Marking room complete
      setUserCompleted(true);
      await loadCompletionStatus(); // Refresh status
      alert('Room marked as completed!');
    } catch (error) {
      console.error('Error marking room complete:', error);
      console.error('Error details:', error.message);
      setError(`Failed to mark room as complete: ${error.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerChange = (questionId, value) => {
    setAnswers(prev => {
      const newAnswer = {
        question_id: questionId,
        answer_value: value,
        answer_text: typeof value === 'string' ? value : null,
        // For range inputs, also store min_value and max_value
        ...(typeof value === 'object' && value.min_value !== undefined && {
          min_value: value.min_value,
          max_value: value.max_value
        })
      };
      return {
        ...prev,
        [questionId]: newAnswer
      };
    });
  };

  const handleMultipleSelection = (questionId, option) => {
    setAnswers(prev => {
      const currentAnswer = prev[questionId];
      const currentValues = currentAnswer?.answer_value || [];
      
      // Ensure currentValues is an array
      const valuesArray = Array.isArray(currentValues) ? currentValues : [];
      
      // Toggle the option
      let newValues;
      if (valuesArray.includes(option)) {
        // Remove the option
        newValues = valuesArray.filter(val => val !== option);
      } else {
        // Add the option
        newValues = [...valuesArray, option];
      }
      
      const newAnswer = {
        question_id: questionId,
        answer_value: newValues,
        answer_text: null,
        user_id: userData?.id
      };
      return {
        ...prev,
        [questionId]: newAnswer
      };
    });
  };

  const handleSubmitAnswers = async () => {
    try {
      setLoading(true);
      // Submitting answers
      
      // Submit all answers
      for (const [, answer] of Object.entries(answers)) {
        if (answer && answer.answer_value !== undefined) {
          // Submitting individual answer
          await apiService.submitAnswer(room.id, answer);
        }
      }
      
      // If in drawer mode, call onSubmit callback with answers
      if (isDrawer && onSubmit) {
        onSubmit(answers);
        return;
      }
      
      // Generate suggestions (for non-drawer mode)
      await generateSuggestions();
      
    } catch (error) {
      console.error('Error submitting answers:', error);
      console.error('Error details:', error.message);
      setError(`Failed to submit answers: ${error.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const generateSuggestions = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Prepare preferences from answers
      const preferences = {};
      questions.forEach(question => {
        const answer = answers[question.id];
        if (answer) {
          preferences[question.question_text] = answer.answer_value;
        }
      });
      
      // Generate suggestions
      const suggestionsData = await apiService.generateSuggestions({
        room_id: room.id,
        preferences: preferences
      });
      
      setSuggestions(suggestionsData);
      setCurrentStep('suggestions');
      
    } catch (error) {
      console.error('Error generating suggestions:', error);
      
      // Check if it's an AI service setup error
      if (error.message && error.message.includes('AI service not available')) {
        setError('AI service not configured. Please set up your API keys to generate personalized suggestions.');
      } else {
        setError(`Failed to generate suggestions: ${error.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async (suggestionId, voteType) => {
    try {
      // Check if user ID is available
      if (!userData?.id) {
        setError('User ID not found. Please refresh the page and try again.');
        return;
      }
      
      // Voting on suggestion
      
      // Check if suggestion exists
      const suggestion = suggestions.find(s => s.id === suggestionId);
      if (!suggestion) {
        // Suggestion not found
        setError('Suggestion not found');
        return;
      }
      
      const voteData = {
        suggestion_id: suggestionId,
        user_id: userData?.id,
        vote_type: voteType
      };
      
      // Submitting vote
      await apiService.submitVote(voteData);
      
      // Update local state to show the vote
      setSuggestions(prev => prev.map(suggestion => 
        suggestion.id === suggestionId 
          ? { ...suggestion, userVote: voteType }
          : suggestion
      ));
      
      // Vote submitted successfully
    } catch (error) {
      console.error('Error submitting vote:', error);
      setError(`Failed to submit vote: ${error.message}`);
    }
  };

  const handleLockSuggestions = async () => {
    try {
      setLoading(true);
      
      // All suggestions for locking
      
      // Find all liked suggestions (those with userVote === 'up')
      const likedSuggestions = suggestions.filter(suggestion => 
        suggestion.userVote === 'up'
      );
      
      // Liked suggestions found
      
      if (likedSuggestions.length === 0) {
        alert('No liked suggestions to lock. Please like some suggestions first.');
        return;
      }
      
      // Lock the room with all liked suggestions
      await apiService.lockRoomDecisionMultiple(room.id, likedSuggestions.map(s => s.id));
      alert(`${likedSuggestions.length} liked suggestions locked! All members can now see the consolidated results.`);
      // Could navigate to a results dashboard here
    } catch (error) {
      console.error('Error locking suggestions:', error);
      setError('Failed to lock suggestions');
    } finally {
      setLoading(false);
    }
  };

  // Maps popup functions
  const handleOpenMaps = (suggestion) => {
    // Use maps_embed_url if available, otherwise fallback to maps_url
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

  const getRoomTitle = () => {
    switch (room.room_type) {
      case 'stay': return 'Plan Your Stay';
      case 'travel': return 'Plan Your Travel';
      case 'itinerary': return 'Plan Your Activities';
      case 'eat': return 'Plan Your Meals';
      default: return 'Plan Your Trip';
    }
  };

  const renderQuestions = () => {
    // Rendering questions
    return (
      <div className="questions-section">
        <h2>Answer these questions to get personalized suggestions</h2>
        {loading && questions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
          Loading questions...
        </div>
      ) : questions.length === 0 ? (
        <p>No questions available</p>
      ) : null}
        {questions.map((question) => (
        <div key={question.id} className="question-card">
          <label className="question-label">{question.question_text}</label>
          
          {question.question_type === 'slider' && (
            <div className="slider-container">
              <input
                type="range"
                min={question.min_value}
                max={question.max_value}
                step={question.step || 1}
                value={answers[question.id]?.answer_value || question.min_value}
                onChange={(e) => handleAnswerChange(question.id, parseInt(e.target.value))}
                className="slider"
              />
              <div className="slider-labels">
                <span>{question.question_text.includes('budget') ? `₹${question.min_value}` : question.min_value}</span>
                <span>{question.question_text.includes('budget') ? `₹${question.max_value}` : question.max_value}</span>
              </div>
              <div className="slider-value">
                Current: {question.question_text.includes('budget') ? `₹${answers[question.id]?.answer_value || question.min_value}` : 
                         question.question_text.includes('days') ? `${answers[question.id]?.answer_value || question.min_value} days` :
                         question.question_text.includes('active') ? `${answers[question.id]?.answer_value || question.min_value}/10` :
                         answers[question.id]?.answer_value || question.min_value}
              </div>
            </div>
          )}
          
          {question.question_type === 'range' && (
            <div className="range-container">
              <div className="range-inputs">
                <div className="range-input">
                  <label>Min: {question.currency || '$'}</label>
                  <input
                    type="text"
                    placeholder="Enter minimum amount"
                    value={answers[question.id]?.min_value || ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      // Allow empty string, numbers, and backspace
                      if (value === '' || /^\d+$/.test(value)) {
                        const newMin = value === '' ? null : parseInt(value);
                        handleAnswerChange(question.id, {
                          min_value: newMin,
                          max_value: answers[question.id]?.max_value || null
                        });
                      }
                    }}
                    className="range-min"
                  />
                </div>
                <div className="range-separator">to</div>
                <div className="range-input">
                  <label>Max: {question.currency || '$'}</label>
                  <input
                    type="text"
                    placeholder="Enter maximum amount"
                    value={answers[question.id]?.max_value || ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      // Allow empty string, numbers, and backspace
                      if (value === '' || /^\d+$/.test(value)) {
                        const newMax = value === '' ? null : parseInt(value);
                        handleAnswerChange(question.id, {
                          min_value: answers[question.id]?.min_value || null,
                          max_value: newMax
                        });
                      }
                    }}
                    className="range-max"
                  />
                </div>
              </div>
              <div className="range-display">
                Budget Range: {question.currency || '$'}{answers[question.id]?.min_value || '___'} - {question.currency || '$'}{answers[question.id]?.max_value || '___'}
              </div>
            </div>
          )}
          
          {question.question_type === 'buttons' && (
            <div className="button-options">
              {question.options.map((option) => {
                // Check if this question should allow multiple selections
                const isMultipleSelection = question.question_text.toLowerCase().includes('activities') || 
                                          question.question_text.toLowerCase().includes('accommodation') ||
                                          question.question_text.toLowerCase().includes('type of') ||
                                          question.question_text.toLowerCase().includes('dining experiences are you most interested') ||
                                          question.question_text.toLowerCase().includes('cuisines or food styles');
                
                const isSelected = isMultipleSelection 
                  ? (answers[question.id]?.answer_value || []).includes(option)
                  : answers[question.id]?.answer_value === option;
                
                return (
                  <button
                    key={option}
                    className={`option-button ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      if (isMultipleSelection) {
                        handleMultipleSelection(question.id, option);
                      } else {
                        handleAnswerChange(question.id, option);
                      }
                    }}
                  >
                    {option}
                  </button>
                );
              })}
            </div>
          )}
          
          {question.question_type === 'text' && (
            <textarea
              value={answers[question.id]?.answer_text || ''}
              onChange={(e) => handleAnswerChange(question.id, e.target.value)}
              placeholder={question.placeholder || question.question_text}
              className="text-input"
              rows="3"
            />
          )}
          
          {question.question_type === 'date' && (
            <input
              type="date"
              value={answers[question.id]?.answer_text || ''}
              onChange={(e) => handleAnswerChange(question.id, e.target.value)}
              className="date-input"
              style={{
                padding: '0.75rem',
                border: '2px solid #e0e0e0',
                borderRadius: '8px',
                fontSize: '1rem',
                width: '100%',
                backgroundColor: 'white',
                cursor: 'text'
              }}
            />
          )}
        </div>
      ))}
      
      <button 
        onClick={handleSubmitAnswers}
        disabled={loading}
        className="btn btn-primary"
      >
        {loading ? 'Generating Suggestions...' : 'Get AI Suggestions'}
      </button>
    </div>
    );
  };

  const renderSuggestions = () => (
    <div className="suggestions-section">
      <h2>AI-Powered Suggestions</h2>
      <div className="suggestions-grid">
        {suggestions.map((suggestion) => {
          // Suggestion data for rendering
          return (
          <div key={suggestion.id} className="suggestion-card">
            <div className="suggestion-header">
              <h3>{suggestion.name || suggestion.title}</h3>
              {suggestion.price_range && (
                <div className="suggestion-price">{suggestion.price_range}</div>
              )}
              {suggestion.rating && (
                <div className="suggestion-rating">{suggestion.rating}</div>
              )}
            </div>
            
            <p className="suggestion-description">{suggestion.description}</p>
            
            {suggestion.features && suggestion.features.length > 0 && (
              <div className="suggestion-highlights">
                {suggestion.features.map((feature, index) => (
                  <span key={index} className="highlight-tag">
                    {feature}
                  </span>
                ))}
              </div>
            )}
            
            {suggestion.location && (
              <div className="suggestion-location">{suggestion.location}</div>
            )}
            
            {suggestion.why_recommended && (
              <div className="suggestion-reason">{suggestion.why_recommended}</div>
            )}
            
            <div className="suggestion-actions">
              <button 
                onClick={() => handleVote(suggestion.id, 'up')}
                className={`vote-button up ${suggestion.userVote === 'up' ? 'voted' : ''}`}
                style={{
                  background: suggestion.userVote === 'up' ? '#1d2b5c' : '#f3efe7',
                  color: suggestion.userVote === 'up' ? '#f3efe7' : '#1d2b5c',
                  border: '2px solid #1d2b5c',
                  padding: '0.5rem 1rem',
                  fontWeight: '600',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                  boxShadow: '2px 2px 0px #1d2b5c',
                  transition: '0.2s ease',
                  marginRight: '0.5rem'
                }}
              >
                Like
              </button>
              <button 
                onClick={() => handleVote(suggestion.id, 'down')}
                className={`vote-button down ${suggestion.userVote === 'down' ? 'voted' : ''}`}
                style={{
                  background: suggestion.userVote === 'down' ? '#1d2b5c' : '#f3efe7',
                  color: suggestion.userVote === 'down' ? '#f3efe7' : '#1d2b5c',
                  border: '2px solid #1d2b5c',
                  padding: '0.5rem 1rem',
                  fontWeight: '600',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                  boxShadow: '2px 2px 0px #1d2b5c',
                  transition: '0.2s ease',
                  marginRight: '0.5rem'
                }}
              >
                Dislike
              </button>
              {(suggestion.maps_url || suggestion.external_url || suggestion.booking_url) ? (
                suggestion.link_type === 'booking' ? (
                  <a 
                    href={suggestion.booking_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="explore-button"
                    style={{
                      background: '#27ae60',
                      color: 'white',
                      border: '2px solid #27ae60',
                      padding: '0.5rem 1rem',
                      fontWeight: '600',
                      letterSpacing: '0.5px',
                      textTransform: 'uppercase',
                      textDecoration: 'none',
                      boxShadow: '2px 2px 0px #1e8449',
                      transition: '0.2s ease',
                      display: 'inline-block'
                    }}
                  >
                    Book Now
                  </a>
                ) : (
                  <button
                    onClick={() => handleOpenMaps(suggestion)}
                    className="explore-button"
                    style={{
                      background: '#27ae60',
                      color: 'white',
                      border: '2px solid #27ae60',
                      padding: '0.5rem 1rem',
                      fontWeight: '600',
                      letterSpacing: '0.5px',
                      textTransform: 'uppercase',
                      textDecoration: 'none',
                      boxShadow: '2px 2px 0px #1e8449',
                      transition: '0.2s ease',
                      display: 'inline-block',
                      cursor: 'pointer'
                    }}
                  >
                    View on Maps
                  </button>
                )
              ) : (
                <div style={{ 
                  background: '#f8f9fa', 
                  color: '#666', 
                  padding: '0.5rem 1rem', 
                  fontSize: '0.8rem',
                  border: '1px solid #dee2e6',
                  borderRadius: '4px'
                }}>
                  No link available
                </div>
              )}
            </div>
          </div>
          );
        })}
      </div>
      
      <div className="suggestions-actions">
        <button 
          onClick={() => setCurrentStep('questions')}
          className="btn btn-secondary"
        >
          Back to Questions
        </button>
        <button 
          onClick={loadRoomData}
          className="btn btn-primary"
        >
          Refresh Suggestions
        </button>
        <button 
          onClick={handleLockSuggestions}
          className="btn btn-success"
          style={{background: '#28a745', color: 'white'}}
        >
          Lock Final Decision
        </button>
      </div>
    </div>
  );

  return (
    <div className="room-container">
      <div className="room-header">
        <button onClick={onBack} className="back-button">← Back to Dashboard</button>
        <h1 className="room-title">{getRoomTitle()}</h1>
        <p className="room-subtitle">
          {room.room_type === 'stay' && 'Find the perfect accommodation for your group'}
          {room.room_type === 'travel' && 'Book transportation that works for everyone'}
          {room.room_type === 'itinerary' && 'Plan activities everyone will enjoy'}
          {room.room_type === 'eat' && 'Discover local cuisine and dining experiences'}
        </p>
      </div>

      {/* Completion Status Display */}
      {completionStatus && (
        <div className="completion-status" style={{
          background: '#f8f9fa',
          border: '2px solid #1d2b5c',
          borderRadius: '8px',
          padding: '1rem',
          margin: '1rem 0',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#1d2b5c' }}>
            Room Progress: {completionStatus.completion_status}
          </h3>
          {completionStatus.completions && completionStatus.completions.length > 0 && (
            <div style={{ fontSize: '0.9rem', color: '#666' }}>
              Completed by: {completionStatus.completions.map(comp => comp.user_name).join(', ')}
            </div>
          )}
        </div>
      )}

      {/* User Input for Completion */}
      {currentStep === 'suggestions' && !userCompleted && (
        <div className="user-input-section" style={{
          background: '#f8f9fa',
          border: '2px solid #1d2b5c',
          borderRadius: '8px',
          padding: '1rem',
          margin: '1rem 0'
        }}>
          <h3 style={{ margin: '0 0 1rem 0', color: '#1d2b5c' }}>Mark Room as Complete</h3>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem', color: '#666' }}>Your Name</label>
              <input
                type="text"
                value={userName}
                readOnly
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  background: '#f8f9fa',
                  color: '#666'
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem', color: '#666' }}>Your Email</label>
              <input
                type="email"
                value={userEmail}
                readOnly
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  background: '#f8f9fa',
                  color: '#666'
                }}
              />
            </div>
          </div>
          <button
            onClick={markRoomComplete}
            disabled={loading || !userName || !userEmail}
            style={{
              background: userCompleted ? '#28a745' : '#1d2b5c',
              color: 'white',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              cursor: userCompleted ? 'default' : 'pointer',
              opacity: userCompleted ? 0.7 : 1
            }}
          >
            {userCompleted ? '✓ Completed' : 'Mark as Complete'}
          </button>
        </div>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      {currentStep === 'questions' && renderQuestions()}
      {currentStep === 'suggestions' && renderSuggestions()}
      
      {/* Maps Modal */}
      {mapsModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
          onClick={handleCloseMaps}
        >
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '12px',
              width: '90%',
              height: '80%',
              maxWidth: '1200px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '20px',
                borderBottom: '1px solid #eee',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <h3 style={{ margin: 0, color: '#333' }}>
                {selectedSuggestion?.name || 'Location Map'}
              </h3>
              <button
                onClick={handleCloseMaps}
                style={{
                  background: '#ff4757',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                Close
              </button>
            </div>
            
            {/* Modal Content */}
            <div style={{ flex: 1, padding: '0' }}>
              <iframe
                src={selectedMapUrl}
                width="100%"
                height="100%"
                style={{ border: 'none', borderRadius: '0 0 12px 12px' }}
                allowFullScreen
                loading="lazy"
                title="Google Maps"
              />
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
}

export default PlanningRoom;
