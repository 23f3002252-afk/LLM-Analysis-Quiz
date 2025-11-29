import os
import json
import time
import logging
import requests
import base64
import re
import pandas as pd
from io import StringIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI

logger = logging.getLogger(__name__)

class GroqQuizSolver:
    """
    Enhanced quiz solver using Groq with multi-model fallback and tool-based approach
    Based on GitHub autonomous agent pattern
    """
    
    # Model fallback chain
    AVAILABLE_MODELS = [
        "llama-3.3-70b-versatile",  # Best
        "llama-3.1-70b-versatile",  # Backup
        "llama-3.1-8b-instant",     # Fast fallback
    ]
    
    def __init__(self, email, secret):
        self.email = email
        self.secret = secret
        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        self.start_time = None
        self.current_url = None
        self.conversation_history = []
        
        # System prompt for the agent
        self.SYSTEM_PROMPT = """You are an Autonomous Quiz Solver.

AVAILABLE TOOLS:
1. "navigate": {"url": "string"} - Scrapes the page, returns text and links
2. "download_file": {"url": "string"} - Downloads CSV/data files
3. "python_repl": {"code": "string"} - Executes Python code (pandas available as pd)
4. "analyze_data": {"data": "string", "cutoff": "number"} - Analyzes CSV data with cutoff
5. "submit_answer": {"answer": "any"} - Submits final answer

IMPORTANT RULES:
- The "answer" parameter should be ONLY the actual answer value (string, number, etc.)
- DO NOT include email, secret, or url in the answer field - those are handled automatically
- For demo quizzes with no specific question, submit a simple string like "hello" or "demo"
- For CSV analysis: The rule is ALMOST ALWAYS sum of all numbers GREATER THAN (>) the cutoff, NOT >=

STRATEGY:
1. ALWAYS call "navigate" first to read the quiz page - NEVER skip this step
2. Look for:
   - Secret codes in text (submit the code as a string)
   - CSV/data file links (download and analyze)
   - Cutoff values for filtering (look for phrases like "cutoff: X")
3. For data analysis:
   - Option A: Download CSV then use "python_repl" to analyze:
     ```python
     import pandas as pd
     from io import StringIO
     df = pd.read_csv(StringIO(data), header=None)
     filtered = df[df[0] > CUTOFF]
     print(filtered[0].sum())
     ```
   - Option B: Use "analyze_data" tool directly
4. Submit the answer using "submit_answer" with just the answer value
5. NEVER submit generic answers like "hello" unless it's clearly a demo quiz

RESPONSE FORMAT (STRICT JSON):
{
  "thought": "Your reasoning",
  "tool_name": "tool_name",
  "parameters": {...}
}

EXAMPLES:
- For demo: {"tool_name": "submit_answer", "parameters": {"answer": "hello"}}
- For secret code: {"tool_name": "submit_answer", "parameters": {"answer": "SECRET123"}}
- For data sum: {"tool_name": "submit_answer", "parameters": {"answer": 42}}
"""
    
    def get_browser(self):
        """Initialize headless Chrome"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    
    def navigate(self, url):
        """Tool: Navigate to URL and scrape content"""
        logger.info(f"🌐 Navigating to: {url}")
        driver = self.get_browser()
        try:
            driver.get(url)
            time.sleep(3)
            
            body = driver.find_element(By.TAG_NAME, 'body')
            text = body.text
            
            # Extract links
            links = []
            try:
                link_elements = driver.find_elements(By.TAG_NAME, 'a')
                links = [elem.get_attribute('href') for elem in link_elements if elem.get_attribute('href')]
            except:
                pass
            
            return {
                "text": text[:2000],  # Truncate to save tokens
                "links": links
            }
        finally:
            driver.quit()
    
    def download_file(self, url):
        """Tool: Download file from URL"""
        logger.info(f"⬇️  Downloading: {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Download error: {e}")
            return f"Error: {e}"
    
    def python_repl(self, code):
        """Tool: Execute Python code for data analysis"""
        logger.info(f"🐍 Executing Python code")
        try:
            # Create a safe execution environment
            local_vars = {
                'pd': pd,
                'requests': requests,
                'StringIO': StringIO
            }
            
            # Capture print output
            from io import StringIO as SIO
            import sys
            old_stdout = sys.stdout
            sys.stdout = captured_output = SIO()
            
            # Execute code
            exec(code, {"__builtins__": __builtins__}, local_vars)
            
            # Get output
            sys.stdout = old_stdout
            output = captured_output.getvalue()
            
            logger.info(f"Code output: {output}")
            return output.strip()
            
        except Exception as e:
            logger.error(f"Python execution error: {e}", exc_info=True)
            return f"Error: {e}"
    
    def analyze_data(self, data, cutoff=None):
        """Tool: Analyze CSV data with optional cutoff"""
        logger.info(f"📊 Analyzing data (cutoff: {cutoff})")
        try:
            # Convert cutoff to int if it's a string
            if isinstance(cutoff, str):
                cutoff = int(cutoff)
            
            # Parse CSV
            df = pd.read_csv(StringIO(data), header=None)
            logger.info(f"Data shape: {df.shape}")
            
            if cutoff is not None:
                # Use > (GREATER THAN, not >=)
                filtered = df[df[0] > cutoff]
                result = filtered[0].sum()
                logger.info(f"Sum of values > {cutoff}: {result}")
                return str(int(result))
            else:
                # Just return sum of column 0
                result = df[0].sum()
                return str(int(result))
                
        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            return f"Error: {e}"
    
    def submit_answer(self, answer):
        """Tool: Submit answer to quiz"""
        logger.info(f"📤 Submitting answer: {answer}")
        
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
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            logger.info(f"📡 Response: {response.status_code}")
            result = response.json()
            logger.info(f"📨 {result}")
            return result
            
        except Exception as e:
            logger.error(f"Submit error: {e}")
            return {"error": str(e)}
    
    def query_llm_robust(self, messages):
        """Call LLM with model fallback"""
        for model in self.AVAILABLE_MODELS:
            try:
                logger.info(f"🤖 Using model: {model}")
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=2048
                )
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate" in error_msg.lower():
                    logger.warning(f"⚠️  {model} rate limited, trying next...")
                    continue
                else:
                    raise e
        
        raise Exception("All models failed or rate limited")
    
    def solve_single_quiz(self, url):
        """Solve a single quiz using agent loop"""
        self.current_url = url
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Solve this quiz: {url}\nEmail: {self.email}"}
        ]
        
        max_steps = 10
        for step in range(max_steps):
            logger.info(f"\n{'='*50}")
            logger.info(f"Step {step + 1}/{max_steps}")
            logger.info(f"{'='*50}")
            
            try:
                # Get AI decision
                ai_response = self.query_llm_robust(messages)
                messages.append({"role": "assistant", "content": ai_response})
                
                # Parse decision
                try:
                    # Try to extract JSON
                    if "```json" in ai_response:
                        start = ai_response.find("```json") + 7
                        end = ai_response.find("```", start)
                        json_text = ai_response[start:end].strip()
                    elif "```" in ai_response:
                        start = ai_response.find("```") + 3
                        end = ai_response.find("```", start)
                        json_text = ai_response[start:end].strip()
                    else:
                        json_text = ai_response
                    
                    command = json.loads(json_text)
                except json.JSONDecodeError:
                    logger.warning("⚠️  Invalid JSON from AI")
                    messages.append({"role": "user", "content": "Error: Return valid JSON only"})
                    continue
                
                tool_name = command.get("tool_name")
                params = command.get("parameters", {})
                thought = command.get("thought", "")
                
                logger.info(f"💭 Thought: {thought}")
                logger.info(f"🔧 Tool: {tool_name}")
                logger.info(f"📝 Params: {params}")
                
                # Execute tool
                result = None
                
                if tool_name == "navigate":
                    result = self.navigate(params.get("url"))
                    
                elif tool_name == "download_file":
                    result = self.download_file(params.get("url"))
                    
                elif tool_name == "python_repl":
                    result = self.python_repl(params.get("code"))
                    
                elif tool_name == "analyze_data":
                    result = self.analyze_data(
                        params.get("data"),
                        params.get("cutoff")
                    )
                    
                elif tool_name == "submit_answer":
                    result = self.submit_answer(params.get("answer"))
                    
                    # Check if done
                    if isinstance(result, dict):
                        if result.get("correct"):
                            logger.info("✅ Answer CORRECT!")
                            return result
                        else:
                            logger.warning(f"❌ Answer INCORRECT: {result.get('reason')}")
                            return result
                
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
                
                # Add result to conversation
                messages.append({
                    "role": "user",
                    "content": f"Tool result: {json.dumps(result) if isinstance(result, dict) else str(result)[:500]}"
                })
                
            except Exception as e:
                logger.error(f"❌ Step error: {e}", exc_info=True)
                messages.append({"role": "user", "content": f"Error: {str(e)}"})
        
        logger.error("Max steps reached without solution")
        return None
    
    def solve_quiz_chain(self, initial_url):
        """Solve chain of quizzes"""
        self.start_time = time.time()
        
        current_url = initial_url
        quiz_count = 0
        correct_count = 0
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 Starting Enhanced Quiz Solver")
        logger.info(f"📍 Initial URL: {initial_url}")
        logger.info(f"⚡ Using Groq with model fallback")
        logger.info(f"{'='*70}\n")
        
        while current_url:
            quiz_count += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"📝 Quiz #{quiz_count}: {current_url}")
            logger.info(f"{'='*70}\n")
            
            result = self.solve_single_quiz(current_url)
            
            if result is None:
                logger.error("❌ Failed to solve quiz")
                break
            
            if result.get('correct'):
                correct_count += 1
                logger.info(f"✅ Quiz #{quiz_count} CORRECT!")
            else:
                logger.warning(f"❌ Quiz #{quiz_count} INCORRECT: {result.get('reason')}")
            
            # Get next URL
            next_url = result.get('url')
            if next_url and next_url != current_url:
                logger.info(f"➡️  Next: {next_url}")
                current_url = next_url
                time.sleep(1)
            else:
                logger.info("🏁 Chain complete!")
                break
        
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
        logger.info(f"🤖 Model: Groq (multi-model fallback)")
        logger.info(f"{'='*70}\n")