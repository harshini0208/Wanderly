import { useState, useEffect } from 'react'
import './App.css'
import CreateGroup from './CreateGroup'
import JoinGroup from './JoinGroup'
import GroupDashboard from './GroupDashboard'
import TestSuggestions from './TestSuggestions'
import { UserProvider } from './UserContext'

function App() {
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [showJoinGroup, setShowJoinGroup] = useState(false)
  const [showTestSuggestions, setShowTestSuggestions] = useState(false)
  const [createdGroup, setCreatedGroup] = useState(null)

  // Load data from localStorage on component mount
  useEffect(() => {
    console.log('App useEffect - checking localStorage for group data')
    const savedGroup = localStorage.getItem('wanderly_createdGroup')
    console.log('Saved group from localStorage:', savedGroup)
    
    if (savedGroup) {
      try {
        const groupData = JSON.parse(savedGroup)
        console.log('Parsed group data:', groupData)
        // Validate that the group data has required fields
        if (groupData && groupData.group_id) {
          console.log('Valid group data found, setting createdGroup')
          setCreatedGroup(groupData)
        } else {
          console.error('Invalid group data in localStorage - missing group_id')
          localStorage.removeItem('wanderly_createdGroup')
        }
      } catch (error) {
        console.error('Error loading saved group:', error)
        localStorage.removeItem('wanderly_createdGroup')
      }
    } else {
      console.log('No saved group found in localStorage')
    }
  }, [])

  // Save data to localStorage whenever it changes
  useEffect(() => {
    if (createdGroup) {
      localStorage.setItem('wanderly_createdGroup', JSON.stringify(createdGroup))
    } else {
      localStorage.removeItem('wanderly_createdGroup')
    }
  }, [createdGroup])

  const handleGroupCreated = (groupData) => {
    setCreatedGroup(groupData);
    setShowCreateGroup(false);
  }

  const handleGroupJoined = (groupData) => {
    setCreatedGroup(groupData);
    setShowJoinGroup(false);
  }

  const handleBackToHome = () => {
    setCreatedGroup(null);
    setShowCreateGroup(false);
    setShowJoinGroup(false);
    setShowTestSuggestions(false);
  }

  // Function to clear all localStorage data
  const clearAllData = () => {
    console.log('Clearing all Wanderly data from localStorage')
    localStorage.removeItem('wanderly_createdGroup')
    localStorage.removeItem('wanderly_user')
    // Clear any group-specific data
    const keys = Object.keys(localStorage)
    keys.forEach(key => {
      if (key.startsWith('wanderly_')) {
        localStorage.removeItem(key)
      }
    })
    setCreatedGroup(null)
    setShowCreateGroup(false)
    setShowJoinGroup(false)
    setShowTestSuggestions(false)
  }


  // Show group dashboard if group is created and has valid data
  if (createdGroup && createdGroup.group_id) {
    return (
      <UserProvider>
        <GroupDashboard groupId={createdGroup.group_id} onBack={handleBackToHome} />
      </UserProvider>
    )
  }

  // Show test suggestions page when triggered
  if (showTestSuggestions) return <TestSuggestions onBack={handleBackToHome} />

  // Show join group page when triggered
  if (showJoinGroup) return (
    <UserProvider>
      <JoinGroup onCancel={() => setShowJoinGroup(false)} onGroupJoined={handleGroupJoined} />
    </UserProvider>
  )

  // Only show the CreateGroup page when triggered
  if (showCreateGroup) return (
    <UserProvider>
      <CreateGroup onCancel={() => setShowCreateGroup(false)} onGroupCreated={handleGroupCreated} />
    </UserProvider>
  )

  return (
    <UserProvider>
      <div className="app">
        <h1 className="title">Wanderly</h1>
        <h2 className="subtitle">YOUR AI POWERED GROUP TRIP PLANNER</h2>

        <div className="hero">
          <div className="hero-text">
            <p>
              Transform group trip planning from chaos to collaboration.  
              Our AI-powered platform helps you discover destinations,  
              find perfect accommodations, plan activities, and choose  
              dining experiences that everyone will love.
            </p>
          </div>

          {/* Replace with your actual plane image */}
          <img src="/plane.png" alt="Paper Plane" className="hero-img" />

          <div className="features">
            <div className="feature">AI-Powered – Smart suggestions</div>
            <div className="feature">Collaborative – Group decisions</div>
            <div className="feature">Complete Planning – Stay, travel, activities</div>
            <div className="feature">Consensus – Everyone&apos;s happy</div>
          </div>
        </div>

        <div className="buttons">
          <button className="btn" onClick={() => setShowCreateGroup(true)}>Start Planning Your Trip</button>
          <button className="btn" onClick={() => setShowJoinGroup(true)}>Join Existing Group</button>
          <button className="btn" onClick={() => setShowTestSuggestions(true)} style={{background: '#ff6b6b'}}>Test External Links</button>
          <button className="btn" onClick={clearAllData} style={{background: '#666', fontSize: '12px'}}>Clear All Data (Debug)</button>
        </div>
        
        {/* Debug info */}
        <div style={{marginTop: '20px', fontSize: '12px', color: '#666'}}>
          <div>Debug Info:</div>
          <div>createdGroup: {createdGroup ? JSON.stringify(createdGroup) : 'null'}</div>
          <div>localStorage group: {localStorage.getItem('wanderly_createdGroup') || 'null'}</div>
          <div>localStorage user: {localStorage.getItem('wanderly_user') || 'null'}</div>
        </div>
      </div>
    </UserProvider>
  )
}

export default App
