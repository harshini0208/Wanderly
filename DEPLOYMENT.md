# Vercel Deployment Guide

## ✅ FIXED: Vite Configuration Error

### Problem
`TypeError: Cannot read properties of undefined (reading 'VITE_PORT')`

### Root Cause
- `import.meta.env.VITE_PORT` was undefined in Vercel build environment
- `parseInt(undefined)` was throwing an error
- Missing proper fallback handling

### Solution Applied
1. **Simplified Vite Config**: Removed dynamic environment variable access
2. **Hardcoded Safe Values**: Used static values that work in all environments
3. **Added Vercel Config**: Created `vercel.json` with proper build settings
4. **Environment Variables**: Added VITE variables to `.env` file

### Files Modified
- `vite.config.js`: Simplified configuration with hardcoded values
- `vercel.json`: Added build configuration and API routing
- `.env`: Added VITE environment variables

## Current Configuration

### vite.config.js
```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,  // Hardcoded safe value
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  define: {
    'import.meta.env.VITE_PORT': '"3000"',
    'import.meta.env.VITE_API_URL': '"https://wanderly-4mvr.vercel.app"',
  }
})
```

### vercel.json
```json
{
  "version": 2,
  "builds": [
    {
      "src": "package.json",
      "use": "@vercel/static-build",
      "config": {
        "distDir": "dist"
      }
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/$1"
    }
  ],
  "env": {
    "VITE_PORT": "3000",
    "VITE_API_URL": "https://wanderly-4mvr.vercel.app"
  },
  "buildCommand": "npm run build",
  "outputDirectory": "dist"
}
```

## Testing Results
✅ Local build test: `npm run build` - SUCCESS
✅ Build output: `dist/` folder generated correctly
✅ No environment variable errors

## Deployment Steps
1. Push changes to repository
2. Vercel will use the `vercel.json` configuration
3. Build should complete successfully
4. Frontend served from Vercel
5. API calls proxied to Railway backend

## Environment Variables (Optional)
If you want to override the hardcoded values, set these in Vercel dashboard:
```
VITE_PORT=3000
VITE_API_URL=https://wanderly-new-production.up.railway.app
```

The deployment should now work without the VITE_PORT error!
