import os
import json
import time
import logging
import requests
import base64
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI

logger = logging.getLogger(__name__)

class GroqQuizSolver:
    """
    Quiz solver using Groq via OpenAI-compatible API (more stable!)
    """
    
    def __init__(self, email, secret):
        self.email = email
        self.secret = secret
        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        # Use OpenAI client with Groq endpoint - much more stable!
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = "llama-3.3-70b-versatile"
        
        self.start_time = None
        self.current_url = None
        self.conversation_history = []
        
    def get_browser(self):
        """Initialize headless Chrome browser"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    
    def fetch_quiz_page(self, url):
        """Fetch and render quiz page with JavaScript execution"""
        logger.info(f"🌐 Fetching quiz page: {url}")
        
        driver = self.get_browser()
        try:
            driver.get(url)
            time.sleep(3)
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass
            
            html_content = driver.page_source
            body = driver.find_element(By.TAG_NAME, 'body')
            visible_text = body.text
            
            # Extract links
            links = []
            try:
                link_elements = driver.find_elements(By.TAG_NAME, 'a')
                links = [elem.get_attribute('href') for elem in link_elements if elem.get_attribute('href')]
            except:
                pass
            
            logger.info(f"✅ Page fetched: {len(html_content)} bytes, {len(links)} links")
            
            return {
                'html': html_content,
                'text': visible_text,
                'url': url,
                'links': links
            }
        except Exception as e:
            logger.error(f"❌ Error fetching page: {e}", exc_info=True)
            return None
        finally:
            driver.quit()
    
    def download_file(self, url):
        """Download a file from URL with retry logic"""
        logger.info(f"⬇️  Downloading file from: {url}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                logger.info(f"✅ File downloaded: {len(response.content)} bytes")
                return response.content
            except Exception as e:
                logger.warning(f"⚠️  Download attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.error(f"❌ Failed to download file")
                    return None
    
    def solve_with_groq(self, quiz_content):
        """Use Groq (via OpenAI client) to understand and solve the quiz"""
        logger.info("🤖 Analyzing quiz with Groq (Llama 3.3 70B)")
        
        system_prompt = """You are an expert data analyst and problem solver. Your task is to:
1. Understand the quiz question completely
2. Identify what data needs to be accessed or downloaded
3. Determine the analysis required
4. Provide the correct answer in the exact format requested
5. Identify the submission endpoint

Be precise and methodical. Return your analysis as a JSON object."""

        user_prompt = f"""Quiz Page Analysis:

URL: {quiz_content['url']}

VISIBLE TEXT:
{quiz_content['text']}

LINKS FOUND:
{json.dumps(quiz_content.get('links', []), indent=2)}

Please analyze this quiz and provide a structured solution in JSON format:
{{
    "understanding": "What is the question asking?",
    "data_source": "URL or source of data (if applicable)",
    "file_type": "Type of file to download (pdf/csv/json/excel/etc) or null",
    "analysis_needed": "What calculation/analysis is required?",
    "answer_format": "Expected format of answer (number/string/boolean/object/base64)",
    "submit_url": "Where to POST the answer",
    "answer": null,
    "needs_external_data": true/false,
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of your approach"
}}

IMPORTANT: 
- If you need to download and analyze external data, set "answer" to null and "needs_external_data" to true
- If you can answer immediately from the visible text, provide the actual answer and set "needs_external_data" to false
- Do NOT say "Cannot be calculated" - just use null for the answer field"""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Add conversation history if exists
            if self.conversation_history:
                messages = [{"role": "system", "content": system_prompt}] + self.conversation_history + [{"role": "user", "content": user_prompt}]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=4096
            )
            
            response_text = response.choices[0].message.content
            logger.info(f"💡 Groq response: {response_text[:500]}...")
            
            # Parse JSON response
            solution = self.extract_json(response_text)
            
            if solution:
                # Add to conversation history
                self.conversation_history.append({"role": "user", "content": user_prompt})
                self.conversation_history.append({"role": "assistant", "content": response_text})
            
            return solution
            
        except Exception as e:
            logger.error(f"❌ Error getting Groq analysis: {e}", exc_info=True)
            return None
    
    def extract_json(self, text):
        """Extract JSON from response with multiple strategies"""
        try:
            # Strategy 1: Find JSON in code blocks
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                json_text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                json_text = text[start:end].strip()
            else:
                # Strategy 2: Find JSON-like structure
                match = re.search(r'\{[\s\S]*\}', text)
                if match:
                    json_text = match.group(0)
                else:
                    json_text = text.strip()
            
            return json.loads(json_text)
            
        except json.JSONDecodeError:
            # Strategy 3: Try to fix common issues
            try:
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*]', ']', json_text)
                return json.loads(json_text)
            except:
                logger.error("❌ Could not parse JSON")
                return None
        except Exception as e:
            logger.error(f"❌ Error extracting JSON: {e}")
            return None
    
    def process_external_data(self, data_source, file_type, analysis_needed):
        """Download and process external data using Groq"""
        logger.info(f"📊 Processing external data from {data_source}")
        
        # Download the file
        file_content = self.download_file(data_source)
        if not file_content:
            return None
        
        prompt = f"""I've downloaded a {file_type} file. Here's what I need to do:

Analysis Required: {analysis_needed}

Please:
1. Extract the relevant data from the file
2. Perform the required analysis
3. Provide the final answer

Return JSON:
{{
    "data_extracted": "summary of data found",
    "analysis_performed": "what you calculated",
    "answer": "the final answer",
    "explanation": "brief explanation"
}}"""

        try:
            # Try to decode file as text
            try:
                file_text = file_content.decode('utf-8')
                logger.info(f"📝 Processing text file ({len(file_text)} chars)")
                full_prompt = f"{prompt}\n\nFile Contents:\n{file_text[:30000]}"
            except:
                # Binary file - convert to base64
                logger.info(f"🔢 Processing binary file")
                file_b64 = base64.b64encode(file_content).decode('utf-8')
                full_prompt = f"{prompt}\n\nFile (base64, first 3000 chars): {file_b64[:3000]}..."
            
            messages = [
                {"role": "system", "content": "You are a data analysis expert."},
                {"role": "user", "content": full_prompt}
            ]
            
            if self.conversation_history:
                messages = [{"role": "system", "content": "You are a data analysis expert."}] + self.conversation_history + [{"role": "user", "content": full_prompt}]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=4096
            )
            
            response_text = response.choices[0].message.content
            logger.info(f"✅ Data analysis complete: {response_text[:500]}...")
            
            result = self.extract_json(response_text)
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": full_prompt})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing data: {e}", exc_info=True)
            return None
    
    def submit_answer(self, submit_url, answer):
        """Submit the answer to the quiz endpoint"""
        logger.info(f"📤 Submitting answer to: {submit_url}")
        logger.info(f"💬 Answer: {json.dumps(answer, indent=2) if isinstance(answer, dict) else answer}")
        
        payload = {
            "email": self.email,
            "secret": self.secret,
            "url": self.current_url,
            "answer": answer
        }
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    submit_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                logger.info(f"📡 Submit response: {response.status_code}")
                logger.info(f"📨 Response: {response.text}")
                
                if response.status_code == 200:
                    return response.json()
                else:
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 Retrying...")
                        time.sleep(2)
                    else:
                        return None
                    
            except Exception as e:
                logger.error(f"❌ Error submitting: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return None
    
    def check_time_limit(self):
        """Check if within 3-minute time limit"""
        if self.start_time is None:
            return True
        
        elapsed = time.time() - self.start_time
        remaining = 180 - elapsed
        
        if remaining <= 0:
            logger.warning("⏰ Time limit exceeded")
            return False
        
        logger.info(f"⏱️  Time: {elapsed:.1f}s / 180s ({remaining:.1f}s remaining)")
        return True
    
    def solve_single_quiz(self, url):
        """Solve a single quiz"""
        if not self.check_time_limit():
            return None
        
        self.current_url = url
        
        try:
            # Fetch quiz page
            quiz_content = self.fetch_quiz_page(url)
            if not quiz_content:
                return None
            
            # Analyze with Groq
            solution = self.solve_with_groq(quiz_content)
            if not solution:
                return None
            
            logger.info(f"📋 Solution:\n{json.dumps(solution, indent=2)}")
            
            # Get answer
            answer = solution.get('answer')
            
            # Process external data if needed
            # Check if answer is None, "Cannot...", or needs_external_data is true
            if solution.get('needs_external_data') and (answer is None or (isinstance(answer, str) and "cannot" in answer.lower())):
                data_source = solution.get('data_source')
                file_type = solution.get('file_type')
                analysis_needed = solution.get('analysis_needed')
                
                if data_source:
                    logger.info(f"📊 Processing external data from: {data_source}")
                    result = self.process_external_data(data_source, file_type, analysis_needed)
                    if result:
                        answer = result.get('answer')
                        logger.info(f"✅ External data processed, answer: {answer}")
            
            if answer is None:
                logger.error("❌ No answer determined")
                return None
            
            # Submit answer
            submit_url = solution.get('submit_url')
            if not submit_url:
                logger.error("❌ No submit URL")
                return None
            
            return self.submit_answer(submit_url, answer)
            
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            return None
    
    def solve_quiz_chain(self, initial_url):
        """Solve chain of quizzes"""
        self.start_time = time.time()
        
        current_url = initial_url
        quiz_count = 0
        correct_count = 0
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 Starting Quiz Chain with Groq (Llama 3.3 70B)")
        logger.info(f"📍 Initial URL: {initial_url}")
        logger.info(f"⚡ Using OpenAI-compatible API (stable!)")
        logger.info(f"{'='*70}\n")
        
        while current_url and self.check_time_limit():
            quiz_count += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"📝 Quiz #{quiz_count}: {current_url}")
            logger.info(f"{'='*70}\n")
            
            result = self.solve_single_quiz(current_url)
            
            if result is None:
                logger.error("❌ Failed, stopping")
                break
            
            if result.get('correct'):
                correct_count += 1
                logger.info(f"✅ Quiz #{quiz_count} CORRECT!")
            else:
                logger.warning(f"❌ Quiz #{quiz_count} INCORRECT: {result.get('reason')}")
            
            # Next quiz
            next_url = result.get('url')
            if next_url:
                logger.info(f"➡️  Next: {next_url}")
                current_url = next_url
            else:
                logger.info("🏁 Chain complete!")
                break
            
            time.sleep(1)
        
        # Summary
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
        logger.info(f"🤖 Model: Groq Llama 3.3 70B (via OpenAI API)")
        logger.info(f"{'='*70}\n")