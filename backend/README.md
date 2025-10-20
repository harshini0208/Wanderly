# Wanderly Backend

Python Flask backend for the Wanderly group trip planning application.

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the backend:**
   ```bash
   python app.py
   ```
   
   Or use the provided script:
   ```bash
   ./run.sh
   ```

3. **The backend will start on:** `http://localhost:5000`

## API Endpoints

### Groups
- `POST /api/groups/` - Create a new group
- `POST /api/groups/join` - Join an existing group
- `GET /api/groups/<group_id>` - Get group details
- `GET /api/groups/` - Get user's groups

### Health Check
- `GET /api/health` - Health check endpoint

## Environment Variables

Create a `.env` file with:
```
FLASK_ENV=development
PORT=5000
```

## Features

- **Create Group**: Users can create new travel groups with details like destination, dates, budget
- **Join Group**: Users can join existing groups using invite codes
- **CORS Enabled**: Frontend can communicate with the backend
- **In-memory Storage**: Currently uses in-memory storage (replace with database for production)

## Frontend Integration

The frontend is configured to connect to this backend at `http://localhost:5000/api`. Make sure both frontend and backend are running for full functionality.
