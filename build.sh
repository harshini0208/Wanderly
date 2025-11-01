#!/bin/bash

echo "🚀 Building Wanderly for Cloud Run deployment..."

# Step 1: Build frontend
echo "📦 Building frontend..."
npm run build

# Check if build succeeded
if [ ! -d "dist" ]; then
    echo "❌ Frontend build failed - dist folder not found"
    exit 1
fi

echo "✅ Frontend built successfully"

# Step 2: Deploy to Cloud Run
echo "☁️ Deploying to Google Cloud Run..."

gcloud run deploy wanderly \
    --source=backend \
    --platform=managed \
    --region=us-central1 \
    --allow-unauthenticated \
    --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest" \
    --memory=2Gi \
    --cpu=1 \
    --timeout=300 \
    --max-instances=10

echo "✅ Deployment complete!"
echo "🌐 Your app should be available at: https://wanderly-323958238334.us-central1.run.app"