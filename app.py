import os
import json
import logging
from flask import Flask, request, jsonify
from datetime import datetime
import threading
from quiz_solver import GroqQuizSolver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration
EMAIL = os.getenv('STUDENT_EMAIL', '23f3002252@ds.study.iitm.ac.in')
SECRET = os.getenv('STUDENT_SECRET', 'SECRET_KEY')

def solve_quiz_async(email, secret, url):
    """Solve quiz in background thread"""
    try:
        solver = GroqQuizSolver(email, secret)
        solver.solve_quiz_chain(url)
    except Exception as e:
        logger.error(f"Error solving quiz: {e}", exc_info=True)

@app.route('/quiz', methods=['POST'])
def handle_quiz():
    """Handle incoming quiz requests"""
    try:
        if not request.is_json:
            logger.warning("Invalid JSON")
            return jsonify({"error": "Invalid JSON"}), 400
        
        data = request.get_json()
        logger.info(f"Received quiz request: {data}")
        
        # Verify fields
        if 'email' not in data or 'secret' not in data or 'url' not in data:
            logger.warning("Missing fields")
            return jsonify({"error": "Missing fields"}), 400
        
        # Verify secret
        if data['secret'] != SECRET:
            logger.warning(f"Invalid secret")
            return jsonify({"error": "Invalid secret"}), 403
        
        # Verify email
        if data['email'] != EMAIL:
            logger.warning(f"Email mismatch")
            return jsonify({"error": "Email mismatch"}), 403
        
        # Start solving in background
        quiz_url = data['url']
        logger.info(f"Starting Groq solver for: {quiz_url}")
        
        thread = threading.Thread(
            target=solve_quiz_async,
            args=(data['email'], data['secret'], quiz_url)
        )
        thread.daemon = True
        thread.start()
        
        # Return immediate 200
        return jsonify({
            "status": "accepted",
            "message": "Quiz solving started with Groq (Llama 3.3 70B)",
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except json.JSONDecodeError:
        logger.error("JSON decode error")
        return jsonify({"error": "Invalid JSON"}), 400
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "ai_model": "Groq Llama 3.3 70B Versatile",
        "speed": "Super fast! ⚡",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)