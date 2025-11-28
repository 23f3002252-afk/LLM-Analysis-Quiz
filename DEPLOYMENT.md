# Deployment Guide

This guide covers deploying the LLM Analysis Quiz project to various cloud platforms.

## Quick Start

All platforms require:
1. A GitHub repository with your code
2. Three environment variables:
   - `STUDENT_EMAIL`
   - `STUDENT_SECRET`
   - `ANTHROPIC_API_KEY`

---

## Railway.app (Recommended - Easiest)

Railway offers free tier and simple deployment with Chrome support.

### Steps:

1. **Sign up**: Go to [railway.app](https://railway.app) and sign in with GitHub

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Add Environment Variables**:
   - Go to "Variables" tab
   - Add:
     ```
     STUDENT_EMAIL=your-email@example.com
     STUDENT_SECRET=your-secret-string
     ANTHROPIC_API_KEY=sk-ant-api03-...
     PORT=3000
     ```

4. **Configure Build**:
   - Railway auto-detects Python
   - Uses Dockerfile automatically
   - No additional config needed

5. **Deploy**:
   - Click "Deploy"
   - Wait for build to complete
   - Get your public URL: `https://your-app.railway.app`

6. **Update Endpoint**:
   - Your quiz endpoint: `https://your-app.railway.app/quiz`
   - Submit this URL to the Google Form

### Cost:
- Free tier: $5 credit/month (enough for this project)
- Sleeps after inactivity (keep alive with cron job if needed)

---

## Render.com

Render offers free tier with good reliability.

### Steps:

1. **Sign up**: Go to [render.com](https://render.com)

2. **Create Web Service**:
   - Click "New +" → "Web Service"
   - Connect GitHub repository
   - Select your repo

3. **Configure**:
   - **Name**: llm-quiz-solver
   - **Environment**: Docker
   - **Plan**: Free
   - **Region**: Choose closest to you

4. **Environment Variables**:
   ```
   STUDENT_EMAIL=your-email@example.com
   STUDENT_SECRET=your-secret-string
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment
   - URL: `https://llm-quiz-solver.onrender.com`

### Notes:
- Free tier spins down after 15 min inactivity
- First request after sleep takes ~30 seconds
- Upgrade to paid ($7/mo) for always-on

---

## Google Cloud Run

Serverless with great scaling and reliability.

### Prerequisites:
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

### Steps:

1. **Enable APIs**:
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

2. **Build and Deploy**:
```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Build
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/quiz-solver

# Deploy
gcloud run deploy quiz-solver \
  --image gcr.io/YOUR_PROJECT_ID/quiz-solver \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars STUDENT_EMAIL=your-email@example.com \
  --set-env-vars STUDENT_SECRET=your-secret \
  --set-env-vars ANTHROPIC_API_KEY=sk-ant-... \
  --memory 1Gi \
  --timeout 300
```

3. **Get URL**:
```bash
gcloud run services describe quiz-solver --region us-central1 --format 'value(status.url)'
```

### Cost:
- Free tier: 2 million requests/month
- Pay only for actual usage
- ~$0.40 per million requests

---

## Heroku

Traditional PaaS with good documentation.

### Prerequisites:
```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh
heroku login
```

### Steps:

1. **Create App**:
```bash
heroku create your-quiz-solver
```

2. **Add Buildpacks**:
```bash
heroku buildpacks:add --index 1 heroku/python
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add --index 3 https://github.com/heroku/heroku-buildpack-chromedriver
```

3. **Set Environment Variables**:
```bash
heroku config:set STUDENT_EMAIL=your-email@example.com
heroku config:set STUDENT_SECRET=your-secret
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
```

4. **Deploy**:
```bash
git push heroku main
```

5. **Scale**:
```bash
heroku ps:scale web=1
```

6. **Get URL**:
```bash
heroku info -s | grep web_url
```

### Cost:
- Free tier discontinued (min $5/mo)
- Eco dynos: $5/mo (sleeps after 30 min)
- Basic: $7/mo (always on)

---

## DigitalOcean App Platform

Simple deployment with good performance.

### Steps:

1. **Sign up**: Go to [digitalocean.com](https://www.digitalocean.com)

2. **Create App**:
   - Click "Create" → "Apps"
   - Connect GitHub
   - Select repository

3. **Configure**:
   - **Type**: Web Service
   - **Run Command**: `gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 300 app:app`
   - **HTTP Port**: 8080

4. **Environment Variables**:
   ```
   STUDENT_EMAIL=your-email@example.com
   STUDENT_SECRET=your-secret-string
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

5. **Deploy**:
   - Choose plan (Basic: $5/mo)
   - Click "Launch"

### Cost:
- Basic: $5/mo
- Professional: $12/mo (for better performance)

---

## Fly.io

Modern platform with good free tier.

### Prerequisites:
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh
flyctl auth login
```

### Steps:

1. **Create fly.toml**:
```toml
app = "quiz-solver"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8080"

[[services]]
  http_checks = []
  internal_port = 8080
  processes = ["app"]
  protocol = "tcp"
  
  [[services.ports]]
    handlers = ["http"]
    port = 80
  
  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

2. **Launch**:
```bash
flyctl launch
```

3. **Set Secrets**:
```bash
flyctl secrets set STUDENT_EMAIL=your-email@example.com
flyctl secrets set STUDENT_SECRET=your-secret
flyctl secrets set ANTHROPIC_API_KEY=sk-ant-...
```

4. **Deploy**:
```bash
flyctl deploy
```

5. **Get URL**:
```bash
flyctl info
```

### Cost:
- Free tier: 3 shared VMs
- $0.0000022/sec for additional resources

---

## Vercel (NOT Recommended)

Vercel is designed for frontend/serverless functions, not long-running processes.

**Issues**:
- 10-second timeout on free tier (not enough for quiz solving)
- No built-in Chrome support
- Serverless environment restrictions

**Skip this option** unless you heavily modify the architecture.

---

## AWS Elastic Beanstalk

Enterprise-grade with more complexity.

### Prerequisites:
```bash
pip install awsebcli
eb init
```

### Steps:

1. **Initialize**:
```bash
eb init -p python-3.11 quiz-solver
```

2. **Create Environment**:
```bash
eb create quiz-solver-env
```

3. **Set Environment Variables**:
```bash
eb setenv STUDENT_EMAIL=your-email@example.com \
          STUDENT_SECRET=your-secret \
          ANTHROPIC_API_KEY=sk-ant-...
```

4. **Deploy**:
```bash
eb deploy
```

5. **Get URL**:
```bash
eb status
```

### Cost:
- t2.micro (free tier eligible): Free for 12 months
- After free tier: ~$10/mo

---

## Comparison Table

| Platform | Free Tier | Setup Difficulty | Reliability | Best For |
|----------|-----------|------------------|-------------|----------|
| Railway | $5 credit/mo | ⭐⭐⭐⭐⭐ Easy | ⭐⭐⭐⭐ Good | Quick start |
| Render | Yes (sleeps) | ⭐⭐⭐⭐⭐ Easy | ⭐⭐⭐⭐ Good | Simple projects |
| Google Cloud Run | 2M req/mo | ⭐⭐⭐ Medium | ⭐⭐⭐⭐⭐ Excellent | Production |
| Heroku | No ($5 min) | ⭐⭐⭐⭐ Easy | ⭐⭐⭐⭐ Good | Traditional apps |
| DigitalOcean | No ($5 min) | ⭐⭐⭐⭐ Easy | ⭐⭐⭐⭐ Good | Balanced option |
| Fly.io | 3 VMs free | ⭐⭐⭐ Medium | ⭐⭐⭐⭐ Good | Modern apps |
| AWS EB | 12 mo free | ⭐⭐ Hard | ⭐⭐⭐⭐⭐ Excellent | Enterprise |

---

## Recommendation

**For this project**: Use **Railway.app**

Reasons:
1. ✅ Easiest setup (5 minutes)
2. ✅ Free tier sufficient
3. ✅ Chrome works out of box
4. ✅ Good for evaluation period
5. ✅ Auto-deploys on git push
6. ✅ Good logs and monitoring

**For production**: Use **Google Cloud Run**

Reasons:
1. ✅ Best scaling
2. ✅ Pay only for usage
3. ✅ Enterprise reliability
4. ✅ Better for long-term

---

## Post-Deployment Checklist

After deploying to any platform:

1. **Test Health Endpoint**:
   ```bash
   curl https://your-app-url.com/health
   ```

2. **Test Quiz Endpoint**:
   ```bash
   curl -X POST https://your-app-url.com/quiz \
     -H "Content-Type: application/json" \
     -d '{
       "email": "your-email@example.com",
       "secret": "your-secret",
       "url": "https://tds-llm-analysis.s-anand.net/demo"
     }'
   ```

3. **Test Secret Validation** (should return 403):
   ```bash
   curl -X POST https://your-app-url.com/quiz \
     -H "Content-Type: application/json" \
     -d '{
       "email": "your-email@example.com",
       "secret": "wrong-secret",
       "url": "https://example.com/test"
     }'
   ```

4. **Check Logs**:
   - Railway: Dashboard → Logs
   - Render: Dashboard → Logs
   - GCP: `gcloud run logs read quiz-solver`
   - Heroku: `heroku logs --tail`

5. **Monitor Performance**:
   - Ensure requests complete within 3 minutes
   - Check memory usage
   - Verify Chrome/Selenium working

6. **Submit to Google Form**:
   - URL: `https://your-app-url.com/quiz`
   - Ensure it's HTTPS
   - Test one more time before evaluation

---

## Troubleshooting

### Chrome Issues
If Chrome fails:
```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils
```

### Timeout Issues
If requests timeout:
```python
# In app.py, increase timeout
@app.route('/quiz', methods=['POST'])
def handle_quiz():
    # ... existing code ...
    
    # Increase timeout
    thread.join(timeout=300)  # 5 minutes max
```

### Memory Issues
If running out of memory:
- Increase container memory (1GB → 2GB)
- Optimize Chrome options
- Process data in chunks

### API Rate Limits
If hitting Anthropic limits:
- Add retry logic with exponential backoff
- Use caching for repeated queries
- Consider batch processing

---

## Keep-Alive (Optional)

Some free tiers sleep after inactivity. Keep your app alive:

### Using UptimeRobot:
1. Sign up at [uptimerobot.com](https://uptimerobot.com)
2. Add monitor for your `/health` endpoint
3. Check interval: 5 minutes

### Using Cron-Job.org:
1. Sign up at [cron-job.org](https://cron-job.org)
2. Create job to ping `/health`
3. Schedule: Every 10 minutes

**Note**: Only needed for Railway, Render free tier, and Heroku eco dynos.

---

## Security Best Practices

1. **Never commit secrets**:
   - Always use environment variables
   - Add .env to .gitignore

2. **Validate all inputs**:
   - Check email and secret on every request
   - Sanitize URLs before fetching

3. **Rate limiting**:
   - Add rate limits to prevent abuse
   - Use Flask-Limiter if needed

4. **Logging**:
   - Never log secrets
   - Log all quiz attempts
   - Monitor for suspicious activity

5. **HTTPS only**:
   - Ensure your endpoint uses HTTPS
   - Never use HTTP in production
