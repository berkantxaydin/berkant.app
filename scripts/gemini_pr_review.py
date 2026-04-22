import os
import time
import subprocess
import requests
from google import genai # type: ignore

def main():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gh_token = os.environ.get("GITHUB_TOKEN")
    pr_number = os.environ.get("PR_NUMBER")
    repo = os.environ.get("REPO_NAME")

    if not gemini_key:
        print(" No GEMINI_API_KEY found in GitHub Secrets. Skipping AI review.")
        return

    # 1. Grab the Git Diff
    print(" Fetching git diff...")
    diff_cmd = ["git", "diff", "origin/main...HEAD"]
    result = subprocess.run(diff_cmd, capture_output=True, text=True)
    diff_text = result.stdout

    if not diff_text or len(diff_text.strip()) == 0:
        print(" No code changes found in diff.")
        return

    # Truncate if the diff is massive (e.g., someone committed a database by accident)
    if len(diff_text) > 45000:
        diff_text = diff_text[:45000] + "\n\n... [DIFF TRUNCATED DUE TO SIZE]"

    # 2. Ask Gemini to Review
    print(" Sending diff to Gemini API...")
    try:
        client = genai.Client(api_key=gemini_key)
        
        prompt = f"""
        Act as a Senior Security & Python Engineer. Review the following Git diff for a Pull Request.
        Context: This project is a highly constrained Flask app running on 16GB RAM using SQLite (WAL).
        
        Tasks:
        1. Look for obvious bugs or logic errors.
        2. Check for security vulnerabilities (especially SQL injection or bad file handling).
        3. Ensure no bloated libraries are being imported.
        
        Format your response in Markdown. Be concise. If the code looks perfect, say so.
        
        DIFF:
        ```diff
        {diff_text}
        ```
        """
        
        # Retry mechanism for 503 errors and rate limits
        max_retries = 3
        retry_delay = 5 # seconds
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                review_comment = response.text
                break # Success!
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        print(f" Gemini API busy (Attempt {attempt+1}/{max_retries}). Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2 # Exponential backoff
                        continue
                raise e # Re-raise if not a retryable error or last attempt
    except Exception as e:
        print(f" Gemini AI failed to generate review: {e}")
        return

    # 3. Post the comment back to GitHub
    print(" Posting review to GitHub PR...")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {gh_token}"
    }
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    payload = {"body": f"###  Gemini AI Code Review\n\n{review_comment}"}

    r = requests.post(url, headers=headers, json=payload)
    
    if r.status_code == 201:
        print(" Successfully posted Gemini review to PR!")
    else:
        print(f" Failed to post comment: {r.status_code} - {r.text}")

if __name__ == "__main__":
    main()