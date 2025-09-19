# Wanderly Setup Guide

This guide will walk you through setting up the Wanderly Group Trip Planner backend for your hackathon project.

## 🎯 Project Overview

**Wanderly** is an AI-powered group trip planner that helps friends and families collaboratively plan trips through interactive rooms and AI suggestions. It's perfect for Google's Gen AI hackathon!

### Key Features for Hackathon
- ✅ **Google AI Integration**: Uses Gemini for intelligent suggestions
- ✅ **Google Maps API**: Location services and place recommendations  
- ✅ **Firebase**: Real-time data and authentication
- ✅ **BigQuery**: Analytics and user behavior tracking
- ✅ **Innovative UX**: Interactive Q&A instead of free-form chat
- ✅ **Group Consensus**: AI-assisted decision making

## 🚀 Quick Setup (30 minutes)

### Step 1: Google Cloud Setup (10 minutes)

1. **Create Google Cloud Project**
   ```bash
   # Install gcloud CLI
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

2. **Enable Required APIs**
   ```bash
   gcloud services enable maps-backend.googleapis.com
   gcloud services enable generativelanguage.googleapis.com
   gcloud services enable bigquery.googleapis.com
   ```

3. **Create API Keys**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to "APIs & Services" > "Credentials"
   - Create API Key for Maps API
   - Create API Key for Generative AI API

### Step 2: Firebase Setup (10 minutes)

1. **Create Firebase Project**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Click "Create a project"
   - Enable Google Analytics (optional)

2. **Enable Firestore**
   - Go to "Firestore Database"
   - Click "Create database"
   - Choose "Start in test mode"

3. **Enable Authentication**
   - Go to "Authentication" > "Sign-in method"
   - Enable "Email/Password" or "Google"

4. **Generate Service Account**
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Download the JSON file

### Step 3: Backend Setup (10 minutes)

1. **Clone and Install**
   ```bash
   git clone <your-repo>
   cd Wanderly-1
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp env_example.txt .env
   # Edit .env with your credentials
   ```

3. **Run the Server**
   ```bash
   python main.py
   ```

4. **Test the API**
   ```bash
   curl http://localhost:8000/health
   ```

## 🔧 Detailed Configuration

### Environment Variables

Create a `.env` file with these values:

```env
# Google AI (Required)
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash

# Google Maps (Required)
GOOGLE_MAPS_API_KEY=your_maps_api_key

# Firebase (Required)
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_PRIVATE_KEY_ID=from_service_account_json
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=from_service_account_json
FIREBASE_CLIENT_ID=from_service_account_json

# BigQuery (Required)
GOOGLE_CLOUD_PROJECT_ID=your_gcp_project_id
BIGQUERY_DATASET_ID=wanderly_analytics

# App (Required)
SECRET_KEY=your_random_secret_key
```

### Firebase Service Account Setup

Extract these values from your Firebase service account JSON:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "your-private-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-client-email",
  "client_id": "your-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

### BigQuery Setup

Create the analytics dataset:

```sql
-- Run in BigQuery Console
CREATE SCHEMA IF NOT EXISTS `your_project_id.wanderly_analytics`;

CREATE TABLE IF NOT EXISTS `your_project_id.wanderly_analytics.user_actions` (
  user_id STRING,
  action STRING,
  metadata STRING,
  timestamp TIMESTAMP
);
```

## 🧪 Testing the Integration

### Test Google AI Integration

```python
# Test script
import os
from app.services.ai_service import AIService

ai = AIService()
suggestions = ai.generate_suggestions(
    room_type="stay",
    preferences={"budget": 2000, "type": "Hotel"},
    destination="Goa"
)
print(suggestions)
```

### Test Google Maps Integration

```python
# Test script
from app.services.maps_service import MapsService

maps = MapsService()
places = maps.search_places("hotels in Goa", "Goa, India")
print(places)
```

### Test Firebase Connection

```python
# Test script
from app.database import init_firebase

db = init_firebase()
print("Firebase connected successfully!")
```

## 🎨 Frontend Integration

Your frontend teammate can integrate with these endpoints:

### Authentication Flow
```javascript
// Frontend authentication
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';

const auth = getAuth();
const user = await signInWithEmailAndPassword(auth, email, password);
const token = await user.getIdToken();

// Use token in API calls
fetch('/api/groups/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

### Group Creation Flow
```javascript
// Create group
const group = await fetch('/api/groups/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: "Goa 2025 🌴",
    destination: "Goa, India",
    start_date: "2025-01-15T00:00:00Z",
    end_date: "2025-01-20T00:00:00Z"
  })
});

// Create rooms
await fetch(`/api/groups/${group.id}/rooms`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## 🚀 Deployment Options

### Option 1: Google Cloud Run (Recommended)

```bash
# Build and deploy
gcloud run deploy wanderly-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Option 2: Heroku

```bash
# Install Heroku CLI
heroku create wanderly-backend
heroku config:set GOOGLE_API_KEY=your_key
heroku config:set GOOGLE_MAPS_API_KEY=your_key
# ... set other env vars
git push heroku main
```

### Option 3: Railway

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

## 📊 Monitoring & Analytics

### BigQuery Analytics

The app automatically logs user actions. Query them:

```sql
-- Most popular destinations
SELECT 
  JSON_EXTRACT_SCALAR(metadata, '$.destination') as destination,
  COUNT(*) as trip_count
FROM `your_project.wanderly_analytics.user_actions`
WHERE action = 'group_created'
GROUP BY destination
ORDER BY trip_count DESC;

-- User engagement
SELECT 
  user_id,
  COUNT(*) as total_actions,
  COUNT(DISTINCT DATE(timestamp)) as active_days
FROM `your_project.wanderly_analytics.user_actions`
GROUP BY user_id
ORDER BY total_actions DESC;
```

## 🎯 Hackathon Presentation Tips

### Demo Flow
1. **Create Group**: Show group creation with invite link
2. **Join Group**: Demonstrate invite link functionality
3. **Interactive Planning**: Show Q&A widgets in each room
4. **AI Suggestions**: Highlight Gemini-powered recommendations
5. **Group Voting**: Demonstrate real-time voting system
6. **Consensus Building**: Show AI-assisted decision making
7. **Final Dashboard**: Display completed trip plan

### Key Points to Highlight
- **Google AI Integration**: Show how Gemini understands preferences
- **Google Maps Integration**: Highlight location-based suggestions
- **Real-time Collaboration**: Demonstrate live voting
- **Innovative UX**: Emphasize structured Q&A vs. free chat
- **Scalability**: Show Firebase + BigQuery architecture

### Technical Highlights
- **AI-Powered**: Uses Google's latest Gemini model
- **Real-time**: Firebase for instant updates
- **Analytics**: BigQuery for insights
- **Scalable**: Cloud-native architecture
- **Secure**: Firebase authentication

## 🆘 Troubleshooting

### Common Issues

1. **Firebase Connection Error**
   ```bash
   # Check service account JSON format
   # Ensure private key has proper newlines
   ```

2. **Google Maps API Error**
   ```bash
   # Verify API key has Maps API enabled
   # Check billing is enabled
   ```

3. **BigQuery Permission Error**
   ```bash
   # Ensure service account has BigQuery permissions
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
     --role="roles/bigquery.dataEditor"
   ```

4. **CORS Issues**
   ```python
   # Update CORS settings in main.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000"],  # Your frontend URL
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

## 📞 Support

If you encounter issues:

1. Check the logs: `python main.py` (verbose output)
2. Test individual services with the test scripts
3. Verify all environment variables are set
4. Check Google Cloud quotas and billing

## 🎉 Ready to Demo!

Your Wanderly backend is now ready for the hackathon! The combination of Google AI, Maps, Firebase, and BigQuery makes it a perfect showcase of Google's ecosystem.

**Good luck with your hackathon presentation! 🚀**


