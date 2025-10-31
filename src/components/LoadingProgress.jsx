import React from 'react';

function LoadingProgress({ isLoading }) {
  if (!isLoading) return null;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      width: '100%'
    }}>
      <div style={{
        border: '4px solid rgba(255, 255, 255, 0.3)',
        borderTop: '4px solid white',
        borderRadius: '50%',
        width: '60px',
        height: '60px',
        animation: 'spin 1s linear infinite',
        marginBottom: '1.5rem'
      }}></div>
      
      <p style={{ 
        fontSize: '1rem', 
        fontWeight: 400,
        color: 'white',
        fontFamily: "'Trebuchet MS', 'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Arial, sans-serif",
        textAlign: 'center',
        margin: 0
      }}>
        wanderly is getting suggestions
      </p>
    </div>
  );
}

export default LoadingProgress;
