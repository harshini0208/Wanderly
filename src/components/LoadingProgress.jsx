import React, { useState, useEffect } from 'react';

const LOADING_STEPS = [
  { text: 'Getting AI suggestions...', duration: 2000 },
  { text: 'Getting AI suggestions...', duration: 2000 },
  { text: 'Getting AI suggestions...', duration: 2000 },
  { text: 'Getting AI suggestions...', duration: 1500 }
];

function LoadingProgress({ isLoading, text }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      setCurrentStep(0);
      setProgress(0);
      return;
    }

    // Progress bar animation
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 95) return prev; // Cap at 95% until actually done
        return prev + 1;
      });
    }, 100);

    // Step progression
    let stepTimeouts = [];
    let totalTime = 0;
    
    LOADING_STEPS.forEach((step, index) => {
      totalTime += step.duration;
      const timeout = setTimeout(() => {
        setCurrentStep(index);
      }, totalTime);
      stepTimeouts.push(timeout);
    });

    return () => {
      clearInterval(progressInterval);
      stepTimeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [isLoading]);

  useEffect(() => {
    if (!isLoading && progress < 100) {
      // Complete the progress when loading is done
      setProgress(100);
    }
  }, [isLoading]);

  if (!isLoading && progress === 0) return null;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '3rem',
      color: '#1d2b5c'
    }}>
      <div style={{
        border: '4px solid #f3f3f3',
        borderTop: '4px solid #1976D2',
        borderRadius: '50%',
        width: '60px',
        height: '60px',
        animation: 'spin 1s linear infinite',
        marginBottom: '1.5rem'
      }}></div>
      
      <p style={{ 
        fontSize: '1.2rem', 
        fontWeight: 700,
        marginBottom: '0.5rem',
        color: '#1976D2'
      }}>
        {text || LOADING_STEPS[currentStep]?.text || 'Processing...'}
      </p>
      
      <div style={{
        width: '100%',
        maxWidth: '400px',
        height: '8px',
        backgroundColor: '#e0e0e0',
        borderRadius: '4px',
        overflow: 'hidden',
        marginTop: '1rem'
      }}>
        <div style={{
          width: `${progress}%`,
          height: '100%',
          backgroundColor: '#1976D2',
          transition: 'width 0.3s ease',
          borderRadius: '4px'
        }}></div>
      </div>
      
      <p style={{
        fontSize: '0.9rem',
        color: '#666',
        marginTop: '1rem',
        textAlign: 'center',
        maxWidth: '400px'
      }}>
        This may take a few moments while we find the best options for you
      </p>
    </div>
  );
}

export default LoadingProgress;
