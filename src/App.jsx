import { useState, useEffect } from 'react'
import './App.css'
import CreateGroup from './CreateGroup'
import JoinGroup from './JoinGroup'
import GroupDashboard from './GroupDashboard'
import apiService from './api'
import planeImage from './assets/plane.png';
import landingImage from './assets/people.png';

function App() {
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const [showJoinGroup, setShowJoinGroup] = useState(false)
  const [createdGroup, setCreatedGroup] = useState(null)
  const [isCheckingProgress, setIsCheckingProgress] = useState(true)
  const [inviteCodeFromUrl, setInviteCodeFromUrl] = useState(null)

  // Load data from localStorage and check for saved progress on component mount
  useEffect(() => {
    const checkSavedProgress = async () => {
      try {
        // First, check URL parameters for group invite
        const urlParams = new URLSearchParams(window.location.search)
        const groupIdFromUrl = urlParams.get('group') || urlParams.get('invite')
        
        if (groupIdFromUrl) {
          // Try to load group from URL
          try {
            const groupData = await apiService.getGroup(groupIdFromUrl)
            if (groupData && groupData.id) {
              // Check if we have user data saved
              const savedUser = localStorage.getItem('wanderly_user_data')
              if (savedUser) {
                try {
                  const userData = JSON.parse(savedUser)
                  apiService.setUser(userData.userId, userData.userName, userData.userEmail)
                  setCreatedGroup({
                    ...groupData,
                    user_name: userData.userName,
                    user_email: userData.userEmail
                  })
                  setIsCheckingProgress(false)
                  return
                } catch (e) {
                  console.error('Error loading user data:', e)
                }
              }
              // If no saved user data, show join page with pre-filled invite code
              setInviteCodeFromUrl(groupIdFromUrl)
              setShowJoinGroup(true)
              setIsCheckingProgress(false)
              return
            }
          } catch (error) {
            console.error('Error loading group from URL:', error)
            // Continue to check localStorage
          }
        }

        // Check localStorage for saved group
        const savedGroup = localStorage.getItem('wanderly_createdGroup')
        if (savedGroup) {
          try {
            const parsedGroup = JSON.parse(savedGroup)
            
            // Verify the group still exists by calling API
            try {
              const verifiedGroup = await apiService.getGroup(parsedGroup.id)
              if (verifiedGroup && verifiedGroup.id) {
                // Group exists, check if we have user data
                const savedUser = localStorage.getItem('wanderly_user_data')
                if (savedUser) {
                  try {
                    const userData = JSON.parse(savedUser)
                    apiService.setUser(userData.userId, userData.userName, userData.userEmail)
                    setCreatedGroup({
                      ...verifiedGroup,
                      user_name: parsedGroup.user_name || userData.userName,
                      user_email: parsedGroup.user_email || userData.userEmail
                    })
                  } catch (e) {
                    console.error('Error loading user data:', e)
                    // Still set group, user can re-authenticate if needed
                    setCreatedGroup({
                      ...verifiedGroup,
                      user_name: parsedGroup.user_name,
                      user_email: parsedGroup.user_email
                    })
                  }
                } else {
                  // No user data but group exists - set group with saved user info
                  setCreatedGroup({
                    ...verifiedGroup,
                    user_name: parsedGroup.user_name,
                    user_email: parsedGroup.user_email
                  })
                }
              } else {
                // Group doesn't exist anymore, clear localStorage
                localStorage.removeItem('wanderly_createdGroup')
              }
            } catch (error) {
              console.error('Error verifying saved group:', error)
              // If verification fails, still try to use saved group
              // User will see error if group truly doesn't exist
              setCreatedGroup(parsedGroup)
            }
          } catch (error) {
            console.error('Error parsing saved group:', error)
            localStorage.removeItem('wanderly_createdGroup')
          }
        }
      } catch (error) {
        console.error('Error checking saved progress:', error)
      } finally {
        setIsCheckingProgress(false)
      }
    }

    checkSavedProgress()
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
    // Clear user data when going back to home
    apiService.clearUser();
  }


  // Show group dashboard if group is created
  if (createdGroup) {
    return <GroupDashboard 
      groupId={createdGroup.id} 
      userData={{
        id: apiService.userId,
        name: createdGroup.user_name,
        email: createdGroup.user_email
      }}
      onBack={handleBackToHome} 
    />
  }


  // Show join group page when triggered
  if (showJoinGroup) return <JoinGroup 
    onCancel={() => {
      setShowJoinGroup(false)
      setInviteCodeFromUrl(null)
    }} 
    onGroupJoined={(groupData) => {
      setInviteCodeFromUrl(null)
      handleGroupJoined(groupData)
    }}
    initialInviteCode={inviteCodeFromUrl}
  />

  // Only show the CreateGroup page when triggered
  if (showCreateGroup) return <CreateGroup onCancel={() => setShowCreateGroup(false)} onGroupCreated={handleGroupCreated} />

  // Show loading state while checking for saved progress
  if (isCheckingProgress) {
    return (
      <div className="app-container">
        <div className="left-half" style={{ backgroundImage: `url(${landingImage})` }}></div>
        <div className="right-half">
          <div className="app">
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
              <h1 className="title">Wanderly</h1>
              <p style={{ marginTop: '1rem', color: '#666' }}>Loading...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <div className="left-half" style={{ backgroundImage: `url(${landingImage})` }}></div>
      <div className="right-half">
        <div className="app">
          <h1 className="title">Wanderly</h1>
          <h2 className="subtitle">Your AI Powered Group Trip Planner</h2>

          <div className="hero">
            <div className="hero-text">
              <p>
                Transform group trip planning from chaos to collaboration.  <br />
                Our AI-powered platform helps you discover destinations,  
                find perfect accommodations, plan activities, and choose  
                dining experiences that everyone will love.
              </p>
            </div>

            <img src={planeImage} alt="Paper Plane" className="centered-plane-img" />

            <div className="buttons">
              <button className="btn btn-primary" onClick={() => setShowCreateGroup(true)}>Create New Group</button>
              <button className="btn btn-secondary" onClick={() => {
                // Check URL parameters for invite code
                const urlParams = new URLSearchParams(window.location.search)
                const groupIdFromUrl = urlParams.get('group') || urlParams.get('invite')
                if (groupIdFromUrl) {
                  setInviteCodeFromUrl(groupIdFromUrl)
                }
                setShowJoinGroup(true)
              }}>Join Existing Group</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
