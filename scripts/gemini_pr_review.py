import os
import subprocess
import requests
import google.generativeai as genai

def main():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gh_token = os.environ.get("GITHUB_TOKEN")
    pr_number = os.environ.get("PR_NUMBER")
    repo = os.environ.get("REPO_NAME")

    if not gemini_key:
        print("⚠️ No GEMINI_API_KEY found in GitHub Secrets. Skipping AI review.")
        return

    # 1. Grab the Git Diff
    print("🔍 Fetching git diff...")
    diff_cmd = ["git", "diff", "origin/main...HEAD"]
    result = subprocess.run(diff_cmd, capture_output=True, text=True)
    diff_text = result.stdout

    if not diff_text or len(diff_text.strip()) == 0:
        print("ℹ️ No code changes found in diff.")
        return

    # Truncate if the diff is massive (e.g., someone committed a database by accident)
    if len(diff_text) > 45000:
        diff_text = diff_text[:45000] + "\n\n... [DIFF TRUNCATED DUE TO SIZE]"

    # 2. Ask Gemini to Review
    print("🧠 Sending diff to Gemini API...")
    try:
        genai.configure(api_key=gemini_key)
        
        # Using Gemini 2.5 Flash as requested by the user
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        Act as a Senior Security & Python Engineer. Review the following Git diff for a Pull Request.
        Context: This project is a highly constrained Flask app running on 8GB RAM using SQLite (WAL).
        
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
        
        response = model.generate_content(prompt)
        review_comment = response.text
    except Exception as e:
        print(f"❌ Gemini AI failed to generate review: {e}")
        return

    # 3. Post the comment back to GitHub
    print("📝 Posting review to GitHub PR...")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {gh_token}"
    }
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    payload = {"body": f"### 🤖 Gemini AI Code Review\n\n{review_comment}"}

    r = requests.post(url, headers=headers, json=payload)
    
    if r.status_code == 201:
        print("✅ Successfully posted Gemini review to PR!")
    else:
        print(f"❌ Failed to post comment: {r.status_code} - {r.text}")

if __name__ == "__main__":
    main()