import { useState } from 'react';
import apiService from './api';

function TestConnection() {
  const [testResult, setTestResult] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const testBackendConnection = async () => {
    setIsLoading(true);
    setTestResult('Testing...');
    
    try {
      // Test the health endpoint (no auth required)
      const response = await fetch('/health');
      const data = await response.json();
      
      if (response.ok) {
        setTestResult(`✅ Backend connected! Status: ${data.status}`);
      } else {
        setTestResult(`❌ Backend error: ${data.detail || 'Unknown error'}`);
      }
    } catch (error) {
      setTestResult(`❌ Connection failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', margin: '20px', borderRadius: '8px' }}>
      <h3>Backend Connection Test</h3>
      <button 
        onClick={testBackendConnection} 
        disabled={isLoading}
        style={{ 
          padding: '10px 20px', 
          backgroundColor: '#007bff', 
          color: 'white', 
          border: 'none', 
          borderRadius: '4px',
          cursor: isLoading ? 'not-allowed' : 'pointer'
        }}
      >
        {isLoading ? 'Testing...' : 'Test Backend Connection'}
      </button>
      
      {testResult && (
        <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          {testResult}
        </div>
      )}
    </div>
  );
}

export default TestConnection;
