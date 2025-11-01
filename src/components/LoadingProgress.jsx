import React, { useState, useEffect } from 'react';
import apiService from '../api';

function LoadingProgress({ isLoading, destination = null }) {
  const [funFacts, setFunFacts] = useState([]);
  const [currentFactIndex, setCurrentFactIndex] = useState(0);
  const [loadingFacts, setLoadingFacts] = useState(true);

  useEffect(() => {
    if (!isLoading || !destination) return;

    // Fetch fun facts about the destination
    const fetchFunFacts = async () => {
      try {
        const response = await apiService.getDestinationFunFacts(destination);
        if (response.facts && Array.isArray(response.facts) && response.facts.length > 0) {
          setFunFacts(response.facts);
          setCurrentFactIndex(0);
        }
      } catch (error) {
        console.error('Error fetching fun facts:', error);
      } finally {
        setLoadingFacts(false);
      }
    };

    fetchFunFacts();
  }, [isLoading, destination]);

  // Rotate through facts every 4 seconds
  useEffect(() => {
    if (funFacts.length <= 1) return;

    const interval = setInterval(() => {
      setCurrentFactIndex((prevIndex) => (prevIndex + 1) % funFacts.length);
    }, 4000); // Change fact every 4 seconds

    return () => clearInterval(interval);
  }, [funFacts.length]);

  if (!isLoading) return null;

  const currentFact = funFacts[currentFactIndex] || '';

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      width: '100%',
      padding: '2rem'
    }}>
      <div style={{
        border: '4px solid rgba(255, 255, 255, 0.3)',
        borderTop: '4px solid white',
        borderRadius: '50%',
        width: '60px',
        height: '60px',
        animation: 'spin 1s linear infinite',
        marginBottom: '2rem'
      }}></div>
      
      <p style={{ 
        fontSize: '1rem', 
        fontWeight: 400,
        color: 'white',
        fontFamily: "'Trebuchet MS', 'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Arial, sans-serif",
        textAlign: 'center',
        marginBottom: '1.5rem',
        margin: '0 0 1.5rem 0'
      }}>
        wanderly is getting suggestions
      </p>

      {/* Fun Facts Section */}
      {destination && (
        <div style={{
          maxWidth: '500px',
          width: '100%',
          minHeight: '80px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          {loadingFacts && (
            <p style={{
              fontSize: '0.9rem',
              color: 'rgba(255, 255, 255, 0.8)',
              fontStyle: 'italic',
              textAlign: 'center'
            }}>
              Loading fun facts...
            </p>
          )}
          
          {!loadingFacts && currentFact && (
            <div style={{
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              borderRadius: '12px',
              padding: '1.5rem',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
              animation: 'fadeIn 0.5s ease-in'
            }}>
              <p style={{
                fontSize: '0.95rem',
                color: 'white',
                fontFamily: "'Trebuchet MS', 'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Arial, sans-serif",
                textAlign: 'center',
                lineHeight: '1.6',
                margin: 0
              }}>
                ✨ {currentFact}
              </p>
              
              {funFacts.length > 1 && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  gap: '8px',
                  marginTop: '1rem'
                }}>
                  {funFacts.map((_, index) => (
                    <div
                      key={index}
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: index === currentFactIndex 
                          ? 'rgba(255, 255, 255, 0.9)' 
                          : 'rgba(255, 255, 255, 0.3)',
                        transition: 'background-color 0.3s ease'
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

export default LoadingProgress;
