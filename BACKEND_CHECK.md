# Backend Deployment Check

## Quick Test

Try accessing these URLs in your browser:

1. **Health Check**: `https://wanderly-4mvr.vercel.app/health`
2. **Root Endpoint**: `https://wanderly-4mvr.vercel.app/`
3. **API Groups**: `https://wanderly-4mvr.vercel.app/api/groups`

## Expected Responses:

### Health Check (`/health`):
```json
{
  "status": "healthy",
  "service": "wanderly-backend",
  "version": "v2.4"
}
```

### Root (`/`):
```json
{
  "message": "Wanderly Group Trip Planner API",
  "status": "running"
}
```

## If Backend is Not Working:

1. **Check Vercel Dashboard**: Make sure your backend deployment is successful
2. **Check Logs**: Look for any deployment errors
3. **Environment Variables**: Ensure all required env vars are set
4. **Python Version**: Make sure Vercel is using the correct Python version

## Backend Vercel Configuration:

If you need to redeploy your backend, use the `backend-vercel.json` file I created with proper Python/FastAPI configuration.
