#!/usr/bin/env python3
"""
Test script to verify all Google AI integrations are working correctly.
Run this after setting up your environment variables.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Test if all required environment variables are set"""
    print("🔍 Testing environment variables...")
    
    required_vars = [
        'GOOGLE_API_KEY',
        'GOOGLE_MAPS_API_KEY', 
        'FIREBASE_PROJECT_ID',
        'FIREBASE_PRIVATE_KEY',
        'FIREBASE_CLIENT_EMAIL',
        'GOOGLE_CLOUD_PROJECT_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All environment variables are set")
        return True

def test_google_ai():
    """Test Google AI (Gemini) integration"""
    print("\n🤖 Testing Google AI integration...")
    
    try:
        from app.services.ai_service import AIService
        
        ai_service = AIService()
        
        # Test suggestion generation
        suggestions = ai_service.generate_suggestions(
            room_type="stay",
            preferences={
                "budget": 2000,
                "type": "Hotel",
                "location": "Beachside"
            },
            destination="Goa, India"
        )
        
        if suggestions and len(suggestions) > 0:
            print(f"✅ Google AI working! Generated {len(suggestions)} suggestions")
            print(f"   Sample: {suggestions[0].get('title', 'N/A')}")
            return True
        else:
            print("❌ Google AI returned no suggestions")
            return False
            
    except Exception as e:
        print(f"❌ Google AI error: {str(e)}")
        return False

def test_google_maps():
    """Test Google Maps API integration"""
    print("\n🗺️ Testing Google Maps integration...")
    
    try:
        from app.services.maps_service import MapsService
        
        maps_service = MapsService()
        
        # Test place search
        places = maps_service.search_places("hotels in Goa", "Goa, India")
        
        if places and len(places) > 0:
            print(f"✅ Google Maps working! Found {len(places)} places")
            print(f"   Sample: {places[0].get('name', 'N/A')}")
            return True
        else:
            print("❌ Google Maps returned no places")
            return False
            
    except Exception as e:
        print(f"❌ Google Maps error: {str(e)}")
        return False

def test_firebase():
    """Test Firebase connection"""
    print("\n🔥 Testing Firebase connection...")
    
    try:
        from app.database import init_firebase
        
        db = init_firebase()
        
        # Test basic connection
        test_collection = db.collection('test')
        test_doc = test_collection.document('connection_test')
        test_doc.set({'test': True, 'timestamp': '2024-01-01'})
        
        # Clean up
        test_doc.delete()
        
        print("✅ Firebase connection working!")
        return True
        
    except Exception as e:
        print(f"❌ Firebase error: {str(e)}")
        return False

def test_bigquery():
    """Test BigQuery connection"""
    print("\n📊 Testing BigQuery connection...")
    
    try:
        from google.cloud import bigquery
        from app.config import settings
        
        client = bigquery.Client(project=settings.google_cloud_project_id)
        
        # Test basic query
        query = "SELECT 1 as test_value"
        results = client.query(query)
        
        for row in results:
            if row.test_value == 1:
                print("✅ BigQuery connection working!")
                return True
        
        print("❌ BigQuery query returned unexpected result")
        return False
        
    except Exception as e:
        print(f"❌ BigQuery error: {str(e)}")
        return False

def test_fastapi():
    """Test FastAPI application startup"""
    print("\n🚀 Testing FastAPI application...")
    
    try:
        from main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/health")
        
        if response.status_code == 200:
            print("✅ FastAPI application working!")
            return True
        else:
            print(f"❌ FastAPI health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ FastAPI error: {str(e)}")
        return False

def main():
    """Run all integration tests"""
    print("🧪 Wanderly Integration Tests")
    print("=" * 40)
    
    tests = [
        ("Environment Variables", test_environment),
        ("Google AI (Gemini)", test_google_ai),
        ("Google Maps API", test_google_maps),
        ("Firebase", test_firebase),
        ("BigQuery", test_bigquery),
        ("FastAPI", test_fastapi)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("📋 Test Summary")
    print("=" * 40)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integrations are working! Your backend is ready for the hackathon!")
        return 0
    else:
        print("⚠️  Some integrations failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())


