import os
from flask import Flask, jsonify, request
import logging
import ai_service

# Local database operations
from database import get_db_connection, init_db, insert_example_data, query_example_json

app = Flask(__name__)

# Basic logging configuration
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return jsonify({
        "message": "Welcome to proglem API", 
        "hint": "Try checking out /api/cv"
    }), 200

@app.route('/health')
def health_check():
    """Standard healthcheck route for load balancers / cloudflared."""
    return jsonify({"status": "healthy"}), 200

@app.route('/api/cv', methods=['GET'])
def get_cvs():
    """
    Get CVs, demonstrating querying inside a JSON column via SQLite.
    """
    try:
        results = query_example_json()
        return jsonify({
            "status": "success",
            "count": len(results),
            "data": results
        }), 200
    except Exception as e:
        app.logger.error(f"Error querying CVs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/cv', methods=['POST'])
def add_cv():
    """
    Add a new CV with dynamic JSON data.
    Body should contain: { "user_id": int, "title": str, "summary": str, "cv_data": dict }
    """
    data = request.json
    
    # Basic validation
    if not data or not data.get('user_id') or not data.get('title') or not data.get('cv_data'):
        return jsonify({"error": "Missing required fields (user_id, title, cv_data)"}), 400
        
    import json
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cv_json = json.dumps(data['cv_data'])
        
        cursor.execute(
            "INSERT INTO CV_Catalog (user_id, title, summary, cv_data) VALUES (?, ?, ?, ?)",
            (data['user_id'], data['title'], data.get('summary', ''), cv_json)
        )
        conn.commit()
        cv_id = cursor.lastrowid
        
        return jsonify({"message": "CV stored successfully", "cv_id": cv_id}), 201
    except Exception as e:
        app.logger.error(f"Database error while saving CV: {e}")
        conn.rollback()
        return jsonify({"error": "Failed to create CV"}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    # Initialize the local database file if it doesn't exist
    if not os.path.exists('proglem.db'):
        app.logger.info("Database not found. Initializing a fresh one...")
        init_db()
        insert_example_data()
        
    # Running strictly on 127.0.0.1 for an NGINX reverse-proxy setup
    app.run(host='127.0.0.1', port=5000, debug=True)

@app.route('/api/jam/get_upload_url', methods=['GET'])
def get_upload_url():
    """Generates a secure S3/R2 upload URL to bypass local bandwidth limits."""
    
    # 1. Verify the unique upload key header
    auth_key = request.headers.get('unique_upload_key')
    if auth_key != "my-secret-jam-key": # In production, validate against DB
        return jsonify({"error": "Unauthorized"}), 403

    filename = request.args.get('filename', 'default.zip')
    
    # 2. Configure Boto3 for Cloudflare R2 (or AWS S3)
    # R2 uses S3-compatible APIs. 
    s3_client = boto3.client(
        's3',
        endpoint_url=os.environ.get('R2_ENDPOINT_URL'), # e.g., https://<accountid>.r2.cloudflarestorage.com
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID', 'your-key'),
        aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY', 'your-secret'),
        region_name='auto' 
    )

    # 3. Generate the Pre-signed POST
    try:
        presigned_data = s3_client.generate_presigned_post(
            Bucket=os.environ.get('R2_BUCKET_NAME', 'jam-uploads'),
            Key=f"submissions/{filename}",
            Conditions=[
                ["content-length-range", 1, 524288000] # Max 500MB per game
            ],
            ExpiresIn=3600 # URL expires in 1 hour
        )
        # Returns { "url": "...", "fields": { "key": "...", "policy": "..." } }
        return jsonify(presigned_data)
        
    except ClientError as e:
        return jsonify({"error": str(e)}), 500

# Initialize the LLM before the first request
@app.before_first_request
def setup_ai():
    # In a real setup, ensure the model file is downloaded!
    try:
        ai_service.init_llm()
    except Exception as e:
        print(f"⚠️ Skipping LLM init (model missing or not configured): {e}")

@app.route('/api/ai/ask', methods=['POST'])
def ask_ai():
    """Submit a question to the local AI."""
    data = request.json
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    task_id, is_busy = ai_service.submit_prompt(prompt)

    # The magic 202 Response:
    if is_busy:
        return jsonify({
            "message": "AI is currently thinking about another request. You are in the queue.",
            "task_id": task_id,
            "status": "thinking"
        }), 202 # HTTP 202 Accepted (Processing, but not finished)
    else:
        return jsonify({
            "message": "Request accepted. AI is processing.",
            "task_id": task_id,
            "status": "thinking"
        }), 202

@app.route('/api/ai/status/<task_id>', methods=['GET'])
def ai_status(task_id):
    """Poll this endpoint to get the final answer."""
    result = ai_service.get_result(task_id)
    return jsonify(result)