import { useState, useEffect } from 'react';
import './PlanningRoom.css';
import apiService from './api';

function PlanningRoom({ room, group, userData, onBack }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [suggestions, setSuggestions] = useState([]);
  const [currentStep, setCurrentStep] = useState('questions'); // questions, suggestions, voting
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [completionStatus, setCompletionStatus] = useState(null);
  const [userCompleted, setUserCompleted] = useState(false);
  const [userName, setUserName] = useState(userData?.name || '');
  const [userEmail, setUserEmail] = useState(userData?.email || '');

  useEffect(() => {
    console.log('PlanningRoom mounted with room:', room);
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

  const loadRoomData = async () => {
    try {
      setLoading(true);
      console.log('Loading room data for room ID:', room.id);
      
      // Load questions
      let questionsData = [];
      try {
        console.log('Fetching questions for room:', room.id);
        questionsData = await apiService.getRoomQuestions(room.id);
        console.log('Questions fetched successfully:', questionsData);
        
        // If no questions exist, create them
        if (questionsData.length === 0) {
          console.log('No questions found, creating default questions...');
          try {
            console.log('Creating questions for room:', room.id);
            const createResult = await apiService.createQuestionsForRoom(room.id);
            console.log('Questions creation result:', createResult);
            
            // Wait a moment for the questions to be created
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Fetch the newly created questions
            questionsData = await apiService.getRoomQuestions(room.id);
            console.log('Questions created and fetched:', questionsData);
          } catch (createErr) {
            console.error('Failed to create questions:', createErr);
            questionsData = [];
          }
        } else {
          console.log('Questions already exist, using existing ones');
        }
      } catch (err) {
        console.log('Error fetching questions, creating default questions...', err);
        // If there's an error fetching questions, create them
        try {
          console.log('Creating questions for room:', room.id);
          const createResult = await apiService.createQuestionsForRoom(room.id);
          console.log('Questions creation result:', createResult);
          
          // Wait a moment for the questions to be created
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          // Fetch the newly created questions
          questionsData = await apiService.getRoomQuestions(room.id);
          console.log('Questions created and fetched:', questionsData);
        } catch (createErr) {
          console.error('Failed to create questions:', createErr);
          questionsData = [];
        }
      }
      // Remove duplicate questions based on question_text
      const uniqueQuestions = questionsData.filter((question, index, self) => 
        index === self.findIndex(q => q.question_text === question.question_text)
      );
      
      setQuestions(uniqueQuestions);
      console.log('Questions loaded (deduplicated):', uniqueQuestions);
      
      // Load existing answers
      try {
        const answersData = await apiService.getRoomAnswers(room.id);
        const answersMap = {};
        answersData.forEach(answer => {
          answersMap[answer.question_id] = answer;
        });
        setAnswers(answersMap);
      } catch (err) {
        console.log('No answers found yet');
        setAnswers({});
      }
      
      // Load suggestions if they exist (but don't change step)
      try {
        const suggestionsData = await apiService.getRoomSuggestions(room.id);
        if (suggestionsData.length > 0) {
          setSuggestions(suggestionsData);
          // Don't automatically go to suggestions - let user answer questions first
        }
      } catch (err) {
        // No suggestions yet
      }
      
      // Always start with questions step
      setCurrentStep('questions');
      console.log('Current step set to:', 'questions');
      
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
      console.log('Marking room complete for room ID:', room.id);
      console.log('User name:', userName);
      console.log('User email:', userEmail);
      const result = await apiService.markRoomComplete(room.id, userName, userEmail);
      console.log('Mark room complete result:', result);
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
    setAnswers(prev => ({
      ...prev,
      [questionId]: {
        question_id: questionId,
        answer_value: value,
        answer_text: typeof value === 'string' ? value : null
      }
    }));
  };

  const handleSubmitAnswers = async () => {
    try {
      setLoading(true);
      console.log('Submitting answers for room:', room.id);
      console.log('Answers to submit:', answers);
      
      // Submit all answers
      for (const [questionId, answer] of Object.entries(answers)) {
        if (answer && answer.answer_value !== undefined) {
          console.log('Submitting answer for question:', questionId, answer);
          await apiService.submitAnswer(room.id, answer);
        }
      }
      
      // Generate suggestions
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
      setError('Failed to generate suggestions');
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async (suggestionId, voteType) => {
    try {
      console.log('Voting on suggestion:', suggestionId, voteType);
      console.log('Available suggestions:', suggestions.map(s => s.id));
      
      // Check if suggestion exists
      const suggestion = suggestions.find(s => s.id === suggestionId);
      if (!suggestion) {
        console.error('Suggestion not found:', suggestionId);
        setError('Suggestion not found');
        return;
      }
      
      const voteData = {
        suggestion_id: suggestionId,
        vote_type: voteType
      };
      
      console.log('Submitting vote with data:', voteData);
      await apiService.submitVote(voteData);
      
      // Update local state to show the vote
      setSuggestions(prev => prev.map(suggestion => 
        suggestion.id === suggestionId 
          ? { ...suggestion, userVote: voteType }
          : suggestion
      ));
      
      console.log('Vote submitted successfully');
    } catch (error) {
      console.error('Error submitting vote:', error);
      setError(`Failed to submit vote: ${error.message}`);
    }
  };

  const handleLockSuggestions = async () => {
    try {
      setLoading(true);
      
      console.log('All suggestions:', suggestions.map(s => ({ 
        id: s.id, 
        title: s.title, 
        userVote: s.userVote 
      })));
      
      // Find all liked suggestions (those with userVote === 'up')
      const likedSuggestions = suggestions.filter(suggestion => 
        suggestion.userVote === 'up'
      );
      
      console.log('Liked suggestions found:', likedSuggestions.length);
      
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
      if (error.message && error.message.includes('Only group creator can lock decisions')) {
        setError('Only the group creator can lock final decisions. Please ask the group creator to lock the suggestions.');
      } else {
        setError('Failed to lock suggestions');
      }
    } finally {
      setLoading(false);
    }
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
    console.log('Rendering questions, count:', questions.length);
    return (
      <div className="questions-section">
        <h2>Answer these questions to get personalized suggestions</h2>
        {questions.length === 0 && <p>No questions available</p>}
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
          
          {question.question_type === 'buttons' && (
            <div className="button-options">
              {question.options.map((option) => (
                <button
                  key={option}
                  className={`option-button ${answers[question.id]?.answer_value === option ? 'selected' : ''}`}
                  onClick={() => handleAnswerChange(question.id, option)}
                >
                  {option}
                </button>
              ))}
            </div>
          )}
          
          {question.question_type === 'text' && (
            <textarea
              value={answers[question.id]?.answer_text || ''}
              onChange={(e) => handleAnswerChange(question.id, e.target.value)}
              placeholder={question.question_text}
              className="text-input"
              rows="3"
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
          console.log('Suggestion data:', suggestion);
          console.log('External URL:', suggestion.external_url);
          return (
          <div key={suggestion.id} className="suggestion-card">
            <div className="suggestion-header">
              <h3>{suggestion.title}</h3>
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
              {suggestion.external_url ? (
                <a 
                  href={suggestion.external_url.startsWith('http') ? suggestion.external_url : `https://www.google.com/search?q=${encodeURIComponent(suggestion.title + ' ' + suggestion.location?.address || '')}`} 
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
                  🔗 Explore
                </a>
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
        {apiService.userId && group && group.created_by === apiService.userId && (
          <button 
            onClick={handleLockSuggestions}
            className="btn btn-success"
            style={{background: '#28a745', color: 'white'}}
          >
            🔒 Lock Final Decision
          </button>
        )}
        {apiService.userId && group && group.created_by !== apiService.userId && (
          <div style={{padding: '1rem', background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: '0.375rem', textAlign: 'center'}}>
            <p style={{margin: 0, color: '#6c757d'}}>
              Only the group creator can lock final decisions. 
              <br />
              Please ask the group creator to finalize the suggestions.
            </p>
          </div>
        )}
      </div>
    </div>
  );

  if (loading && currentStep === 'questions') {
    return (
      <div className="room-container">
        <div className="loading">Loading room data...</div>
        <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
      </div>
    );
  }

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
      <img src="/plane.png" alt="Paper Plane" className="corner-plane" />
    </div>
  );
}

export default PlanningRoom;
