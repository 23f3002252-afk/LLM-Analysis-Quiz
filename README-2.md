# LLM Analysis Quiz Project

This project solves data analysis quizzes using Large Language Models (LLMs) and automated web scraping.

## Project Structure

```
.
├── app.py              # Flask API server
├── quiz_solver.py      # Quiz solving logic with LLM integration
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container configuration
├── .env.example       # Environment variables template
├── prompts.md         # System and user prompts for testing
└── README.md          # This file
```

## Features

- **API Endpoint**: Flask server that accepts quiz tasks via POST requests
- **Automated Quiz Solving**: Uses Claude AI to understand and solve data analysis tasks
- **Headless Browser**: Selenium with Chrome for JavaScript-rendered pages
- **Chain Solving**: Automatically proceeds through multiple quiz URLs
- **Time Management**: Respects the 3-minute time limit per quiz chain
- **Robust Error Handling**: Validates secrets, handles timeouts, and logs errors

## Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd llm-analysis-quiz
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Chrome and ChromeDriver

**Ubuntu/Debian:**
```bash
# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# Install ChromeDriver
sudo apt-get install chromium-chromedriver
```

**macOS:**
```bash
brew install --cask google-chrome
brew install chromedriver
```

### 4. Configure Environment

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
nano .env
```

Update with your values:
```
STUDENT_EMAIL=your-email@student.university.edu
STUDENT_SECRET=your-secret-string-here
ANTHROPIC_API_KEY=sk-ant-api03-your-api-key-here
PORT=5000
```

### 5. Run the Server

```bash
python app.py
```

Or with gunicorn for production:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 app:app
```

## Docker Deployment

### Build the Docker Image

```bash
docker build -t llm-quiz-solver .
```

### Run the Container

```bash
docker run -d \
  -p 5000:5000 \
  -e STUDENT_EMAIL="your-email@example.com" \
  -e STUDENT_SECRET="your-secret" \
  -e ANTHROPIC_API_KEY="sk-ant-api03-..." \
  --name quiz-solver \
  llm-quiz-solver
```

## Cloud Deployment

### Deploy to Railway/Render/Heroku

1. Create a new web service
2. Connect your GitHub repository
3. Set environment variables:
   - `STUDENT_EMAIL`
   - `STUDENT_SECRET`
   - `ANTHROPIC_API_KEY`
4. Deploy!

### Deploy to Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/quiz-solver

# Deploy
gcloud run deploy quiz-solver \
  --image gcr.io/YOUR_PROJECT/quiz-solver \
  --platform managed \
  --region us-central1 \
  --set-env-vars STUDENT_EMAIL=your-email,STUDENT_SECRET=your-secret,ANTHROPIC_API_KEY=sk-ant-...
```

## Testing

### Test the Health Endpoint

```bash
curl http://localhost:5000/health
```

### Test with Demo Quiz

```bash
curl -X POST http://localhost:5000/quiz \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

### Test Secret Validation

```bash
# Should return 403
curl -X POST http://localhost:5000/quiz \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "wrong-secret",
    "url": "https://example.com/quiz"
  }'
```

## Prompt Testing

See `prompts.md` for:
- System prompt (100 chars) - Defends against revealing code words
- User prompt (100 chars) - Attempts to extract code words

## How It Works

1. **Receive Quiz Request**: API endpoint receives POST with quiz URL
2. **Validate Request**: Checks email and secret match configuration
3. **Start Async Solving**: Launches background thread to solve quiz
4. **Fetch Quiz Page**: Uses Selenium to render JavaScript and extract content
5. **Analyze with LLM**: Sends page content to Claude to understand the task
6. **Execute Analysis**: Downloads data, performs calculations
7. **Submit Answer**: Posts answer to the specified endpoint
8. **Chain Continuation**: If there's a next URL, continues solving
9. **Time Management**: Tracks elapsed time, stops at 3-minute limit

## Logging

Logs are written to stdout with timestamps. Monitor with:

```bash
# Local
tail -f app.log

# Docker
docker logs -f quiz-solver
```

## Troubleshooting

### Chrome/ChromeDriver Issues

If you get "chromedriver not found":
```bash
which chromedriver
# Add to PATH if needed
export PATH=$PATH:/usr/local/bin
```

### API Key Issues

Verify your Anthropic API key:
```bash
echo $ANTHROPIC_API_KEY
```

### Port Already in Use

Change the port:
```bash
PORT=8080 python app.py
```

## License

MIT License - see LICENSE file

## Google Form Submission

Submit these values to the Google Form:

1. **Email**: Your student email
2. **Secret**: A strong random string (save in .env)
3. **System Prompt**: See `prompts.md`
4. **User Prompt**: See `prompts.md`
5. **API Endpoint**: Your deployed URL (e.g., `https://your-app.railway.app/quiz`)
6. **GitHub Repo**: Your public repository URL

## Evaluation Time

- **Date**: Saturday, 29 Nov 2025
- **Time**: 3:00 PM - 4:00 PM IST
- Ensure your server is running and accessible during this time!

## Architecture Decisions

### Why Claude Sonnet 4?
- Excellent at understanding complex instructions
- Strong reasoning for data analysis tasks
- Good balance of speed and capability

### Why Selenium?
- Handles JavaScript-rendered pages
- Required for `atob()` and dynamic content
- More reliable than static HTML parsers

### Why Background Threading?
- Immediate 200 response to satisfy timeout requirements
- Allows long-running quiz solving process
- Non-blocking server for multiple requests

### Why Gunicorn?
- Production-ready WSGI server
- Better than Flask's development server
- Handles concurrent requests properly

## Performance Optimization

- Keep Chrome headless for speed
- Cache LLM responses where possible
- Minimize network roundtrips
- Use streaming for large data files
- Parallel processing where allowed

## Security Considerations

- Validate all incoming requests
- Never log secrets
- Sanitize URLs before fetching
- Timeout on all network requests
- Rate limit to prevent abuse
