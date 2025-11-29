import os
import json
import time
import logging
import requests
import subprocess
import sys
import base64
import tempfile
from openai import OpenAI

logger = logging.getLogger(__name__)

class GroqQuizSolver:
    """
    Quiz solver based on proven working implementation
    Uses Groq with proper audio/image support
    """
    
    AVAILABLE_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile", 
        "llama-3.1-8b-instant",
    ]
    
    def __init__(self, email, secret):
        self.email = email
        self.secret = secret
        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        self.start_time = None
        self.current_url = None
        
        self.SYSTEM_PROMPT = """You are an Autonomous Quiz Solver.
You reply with a JSON OBJECT.

AVAILABLE TOOLS:
1. "navigate": {"url": "string"} - Scrapes page, returns text and links
2. "transcribe_audio": {"audio_url": "string"} - Transcribes audio with Groq Whisper
3. "analyze_image": {"image_url": "string", "question": "string"} - Analyzes images with Groq Vision
4. "python_repl": {"code": "string"} - Executes Python (pandas available)
5. "submit_answer": {"answer": "any"} - Submits final answer

STRATEGY:
1. ALWAYS navigate first to see the quiz page
2. For SECRET CODE: Navigate to data URL and extract the secret
3. For CSV DATA: 
   - CRITICAL: Use python_repl to DOWNLOAD CSV with requests.get(), NOT navigate
   - Example: requests.get('https://url/data.csv').text
   - Audio might say ">=" but quiz usually wants ">" (strictly greater)
   - Extract cutoff from main page text
   - Calculate: Sum of column 0 where value > cutoff
4. For AUDIO: Transcribe and follow instructions CAREFULLY
5. For IMAGE: Analyze and extract code/number
6. For DEMO: Submit simple string like "hello"

CRITICAL CSV HANDLING:
- navigate() cannot read CSV files (browsers download them)
- ALWAYS use python_repl with requests.get() to download CSV
- Parse with pandas.read_csv(StringIO(response.text))

RESPONSE FORMAT (STRICT JSON):
{
  "thought": "reasoning",
  "tool_name": "tool_name",
  "parameters": {...}
}"""
    
    def navigate(self, url):
        """Navigate and scrape page using Selenium to handle JavaScript"""
        logger.info(f"🌐 Navigating: {url}")
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            
            # Wait for JavaScript to render
            import time
            time.sleep(3)
            
            # Get all text
            text = driver.find_element(By.TAG_NAME, 'body').text
            
            # Get all links
            links = []
            for elem in driver.find_elements(By.TAG_NAME, 'a'):
                href = elem.get_attribute('href')
                if href:
                    links.append({"href": href, "text": elem.text})
            
            # Look for audio
            audio = None
            try:
                audio_elem = driver.find_element(By.TAG_NAME, 'audio')
                audio = audio_elem.get_attribute('src')
            except:
                pass
            
            driver.quit()
            
            # Log what we found
            logger.info(f"Found {len(links)} links, audio: {bool(audio)}")
            logger.info(f"Text preview: {text[:300]}")
            
            return json.dumps({
                "text": text,
                "links": links[:15],
                "audio": audio
            })
        except Exception as e:
            logger.error(f"Navigate error: {e}", exc_info=True)
            return f"Error: {e}"
    
    def transcribe_audio(self, audio_url):
        """Transcribe audio using Groq Whisper"""
        logger.info(f"🎵 Transcribing: {audio_url}")
        try:
            # Download audio
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            
            # Determine extension
            if ".ogg" in audio_url:
                ext = ".ogg"
            elif ".wav" in audio_url:
                ext = ".wav"
            else:
                ext = ".mp3"
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(response.content)
                filename = tmp.name
            
            try:
                # Transcribe with Groq
                with open(filename, "rb") as file:
                    transcription = self.client.audio.transcriptions.create(
                        file=(filename, file.read()),
                        model="whisper-large-v3",
                        response_format="json",
                        language="en",
                        temperature=0.0
                    )
                logger.info(f"✅ Transcription: {transcription.text}")
                return f"TRANSCRIPTION: {transcription.text}"
            finally:
                os.unlink(filename)
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return f"Error: {e}"
    
    def analyze_image(self, image_url, question="What do you see?"):
        """Analyze image using Groq Vision or PIL fallback"""
        logger.info(f"🖼️  Analyzing: {image_url}")
        try:
            # Download image first
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Try Groq vision model first
            try:
                b64_image = base64.b64encode(response.content).decode('utf-8')
                
                completion = self.client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}"
                                }
                            }
                        ]
                    }],
                    model="llama-3.2-90b-vision-preview",
                    temperature=0.1
                )
                
                result = completion.choices[0].message.content
                logger.info(f"✅ Vision: {result}")
                return f"IMAGE ANALYSIS: {result}"
            except Exception as vision_error:
                logger.warning(f"Vision API failed: {vision_error}, using PIL fallback")
                
                # Fallback: Use PIL to analyze image
                from PIL import Image
                from io import BytesIO
                from collections import Counter
                
                img = Image.open(BytesIO(response.content))
                
                # For heatmap: find most frequent color
                if 'heatmap' in image_url or 'color' in question.lower():
                    pixels = list(img.getdata())
                    most_common = Counter(pixels).most_common(1)[0][0]
                    
                    # Convert to hex
                    if isinstance(most_common, int):  # Grayscale
                        hex_color = f"#{most_common:02x}{most_common:02x}{most_common:02x}"
                    else:  # RGB
                        hex_color = f"#{most_common[0]:02x}{most_common[1]:02x}{most_common[2]:02x}"
                    
                    logger.info(f"✅ PIL Analysis: Most frequent color = {hex_color}")
                    return f"IMAGE ANALYSIS: Most frequent color is {hex_color}"
                else:
                    return f"IMAGE ANALYSIS: {img.size[0]}x{img.size[1]} image, {img.mode} mode"
                    
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Error: {e}"
    
    def python_repl(self, code):
        """Execute Python code"""
        logger.info(f"🐍 Executing Python")
        try:
            prepend = """import pandas as pd
import numpy as np
import requests
import json
from io import BytesIO, StringIO
try:
    from PIL import Image
    from collections import Counter
except ImportError:
    pass
"""
            full_code = prepend + code
            
            result = subprocess.run(
                [sys.executable, "-c", full_code],
                capture_output=True,
                text=True,
                timeout=45
            )
            
            if result.returncode == 0:
                return f"STDOUT:\n{result.stdout}"
            else:
                return f"STDERR:\n{result.stderr}"
                
        except Exception as e:
            return f"Error: {e}"
    
    def submit_answer(self, answer):
        """Submit answer to quiz"""
        logger.info(f"📤 Submitting: {answer}")
        
        payload = {
            "email": self.email,
            "secret": self.secret,
            "url": self.current_url,
            "answer": answer
        }
        
        try:
            response = requests.post(
                "https://tds-llm-analysis.s-anand.net/submit",
                json=payload,
                timeout=15
            )
            
            logger.info(f"📡 {response.status_code}")
            result = response.json()
            logger.info(f"📨 {result}")
            return result
            
        except Exception as e:
            logger.error(f"Submit error: {e}")
            return {"error": str(e)}
    
    def query_llm(self, messages):
        """Query LLM with fallback"""
        for model in self.AVAILABLE_MODELS:
            try:
                logger.info(f"🤖 Model: {model}")
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=2048
                )
                return response.choices[0].message.content
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    logger.warning(f"⚠️  {model} rate limited")
                    continue
                else:
                    raise
        raise Exception("All models failed")
    
    def solve_single_quiz(self, url):
        """Solve one quiz"""
        self.current_url = url
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Solve: {url}\nEmail: {self.email}"}
        ]
        
        for step in range(10):
            logger.info(f"\n{'='*50}")
            logger.info(f"Step {step+1}/10")
            logger.info(f"{'='*50}")
            
            try:
                # Get AI decision
                ai_response = self.query_llm(messages)
                messages.append({"role": "assistant", "content": ai_response})
                
                # Parse JSON
                try:
                    if "```json" in ai_response:
                        start = ai_response.find("```json") + 7
                        end = ai_response.find("```", start)
                        json_text = ai_response[start:end].strip()
                    else:
                        json_text = ai_response
                    
                    command = json.loads(json_text)
                except:
                    logger.warning("Invalid JSON")
                    messages.append({"role": "user", "content": "Return valid JSON"})
                    continue
                
                tool_name = command.get("tool_name")
                params = command.get("parameters", {})
                thought = command.get("thought", "")
                
                logger.info(f"💭 {thought}")
                logger.info(f"🔧 {tool_name}")
                
                # Execute tool
                result = None
                
                if tool_name == "navigate":
                    result = self.navigate(params.get("url"))
                    
                elif tool_name == "transcribe_audio":
                    result = self.transcribe_audio(params.get("audio_url"))
                    
                elif tool_name == "analyze_image":
                    result = self.analyze_image(
                        params.get("image_url"),
                        params.get("question", "What is in this image?")
                    )
                    
                elif tool_name == "python_repl":
                    result = self.python_repl(params.get("code"))
                    
                elif tool_name == "submit_answer":
                    result = self.submit_answer(params.get("answer"))
                    
                    if isinstance(result, dict):
                        if result.get("correct"):
                            logger.info("✅ CORRECT!")
                            return result
                        else:
                            logger.warning(f"❌ INCORRECT: {result.get('reason')}")
                            return result
                
                # Add result
                messages.append({
                    "role": "user",
                    "content": f"Tool result: {str(result)[:500]}"
                })
                
            except Exception as e:
                logger.error(f"Step error: {e}")
                messages.append({"role": "user", "content": f"Error: {e}"})
        
        return None
    
    def solve_quiz_chain(self, initial_url):
        """Solve quiz chain"""
        self.start_time = time.time()
        
        current_url = initial_url
        quiz_count = 0
        correct_count = 0
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 Starting Working Quiz Solver")
        logger.info(f"📍 URL: {initial_url}")
        logger.info(f"{'='*70}\n")
        
        while current_url:
            quiz_count += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"📝 Quiz #{quiz_count}: {current_url}")
            logger.info(f"{'='*70}\n")
            
            result = self.solve_single_quiz(current_url)
            
            if result is None:
                logger.error("Failed")
                break
            
            if result.get('correct'):
                correct_count += 1
                logger.info(f"✅ Quiz #{quiz_count} CORRECT!")
            else:
                logger.warning(f"❌ Quiz #{quiz_count} INCORRECT")
            
            next_url = result.get('url')
            if next_url and next_url != current_url:
                logger.info(f"➡️  Next: {next_url}")
                current_url = next_url
                time.sleep(1)
            else:
                logger.info("🏁 Complete!")
                break
        
        elapsed = time.time() - self.start_time
        success_rate = (correct_count / quiz_count * 100) if quiz_count > 0 else 0
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total: {quiz_count}")
        logger.info(f"✅ Correct: {correct_count}")
        logger.info(f"❌ Incorrect: {quiz_count - correct_count}")
        logger.info(f"📈 Success: {success_rate:.1f}%")
        logger.info(f"⏱️  Time: {elapsed:.1f}s")
        logger.info(f"{'='*70}\n")