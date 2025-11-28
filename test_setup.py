#!/usr/bin/env python3
"""
Test script for LLM Analysis Quiz project (Groq version)
Run this to verify your setup before deployment
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Test that all required environment variables are set"""
    print("Testing environment variables...")
    
    required_vars = ['STUDENT_EMAIL', 'STUDENT_SECRET', 'GROQ_API_KEY']
    missing = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            print(f"  ✗ {var}: NOT SET")
        else:
            # Mask sensitive values
            if 'API' in var or 'SECRET' in var:
                display = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display = value
            print(f"  ✓ {var}: {display}")
    
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("Please set them in your .env file")
        return False
    
    print("\n✅ All environment variables are set\n")
    return True

def test_dependencies():
    """Test that all required packages are installed"""
    print("Testing dependencies...")
    
    required_packages = [
        'flask',
        'groq',
        'selenium',
        'requests',
        'dotenv'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package if package != 'dotenv' else 'dotenv')
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package}: NOT INSTALLED")
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies are installed\n")
    return True

def test_chrome_driver():
    """Test that Chrome and ChromeDriver are available"""
    print("Testing Chrome/ChromeDriver...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        driver.get('about:blank')
        driver.quit()
        
        print("  ✓ Chrome browser available")
        print("  ✓ ChromeDriver working")
        print("\n✅ Chrome setup is working\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Chrome/ChromeDriver error: {e}")
        print("\n❌ Chrome setup failed")
        print("Install Chrome and ChromeDriver:")
        print("  macOS: brew install chromedriver")
        print("  Then: xattr -d com.apple.quarantine $(which chromedriver)")
        return False

def test_groq_api():
    """Test Groq API connectivity"""
    print("Testing Groq API...")
    
    try:
        from groq import Groq
        
        client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with just 'OK'"}],
            max_tokens=10
        )
        
        response_text = response.choices[0].message.content.strip()
        
        if 'OK' in response_text.upper():
            print(f"  ✓ API connection successful")
            print(f"  ✓ Response received: {response_text}")
            print(f"  ✓ Model: Llama 3.1 70B")
            print("\n✅ Groq API is working\n")
            return True
        else:
            print(f"  ⚠ Unexpected response: {response_text}")
            return False
            
    except Exception as e:
        print(f"  ✗ API error: {e}")
        print("\n❌ Groq API test failed")
        print("Check your GROQ_API_KEY")
        print("Get one at: https://console.groq.com/keys")
        return False

def test_local_server():
    """Test the local Flask server"""
    print("Testing local Flask server...")
    
    # Try to connect to local server
    try:
        response = requests.get('http://localhost:3000/health', timeout=2)
        
        if response.status_code == 200:
            print("  ✓ Server is running")
            print(f"  ✓ Health check passed: {response.json()}")
            print("\n✅ Local server is working\n")
            return True
        else:
            print(f"  ✗ Server returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("  ⚠ Server not running")
        print("  Start with: python app.py")
        print("\n⚠️  Skipping server test (not critical for setup)\n")
        return None  # Not a failure, just not running yet
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_quiz_endpoint():
    """Test the quiz endpoint with demo"""
    print("Testing quiz endpoint with demo...")
    
    try:
        payload = {
            "email": os.getenv('STUDENT_EMAIL'),
            "secret": os.getenv('STUDENT_SECRET'),
            "url": "https://tds-llm-analysis.s-anand.net/demo"
        }
        
        response = requests.post(
            'http://localhost:3000/quiz',
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            print("  ✓ Quiz endpoint accepted request")
            print(f"  ✓ Response: {response.json()}")
            print("\n✅ Quiz endpoint is working\n")
            return True
        else:
            print(f"  ✗ Endpoint returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("  ⚠ Server not running")
        print("\n⚠️  Skipping endpoint test\n")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_secret_validation():
    """Test that secret validation works"""
    print("Testing secret validation...")
    
    try:
        payload = {
            "email": os.getenv('STUDENT_EMAIL'),
            "secret": "wrong-secret-12345",
            "url": "https://example.com/test"
        }
        
        response = requests.post(
            'http://localhost:3000/quiz',
            json=payload,
            timeout=5
        )
        
        if response.status_code == 403:
            print("  ✓ Invalid secret properly rejected (403)")
            print("\n✅ Secret validation is working\n")
            return True
        else:
            print(f"  ✗ Expected 403, got {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("  ⚠ Server not running")
        print("\n⚠️  Skipping validation test\n")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("="*60)
    print("LLM Analysis Quiz - Setup Verification (Groq Version)")
    print("="*60 + "\n")
    
    results = {}
    
    # Critical tests (must pass)
    results['environment'] = test_environment()
    results['dependencies'] = test_dependencies()
    
    # Important tests (should pass)
    results['chrome'] = test_chrome_driver()
    results['groq'] = test_groq_api()
    
    # Optional tests (nice to have)
    results['server'] = test_local_server()
    if results['server']:
        results['endpoint'] = test_quiz_endpoint()
        results['validation'] = test_secret_validation()
    
    # Summary
    print("="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    print(f"\n✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Skipped: {skipped}")
    
    critical_tests = ['environment', 'dependencies', 'chrome', 'groq']
    critical_passed = all(results.get(t, False) for t in critical_tests)
    
    if critical_passed:
        print("\n🎉 All critical tests passed! You're ready to deploy.")
        print("\nNext steps:")
        print("1. Deploy to Render.com (Railway is down)")
        print("2. Get your public HTTPS URL")
        print("3. Fill out the Google Form with your URL")
        print("4. Test with: curl -X POST <your-url>/quiz -H 'Content-Type: application/json' -d '{...}'")
        return 0
    else:
        print("\n❌ Some critical tests failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())