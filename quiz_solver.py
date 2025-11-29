import os
import json
import time
import logging
import requests
import tempfile
from io import StringIO
from urllib.parse import urlsplit

import pandas as pd
from PIL import Image
from collections import Counter
from openai import OpenAI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GroqQuizSolver:
    """
    Deterministic quiz solver for Tools in Data Science LLM Analysis Project 2.

    - Uses requests for all HTTP interactions (no Selenium, Render compatible).
    - Uses Groq Whisper (whisper-large-v3) for audio transcription.
    - Uses PIL to analyze images (e.g., most frequent color in a heatmap).
    - Uses pandas to normalize CSV to JSON.
    - Uses GitHub API for the git-tree quiz.

    Interface:

        solver = GroqQuizSolver(email, secret)
        solver.solve_quiz_chain("https://tds-llm-analysis.s-anand.net/project2")
    """

    BASE_SUBMIT_URL = "https://tds-llm-analysis.s-anand.net/submit"
    BASE_HOST = "https://tds-llm-analysis.s-anand.net"

    def __init__(self, email: str, secret: str):
        self.email = email
        self.secret = secret

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    # -------------------------------------------------------------------------
    # Core utilities
    # -------------------------------------------------------------------------

    def http_get_text(self, url: str) -> str:
        logger.info(f"GET (text): {url}")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def http_get_binary(self, url: str) -> bytes:
        logger.info(f"GET (binary): {url}")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def submit_answer(self, url: str, answer):
        """Submit answer to the TDS quiz server."""
        payload = {
            "email": self.email,
            "secret": self.secret,
            "url": url,
            "answer": answer,
        }
        logger.info(f"📤 Submitting answer to {url}: {repr(answer)[:200]}")
        resp = requests.post(self.BASE_SUBMIT_URL, json=payload, timeout=30)
        logger.info(f"📡 Status: {resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            logger.exception("Failed to decode JSON from submit response")
            raise
        logger.info(f"📨 Response: {data}")
        return data

    # -------------------------------------------------------------------------
    # Quiz 1: /project2 - Demo / secret
    # -------------------------------------------------------------------------

    def solve_project2_root(self, url: str):
        """
        /project2

        The instructions say: start by POSTing some JSON, the page mainly explains
        how to play. In your previous logs, submitting "hello" was accepted.

        We'll submit a simple non-empty string.
        """
        answer = "hello"
        return self.submit_answer(url, answer)

    # -------------------------------------------------------------------------
    # Quiz 2: /project2-uv - uv http get command
    # -------------------------------------------------------------------------

    def solve_project2_uv(self, url: str):
        """
        /project2-uv

        Task (from page text):

            Craft the command string (not the output) using:
                uv http get https://tds-llm-analysis.s-anand.net/project2/uv.json?email=<your email>
            Include header:
                -H "Accept: application/json"

        Return the command itself as the answer.
        """
        target_url = f"{self.BASE_HOST}/project2/uv.json?email={self.email}"
        cmd = f'uv http get {target_url} -H "Accept: application/json"'
        return self.submit_answer(url, cmd)

    # -------------------------------------------------------------------------
    # Quiz 3: /project2-git - git add/commit commands
    # -------------------------------------------------------------------------

    def solve_project2_git(self, url: str):
        """
        /project2-git

        Task:

            Write two shell commands to:
            1. Stage only env.sample
            2. Commit with message "chore: keep env sample"

        Answer can contain newline between commands.
        """
        answer = 'git add env.sample\ngit commit -m "chore: keep env sample"'
        return self.submit_answer(url, answer)

    # -------------------------------------------------------------------------
    # Quiz 4: /project2-md - relative link target
    # -------------------------------------------------------------------------

    def solve_project2_md(self, url: str):
        """
        /project2-md

        Task (from page text):

            The correct relative link target is exactly /project2/data-preparation.md
            Submit that exact string as the answer.

        To be robust, we parse it from the page using a regex instead of hardcoding.
        """
        import re

        text = self.http_get_text(url)
        match = re.search(r"/project2/[A-Za-z0-9_\-]+\.md", text)
        if not match:
            raise RuntimeError("Could not find /project2/*.md in page text")
        link_target = match.group(0)
        logger.info(f"Detected relative link target: {link_target}")
        return self.submit_answer(url, link_target)

    # -------------------------------------------------------------------------
    # Quiz 5: /project2-audio-passphrase - audio transcription
    # -------------------------------------------------------------------------

    def transcribe_audio_url(self, audio_url: str) -> str:
        """
        Download audio and transcribe using Groq Whisper.
        Returns transcription as a plain string.
        """
        logger.info(f"🎵 Downloading audio: {audio_url}")
        audio_bytes = self.http_get_binary(audio_url)

        # Guess extension
        if audio_url.endswith(".opus"):
            ext = ".opus"
        elif audio_url.endswith(".ogg"):
            ext = ".ogg"
        elif audio_url.endswith(".wav"):
            ext = ".wav"
        else:
            ext = ".mp3"

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(audio_bytes)
            tmp_name = tmp.name

        try:
            with open(tmp_name, "rb") as f:
                logger.info("🎙️  Transcribing with whisper-large-v3")
                transcription = self.client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=f,
                    response_format="text",
                    temperature=0.0,
                    language="en",
                )
        finally:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass

        text = transcription.strip()
        logger.info(f"✅ Transcription: {text!r}")
        return text

    def solve_project2_audio(self, url: str):
        """
        /project2-audio-passphrase

        Task (from page text):

            Listen to /project2/audio-passphrase.opus.
            Transcribe the spoken phrase (words plus the 3-digit code)
            in lowercase, spaces allowed.
        """
        page_text = self.http_get_text(url)
        # The page explicitly mentions /project2/audio-passphrase.opus
        audio_url = f"{self.BASE_HOST}/project2/audio-passphrase.opus"
        transcript = self.transcribe_audio_url(audio_url)
        answer = transcript.lower().strip()
        return self.submit_answer(url, answer)

    # -------------------------------------------------------------------------
    # Quiz 6: /project2-heatmap - most frequent color in heatmap.png
    # -------------------------------------------------------------------------

    def most_frequent_color_hex(self, img_bytes: bytes) -> str:
        """
        Compute the most frequent RGB color in an image and return it as #rrggbb.
        """
        img = Image.open(tempfile.SpooledTemporaryFile())
        img.file.write(img_bytes)  # type: ignore[attr-defined]
        img.file.seek(0)           # type: ignore[attr-defined]
        img = Image.open(img.file)  # reopen properly

        # Convert to RGB to normalize (handles RGBA, etc.)
        img = img.convert("RGB")
        pixels = list(img.getdata())
        c = Counter(pixels).most_common(1)[0][0]  # (r, g, b)
        hex_color = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        logger.info(f"Most frequent color: {hex_color}")
        return hex_color

    def solve_project2_heatmap(self, url: str):
        """
        /project2-heatmap

        Task (from page text):

            Open /project2/heatmap.png.
            Find the most frequent RGB color. Return it as a hex string, e.g., #rrggbb.
        """
        img_url = f"{self.BASE_HOST}/project2/heatmap.png"
        img_bytes = self.http_get_binary(img_url)
        hex_color = self.most_frequent_color_hex(img_bytes)
        return self.submit_answer(url, hex_color)

    # -------------------------------------------------------------------------
    # Quiz 7: /project2-csv - messy.csv normalization
    # -------------------------------------------------------------------------

    def normalize_messy_csv(self, csv_url: str) -> str:
        """
        Normalize /project2/messy.csv as per instructions:

        - Output: JSON array of objects.
        - Keys: snake_case -> id, name, joined, value
        - joined: ISO-8601 date (UTC)
        - value: integer
        - Sorted by id ascending.
        """
        csv_text = self.http_get_text(csv_url)
        df = pd.read_csv(StringIO(csv_text))

        # Force 4 columns -> id, name, joined, value
        expected_cols = ["id", "name", "joined", "value"]
        if len(df.columns) != 4:
            logger.warning(
                f"Expected 4 columns in messy.csv, got {len(df.columns)}; will coerce anyway"
            )

        rename_map = {
            old: new for old, new in zip(df.columns, expected_cols)
        }
        df = df.rename(columns=rename_map)

        # id -> integer
        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["id"])
        df["id"] = df["id"].astype(int)

        # name -> strip whitespace, keep as string
        df["name"] = df["name"].astype(str).str.strip()

        # value -> extract integer
        df["value"] = (
            df["value"]
            .astype(str)
            .str.extract(r"(-?\d+)", expand=False)
            .astype("Int64")
        )
        df = df.dropna(subset=["value"])
        df["value"] = df["value"].astype(int)

        # joined -> parse to datetime UTC, then ISO-8601
        df["joined"] = pd.to_datetime(df["joined"], utc=True, errors="coerce")
        df = df.dropna(subset=["joined"])
        # Format as ISO-8601 with 'Z' suffix (UTC)
        df["joined"] = df["joined"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Sort by id ascending
        df = df.sort_values("id")

        records = df.to_dict(orient="records")
        # Compact JSON (no extra spaces)
        json_str = json.dumps(records, separators=(",", ":"))
        logger.info(f"Normalized JSON: {json_str}")
        return json_str

    def solve_project2_csv(self, url: str):
        """
        /project2-csv

        Task (from page text):

            Download /project2/messy.csv.
            Normalize to JSON:
              - snake_case keys (id, name, joined, value)
              - ISO-8601 dates
              - integer values
              - sorted by id ascending
            POST the JSON array as a string answer.
        """
        csv_url = f"{self.BASE_HOST}/project2/messy.csv"
        json_answer = self.normalize_messy_csv(csv_url)
        return self.submit_answer(url, json_answer)

    # -------------------------------------------------------------------------
    # Quiz 8: /project2-gh-tree - GitHub API tree count + email offset
    # -------------------------------------------------------------------------

    def solve_project2_gh_tree(self, url: str):
        """
        /project2-gh-tree

        Task (from page text, paraphrased):

            Use GitHub API:
              GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1
            with params in /project2/gh-tree.json:
              {
                "owner": "...",
                "repo": "...",
                "sha": "...",
                "pathPrefix": "project-1/",
                "extension": ".md"
              }

            Count how many .md files are under pathPrefix.
            Compute 'offset' as the length of your email address.
            Answer = count + offset
        """
        config_url = f"{self.BASE_HOST}/project2/gh-tree.json"
        cfg_text = self.http_get_text(config_url)
        cfg = json.loads(cfg_text)

        owner = cfg["owner"]
        repo = cfg["repo"]
        sha = cfg["sha"]
        path_prefix = cfg["pathPrefix"]
        extension = cfg["extension"]

        gh_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
        logger.info(f"Calling GitHub API: {gh_url}")
        resp = requests.get(gh_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        tree = data.get("tree", [])
        count = 0
        for node in tree:
            path = node.get("path", "")
            if path.startswith(path_prefix) and path.endswith(extension):
                count += 1

        offset = len(self.email)
        answer_value = count + offset
        logger.info(
            f"Count of {extension} under {path_prefix}: {count}, "
            f"email length offset: {offset}, answer: {answer_value}"
        )

        # Answer should be a number; server accepts JSON number.
        return self.submit_answer(url, answer_value)

    # -------------------------------------------------------------------------
    # Orchestrator
    # -------------------------------------------------------------------------

    def solve_quiz_chain(self, initial_url: str):
        """
        Solve the entire quiz chain starting from initial_url.

        Returns the final summary dict from the last submit.
        """
        current_url = initial_url
        quiz_count = 0
        correct_count = 0
        start_time = time.time()

        logger.info("=" * 70)
        logger.info("🚀 Starting Quiz Solver")
        logger.info(f"📍 Initial URL: {initial_url}")
        logger.info("=" * 70)

        last_result = None

        while current_url:
            quiz_count += 1
            path = urlsplit(current_url).path
            logger.info("\n" + "=" * 70)
            logger.info(f"📝 Quiz #{quiz_count}: {current_url}")
            logger.info("=" * 70)

            if path == "/project2":
                result = self.solve_project2_root(current_url)
            elif path == "/project2-uv":
                result = self.solve_project2_uv(current_url)
            elif path == "/project2-git":
                result = self.solve_project2_git(current_url)
            elif path == "/project2-md":
                result = self.solve_project2_md(current_url)
            elif path == "/project2-audio-passphrase":
                result = self.solve_project2_audio(current_url)
            elif path == "/project2-heatmap":
                result = self.solve_project2_heatmap(current_url)
            elif path == "/project2-csv":
                result = self.solve_project2_csv(current_url)
            elif path == "/project2-gh-tree":
                result = self.solve_project2_gh_tree(current_url)
            else:
                logger.error(f"Unknown quiz path: {path}, stopping.")
                break

            last_result = result

            if result.get("correct"):
                correct_count += 1
                logger.info(f"✅ Quiz #{quiz_count} CORRECT!")
            else:
                logger.warning(
                    f"❌ Quiz #{quiz_count} INCORRECT: {result.get('reason')}"
                )

            next_url = result.get("url")
            if next_url and next_url != current_url:
                logger.info(f"➡️  Next: {next_url}")
                current_url = next_url
                # small politeness delay
                time.sleep(result.get("delay", 1) or 1)
            else:
                logger.info("🏁 No next URL, chain complete.")
                break

        elapsed = time.time() - start_time
        success_rate = (correct_count / quiz_count * 100) if quiz_count else 0.0

        logger.info("\n" + "=" * 70)
        logger.info("📊 SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total quizzes: {quiz_count}")
        logger.info(f"✅ Correct: {correct_count}")
        logger.info(f"❌ Incorrect: {quiz_count - correct_count}")
        logger.info(f"📈 Success: {success_rate:.1f}%")
        logger.info(f"⏱️  Time: {elapsed:.1f}s")
        logger.info("=" * 70 + "\n")

        return last_result


if __name__ == "__main__":
    # Simple manual test entrypoint (for local debugging)
    EMAIL = os.getenv("TDS_EMAIL", "23f3002252@ds.study.iitm.ac.in")
    SECRET = os.getenv("TDS_SECRET", "SECRET_KEY")
    INITIAL_URL = "https://tds-llm-analysis.s-anand.net/project2"

    solver = GroqQuizSolver(EMAIL, SECRET)
    solver.solve_quiz_chain(INITIAL_URL)
