import { useState } from 'react'
import './App.css'
import CreateGroup from './CreateGroup'
import JoinGroup from './JoinGroup'
import GroupDashboard from './GroupDashboard'

function App() {
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [showJoinGroup, setShowJoinGroup] = useState(false)
  const [createdGroup, setCreatedGroup] = useState(null)

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
  }

  const handleReset = () => {
    setCreatedGroup(null);
    setShowCreateGroup(false);
    setShowJoinGroup(false);
    // Clear any cached data
    localStorage.clear();
    sessionStorage.clear();
  }

  // Show group dashboard if group is created
  if (createdGroup) {
    return <GroupDashboard groupId={createdGroup.group_id} onBack={handleBackToHome} />
  }

  // Show join group page when triggered
  if (showJoinGroup) return <JoinGroup onCancel={() => setShowJoinGroup(false)} onGroupJoined={handleGroupJoined} />

  // Only show the CreateGroup page when triggered
  if (showCreateGroup) return <CreateGroup onCancel={() => setShowCreateGroup(false)} onGroupCreated={handleGroupCreated} />

  return (
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
        <button className="btn" onClick={handleReset} style={{background: '#ff6b6b', marginTop: '10px'}}>Reset App</button>
      </div>
    </div>
  )
}

export default App
