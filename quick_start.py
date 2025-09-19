#!/usr/bin/env python3
"""
Quick start script for Wanderly Group Trip Planner
This script helps you get started quickly for the hackathon.
"""

import os
import sys
import subprocess
from pathlib import Path

def print_banner():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    WANDERLY GROUP TRIP PLANNER               ║
    ║                    🚀 Quick Start Script 🚀                  ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} is compatible")
    return True

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_env_file():
    """Create .env file from template"""
    print("\n⚙️ Setting up environment file...")
    
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    template_file = Path("env_example.txt")
    if not template_file.exists():
        print("❌ env_example.txt not found")
        return False
    
    # Copy template to .env
    with open(template_file, 'r') as src, open(env_file, 'w') as dst:
        dst.write(src.read())
    
    print("✅ Created .env file from template")
    print("⚠️  Please edit .env file with your actual credentials")
    return True

def run_tests():
    """Run integration tests"""
    print("\n🧪 Running integration tests...")
    try:
        result = subprocess.run([sys.executable, "test_integrations.py"], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")
        return False

def start_server():
    """Start the FastAPI server"""
    print("\n🚀 Starting Wanderly backend server...")
    print("   Server will be available at: http://localhost:8000")
    print("   API docs will be available at: http://localhost:8000/docs")
    print("\n   Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

def main():
    """Main quick start function"""
    print_banner()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed at dependency installation")
        sys.exit(1)
    
    # Create environment file
    if not create_env_file():
        print("\n❌ Setup failed at environment file creation")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎯 NEXT STEPS:")
    print("=" * 60)
    print("1. Edit .env file with your Google Cloud credentials")
    print("2. Run: python test_integrations.py")
    print("3. Run: python main.py")
    print("4. Visit: http://localhost:8000/docs")
    print("\n📚 For detailed setup instructions, see setup_guide.md")
    print("📖 For API documentation, see README.md")
    
    # Ask if user wants to run tests
    response = input("\n🧪 Would you like to run integration tests now? (y/n): ").lower().strip()
    if response in ['y', 'yes']:
        if run_tests():
            print("\n🎉 All tests passed! Your backend is ready!")
            
            # Ask if user wants to start server
            response = input("\n🚀 Would you like to start the server now? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                start_server()
        else:
            print("\n⚠️  Some tests failed. Please check your credentials in .env file")
    else:
        print("\n👋 Setup complete! Run 'python main.py' when ready to start.")

if __name__ == "__main__":
    main()


