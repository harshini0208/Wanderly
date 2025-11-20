import { useState, useEffect, Fragment } from 'react';
import './PlanningRoom.css';
import apiService from './api';
import { getCurrencyFromLocation } from './currencyUtils';

function PlanningRoom({ room, userData, onBack, onSubmit, isDrawer = false, group = null }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [suggestions, setSuggestions] = useState([]);
  const [allSuggestions, setAllSuggestions] = useState({ departure: [], return: [] }); // Store suggestions separately for return trips
  const [currentLeg, setCurrentLeg] = useState(null); // 'departure', 'return', 'both', or null
  const [currentStep, setCurrentStep] = useState('questions'); // questions, suggestions, voting
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [completionStatus, setCompletionStatus] = useState(null);
  const [userCompleted, setUserCompleted] = useState(false);
  const [userName] = useState(userData?.name || '');
  const [userEmail] = useState(userData?.email || '');
  const [isEditingAnswers, setIsEditingAnswers] = useState(false);
  const [tripTypeSelection, setTripTypeSelection] = useState('');
  const isTransportationRoom = room.room_type === 'transportation' || room.room_type === 'travel';
  
  // Maps popup state
  const [mapsModalOpen, setMapsModalOpen] = useState(false);
  const [selectedMapUrl, setSelectedMapUrl] = useState('');
  const [selectedSuggestion, setSelectedSuggestion] = useState(null);
  
  const cacheQuestionsLocally = (questionsToCache = []) => {
    try {
      localStorage.setItem(`wanderly_questions_${room.id}`, JSON.stringify(questionsToCache));
      localStorage.setItem(`wanderly_questions_time_${room.id}`, Date.now().toString());
    } catch (error) {
      console.error('Error caching questions locally:', error);
    }
  };

  const updateQuestionsState = (nextQuestions = [], shouldCache = true) => {
    setQuestions(nextQuestions);
    if (shouldCache) {
      cacheQuestionsLocally(nextQuestions);
    }
  };

  const getQuestionMeta = (questionId) => {
    return questions.find((q) => q.id === questionId) || null;
  };

  const withQuestionMetadata = (questionId, baseAnswer = {}) => {
    const meta = getQuestionMeta(questionId);
    if (!meta) {
      return baseAnswer;
    }

    const enriched = { ...baseAnswer };
    if (meta.question_text && !enriched.question_text) {
      enriched.question_text = meta.question_text;
    }
    if (meta.section && !enriched.section) {
      enriched.section = meta.section;
    }
    if (meta.trip_leg && !enriched.trip_leg) {
      enriched.trip_leg = meta.trip_leg;
    }
    if (meta.visibility_condition && !enriched.visibility_condition) {
      enriched.visibility_condition = meta.visibility_condition;
    }
    if (meta.question_key && !enriched.question_key) {
      enriched.question_key = meta.question_key;
    }

    return enriched;
  };

  const isTransportationQuestionSetCurrent = (questionsList = []) => {
    if (!Array.isArray(questionsList) || questionsList.length === 0) {
      return false;
    }
    const hasTripType = questionsList.some(q => q.question_key === 'trip_type');
    const hasDepartureBudget = questionsList.some(q => q.question_key === 'departure_budget');
    const hasReturnBudget = questionsList.some(q => q.question_key === 'return_budget');
    return hasTripType && hasDepartureBudget && hasReturnBudget;
  };

  const getQuestionDedupKey = (question) => {
    const text = (question.question_text || '').trim().toLowerCase();
    const section = (question.section || '').trim().toLowerCase();
    const visibility = (question.visibility_condition || '').trim().toLowerCase();
    const tripLeg = (question.trip_leg || '').trim().toLowerCase();
    return `${text}|${section}|${visibility}|${tripLeg}`;
  };

  useEffect(() => {
    const currentUserId = apiService.userId || userData?.id;
    const userKey = currentUserId ? `_${currentUserId}` : '';
    let skipQuestionFetch = false;

    if (currentUserId) {
      const savedAnswers = localStorage.getItem(`wanderly_answers_${room.id}_${currentUserId}`);
      if (savedAnswers) {
        try {
          const parsedAnswers = JSON.parse(savedAnswers);
          const userAnswers = {};
          Object.entries(parsedAnswers).forEach(([questionId, answer]) => {
            if (!answer.user_id || answer.user_id === currentUserId) {
              userAnswers[questionId] = answer;
            }
          });
          setAnswers(userAnswers);
        } catch (error) {
          console.error('Error loading saved answers:', error);
        }
      }
    }

    const savedSuggestions = localStorage.getItem(`wanderly_suggestions_${room.id}${userKey}`);
    if (savedSuggestions) {
      try {
        setSuggestions(JSON.parse(savedSuggestions));
      } catch (error) {
        console.error('Error loading saved suggestions:', error);
      }
    }

    const savedCurrentStep = localStorage.getItem(`wanderly_currentStep_${room.id}${userKey}`);
    if (savedCurrentStep) {
      try {
        setCurrentStep(savedCurrentStep);
      } catch (error) {
        console.error('Error loading saved current step:', error);
      }
    }

    const savedQuestions = localStorage.getItem(`wanderly_questions_${room.id}`);
    if (savedQuestions) {
      try {
        const parsedQuestions = JSON.parse(savedQuestions);
        const isTransport = room.room_type === 'transportation';
        const transportCurrent = !isTransport || isTransportationQuestionSetCurrent(parsedQuestions);
        if (Array.isArray(parsedQuestions) && parsedQuestions.length > 0 && transportCurrent) {
          updateQuestionsState(parsedQuestions, false);
          const cacheTime = parseInt(localStorage.getItem(`wanderly_questions_time_${room.id}`) || '0', 10);
          if (!Number.isNaN(cacheTime) && Date.now() - cacheTime < 300000) {
            skipQuestionFetch = true;
          }
        } else if (isTransport && !transportCurrent) {
          localStorage.removeItem(`wanderly_questions_${room.id}`);
          localStorage.removeItem(`wanderly_questions_time_${room.id}`);
        }
      } catch (error) {
        console.error('Error loading cached questions:', error);
      }
    }

    loadRoomData({ skipQuestionFetch });
    loadCompletionStatus();
  }, [room.id, userData?.id]);

  // Save data to localStorage whenever it changes
  // IMPORTANT: Use user-specific keys to prevent cross-user data contamination
  useEffect(() => {
    const currentUserId = apiService.userId || userData?.id;
    if (!currentUserId) {
      return; // Don't save if no user ID
    }
    
    if (Object.keys(answers).length > 0) {
      // Store answers with user-specific key
      localStorage.setItem(`wanderly_answers_${room.id}_${currentUserId}`, JSON.stringify(answers));
    }
  }, [answers, room.id, userData?.id]);

  useEffect(() => {
    if (!isTransportationRoom) {
      return;
    }
    const tripQuestion = questions.find(
      (q) => q.question_key === 'trip_type' || (q.question_text || '').toLowerCase().includes('type of trip')
    );
    if (!tripQuestion) {
      return;
    }
    const selectedValue = (answers[tripQuestion.id]?.answer_value || '').toString().toLowerCase();
    if (selectedValue && selectedValue !== tripTypeSelection) {
      setTripTypeSelection(selectedValue);
    }
    if (!selectedValue && tripTypeSelection) {
      setTripTypeSelection('');
    }
  }, [isTransportationRoom, questions, answers, tripTypeSelection]);

  useEffect(() => {
    if (!isTransportationRoom) {
      return;
    }
    if (!tripTypeSelection) {
      return;
    }

    setAnswers(prev => {
      let changed = false;
      const updated = { ...prev };

      Object.entries(prev).forEach(([questionId, answerObj]) => {
        const meta = getQuestionMeta(questionId);
        if (!meta || !meta.visibility_condition) {
          return;
        }
        const condition = meta.visibility_condition;
        if (tripTypeSelection.startsWith('one') && condition.startsWith('return')) {
          delete updated[questionId];
          changed = true;
        }
        if (tripTypeSelection === 'return' && condition === 'one_way') {
          delete updated[questionId];
          changed = true;
        }
      });

      return changed ? updated : prev;
    });
  }, [isTransportationRoom, tripTypeSelection, questions]);

  useEffect(() => {
    const userId = userData?.id || apiService.userId;
    const userKey = userId ? `_${userId}` : '';
    
    if (suggestions.length > 0) {
      localStorage.setItem(`wanderly_suggestions_${room.id}${userKey}`, JSON.stringify(suggestions));
    }
  }, [suggestions, room.id, userData?.id]);

  useEffect(() => {
    const userId = userData?.id || apiService.userId;
    const userKey = userId ? `_${userId}` : '';
    
    localStorage.setItem(`wanderly_currentStep_${room.id}${userKey}`, currentStep);
  }, [currentStep, room.id, userData?.id]);

  const getDefaultQuestionsForRoomType = (roomType, currency = '$', fromLocation = '', destination = '') => {
    // Transportation options are now fixed to Flight, Bus, Train as dropdown
    
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
          id: 'trans-trip-type',
          question_text: 'What type of trip?',
          question_type: 'buttons',
          options: ['One Way', 'Return'],
          order: 1,
          section: 'general',
          question_key: 'trip_type'
        },
        {
          id: 'trans-departure-budget',
          question_text: 'What is your departure transportation budget range?',
          question_type: 'range',
          min_value: 0,
          max_value: 2000,
          step: 50,
          currency: currency,
          order: 2,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'departure_common',
          question_key: 'departure_budget'
        },
        {
          id: 'trans-return-budget',
          question_text: 'What is your return transportation budget range?',
          question_type: 'range',
          min_value: 0,
          max_value: 2000,
          step: 50,
          currency: currency,
          order: 3,
          section: 'return',
          trip_leg: 'return',
          visibility_condition: 'return_return',
          question_key: 'return_budget'
        },
        // One-way questions
        {
          id: 'trans-oneway-1',
          question_text: 'What transportation methods do you prefer?',
          question_type: 'dropdown',
          options: ['Flight', 'Bus', 'Train'],
          order: 2,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'one_way'
        },
        {
          id: 'trans-oneway-2',
          question_text: 'What is your preferred departure date?',
          question_type: 'date',
          placeholder: 'Select your departure date',
          order: 3,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'one_way'
        },
        {
          id: 'trans-oneway-3',
          question_text: 'Any specific transportation preferences?',
          question_type: 'text',
          placeholder: 'e.g., direct flights only, eco-friendly options, luxury transport...',
          order: 4,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'one_way'
        },
        // Return trip departure questions
        {
          id: 'trans-return-dep-1',
          question_text: 'What transportation methods do you prefer for departing?',
          question_type: 'dropdown',
          options: ['Flight', 'Bus', 'Train'],
          order: 5,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'return_departure'
        },
        {
          id: 'trans-return-dep-2',
          question_text: 'What is your preferred departure date?',
          question_type: 'date',
          placeholder: 'Select your departure date',
          order: 6,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'return_departure'
        },
        {
          id: 'trans-return-dep-3',
          question_text: 'Any specific transportation preferences for travelling while departing?',
          question_type: 'text',
          placeholder: 'e.g., direct flights only, eco-friendly options, luxury transport...',
          order: 7,
          section: 'departure',
          trip_leg: 'departure',
          visibility_condition: 'return_departure'
        },
        // Return trip return-leg questions
        {
          id: 'trans-return-leg-1',
          question_text: 'What transportation methods do you prefer for returning?',
          question_type: 'dropdown',
          options: ['Flight', 'Bus', 'Train'],
          order: 8,
          section: 'return',
          trip_leg: 'return',
          visibility_condition: 'return_return'
        },
        {
          id: 'trans-return-leg-2',
          question_text: 'What is your preferred return date?',
          question_type: 'date',
          placeholder: 'Select your return date',
          order: 9,
          section: 'return',
          trip_leg: 'return',
          visibility_condition: 'return_return'
        },
        {
          id: 'trans-return-leg-3',
          question_text: 'Any specific transportation preferences for travelling while returning?',
          question_type: 'text',
          placeholder: 'e.g., direct flights only, eco-friendly options, luxury transport...',
          order: 10,
          section: 'return',
          trip_leg: 'return',
          visibility_condition: 'return_return'
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

  const loadRoomData = async ({ skipQuestionFetch = false } = {}) => {
    try {
      setLoading(true);
      
      // FIRST: Get from_location and destination for correct currency and travel type (use passed group prop or fetch)
      let currency = '$';
      let fromLocation = '';
      let destination = '';
      try {
        if (group) {
          // Use group prop if available (faster, no API call needed)
          fromLocation = group.from_location || '';
          destination = group.destination || '';
        } else if (room.group_id) {
          // Fallback: fetch group data if not passed as prop
          const groupData = await apiService.getGroup(room.group_id);
          fromLocation = groupData?.from_location || '';
          destination = groupData?.destination || '';
        }
        currency = getCurrencyFromLocation(fromLocation);
      } catch (groupErr) {
        console.error('Error getting group data:', groupErr);
        // Continue with default currency
      }
      
      // IMMEDIATE: Show preset default questions instantly with correct currency and transportation options
      const defaultQuestions = getDefaultQuestionsForRoomType(room.room_type, currency, fromLocation, destination);
      if (defaultQuestions.length > 0) {
        // Deduplicate default questions by ID and question_text
        const seen = new Set();
        const uniqueDefaults = defaultQuestions.filter((question) => {
          const id = question.id || '';
          const dedupKey = getQuestionDedupKey(question);
          const key = `${id}|${dedupKey}`;
          if (seen.has(key)) {
            return false;
          }
          seen.add(key);
          return true;
        });
        updateQuestionsState(uniqueDefaults, false);
        setLoading(false); // Stop loading immediately - questions are shown
      }
      
      if (!skipQuestionFetch) {
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
                      const id = question.id || '';
                      const key = getQuestionDedupKey(question);
                      if (seenTexts.has(key) || (id && seenIds.has(id))) {
                        return false;
                      }
                      seenTexts.add(key);
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
                    
                    // Filter transportation options to only Flight, Bus, Train and change to dropdown
                    let processedQuestions = finalQuestions.map((question) => {
                      if (question.question_text && 
                          question.question_text.toLowerCase().includes('transportation methods do you prefer')) {
                        return {
                          ...question,
                          question_type: 'dropdown',
                          options: ['Flight', 'Bus', 'Train']
                        };
                      }
                      return question;
                    });
                    
                    const sorted = processedQuestions.slice().sort((a, b) => {
                      const orderA = a.order !== undefined ? a.order : 999;
                      const orderB = b.order !== undefined ? b.order : 999;
                      if (orderA !== orderB) return orderA - orderB;
                      return (a.id || '').localeCompare(b.id || '');
                    });
                    updateQuestionsState(sorted);
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
                    const id = question.id || '';
                    const key = getQuestionDedupKey(question);
                    if (seenTexts.has(key) || (id && seenIds.has(id))) {
                      return false;
                    }
                    seenTexts.add(key);
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
                  
                  // Filter transportation options to only Flight, Bus, Train and change to dropdown
                  let processedQuestions = finalQuestions.map((question) => {
                    if (question.question_text && 
                        question.question_text.toLowerCase().includes('transportation methods do you prefer')) {
                      return {
                        ...question,
                        question_type: 'dropdown',
                        options: ['Flight', 'Bus', 'Train']
                      };
                    }
                    return question;
                  });
                  
                  const sorted = processedQuestions.slice().sort((a, b) => {
                    const orderA = a.order !== undefined ? a.order : 999;
                    const orderB = b.order !== undefined ? b.order : 999;
                    if (orderA !== orderB) return orderA - orderB;
                    return (a.id || '').localeCompare(b.id || '');
                  });
                  updateQuestionsState(sorted);
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
                        const id = question.id || '';
                    const key = getQuestionDedupKey(question);
                    if (seenTexts.has(key) || (id && seenIds.has(id))) {
                          return false;
                        }
                    seenTexts.add(key);
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
                      updateQuestionsState(sorted);
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
              let uniqueQuestions = questionsData.filter((question) => {
                const id = question.id || '';
                const key = getQuestionDedupKey(question);
                
                // If we've seen this exact text OR this ID before, skip it
                if (seenTexts.has(key) || (id && seenIds.has(id))) {
                  return false;
                }
                seenTexts.add(key);
                if (id) seenIds.add(id);
                return true;
              });
              
              // Filter transportation options to only Flight, Bus, Train and change to dropdown
              uniqueQuestions = uniqueQuestions.map((question) => {
                if (question.question_text && 
                    question.question_text.toLowerCase().includes('transportation methods do you prefer')) {
                  return {
                    ...question,
                    question_type: 'dropdown',
                    options: ['Flight', 'Bus', 'Train']
                  };
                }
                return question;
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
              
              // Filter transportation options to only Flight, Bus, Train and change to dropdown
              let processedQuestions = finalQuestions.map((question) => {
                if (question.question_text && 
                    question.question_text.toLowerCase().includes('transportation methods do you prefer')) {
                  return {
                    ...question,
                    question_type: 'dropdown',
                    options: ['Flight', 'Bus', 'Train']
                  };
                }
                return question;
              });
              
              const stableSorted = processedQuestions.slice().sort((a, b) => {
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
                  updateQuestionsState(stableSorted); // Update with API questions (may have currency)
                }
              }
            }
          }
        } catch (fetchErr) {
          console.error('Error fetching questions:', fetchErr);
          // If fetch fails, defaults are already shown - create in background
          apiService.createQuestionsForRoom(room.id).catch(() => {}); // Silent fail
        }
      }
      
      // Load answers and suggestions in parallel (non-blocking)
      // IMPORTANT: Only load current user's answers, not all users' answers
      const currentUserId = apiService.userId || userData?.id;
      
      Promise.all([
        // Only load answers if we have a user ID
        currentUserId 
          ? apiService.getUserAnswers(room.id, currentUserId).then(answersData => {
              // Only update answers if user is not currently editing
              // This prevents API responses from clearing user input
              if (!isEditingAnswers) {
                setAnswers(prev => {
                  const answersMap = { ...prev };
                  // Only load answers for the current user
                  // Filter to ensure we only use answers from the current user
                  const userAnswers = Array.isArray(answersData) 
                    ? answersData.filter(answer => answer.user_id === currentUserId || !answer.user_id)
                    : [];
                  
                  // Only merge answers from API that don't conflict with user's current answers
                  userAnswers.forEach(answer => {
                    const questionId = answer.question_id;
                    const existingAnswer = answersMap[questionId];
                    
                    // Only update if:
                    // 1. We don't have an answer for this question yet, OR
                    // 2. The existing answer is empty/undefined/null
                    const shouldUpdate = !existingAnswer || 
                      (!existingAnswer.answer_value && 
                       existingAnswer.min_value == null && 
                       existingAnswer.max_value == null);
                    
                    if (shouldUpdate) {
                      answersMap[questionId] = withQuestionMetadata(questionId, answer);
                    }
                    // Otherwise, preserve the user's current answer (don't overwrite)
                  });
                  return answersMap;
                });
              }
            }).catch((err) => {
              console.error('Error loading user answers:', err);
              // Only clear answers if user is not editing and no user ID
              if (!isEditingAnswers && !currentUserId) {
                // Don't clear - preserve user's current answers if they exist
              }
            })
          : Promise.resolve(), // Skip loading if no user ID
        
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
    setIsEditingAnswers(true);
    const currentUserId = apiService.userId || userData?.id;
    setAnswers(prev => {
      const answerValue = typeof value === 'object' && value !== null ? value : value;
      let baseAnswer = {
        question_id: questionId,
        answer_value: answerValue,
        answer_text: typeof value === 'string' ? value : null,
        user_id: currentUserId,
        room_id: room.id
      };

      if (typeof value === 'object' && value !== null && value.min_value !== undefined) {
        baseAnswer = {
          ...baseAnswer,
          min_value: value.min_value,
          max_value: value.max_value
        };
      }

      const newAnswer = withQuestionMetadata(questionId, baseAnswer);

      if (newAnswer.question_key === 'trip_type') {
        const normalized = (value || '').toString().toLowerCase();
        setTripTypeSelection(normalized);
      }

      return {
        ...prev,
        [questionId]: newAnswer
      };
    });
  };

  const handleMultipleSelection = (questionId, option) => {
    setIsEditingAnswers(true); // Mark that user is editing to prevent API overwrites
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
      
      const baseAnswer = {
        question_id: questionId,
        answer_value: newValues,
        answer_text: null,
        user_id: apiService.userId || userData?.id,
        room_id: room.id
      };

      const newAnswer = withQuestionMetadata(questionId, baseAnswer);
      return {
        ...prev,
        [questionId]: newAnswer
      };
    });
  };

  const handleSubmitAnswers = async () => {
    try {
      setLoading(true);
      setError(''); // Clear any previous errors
      
      // Validate that we have answers to submit
      const validAnswers = Object.entries(answers).filter(([, answer]) => 
        answer && answer.answer_value !== undefined && answer.answer_value !== null
      );
      
      if (validAnswers.length === 0) {
        setError('Please answer at least one question before submitting.');
        setLoading(false);
        return;
      }
      
      // Validate user is authenticated
      if (!apiService.userId && !userData?.id) {
        setError('User not authenticated. Please refresh the page and try again.');
        setLoading(false);
        return;
      }
      
      // Submit all answers
      const submitPromises = validAnswers.map(([, answer]) => 
        apiService.submitAnswer(room.id, answer).catch(err => {
          console.error(`Failed to submit answer for question ${answer.question_id}:`, err);
          throw err; // Re-throw to be caught by outer catch
        })
      );
      
      await Promise.all(submitPromises);
      
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
      
      // Provide more helpful error messages
      let errorMessage = 'Failed to submit answers: ';
      if (error.message && error.message.includes('Cannot connect to server')) {
        errorMessage += 'Backend server is not running. Please start the backend server and try again.';
      } else if (error.message && error.message.includes('User not authenticated')) {
        errorMessage += 'Please refresh the page and try again.';
      } else if (error.message) {
        errorMessage += error.message;
      } else {
        errorMessage += 'Unknown error. Please check your connection and try again.';
      }
      
      setError(errorMessage);
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
      
      // Check if this is a return trip
      const isReturnTrip = tripTypeSelection === 'return';
      
      if (isReturnTrip && suggestionsData.length > 0) {
        console.log('Processing return trip suggestions:', suggestionsData);
        
        // Separate suggestions by trip_leg and ensure proper tagging
        const departureSuggestions = suggestionsData
          .filter(s => {
            const leg = s.trip_leg || s.leg_type;
            return leg === 'departure' || (!leg); // Include items without leg as departure
          })
          .map(s => ({ 
            ...s, 
            trip_leg: 'departure', 
            leg_type: 'departure', 
            userVote: null 
          }));
        
        const returnSuggestions = suggestionsData
          .filter(s => {
            const leg = s.trip_leg || s.leg_type;
            return leg === 'return';
          })
          .map(s => ({ 
            ...s, 
            trip_leg: 'return', 
            leg_type: 'return', 
            userVote: null 
          }));
        
        console.log('Departure suggestions:', departureSuggestions);
        console.log('Return suggestions:', returnSuggestions);
        
        // Store both sets separately
        setAllSuggestions({ departure: departureSuggestions, return: returnSuggestions });
        
        // Show both sets together for voting
        setSuggestions([...departureSuggestions, ...returnSuggestions]);
        setCurrentLeg('both');
      } else {
        // One-way trip - mark all as departure
        const oneWaySuggestions = suggestionsData.map(s => ({ 
          ...s, 
          trip_leg: 'departure', 
          leg_type: 'departure',
          userVote: null 
        }));
        setSuggestions(oneWaySuggestions);
        setAllSuggestions({ departure: oneWaySuggestions, return: [] });
        setCurrentLeg(null);
      }
      
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
  
  const confirmDepartureSelections = async () => {
    try {
      setLoading(true);
      
      // Get selected departure suggestions (only those with userVote === 'up' that user actually clicked)
      // Filter to ensure we only get suggestions from the current departure leg
      const departureSelections = suggestions
        .filter(s => {
          // Only include suggestions that are actually liked AND are departure leg
          const isLiked = s.userVote === 'up';
          const isDeparture = (s.trip_leg === 'departure' || s.leg_type === 'departure') || 
                             (!s.trip_leg && !s.leg_type && currentLeg === 'departure');
          return isLiked && isDeparture;
        })
        .map(s => {
          // Ensure we have all required fields
          return {
            id: s.id,
            suggestion_id: s.id || s.suggestion_id,
            name: s.name || s.title || s.train_name || s.airline || s.operator || 'Unknown',
            title: s.title || s.name,
            description: s.description,
            price: s.price || s.price_range,
            rating: s.rating,
            trip_leg: 'departure',
            leg_type: 'departure',
            ...s // Include all other fields
          };
        });
      
      console.log('Departure selections to save:', departureSelections);
      
      if (departureSelections.length === 0) {
        alert('Please select at least one departure option before proceeding.');
        setLoading(false);
        return;
      }
      
      // Save departure selections to room (this updates the dashboard in background)
      await apiService.saveRoomSelections(room.id, departureSelections);
      
      alert(`${departureSelections.length} departure selections saved! Now select your return trip options.`);
      
      // Now show return suggestions
      const returnSuggestions = allSuggestions.filter(s => 
        s.trip_leg === 'return' || s.leg_type === 'return'
      );
      
      // Clear votes for return suggestions (start fresh)
      const returnSuggestionsWithClearedVotes = returnSuggestions.map(s => ({ ...s, userVote: null }));
      
      setSuggestions(returnSuggestionsWithClearedVotes);
      setCurrentLeg('return');
      
    } catch (error) {
      console.error('Error confirming departure selections:', error);
      setError(`Failed to save departure selections: ${error.message}`);
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
      
      // Update local state to show the vote in both suggestions and allSuggestions
      setSuggestions(prev => prev.map(suggestion => 
        suggestion.id === suggestionId 
          ? { ...suggestion, userVote: voteType }
          : suggestion
      ));
      
      // Also update allSuggestions if it's a return trip
      if (tripTypeSelection === 'return') {
        setAllSuggestions(prev => ({
          departure: prev.departure.map(s => 
            s.id === suggestionId ? { ...s, userVote: voteType } : s
          ),
          return: prev.return.map(s => 
            s.id === suggestionId ? { ...s, userVote: voteType } : s
          )
        }));
      }
      
      // Vote submitted successfully
    } catch (error) {
      console.error('Error submitting vote:', error);
      setError(`Failed to submit vote: ${error.message}`);
    }
  };

  const handleLockSuggestions = async () => {
    try {
      setLoading(true);
      
      // Find all liked suggestions (those with userVote === 'up')
      const likedSuggestions = suggestions.filter(suggestion => 
        suggestion.userVote === 'up'
      );
      
      if (likedSuggestions.length === 0) {
        alert('No liked suggestions to lock. Please like some suggestions first.');
        setLoading(false);
        return;
      }
      
      // For return trips, save both departure and return selections separately
      if (isTransportationRoom && tripTypeSelection === 'return') {
        // Separate into departure and return selections
        const departureSelections = likedSuggestions
          .filter(s => {
            const leg = s.trip_leg || s.leg_type;
            return leg === 'departure' || !leg; // Include items without leg as departure
          })
          .map(s => ({
            id: s.id,
            suggestion_id: s.id || s.suggestion_id,
            name: s.name || s.title || s.train_name || s.airline || s.operator || 'Unknown',
            title: s.title || s.name,
            description: s.description,
            price: s.price || s.price_range,
            rating: s.rating,
            trip_leg: 'departure',
            leg_type: 'departure',
            ...s
          }));
        
        const returnSelections = likedSuggestions
          .filter(s => {
            const leg = s.trip_leg || s.leg_type;
            return leg === 'return';
          })
          .map(s => ({
            id: s.id,
            suggestion_id: s.id || s.suggestion_id,
            name: s.name || s.title || s.train_name || s.airline || s.operator || 'Unknown',
            title: s.title || s.name,
            description: s.description,
            price: s.price || s.price_range,
            rating: s.rating,
            trip_leg: 'return',
            leg_type: 'return',
            ...s
          }));
        
        // Save both sets of selections
        const allSelections = [...departureSelections, ...returnSelections];
        await apiService.saveRoomSelections(room.id, allSelections);
        
        alert(`${departureSelections.length} departure and ${returnSelections.length} return selections saved!`);
        
        // Mark room as complete
        await markRoomComplete();
      } else {
        // One-way trip or other room types - normal flow
        const oneWaySelections = likedSuggestions.map(s => ({
          ...s,
          trip_leg: 'departure',
          leg_type: 'departure'
        }));
        await apiService.saveRoomSelections(room.id, oneWaySelections);
        alert(`${likedSuggestions.length} liked suggestions locked! All members can now see the consolidated results.`);
      }
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

  const shouldDisplayQuestion = (question) => {
    if (!isTransportationRoom) {
      return true;
    }
    const condition = question.visibility_condition;
    if (!condition) {
      return true;
    }
    if (!tripTypeSelection) {
      return false;
    }
    if (condition === 'one_way') {
      return tripTypeSelection.startsWith('one');
    }
    if (condition === 'return_departure' || condition === 'return_return') {
      return tripTypeSelection === 'return';
    }
    return true;
  };

  const renderQuestions = () => {
    // Rendering questions
    const visibleQuestions = questions.filter(shouldDisplayQuestion);
    let lastSection = null;

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

        {isTransportationRoom && !tripTypeSelection && (
          <div className="trip-type-hint" style={{ marginBottom: '1rem', color: '#666' }}>
            Select <strong>One Way</strong> or <strong>Return</strong> to see the detailed travel questions.
          </div>
        )}

        {visibleQuestions.map((question, index) => {
          const section = question.section;
          // Show section header only once per section for return trips
          // Show "Departure Travel Preferences" before the first departure question
          // Show "Return Travel Preferences" before the first return question
          const isFirstQuestionInSection = 
            isTransportationRoom &&
            tripTypeSelection === 'return' &&
            section &&
            ['departure', 'return'].includes(section) &&
            section !== lastSection;
          
          // Show header before the first question of each section (including budget questions)
          const showSectionHeader = isFirstQuestionInSection;

          if (showSectionHeader) {
            lastSection = section;
          }

          return (
            <Fragment key={question.id}>
              {showSectionHeader && (
                <div
                  className="trip-section-divider"
                  style={{
                    marginTop: '1.5rem',
                    marginBottom: '0.75rem',
                    fontWeight: 600,
                    color: section === 'departure' ? '#2c7be5' : '#d35400'
                  }}
                >
                  {section === 'departure' ? 'Departure Travel Preferences' : 'Return Travel Preferences'}
                </div>
              )}

              <div className="question-card">
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
                    value={(() => {
                      const minVal = answers[question.id]?.min_value;
                      return minVal != null ? String(minVal) : '';
                    })()}
                    onChange={(e) => {
                      const value = e.target.value;
                      setIsEditingAnswers(true); // Mark that user is editing
                      const currentUserId = apiService.userId || userData?.id;
                      // Allow empty string, numbers, and backspace - update immediately
                      if (value === '' || /^\d+$/.test(value)) {
                        const newMin = value === '' ? null : parseInt(value, 10);
                        // Use functional update to ensure we have latest state and preserve ALL other answers
                        setAnswers(prev => {
                          const prevAnswer = prev[question.id] || {};
                          const baseAnswer = {
                            ...prevAnswer,
                            question_id: question.id,
                            user_id: currentUserId,
                            room_id: room.id,
                            min_value: newMin,
                            max_value: prevAnswer.max_value ?? null,
                            answer_value: { min_value: newMin, max_value: prevAnswer.max_value ?? null }
                          };
                          return {
                            ...prev,
                            [question.id]: withQuestionMetadata(question.id, baseAnswer)
                          };
                        });
                      }
                    }}
                    onBlur={() => {
                      // Mark that editing is complete after a short delay
                      setTimeout(() => setIsEditingAnswers(false), 100);
                    }}
                    onFocus={() => {
                      setIsEditingAnswers(true);
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
                    value={(() => {
                      const maxVal = answers[question.id]?.max_value;
                      return maxVal != null ? String(maxVal) : '';
                    })()}
                    onChange={(e) => {
                      const value = e.target.value;
                      setIsEditingAnswers(true); // Mark that user is editing
                      const currentUserId = apiService.userId || userData?.id;
                      // Allow empty string, numbers, and backspace - update immediately
                      if (value === '' || /^\d+$/.test(value)) {
                        const newMax = value === '' ? null : parseInt(value, 10);
                        // Use functional update to ensure we have latest state and preserve ALL other answers
                        setAnswers(prev => {
                          const prevAnswer = prev[question.id] || {};
                          const baseAnswer = {
                            ...prevAnswer,
                            question_id: question.id,
                            user_id: currentUserId,
                            room_id: room.id,
                            min_value: prevAnswer.min_value ?? null,
                            max_value: newMax,
                            answer_value: { min_value: prevAnswer.min_value ?? null, max_value: newMax }
                          };
                          return {
                            ...prev,
                            [question.id]: withQuestionMetadata(question.id, baseAnswer)
                          };
                        });
                      }
                    }}
                    onBlur={() => {
                      // Mark that editing is complete after a short delay
                      setTimeout(() => setIsEditingAnswers(false), 100);
                    }}
                    onFocus={() => {
                      setIsEditingAnswers(true);
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
          
          {question.question_type === 'dropdown' && (
            <select
              value={answers[question.id]?.answer_value || ''}
              onChange={(e) => {
                setIsEditingAnswers(true);
                handleAnswerChange(question.id, e.target.value);
              }}
              onFocus={() => setIsEditingAnswers(true)}
              onBlur={() => setTimeout(() => setIsEditingAnswers(false), 100)}
              className="dropdown-input"
            >
              <option value="">Select an option</option>
              {question.options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
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
                        setIsEditingAnswers(true); // Mark that user is editing
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
              onChange={(e) => {
                setIsEditingAnswers(true); // Mark that user is editing
                handleAnswerChange(question.id, e.target.value);
              }}
              onFocus={() => setIsEditingAnswers(true)}
              onBlur={() => setTimeout(() => setIsEditingAnswers(false), 100)}
              placeholder={question.placeholder || question.question_text}
              className="text-input"
              rows="3"
            />
          )}
          
          {question.question_type === 'date' && (
            <input
              type="date"
              value={answers[question.id]?.answer_text || ''}
              onChange={(e) => {
                setIsEditingAnswers(true); // Mark that user is editing
                handleAnswerChange(question.id, e.target.value);
              }}
              onFocus={() => setIsEditingAnswers(true)}
              onBlur={() => setTimeout(() => setIsEditingAnswers(false), 100)}
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
            </Fragment>
          );
        })}
      
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

  const renderSuggestions = () => {
    const isReturnTrip = tripTypeSelection === 'return';
    
    // For return trips, use allSuggestions if available, otherwise filter from suggestions
    let departureSuggestions = [];
    let returnSuggestions = [];
    
    if (isReturnTrip) {
      if (allSuggestions.departure && allSuggestions.departure.length > 0) {
        departureSuggestions = allSuggestions.departure;
      } else {
        // Fallback: filter from current suggestions
        departureSuggestions = suggestions.filter(s => {
          const leg = s.trip_leg || s.leg_type;
          return leg === 'departure' || !leg;
        });
      }
      
      if (allSuggestions.return && allSuggestions.return.length > 0) {
        returnSuggestions = allSuggestions.return;
      } else {
        // Fallback: filter from current suggestions
        returnSuggestions = suggestions.filter(s => {
          const leg = s.trip_leg || s.leg_type;
          return leg === 'return';
        });
      }
      
      console.log('Rendering - Departure:', departureSuggestions.length, 'Return:', returnSuggestions.length);
    }
    
    const renderSuggestionCard = (suggestion) => {
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
    };

    return (
      <div className="suggestions-section">
        {isReturnTrip ? (
          <>
            {/* Departure Section */}
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ color: '#2c7be5', marginBottom: '1rem' }}>Departure Travel Suggestions</h2>
              <p style={{ color: '#666', marginBottom: '1rem' }}>
                Select your preferred departure options based on your departure preferences.
              </p>
              <div className="suggestions-grid">
                {departureSuggestions.length > 0 ? (
                  departureSuggestions.map((suggestion) => renderSuggestionCard(suggestion))
                ) : (
                  <p style={{ color: '#999', fontStyle: 'italic' }}>No departure suggestions available</p>
                )}
              </div>
            </div>

            {/* Return Section */}
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ color: '#d35400', marginBottom: '1rem' }}>Return Travel Suggestions</h2>
              <p style={{ color: '#666', marginBottom: '1rem' }}>
                Select your preferred return options based on your return preferences.
              </p>
              <div className="suggestions-grid">
                {returnSuggestions.length > 0 ? (
                  returnSuggestions.map((suggestion) => renderSuggestionCard(suggestion))
                ) : (
                  <p style={{ color: '#999', fontStyle: 'italic' }}>No return suggestions available</p>
                )}
              </div>
            </div>
          </>
        ) : (
          <>
            <h2>AI-Powered Suggestions</h2>
            <div className="suggestions-grid">
              {suggestions.map((suggestion) => renderSuggestionCard(suggestion))}
            </div>
          </>
        )}
        
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
  };

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
