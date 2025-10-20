# Wanderly - Group Trip Planner

A React-based frontend application for group trip planning, deployed on GitHub Pages.

## Features

- Create and join trip groups
- Plan activities and accommodations
- Vote on suggestions
- View trip results

## Run backand and frontend to test on localhost

```bash
# Run Backend
   cd backend
   export GOOGLE_APPLICATION_CREDENTIALS="firebase_service_account.json"
   python3 migrate_to_firebase.py

#Run Frontend
  npm run dev
```
## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Deployment to GitHub Pages

```bash
# Deploy to GitHub Pages
npm run deploy
```

The app will be available at: `https://harshinis.github.io/Wanderly-1`

## Project Structure

- `src/` - React frontend source code
- `public/` - Static assets
- `dist/` - Built files for deployment

## Note

This is currently a frontend-only deployment with mock API responses. Backend integration will be added in future updates.
