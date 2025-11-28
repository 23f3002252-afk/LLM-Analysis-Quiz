import os
import json
import time
import logging
import requests
import base64
import re
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import anthropic

logger = logging.getLogger(__name__)

class AdvancedQuizSolver:
    """
    Advanced quiz solver with comprehensive data handling capabilities
    """
    
    def __init__(self, email, secret):
        self.email = email
        self.secret = secret
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.start_time = None
        self.current_url = None
        
    def get_browser(self):
        """Initialize headless Chrome browser with optimal settings"""
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
        logger.info(f"Fetching quiz page: {url}")
        
        driver = self.get_browser()
        try:
            driver.get(url)
            # Wait for content to load
            time.sleep(3)
            
            # Try to wait for specific elements
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass
            
            # Get the rendered HTML
            html_content = driver.page_source
            
            # Get visible text
            body = driver.find_element(By.TAG_NAME, 'body')
            visible_text = body.text
            
            # Try to extract any links
            links = []
            try:
                link_elements = driver.find_elements(By.TAG_NAME, 'a')
                links = [elem.get_attribute('href') for elem in link_elements if elem.get_attribute('href')]
            except:
                pass
            
            logger.info(f"Fetched page: {len(html_content)} bytes, {len(links)} links found")
            
            return {
                'html': html_content,
                'text': visible_text,
                'url': url,
                'links': links
            }
        finally:
            driver.quit()
    
    def download_file(self, url):
        """Download a file from URL"""
        logger.info(f"Downloading file from: {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def solve_with_claude(self, quiz_content, conversation_history=None):
        """
        Use Claude to understand and solve the quiz
        Maintains conversation history for complex multi-step tasks
        """
        logger.info("Analyzing quiz with Claude")
        
        if conversation_history is None:
            conversation_history = []
        
        # Build the prompt
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
    "answer": "Your calculated answer (provide if you can compute it now)",
    "needs_external_data": true/false,
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of your approach"
}}

If you need to download and analyze external data, indicate that in needs_external_data.
If you can answer immediately from the visible text, provide the answer directly."""

        try:
            messages = conversation_history + [
                {"role": "user", "content": user_prompt}
            ]
            
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system_prompt,
                messages=messages
            )
            
            response_text = message.content[0].text
            logger.info(f"Claude analysis: {response_text[:500]}...")
            
            # Parse JSON response
            solution = self.extract_json(response_text)
            
            if solution:
                # Add to conversation history
                conversation_history.append({"role": "user", "content": user_prompt})
                conversation_history.append({"role": "assistant", "content": response_text})
                
            return solution, conversation_history
            
        except Exception as e:
            logger.error(f"Error getting Claude analysis: {e}", exc_info=True)
            return None, conversation_history
    
    def extract_json(self, text):
        """Extract JSON from Claude's response"""
        try:
            # Try to find JSON in code blocks
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                json_text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                json_text = text[start:end].strip()
            else:
                # Try to find JSON-like structure
                match = re.search(r'\{[\s\S]*\}', text)
                if match:
                    json_text = match.group(0)
                else:
                    json_text = text.strip()
            
            return json.loads(json_text)
        except Exception as e:
            logger.error(f"Error extracting JSON: {e}")
            logger.debug(f"Text was: {text}")
            return None
    
    def process_external_data(self, data_source, file_type, analysis_needed, conversation_history):
        """
        Download and process external data using Claude
        """
        logger.info(f"Processing external data from {data_source}")
        
        # Download the file
        file_content = self.download_file(data_source)
        if not file_content:
            logger.error("Failed to download file")
            return None, conversation_history
        
        # Convert to base64 for Claude
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Determine media type
        media_type_map = {
            'pdf': 'application/pdf',
            'csv': 'text/csv',
            'txt': 'text/plain',
            'json': 'application/json',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xls': 'application/vnd.ms-excel'
        }
        
        media_type = media_type_map.get(file_type, 'application/octet-stream')
        
        prompt = f"""I've downloaded a {file_type} file. Here's what I need to do:

Analysis Required: {analysis_needed}

The file is attached. Please:
1. Extract the relevant data from the file
2. Perform the required analysis
3. Provide the final answer

Return your response as JSON:
{{
    "data_extracted": "summary of data found",
    "analysis_performed": "what you calculated",
    "answer": "the final answer",
    "explanation": "brief explanation"
}}"""

        try:
            # Build message with file
            if file_type == 'pdf':
                content = [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": file_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            else:
                # For non-PDF files, try to decode and include as text
                try:
                    file_text = file_content.decode('utf-8')
                    content = f"{prompt}\n\nFile Contents:\n{file_text[:10000]}"  # Limit size
                except:
                    content = f"{prompt}\n\nFile is binary, base64: {file_base64[:1000]}..."
            
            messages = conversation_history + [
                {"role": "user", "content": content}
            ]
            
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                messages=messages
            )
            
            response_text = message.content[0].text
            logger.info(f"Data analysis result: {response_text[:500]}...")
            
            result = self.extract_json(response_text)
            
            # Update conversation history
            conversation_history.append({"role": "user", "content": prompt})
            conversation_history.append({"role": "assistant", "content": response_text})
            
            return result, conversation_history
            
        except Exception as e:
            logger.error(f"Error processing external data: {e}", exc_info=True)
            return None, conversation_history
    
    def submit_answer(self, submit_url, answer):
        """Submit the answer to the quiz endpoint"""
        logger.info(f"Submitting answer to: {submit_url}")
        logger.info(f"Answer: {json.dumps(answer, indent=2) if isinstance(answer, dict) else answer}")
        
        payload = {
            "email": self.email,
            "secret": self.secret,
            "url": self.current_url,
            "answer": answer
        }
        
        try:
            response = requests.post(
                submit_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            logger.info(f"Submit response status: {response.status_code}")
            logger.info(f"Submit response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                logger.error(f"Submit failed with status {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting answer: {e}", exc_info=True)
            return None
    
    def check_time_limit(self):
        """Check if we're still within the 3-minute time limit"""
        if self.start_time is None:
            return True
        
        elapsed = time.time() - self.start_time
        remaining = 180 - elapsed
        
        if remaining <= 0:
            logger.warning("⏰ Time limit exceeded (3 minutes)")
            return False
        
        logger.info(f"⏱️  Time: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining")
        return True
    
    def solve_single_quiz(self, url):
        """Solve a single quiz at the given URL"""
        if not self.check_time_limit():
            logger.error("Stopping due to time limit")
            return None
        
        self.current_url = url
        conversation_history = []
        
        try:
            # Step 1: Fetch the quiz page
            quiz_content = self.fetch_quiz_page(url)
            
            # Step 2: Analyze with Claude
            solution, conversation_history = self.solve_with_claude(quiz_content, conversation_history)
            
            if not solution:
                logger.error("Failed to get solution from Claude")
                return None
            
            logger.info(f"📋 Solution analysis:\n{json.dumps(solution, indent=2)}")
            
            # Step 3: Get the answer
            answer = solution.get('answer')
            
            # Step 4: If external data is needed, process it
            if solution.get('needs_external_data') and answer is None:
                data_source = solution.get('data_source')
                file_type = solution.get('file_type')
                analysis_needed = solution.get('analysis_needed')
                
                if data_source:
                    result, conversation_history = self.process_external_data(
                        data_source,
                        file_type,
                        analysis_needed,
                        conversation_history
                    )
                    
                    if result:
                        answer = result.get('answer')
            
            if answer is None:
                logger.error("❌ Failed to determine answer")
                return None
            
            # Step 5: Submit the answer
            submit_url = solution.get('submit_url')
            if not submit_url:
                logger.error("❌ No submit URL found")
                return None
            
            result = self.submit_answer(submit_url, answer)
            return result
            
        except Exception as e:
            logger.error(f"❌ Error solving quiz: {e}", exc_info=True)
            return None
    
    def solve_quiz_chain(self, initial_url):
        """Solve a chain of quizzes starting from initial URL"""
        self.start_time = time.time()
        
        current_url = initial_url
        quiz_count = 0
        correct_count = 0
        incorrect_count = 0
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 Starting Quiz Chain")
        logger.info(f"📍 Initial URL: {initial_url}")
        logger.info(f"{'='*70}\n")
        
        while current_url and self.check_time_limit():
            quiz_count += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"📝 Quiz #{quiz_count}: {current_url}")
            logger.info(f"{'='*70}\n")
            
            result = self.solve_single_quiz(current_url)
            
            if result is None:
                logger.error("❌ Failed to solve quiz, stopping chain")
                break
            
            if result.get('correct'):
                correct_count += 1
                logger.info(f"✅ Answer #{quiz_count} was CORRECT!")
            else:
                incorrect_count += 1
                reason = result.get('reason', 'Unknown reason')
                logger.warning(f"❌ Answer #{quiz_count} was INCORRECT: {reason}")
            
            # Get next URL
            next_url = result.get('url')
            if next_url:
                logger.info(f"➡️  Moving to next quiz: {next_url}")
                current_url = next_url
            else:
                logger.info("🏁 No more quizzes - Chain completed!")
                break
            
            # Small delay between quizzes
            time.sleep(1)
        
        # Final summary
        elapsed = time.time() - self.start_time
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 QUIZ CHAIN SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total Quizzes: {quiz_count}")
        logger.info(f"✅ Correct: {correct_count}")
        logger.info(f"❌ Incorrect: {incorrect_count}")
        logger.info(f"⏱️  Total Time: {elapsed:.1f}s / 180s")
        logger.info(f"{'='*70}\n")
