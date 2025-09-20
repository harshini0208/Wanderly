import { useState, useEffect } from 'react';
import apiService from './api';

function TestSuggestions({ onBack }) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadTestSuggestions();
  }, []);

  const loadTestSuggestions = async () => {
    try {
      setLoading(true);
      const testSuggestions = await apiService.getTestSuggestions();
      console.log('Test suggestions received:', testSuggestions);
      setSuggestions(testSuggestions);
    } catch (error) {
      console.error('Error loading test suggestions:', error);
      setError('Failed to load test suggestions');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Loading test suggestions...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <button 
        onClick={onBack}
        style={{
          background: '#1d2b5c',
          color: 'white',
          border: 'none',
          padding: '0.5rem 1rem',
          borderRadius: '4px',
          cursor: 'pointer',
          marginBottom: '1rem'
        }}
      >
        ← Back to Home
      </button>
      <h1>Test Suggestions with External URLs</h1>
      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
        {suggestions.map((suggestion, index) => (
          <div key={index} style={{ 
            border: '2px solid #1d2b5c', 
            padding: '1.5rem', 
            borderRadius: '8px',
            backgroundColor: 'white'
          }}>
            <h3>{suggestion.title}</h3>
            <p>{suggestion.description}</p>
            <p><strong>Price:</strong> ₹{suggestion.price} {suggestion.currency}</p>
            <div style={{ margin: '1rem 0' }}>
              <strong>Highlights:</strong>
              <ul>
                {suggestion.highlights.map((highlight, i) => (
                  <li key={i}>{highlight}</li>
                ))}
              </ul>
            </div>
            <div style={{ margin: '1rem 0' }}>
              <strong>External URL:</strong> {suggestion.external_url || 'None'}
            </div>
            {suggestion.external_url && (
              <a 
                href={suggestion.external_url} 
                target="_blank" 
                rel="noopener noreferrer"
                style={{
                  display: 'inline-block',
                  background: '#27ae60',
                  color: 'white',
                  padding: '0.5rem 1rem',
                  textDecoration: 'none',
                  borderRadius: '4px',
                  fontWeight: '600'
                }}
              >
                🔗 Explore More
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default TestSuggestions;
