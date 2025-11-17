from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_from_directory
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_mail import Mail, Message
import os
import logging
import random
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
import warnings
import requests  
warnings.filterwarnings("ignore")
from flask_wtf.csrf import CSRFProtect
import re
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import ssl
import certifi
import html
from markupsafe import escape


try:
    load_dotenv()
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")


app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))


app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb+srv://kira_user:kira_db_1234@kira.qzitaui.mongodb.net/kira?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true&serverSelectionTimeoutMS=5000&appName=KIRA")
app.config["MONGO_CONNECT"] = False  # Lazy connection
app.config["MONGO_CONNECT_TIMEOUT_MS"] = 5000  # 5 second connection timeout
app.config["MONGO_SOCKET_TIMEOUT_MS"] = 5000   # 5 second socket timeout
app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"] = 5000  # 5 second server selection timeout
mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# Create indexes lazily to avoid startup connection issues
def ensure_indexes():
    try:
        mongo.db.users.create_index("email", unique=True)
        mongo.db.questions.create_index("username")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("EMAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("EMAIL_PASSWORD")
app.config['ADMIN_EMAIL'] = os.getenv('ADMIN_EMAIL')
mail = Mail(app)
csrf = CSRFProtect(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,  
    default_limits=["5 per minute"]  
)


logging.basicConfig(level=logging.INFO)  # Changed from DEBUG to reduce MongoDB noise
logger = logging.getLogger(__name__)

# Disable pymongo's debug logging
logging.getLogger('pymongo').setLevel(logging.WARNING)

# Flag to track if indexes have been created
indexes_created = False

@app.before_request
def before_first_request():
    global indexes_created
    if not indexes_created:
        ensure_indexes()
        indexes_created = True


# Google Gemini 2.5 Flash API endpoint and API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

# Load training data from text file
def load_training_data():
    """
    Load training data from data.txt file.
    Supports three formats:
    1. Q&A format (multi-line):
       "Question text",
       "output": "Answer text"
    2. Contact format:
       "name": "Person Name", "email": "email@kiit.ac.in"
    3. Input-Output format (single-line):
       "input": "Question", "output": {...structured data...}
    """
    try:
        with open("data.txt", "r", encoding="utf-8") as file:
            content = file.read()
        
        training_data = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Format 3: Single-line input-output format (campus locations, etc.)
            if '"input":' in line and '"output":' in line:
                import re
                # Extract input (question)
                input_match = re.search(r'"input":\s*"([^"]+)"', line)
                
                if input_match:
                    question = input_match.group(1)
                    
                    # Extract the output part (everything after "output":)
                    output_start = line.find('"output":') + 10
                    output_part = line[output_start:].strip()
                    
                    # Check if output is structured (has "name":, "address":, etc.)
                    if '"name":' in output_part:
                        # Parse structured output for campus locations
                        name_match = re.search(r'"name":\s*"([^"]+)"', output_part)
                        address_match = re.search(r'"address":\s*"([^"]+)"', output_part)
                        link_match = re.search(r'"google_maps_link":\s*"([^"]+)"', output_part)
                        
                        name = name_match.group(1) if name_match else ""
                        address = address_match.group(1) if address_match else ""
                        link = link_match.group(1) if link_match else ""
                        
                        # Create formatted answer
                        answer = f"{name} is located at {address}."
                        if link:
                            answer += f" Google Maps: {link}"
                        
                        training_data.append({
                            'input': question,
                            'output': answer
                        })
                    else:
                        # Simple text output
                        output_text = output_part.strip('"')
                        training_data.append({
                            'input': question,
                            'output': output_text
                        })
            
            # Format 1: Q&A pairs (question followed by output on next line)
            elif line.startswith('"') and line.endswith('",') and '"name":' not in line and '"input":' not in line:
                # Extract question
                question = line[1:-2]  # Remove quotes and comma
                
                # Look for the next line with "output"
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if '"output":' in next_line:
                        # Extract output - handle different quote patterns
                        output_start = next_line.find('"output":') + 10
                        output_text = next_line[output_start:].strip()
                        
                        # Remove quotes from output
                        if output_text.startswith('"'):
                            output_text = output_text[1:]
                        if output_text.endswith('"'):
                            output_text = output_text[:-1]
                        
                        training_data.append({
                            'input': question,
                            'output': output_text
                        })
            
            # Format 2: Contact information (name and email)
            elif '"name":' in line and '"email":' in line and '"input":' not in line:
                import re
                # Extract name and email using regex
                name_match = re.search(r'"name":\s*"([^"]+)"', line)
                email_match = re.search(r'"email":\s*"([^"]+)"', line)
                
                if name_match and email_match:
                    name = name_match.group(1)
                    email = email_match.group(1)
                    
                    # Create Q&A pairs for contact information
                    training_data.append({
                        'input': f"What is the contact information for {name}?",
                        'output': f"{name} can be contacted at email: {email}"
                    })
                    
                    training_data.append({
                        'input': f"What is {name}'s email?",
                        'output': f"{name}'s email is {email}"
                    })
                    
                    training_data.append({
                        'input': f"Who is {name}?",
                        'output': f"{name} is a faculty/staff member at KIIT. Contact: {email}"
                    })
                    
                    training_data.append({
                        'input': f"contact info of {name}",
                        'output': f"{name} - Email: {email}"
                    })
            
            i += 1
        
        logger.info(f"Loaded {len(training_data)} Q&A pairs from data.txt")
        return training_data
        
    except FileNotFoundError:
        logger.error("data.txt file not found, trying training_data.json as fallback")
        try:
            with open("training_data.json", "r") as file:
                return json.load(file)
        except:
            logger.error("Neither data.txt nor training_data.json found")
            return []
    except Exception as e:
        logger.error(f"Error loading training data: {e}")
        return []

training_data = load_training_data()

# ===== Security: Input Sanitization =====
def sanitize_input(text):
    """Sanitize user input to prevent XSS attacks"""
    if not text:
        return ""
    # Escape HTML characters
    sanitized = html.escape(str(text))
    # Remove potentially dangerous patterns
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    return sanitized.strip()

def validate_email(email):
    """Validate email format and domain"""
    if not email:
        return False
    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
    # Check KIIT domain
    return email.lower().endswith('@kiit.ac.in')

# Function to find relevant context based on query
def find_relevant_context(query, training_data, top_n=5):
    """
    Find the most relevant Q&A pairs from training data based on the user's query.
    Uses HYBRID approach: Regex patterns + keyword matching + similarity scoring.
    """
    import re
    from collections import Counter
    
    # Normalize and tokenize the query
    def normalize_text(text):
        text = text.lower()
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text
    
    def get_keywords(text):
        # Remove common stop words
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'and', 'or', 'but', 'what', 'how', 'when', 'where', 'who', 'which', 
                     'can', 'could', 'would', 'should', 'do', 'does', 'did', 'has', 'have', 'had',
                     'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her', 'its',
                     'our', 'their', 'me', 'him', 'us', 'them', 'this', 'that', 'these', 'those',
                     'am', 'be', 'been', 'being', 'by', 'from', 'with', 'about', 'into', 'through'}
        words = normalize_text(text).split()
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def stem_word(word):
        """Simple stemming to handle plurals and common variations"""
        # Remove common suffixes
        word = re.sub(r'(ing|ed|s|es|ies|tion|ly)$', '', word)
        return word if len(word) > 2 else word + 's'  # restore if too short
    
    def regex_word_match(keyword, text):
        """Use regex for precise word boundary matching with variations"""
        # Handle plurals and common variations
        pattern = rf'\b{re.escape(keyword)}(s|es|ed|ing)?\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def regex_phrase_match(phrase, text):
        """Use regex to find phrase with flexible word boundaries"""
        # Allow for minor variations (extra spaces, punctuation)
        phrase_pattern = r'\s+'.join([re.escape(word) for word in phrase.split()])
        pattern = rf'\b{phrase_pattern}\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    # Get query keywords
    query_keywords = get_keywords(query)
    query_keyword_counts = Counter(query_keywords)
    
    if not query_keywords:
        # If no keywords, return first few items
        return training_data[:top_n]
    
    # Normalize query for matching
    normalized_query = normalize_text(query)
    
    # Score each training item
    scored_items = []
    for item in training_data:
        input_text = item.get('input', '')
        output_text = item.get('output', '')
        
        # Normalize texts
        normalized_input = normalize_text(input_text)
        normalized_output = normalize_text(output_text)
        
        # Get keywords from input and output
        input_keywords = get_keywords(input_text)
        output_keywords = get_keywords(output_text)
        all_item_keywords = input_keywords + output_keywords
        
        # Calculate similarity score
        score = 0
        
        # 1. REGEX: Exact phrase matching with word boundaries (highest weight)
        if regex_phrase_match(normalized_query, normalized_input):
            score += 60  # Even higher for precise regex match
        elif normalized_query in normalized_input or normalized_input in normalized_query:
            score += 45
        
        # 2. REGEX: Word boundary matching for individual keywords
        for keyword in query_keywords:
            # Use regex for more precise matching with variations
            if regex_word_match(keyword, input_text):
                score += 7  # Higher score for regex word boundary match
            elif keyword in input_keywords:
                score += 5  # Regular keyword match
            
            if regex_word_match(keyword, output_text):
                score += 3
            elif keyword in output_keywords:
                score += 2
        
        # 3. Stem-based matching for variations (fees/fee, courses/course, etc.)
        for keyword in query_keywords:
            stemmed_keyword = stem_word(keyword)
            for item_keyword in all_item_keywords:
                stemmed_item = stem_word(item_keyword)
                if stemmed_keyword == stemmed_item and keyword != item_keyword:
                    score += 3  # Bonus for stem match (handles plurals, etc.)
        
        # 4. Partial matching for compound words and substrings
        for keyword in query_keywords:
            if len(keyword) > 3:
                for item_keyword in all_item_keywords:
                    if len(item_keyword) > 3:
                        if keyword in item_keyword or item_keyword in keyword:
                            score += 1
        
        # 5. REGEX: Multi-word phrase detection
        if len(query_keywords) >= 2:
            # Check for 2-word combinations
            for i in range(len(query_keywords) - 1):
                bigram = f"{query_keywords[i]} {query_keywords[i+1]}"
                if regex_phrase_match(bigram, input_text):
                    score += 10  # Strong signal for multi-word match
                if regex_phrase_match(bigram, output_text):
                    score += 5
        
        # 6. Bonus for multiple keyword matches
        common_keywords = set(query_keywords) & set(all_item_keywords)
        if len(common_keywords) > 1:
            score += len(common_keywords) * 3  # Increased bonus
        
        # 7. Query word order preservation bonus (using regex)
        if len(query_keywords) >= 2:
            # Check if keywords appear in similar order
            pattern_parts = [rf'(?=.*\b{re.escape(kw)})' for kw in query_keywords[:3]]
            order_pattern = ''.join(pattern_parts)
            if re.search(order_pattern, normalized_input, re.IGNORECASE):
                score += 5
        
        if score > 0:
            scored_items.append((score, item))
    
    # Sort by score (highest first) and return top N
    scored_items.sort(reverse=True, key=lambda x: x[0])
    relevant_items = [item for score, item in scored_items[:top_n]]
    
    # If we found fewer relevant items than requested, fill with general items
    if len(relevant_items) < top_n and len(training_data) > len(relevant_items):
        remaining_items = [item for item in training_data if item not in relevant_items]
        relevant_items.extend(remaining_items[:top_n - len(relevant_items)])
    
    return relevant_items if relevant_items else training_data[:top_n]

# Serve static files
@app.route("/static/<path:filename>")
@csrf.exempt
def static_files(filename):
    return send_from_directory("static", filename)

# Serve service worker (PWA)
@app.route("/service-worker.js")
@csrf.exempt
def service_worker():
    return send_from_directory("static", "service-worker.js", mimetype='application/javascript')

# Serve manifest (PWA)
@app.route("/manifest.json")
@csrf.exempt
def manifest():
    return send_from_directory("static", "manifest.json", mimetype='application/json')

# Serve Login.Page)
@app.route("/")
@csrf.exempt
def index():
    return render_template("loginpage.html")

# Serve registration page
@app.route("/register-page")
@csrf.exempt
def register_page():
    return render_template("registrationpage.html")

# User Registration Endpoint
@app.route("/register", methods=["POST"])
@csrf.exempt
def register():
    try:
        data = request.json
        logger.debug(f"Received registration data: {data}")

        name = data.get("name")
        email = data.get("email")
        roll_number = data.get("rollNumber")
        password = data.get("password")

        if not all([name, email, roll_number, password]):
            logger.error("Missing required fields")
            return jsonify({"success": False, "message": "All fields are required"}), 400
        
        # Sanitize inputs
        name = sanitize_input(name)
        email = sanitize_input(email)
        roll_number = sanitize_input(roll_number)
        
        # Validate email
        if not validate_email(email):
            logger.error(f"Invalid email: {email}")
            return jsonify({"success": False, "message": "Only @kiit.ac.in email addresses are allowed"}), 400
        
        # Validate name length
        if len(name) < 3 or len(name) > 100:
            return jsonify({"success": False, "message": "Name must be between 3 and 100 characters"}), 400
        
        # Validate roll number format
        if not re.match(r'^[0-9]{7,10}$', roll_number):
            return jsonify({"success": False, "message": "Invalid roll number format"}), 400
        
        # Validate password strength
        if len(password) < 8:
            return jsonify({"success": False, "message": "Password must be at least 8 characters"}), 400

        existing_user = mongo.db.users.find_one({"email": email})
        if existing_user:
            logger.error("User already exists")
            return jsonify({"success": False, "message": "This email is already registered. Try logging in or using a different email."}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        user_data = {
            "name": name,
            "email": email,
            "roll_number": roll_number,
            "password": hashed_password
        }
        mongo.db.users.insert_one(user_data)
        logger.debug(f"User registered successfully: {user_data}")

        return jsonify({"success": True, "message": "User registered successfully"}), 201

    except Exception as e:
        logger.error(f"Error during registration: {e}")
        return jsonify({"success": False, "message": "An error occurred during registration"}), 500

# Send OTP Endpoint
@app.route("/send-otp", methods=["POST"])
@csrf.exempt
def send_otp():
    try:
        data = request.json
        email = data.get("email")

        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400

        otp = str(random.randint(1000, 9999))
        expiry_time = datetime.utcnow() + timedelta(minutes=15)

        mongo.db.otp_verification.update_one(
            {"email": email},
            {"$set": {"otp": otp, "expires_at": expiry_time}},
            upsert=True
        )

        msg = Message(
            subject="Your OTP Code",
            sender=app.config["MAIL_USERNAME"],
            recipients=[email],
            body=f"Your OTP for registration is: {otp}. It will expire in 15 minutes."
        )
        mail.send(msg)

        return jsonify({"success": True, "message": "OTP sent successfully"}), 200

    except Exception as e:
        logger.error(f"Error sending OTP: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/verify-otp", methods=["POST"])
@csrf.exempt
def verify_otp():
    try:
        data = request.json
        name = data.get("name")
        email = data.get("email")
        roll_number = data.get("rollNumber")
        password = data.get("password")
        otp = data.get("otp")

        if not all([name, email, roll_number, password, otp]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        otp_record = mongo.db.otp_verification.find_one({"email": email})

        if not otp_record or otp_record["otp"] != otp:
            return jsonify({"success": False, "message": "Invalid OTP"}), 400

        if otp_record["expires_at"] < datetime.utcnow():
            return jsonify({"success": False, "message": "OTP has expired"}), 400

        existing_user = mongo.db.users.find_one({"email": email})
        if existing_user:
            return jsonify({"success": False, "message": "This email is already registered"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        mongo.db.users.insert_one({
            "name": name,
            "email": email,
            "roll_number": roll_number,
            "password": hashed_password
        })

        mongo.db.otp_verification.delete_one({"email": email})

        return jsonify({"success": True, "message": "User registered successfully"}), 201

    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
    
        data = request.json
        logger.debug(f"Received login data: {data}")

        email = data.get("email")
        password = data.get("password")
        remember_me = data.get("remember_me", False)

        if not all([email, password]):
            logger.error("Missing email or password")
            return jsonify({"success": False, "message": "Email and password are required"}), 400
        
        # Validate KIIT email domain
        if not email.lower().endswith('@kiit.ac.in'):
            logger.error(f"Invalid email domain: {email}")
            return jsonify({"success": False, "message": "Only @kiit.ac.in email addresses are allowed"}), 400

        user = mongo.db.users.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = email
            session["email"] = email
            
            # Set session to permanent if remember me is checked
            if remember_me:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            else:
                session.permanent = False
            
            # Update last login time
            mongo.db.users.update_one(
                {"email": email},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            
            logger.debug(f"User logged in successfully: {email}")
            return jsonify({"success": True, "message": "Login successful", "redirect": url_for("chat")}), 200

        logger.error("Invalid credentials")
        return jsonify({"success": False, "message": "Incorrect email or password. Please check and try again."}), 401

    except Exception as e:
        logger.error(f"Error during login: {e}")
        return jsonify({"success": False, "message": "An error occurred during login"}), 500

@app.route("/ask", methods=["POST"])
@csrf.exempt
@limiter.limit("30 per minute")  # Rate limiting: 30 requests per minute
def ask():
    if "user" not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401
    try:
        data = request.json
        question = data.get("question")
        session_id = data.get("session_id")  # Get session_id from request
        
        if not question:
            return jsonify({"success": False, "message": "Question is required"}), 400
        
        # Sanitize input
        question = sanitize_input(question)
        
        # Validate question length
        if len(question) > 500:
            return jsonify({"success": False, "message": "Question too long (max 500 characters)"}), 400

        username = session["user"]
        email = session.get("email")
        
        # Handle greetings and common conversational inputs
        greeting_patterns = [
            r'\b(hi|hello|hey|hola|namaste|greetings)\b',
            r'\b(good morning|good afternoon|good evening)\b',
            r'\b(how are you|what\'s up|wassup)\b'
        ]
        
        question_lower = question.lower().strip()
        is_greeting = any(re.search(pattern, question_lower, re.IGNORECASE) for pattern in greeting_patterns)
        
        if is_greeting and len(question.split()) <= 5:
            # Handle pure greetings
            return jsonify({
                "success": True, 
                "answer": "Hello! 👋 I'm KiRA, your AI assistant for KIIT University. I can help you with:\n\n• Campus locations and facilities\n• Faculty contact information\n• Academic programs and courses\n• Admission procedures\n• Exam schedules\n• University policies\n\nWhat would you like to know about KIIT?"
            }), 200

        # Store question in database with better error handling
        try:
            user_query_doc = mongo.db.questions.find_one({"username": username})
            if user_query_doc:
                existing_questions = {q["qns"].lower() for q in user_query_doc.get("queries", [])}
                if question.lower() not in existing_questions:
                    mongo.db.questions.update_one(
                        {"username": username},
                        {"$push": {"queries": {"qns": question, "timestamp": datetime.utcnow()}}}
                    )
            else:
                query_data = {
                    "username": username,
                    "queries": [{"qns": question, "timestamp": datetime.utcnow()}]
                }
                mongo.db.questions.insert_one(query_data)
        except Exception as db_error:
            logger.warning(f"Database error (non-critical): {db_error}")
            # Continue even if database save fails

        # Find relevant context from training data based on the query
        # Using 15 items from 620+ Q&A pairs (multiple formats: Q&A, contacts, campus locations)
        relevant_items = find_relevant_context(question, training_data, top_n=15)
        
        # Build context from relevant training data
        if relevant_items:
            context = "\n\n".join([f"Q: {item['input']}\nA: {item['output']}" for item in relevant_items])
            logger.info(f"Found {len(relevant_items)} relevant context items for query")
        else:
            context = "No specific context available."
            logger.warning("No relevant context found for query")
        
        # Prepare payload for Gemini API
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"""You are KIRA, an AI assistant for KIIT University. 

IMPORTANT INSTRUCTIONS:
1. You must ONLY use the information provided in the context below to answer questions.
2. DO NOT use your general knowledge or make up information.
3. If the answer is NOT found in the context, you must respond EXACTLY with: "Sorry!! Failed to generate Response."
4. Do not add explanations or suggestions if the answer is not in the context.

Context from Knowledge Base:
{context}

User Question: {question}

Answer the question ONLY if the information is present in the context above. Otherwise, respond with exactly: "Sorry!! Failed to generate Response." """
                }]
            }]
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Make API request with retry logic and shorter timeout
        max_retries = 2
        timeout = 15
        
        for attempt in range(max_retries):
            try:
                response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"API request attempt {attempt + 1} failed: {e}. Retrying...")
                    continue
                else:
                    logger.error(f"API request failed after {max_retries} attempts: {e}")
                    return jsonify({
                        "success": False, 
                        "answer": "I'm having trouble connecting to the AI service right now. Please check your internet connection and try again."
                    }), 200
            except Exception as e:
                logger.error(f"Unexpected error calling Gemini API: {e}")
                return jsonify({
                    "success": False, 
                    "answer": "Sorry, I encountered an error while processing your question. Please try again."
                }), 200

        # Extract text from Gemini response
        try:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                generated_text = result['candidates'][0]['content']['parts'][0]['text']
            else:
                generated_text = "Sorry, I couldn't find an answer."

            formatted_text = generated_text.replace("*", "").strip()
            
            # Save messages to chat session if session_id is provided
            if session_id and email:
                try:
                    from bson.objectid import ObjectId
                    mongo.db.chat_sessions.update_one(
                        {"_id": ObjectId(session_id), "user_email": email},
                        {"$push": {
                            "messages": {
                                "$each": [
                                    {"role": "user", "content": question, "timestamp": datetime.utcnow()},
                                    {"role": "assistant", "content": formatted_text, "timestamp": datetime.utcnow()}
                                ]
                            }
                        }}
                    )
                except Exception as session_error:
                    logger.warning(f"Error saving to chat session: {session_error}")
            
            return jsonify({"success": True, "answer": formatted_text}), 200
            
        except Exception as parse_error:
            logger.error(f"Error parsing API response: {parse_error}")
            return jsonify({
                "success": False, 
                "answer": "Sorry, I couldn't process the response properly. Please try again."
            }), 200

    except Exception as e:
        logger.error(f"Error during question processing: {e}")
        return jsonify({
            "success": False, 
            "answer": "An unexpected error occurred. Please try again later."
        }), 200
    

@app.route("/get-queries", methods=["GET"])
@csrf.exempt
def get_queries():
    if "user" not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401
    try:
        username = session["user"]
        
        # Try to connect to MongoDB with timeout handling
        try:
            user_query_doc = mongo.db.questions.find_one(
                {"username": username},
                max_time_ms=5000  # 5 second timeout
            )
        except Exception as db_error:
            logger.error(f"Database connection error: {db_error}")
            # Return empty list rather than failing completely
            return jsonify({"success": True, "queries": []}), 200

        if not user_query_doc:
            return jsonify({"success": True, "queries": []}), 200

        # Deduplicate while preserving order and keeping latest entries
        seen = set()
        deduped_queries = []
        
        # Reverse to process oldest first, then reverse again to maintain recent-first order
        for query in reversed(user_query_doc.get("queries", [])):
            clean_q = query["qns"].strip().lower()
            if clean_q not in seen:
                seen.add(clean_q)
                deduped_queries.append(query)
        
        # Reverse back to show most recent first
        deduped_queries.reverse()

        # Format timestamps
        for query in deduped_queries:
            if "timestamp" in query:
                try:
                    query["timestamp"] = query["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                except:
                    query["timestamp"] = "N/A"

        return jsonify({"success": True, "queries": deduped_queries}), 200

    except Exception as e:
        logger.error(f"Error retrieving queries: {e}")
        # Return empty list so the UI doesn't break
        return jsonify({"success": True, "queries": []}), 200
    

@app.route("/recent-questions", methods=["GET"])
@csrf.exempt
def recent_questions():
    if "user" not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401

    try:
        username = session["user"]
        user_query_doc = mongo.db.questions.find_one({"username": username}, {"_id": 0, "queries": 1})

        if user_query_doc and "queries" in user_query_doc:
            # Remove duplicate questions while preserving order
            seen_questions = set()
            unique_queries = []
            for query in user_query_doc["queries"]:
                if query["qns"].lower() not in seen_questions:
                    seen_questions.add(query["qns"].lower())
                    unique_queries.append(query)

            # Sort by timestamp in descending order (most recent first)
            unique_queries.sort(key=lambda x: x["timestamp"], reverse=True)

            return jsonify({"success": True, "questions": unique_queries}), 200
        else:
            return jsonify({"success": True, "questions": []}), 200

    except Exception as e:
        logger.error(f"Error fetching recent questions: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500
    

# Serve chat.html (Chat Page)
@app.route("/chat")
@csrf.exempt
def chat():
    if "user" in session:
        return render_template("chat.html")
    return redirect(url_for("index"))

# Get user info endpoint
@app.route("/get-user-info", methods=["GET"])
@csrf.exempt
def get_user_info():
    if "user" not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401
    
    try:
        email = session["user"]
        user = mongo.db.users.find_one({"email": email}, {"_id": 0, "name": 1, "email": 1, "roll_number": 1, "role": 1})
        
        if user:
            # Get user statistics
            query_doc = mongo.db.questions.find_one({"username": email})
            total_questions = len(query_doc.get("queries", [])) if query_doc else 0
            
            return jsonify({
                "success": True, 
                "name": user.get("name", "User"), 
                "email": user.get("email", ""),
                "roll_number": user.get("roll_number", "N/A"),
                "role": user.get("role", "user"),
                "total_questions": total_questions
            }), 200
        else:
            return jsonify({"success": False, "message": "User not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500

# Serve about.html (About Page)
@app.route("/about")
@csrf.exempt
def about():
    return render_template("about.html")

# Serve contact.html (Contact Page)
@app.route("/contact")
@csrf.exempt
def contact():
    return render_template("contact.html")

@app.route('/submit-form', methods=['POST'])
@limiter.limit("5 per minute")
def submit_contact_form():
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        # Validate inputs
        if not all([name, email, message]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"success": False, "message": "Invalid email format"}), 400

        # Validate email domain (@kiit.ac.in)
        if not email.endswith('@kiit.ac.in'):
            return jsonify({"success": False, "message": "Please use your KIIT University email ID (@kiit.ac.in)"}), 400

        # Validate message length
        if len(message) > 1000:
            return jsonify({"success": False, "message": "Message too long (max 1000 characters)"}), 400

        # Store in MongoDB
        submission = {
            "name": name,
            "email": email,
            "message": message,
            "timestamp": datetime.utcnow(),
            "ip_address": request.remote_addr
        }
        mongo.db.contact_submissions.insert_one(submission)

        # Send email notification (optional)
        send_email_notification(name, email, message)

        return jsonify({"success": True, "message": "Your message has been sent successfully!"}), 200

    except Exception as e:
        logger.error(f"Error processing contact form: {e}")
        return jsonify({"success": False, "message": "An error occurred while processing your request"}), 500

def send_email_notification(name, email, message):
    """
    Send an email notification to the admin about the new contact form submission.
    """
    try:
        msg = Message(
            subject=f"KIRA Support Problem from {name}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[app.config['ADMIN_EMAIL']],
            body=f"""
            Name: {name}
            Email: {email}
            Message:
            {message}
            """
        )
        mail.send(msg)
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")

# Serve forgotpassword.html (Forgot Password Page)
@app.route("/forgotpassword")
@csrf.exempt
def forgot_password():
    return render_template("forgotpassword.html")

# Forgot Password Endpoint
@app.route("/forgot-password", methods=["POST"])
@csrf.exempt
def forgot_password_submit():
    try:
        data = request.json
        email = data.get("email")

        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400

        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "message": "Email not registered"}), 404

        otp = str(random.randint(1000, 9999))
        expiry_time = datetime.utcnow() + timedelta(minutes=15)

        mongo.db.users.update_one({"email": email}, {"$set": {"reset_otp": otp, "otp_expires_at": expiry_time}})

        msg = Message(
            subject="Password Reset OTP",
            sender=app.config["MAIL_USERNAME"],
            recipients=[email],
            body=f"Your OTP for password reset is: {otp}. It will expire in 15 minutes."
        )
        mail.send(msg)

        return jsonify({"success": True, "message": "OTP sent to your email"}), 200

    except Exception as e:
        logger.error(f"Error during forgot password: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500

# Reset Password Endpoint
@app.route("/reset-password", methods=["POST"])
@csrf.exempt
def reset_password():
    try:
        data = request.json
        email = data.get("email")
        new_password = data.get("new_password")

        if not all([email, new_password]):
            return jsonify({"success": False, "message": "Email and new password are required"}), 400

        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
        mongo.db.users.update_one({"email": email}, {"$set": {"password": hashed_password}})

        return jsonify({"success": True, "message": "Password reset successfully"}), 200

    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500

# Verify OTP for Password Reset
@app.route("/verify-reset-otp", methods=["POST"])
@csrf.exempt
def verify_reset_otp():
    try:
        data = request.json
        email = data.get("email")
        otp = data.get("otp")

        if not all([email, otp]):
            return jsonify({"success": False, "message": "Email and OTP are required"}), 400

        user = mongo.db.users.find_one({"email": email})
        if not user or "reset_otp" not in user or "otp_expires_at" not in user:
            return jsonify({"success": False, "message": "Invalid OTP request"}), 400

        if datetime.utcnow() > user["otp_expires_at"]:
            return jsonify({"success": False, "message": "OTP has expired. Please request a new one."}), 400

        if user["reset_otp"] != otp:
            return jsonify({"success": False, "message": "Invalid OTP"}), 400

        mongo.db.users.update_one({"email": email}, {"$unset": {"reset_otp": "", "otp_expires_at": ""}})

        return jsonify({"success": True, "message": "OTP verified successfully"}), 200

    except Exception as e:
        logger.error(f"Error during OTP verification: {e}")
        return jsonify({"success": False, "message": "An error occurred"}), 500

# Profile Page
@app.route('/profile')
@csrf.exempt
def profile():
    if 'user' not in session:
        return redirect(url_for('index'))

    user = mongo.db.users.find_one({"email": session['user']})
    if user:
        return render_template('profile.html')
    return redirect(url_for('index'))

@app.route('/settings')
@csrf.exempt
def settings():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('settings.html')

# Get Profile Data
@app.route('/get-profile')
@csrf.exempt
def get_profile():
    if 'user' not in session:
        return jsonify({"success": False}), 401

    try:
        email = session['user']
        user = mongo.db.users.find_one({"email": email}, {'_id': 0, 'password': 0})
        
        if user:
            # Get detailed statistics
            query_doc = mongo.db.questions.find_one({"username": email})
            queries = query_doc.get("queries", []) if query_doc else []
            
            # Calculate statistics
            total_questions = len(queries)
            
            # Get recent activity (last 5 questions with timestamps)
            recent_activity = []
            for query in sorted(queries, key=lambda x: x.get("timestamp", datetime.min), reverse=True)[:5]:
                recent_activity.append({
                    "question": query.get("qns", ""),
                    "timestamp": query.get("timestamp", datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S") if "timestamp" in query else "N/A"
                })
            
            # Add statistics to user object
            user['statistics'] = {
                'total_questions': total_questions,
                'recent_activity': recent_activity
            }
            
            return jsonify({"success": True, "user": user})
        return jsonify({"success": False}), 404
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Logout
@app.route("/logout")
@csrf.exempt
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

# Feedback route for message ratings
@app.route('/feedback', methods=['POST'])
@csrf.exempt
def save_feedback():
    """Save user feedback for bot responses"""
    try:
        data = request.json
        message_id = data.get('message_id')
        rating = data.get('rating')
        timestamp = data.get('timestamp')
        
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        # Save feedback to database
        feedback_data = {
            "email": email,
            "message_id": message_id,
            "rating": rating,
            "timestamp": timestamp,
            "created_at": datetime.utcnow()
        }
        
        mongo.db.feedback.insert_one(feedback_data)
        logger.info(f"Feedback saved: {email} - {rating}")
        
        return jsonify({"success": True, "message": "Feedback saved"}), 200
        
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return jsonify({"success": False, "message": "Error saving feedback"}), 500

# Update Profile route
@app.route('/update-profile', methods=['POST'])
@csrf.exempt
def update_profile():
    """Update user profile information"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        data = request.json
        name = data.get('name', '').strip()
        roll_number = data.get('roll_number', '').strip()
        
        # Validation
        if not name or len(name) < 3:
            return jsonify({"success": False, "message": "Name must be at least 3 characters"}), 400
        
        if not roll_number or not re.match(r'^[0-9]{7,10}$', roll_number):
            return jsonify({"success": False, "message": "Invalid roll number format"}), 400
        
        # Update user in database
        result = mongo.db.users.update_one(
            {"email": email},
            {"$set": {
                "name": name,
                "roll_number": roll_number,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"Profile updated for: {email}")
            return jsonify({"success": True, "message": "Profile updated successfully"}), 200
        else:
            return jsonify({"success": False, "message": "No changes made"}), 400
            
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return jsonify({"success": False, "message": "Error updating profile"}), 500

# Change Password route
@app.route('/change-password', methods=['POST'])
@csrf.exempt
def change_password():
    """Change user password"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        # Validation
        if not current_password or not new_password:
            return jsonify({"success": False, "message": "All fields are required"}), 400
        
        if len(new_password) < 8:
            return jsonify({"success": False, "message": "Password must be at least 8 characters"}), 400
        
        # Get user from database
        user = mongo.db.users.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Verify current password
        if not bcrypt.check_password_hash(user['password'], current_password):
            return jsonify({"success": False, "message": "Incorrect current password"}), 401
        
        # Hash new password
        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        # Update password in database
        mongo.db.users.update_one(
            {"email": email},
            {"$set": {
                "password": hashed_password,
                "password_updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"Password changed for: {email}")
        return jsonify({"success": True, "message": "Password changed successfully"}), 200
        
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({"success": False, "message": "Error changing password"}), 500

# ===== Chat Sessions Routes =====

@app.route('/get-chat-sessions', methods=['GET'])
def get_chat_sessions():
    """Get all chat sessions for the logged-in user"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        sessions = list(mongo.db.chat_sessions.find(
            {"user_email": email},
            {"_id": 1, "name": 1, "created_at": 1}
        ).sort("created_at", -1))
        
        # Convert ObjectId to string
        for sess in sessions:
            sess['_id'] = str(sess['_id'])
        
        return jsonify({"success": True, "sessions": sessions}), 200
        
    except Exception as e:
        logger.error(f"Error getting chat sessions: {e}")
        return jsonify({"success": False, "message": "Error loading sessions"}), 500

@app.route('/create-chat-session', methods=['POST'])
@csrf.exempt
def create_chat_session():
    """Create a new chat session"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        data = request.json
        session_name = data.get('name', f"Chat {datetime.now().strftime('%Y-%m-%d')}")
        
        new_session = {
            "user_email": email,
            "name": session_name,
            "created_at": datetime.utcnow(),
            "messages": []
        }
        
        result = mongo.db.chat_sessions.insert_one(new_session)
        
        logger.info(f"Chat session created for: {email}")
        return jsonify({"success": True, "session_id": str(result.inserted_id)}), 200
        
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        return jsonify({"success": False, "message": "Error creating session"}), 500

@app.route('/get-session-messages/<session_id>', methods=['GET'])
def get_session_messages(session_id):
    """Get all messages for a specific session"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        from bson.objectid import ObjectId
        
        chat_session = mongo.db.chat_sessions.find_one({
            "_id": ObjectId(session_id),
            "user_email": email
        })
        
        if not chat_session:
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        messages = chat_session.get('messages', [])
        
        return jsonify({"success": True, "messages": messages}), 200
        
    except Exception as e:
        logger.error(f"Error getting session messages: {e}")
        return jsonify({"success": False, "message": "Error loading messages"}), 500

@app.route('/rename-chat-session', methods=['POST'])
@csrf.exempt
def rename_chat_session():
    """Rename a chat session"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        data = request.json
        session_id = data.get('session_id')
        new_name = data.get('name', '').strip()
        
        if not session_id or not new_name:
            return jsonify({"success": False, "message": "Invalid data"}), 400
        
        from bson.objectid import ObjectId
        
        result = mongo.db.chat_sessions.update_one(
            {"_id": ObjectId(session_id), "user_email": email},
            {"$set": {"name": new_name}}
        )
        
        if result.modified_count > 0:
            return jsonify({"success": True, "message": "Session renamed"}), 200
        else:
            return jsonify({"success": False, "message": "Session not found"}), 404
        
    except Exception as e:
        logger.error(f"Error renaming session: {e}")
        return jsonify({"success": False, "message": "Error renaming session"}), 500

@app.route('/delete-chat-session', methods=['POST'])
@csrf.exempt
def delete_chat_session():
    """Delete a chat session"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({"success": False, "message": "Invalid session ID"}), 400
        
        from bson.objectid import ObjectId
        
        result = mongo.db.chat_sessions.delete_one({
            "_id": ObjectId(session_id),
            "user_email": email
        })
        
        if result.deleted_count > 0:
            return jsonify({"success": True, "message": "Session deleted"}), 200
        else:
            return jsonify({"success": False, "message": "Session not found"}), 404
        
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return jsonify({"success": False, "message": "Error deleting session"}), 500

# ===== End Chat Sessions Routes =====

# ===== Settings Routes =====

@app.route('/get-user-settings', methods=['GET'])
def get_user_settings():
    """Get user settings"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        user = mongo.db.users.find_one({"email": email})
        
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        settings = user.get('settings', {})
        
        return jsonify({"success": True, "settings": settings}), 200
        
    except Exception as e:
        logger.error(f"Error getting user settings: {e}")
        return jsonify({"success": False, "message": "Error loading settings"}), 500

@app.route('/update-user-settings', methods=['POST'])
@csrf.exempt
def update_user_settings():
    """Update user settings"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        data = request.json
        
        # Update settings in database
        result = mongo.db.users.update_one(
            {"email": email},
            {"$set": {f"settings.{key}": value for key, value in data.items()}}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            return jsonify({"success": True, "message": "Settings updated"}), 200
        else:
            return jsonify({"success": False, "message": "User not found"}), 404
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({"success": False, "message": "Error updating settings"}), 500

@app.route('/export-user-data', methods=['GET'])
def export_user_data():
    """Export all user data"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        # Get user data
        user = mongo.db.users.find_one({"email": email})
        questions = mongo.db.questions.find_one({"username": email})
        sessions = list(mongo.db.chat_sessions.find({"user_email": email}))
        feedback = list(mongo.db.feedback.find({"user_email": email}))
        
        # Remove sensitive data and convert ObjectId to string
        if user:
            user.pop('password', None)
            user['_id'] = str(user['_id'])
        
        if questions:
            questions['_id'] = str(questions['_id'])
        
        for sess in sessions:
            sess['_id'] = str(sess['_id'])
        
        for fb in feedback:
            fb['_id'] = str(fb['_id'])
        
        export_data = {
            "user": user,
            "questions": questions,
            "chat_sessions": sessions,
            "feedback": feedback,
            "export_date": datetime.utcnow().isoformat()
        }
        
        return jsonify({"success": True, "data": export_data}), 200
        
    except Exception as e:
        logger.error(f"Error exporting user data: {e}")
        return jsonify({"success": False, "message": "Error exporting data"}), 500

@app.route('/clear-chat-history', methods=['POST'])
@csrf.exempt
def clear_chat_history():
    """Clear user's chat history"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        # Delete all chat sessions
        mongo.db.chat_sessions.delete_many({"user_email": email})
        
        # Delete all questions
        mongo.db.questions.delete_one({"username": email})
        
        logger.info(f"Chat history cleared for: {email}")
        return jsonify({"success": True, "message": "Chat history cleared"}), 200
        
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        return jsonify({"success": False, "message": "Error clearing history"}), 500

@app.route('/delete-account', methods=['POST'])
@csrf.exempt
def delete_account():
    """Delete user account and all data"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        # Delete all user data
        mongo.db.users.delete_one({"email": email})
        mongo.db.questions.delete_one({"username": email})
        mongo.db.chat_sessions.delete_many({"user_email": email})
        mongo.db.feedback.delete_many({"user_email": email})
        
        # Clear session
        session.clear()
        
        logger.info(f"Account deleted: {email}")
        return jsonify({"success": True, "message": "Account deleted successfully"}), 200
        
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        return jsonify({"success": False, "message": "Error deleting account"}), 500

# ===== End Settings Routes =====

# Activity Analytics route
@app.route('/get-activity-analytics', methods=['GET'])
def get_activity_analytics():
    """Get activity analytics for charts"""
    try:
        email = session.get("email")
        if not email:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        # Get user's questions
        user_queries = mongo.db.questions.find_one({"username": email})
        
        if not user_queries or 'queries' not in user_queries:
            # Return empty data
            return jsonify({
                "success": True,
                "questions_over_time": {"labels": [], "values": []},
                "top_topics": {"labels": ["No data yet"], "values": [1]},
                "peak_hours": {"labels": [], "values": []}
            }), 200
        
        queries = user_queries['queries']
        
        # Questions Over Time (last 7 days)
        from collections import defaultdict
        questions_by_date = defaultdict(int)
        topics_count = defaultdict(int)
        hours_count = defaultdict(int)
        
        for query in queries:
            # Parse timestamp
            if 'timestamp' in query and query['timestamp']:
                try:
                    ts = query['timestamp']
                    date_str = ts.strftime('%m/%d')
                    hour = ts.hour
                    
                    questions_by_date[date_str] += 1
                    hours_count[hour] += 1
                except:
                    pass
            
            # Categorize topics (simple keyword matching)
            question_text = query.get('qns', '').lower()
            if any(word in question_text for word in ['campus', 'location', 'where', 'building']):
                topics_count['Campus'] += 1
            elif any(word in question_text for word in ['faculty', 'professor', 'teacher', 'contact']):
                topics_count['Faculty'] += 1
            elif any(word in question_text for word in ['exam', 'test', 'assessment']):
                topics_count['Exams'] += 1
            elif any(word in question_text for word in ['admission', 'enroll', 'apply']):
                topics_count['Admissions'] += 1
            elif any(word in question_text for word in ['course', 'program', 'degree']):
                topics_count['Courses'] += 1
            else:
                topics_count['General'] += 1
        
        # Format data for charts
        # Questions over time (last 7 days)
        from datetime import datetime, timedelta
        today = datetime.now()
        last_7_days = [(today - timedelta(days=i)).strftime('%m/%d') for i in range(6, -1, -1)]
        questions_over_time = {
            "labels": last_7_days,
            "values": [questions_by_date.get(date, 0) for date in last_7_days]
        }
        
        # Top topics
        sorted_topics = sorted(topics_count.items(), key=lambda x: x[1], reverse=True)[:6]
        top_topics = {
            "labels": [topic[0] for topic in sorted_topics],
            "values": [topic[1] for topic in sorted_topics]
        }
        
        # Peak hours
        hours_labels = [f"{h:02d}:00" for h in range(24)]
        peak_hours = {
            "labels": hours_labels,
            "values": [hours_count.get(h, 0) for h in range(24)]
        }
        
        return jsonify({
            "success": True,
            "questions_over_time": questions_over_time,
            "top_topics": top_topics,
            "peak_hours": peak_hours
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting activity analytics: {e}")
        return jsonify({"success": False, "message": "Error loading analytics"}), 500

# ===== Admin Dashboard Routes =====

def get_feedback_stats():
    """Get feedback statistics"""
    try:
        total_feedback = mongo.db.feedback.count_documents({})
        positive_feedback = mongo.db.feedback.count_documents({"rating": "positive"})
        negative_feedback = mongo.db.feedback.count_documents({"rating": "negative"})
        
        return {
            "total": total_feedback,
            "positive": positive_feedback,
            "negative": negative_feedback,
            "satisfaction_rate": round((positive_feedback / total_feedback * 100) if total_feedback > 0 else 0, 2)
        }
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        return {"total": 0, "positive": 0, "negative": 0, "satisfaction_rate": 0}

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard - requires admin role"""
    try:
        # Check if user is logged in
        if "email" not in session:
            return redirect(url_for('login_page'))
        
        # Check if user is admin
        user = mongo.db.users.find_one({"email": session.get("email")})
        if not user or user.get('role') != 'admin':
            return render_template('error.html', 
                                 message="Access Denied", 
                                 description="You don't have permission to access the admin dashboard."), 403
        
        # Get statistics
        stats = {
            'total_users': mongo.db.users.count_documents({}),
            'total_questions': sum(
                len(doc.get('queries', [])) 
                for doc in mongo.db.questions.find({}, {'queries': 1})
            ),
            'total_sessions': mongo.db.chat_sessions.count_documents({}),
            'active_sessions': mongo.db.chat_sessions.count_documents({
                'updated_at': {'$gte': datetime.utcnow() - timedelta(days=1)}
            }),
            'feedback_stats': get_feedback_stats(),
            'contact_submissions': mongo.db.contact_submissions.count_documents({})
        }
        
        return render_template('admin.html', stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        return render_template('error.html', 
                             message="Error", 
                             description="Failed to load admin dashboard."), 500

@app.route('/admin/api/stats', methods=['GET'])
def get_admin_stats():
    """Get detailed admin statistics (API endpoint)"""
    try:
        if "email" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        user = mongo.db.users.find_one({"email": session.get("email")})
        if not user or user.get('role') != 'admin':
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        # User growth over last 30 days
        user_growth = []
        for i in range(29, -1, -1):
            date = datetime.utcnow() - timedelta(days=i)
            count = mongo.db.users.count_documents({
                'created_at': {'$lte': date}
            })
            user_growth.append({
                'date': date.strftime('%m/%d'),
                'count': count
            })
        
        # Questions per day (last 7 days)
        questions_per_day = []
        for i in range(6, -1, -1):
            date = datetime.utcnow() - timedelta(days=i)
            date_str = date.strftime('%m/%d')
            
            # Count questions for this day
            count = 0
            for doc in mongo.db.questions.find({}, {'queries': 1}):
                for query in doc.get('queries', []):
                    if 'timestamp' in query:
                        query_date = query['timestamp'].strftime('%m/%d')
                        if query_date == date_str:
                            count += 1
            
            questions_per_day.append({
                'date': date_str,
                'count': count
            })
        
        # Top users by activity
        top_users = []
        for user_doc in mongo.db.questions.find({}, {'username': 1, 'queries': 1}).sort('queries', -1).limit(10):
            user_email = user_doc.get('username')
            query_count = len(user_doc.get('queries', []))
            user_info = mongo.db.users.find_one({'email': user_email}, {'name': 1, 'email': 1})
            
            if user_info:
                top_users.append({
                    'name': user_info.get('name', 'Unknown'),
                    'email': user_email,
                    'query_count': query_count
                })
        
        # Recent feedback
        recent_feedback = []
        for feedback in mongo.db.feedback.find({}).sort('timestamp', -1).limit(10):
            recent_feedback.append({
                'user_email': feedback.get('user_email', 'Anonymous'),
                'rating': feedback.get('rating'),
                'message': feedback.get('message_text', '')[:100],
                'timestamp': feedback.get('timestamp').strftime('%Y-%m-%d %H:%M') if feedback.get('timestamp') else 'N/A'
            })
        
        # System health
        system_health = {
            'database_status': 'healthy',
            'total_collections': len(mongo.db.list_collection_names()),
            'avg_response_time': 'N/A'  # Can be calculated if you track this
        }
        
        return jsonify({
            "success": True,
            "user_growth": user_growth,
            "questions_per_day": questions_per_day,
            "top_users": top_users,
            "recent_feedback": recent_feedback,
            "system_health": system_health
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        return jsonify({"success": False, "message": "Error loading statistics"}), 500

@app.route('/admin/api/users', methods=['GET'])
def get_all_users():
    """Get all users (admin only)"""
    try:
        if "email" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        user = mongo.db.users.find_one({"email": session.get("email")})
        if not user or user.get('role') != 'admin':
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        users = []
        for user_doc in mongo.db.users.find({}, {'password': 0}).sort('created_at', -1):
            user_doc['_id'] = str(user_doc['_id'])
            user_doc['created_at'] = user_doc.get('created_at').strftime('%Y-%m-%d %H:%M') if user_doc.get('created_at') else 'N/A'
            user_doc['last_login'] = user_doc.get('last_login').strftime('%Y-%m-%d %H:%M') if user_doc.get('last_login') else 'Never'
            users.append(user_doc)
        
        return jsonify({"success": True, "users": users}), 200
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({"success": False, "message": "Error loading users"}), 500

@app.route('/admin/api/promote-user', methods=['POST'])
@csrf.exempt
def promote_user():
    """Promote a user to admin"""
    try:
        if "email" not in session:
            return jsonify({"success": False, "message": "Not logged in"}), 401
        
        admin_user = mongo.db.users.find_one({"email": session.get("email")})
        if not admin_user or admin_user.get('role') != 'admin':
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        data = request.json
        target_email = data.get('email')
        
        if not target_email:
            return jsonify({"success": False, "message": "Email required"}), 400
        
        result = mongo.db.users.update_one(
            {"email": target_email},
            {"$set": {"role": "admin"}}
        )
        
        if result.modified_count > 0:
            logger.info(f"User {target_email} promoted to admin by {session.get('email')}")
            return jsonify({"success": True, "message": "User promoted to admin"}), 200
        else:
            return jsonify({"success": False, "message": "User not found"}), 404
        
    except Exception as e:
        logger.error(f"Error promoting user: {e}")
        return jsonify({"success": False, "message": "Error promoting user"}), 500

# ===== End Admin Dashboard Routes =====

# Google OAuth Login route
@app.route('/auth/google', methods=['POST'])
@csrf.exempt
def google_auth():
    """Handle Google OAuth login"""
    try:
        data = request.json
        credential = data.get('credential')
        
        if not credential:
            return jsonify({"success": False, "message": "No credential provided"}), 400
        
        # Verify the Google token (you'll need to install google-auth library)
        # For now, we'll decode the JWT to get user info
        import base64
        import json as json_lib
        
        # Decode JWT payload (simple decode, not verified - for production use google.oauth2.id_token)
        try:
            payload_part = credential.split('.')[1]
            # Add padding if needed
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += '=' * padding
            
            decoded_bytes = base64.urlsafe_b64decode(payload_part)
            user_info = json_lib.loads(decoded_bytes)
            
            email = user_info.get('email', '')
            name = user_info.get('name', '')
            
            # Validate KIIT email
            if not email.lower().endswith('@kiit.ac.in'):
                return jsonify({"success": False, "message": "Only @kiit.ac.in email addresses are allowed"}), 403
            
            # Check if user exists
            user = mongo.db.users.find_one({"email": email})
            
            if not user:
                # Create new user with Google auth
                new_user = {
                    "name": name,
                    "email": email,
                    "roll_number": "",  # Can be updated later
                    "password": bcrypt.generate_password_hash(os.urandom(24).hex()).decode('utf-8'),  # Random password
                    "auth_provider": "google",
                    "created_at": datetime.utcnow(),
                    "last_login": datetime.utcnow()
                }
                mongo.db.users.insert_one(new_user)
                logger.info(f"New Google user created: {email}")
            else:
                # Update last login
                mongo.db.users.update_one(
                    {"email": email},
                    {"$set": {"last_login": datetime.utcnow()}}
                )
            
            # Set session
            session["user"] = email
            session["email"] = email
            session.permanent = True
            
            logger.info(f"Google login successful: {email}")
            return jsonify({"success": True, "message": "Login successful", "redirect": url_for("chat")}), 200
            
        except Exception as decode_error:
            logger.error(f"Error decoding Google credential: {decode_error}")
            return jsonify({"success": False, "message": "Invalid Google credential"}), 400
        
    except Exception as e:
        logger.error(f"Error in Google auth: {e}")
        return jsonify({"success": False, "message": "Google authentication failed"}), 500

if __name__ == "__main__":
    # Use PORT environment variable for deployment, default to 5001 for local development
    port = int(os.getenv("PORT", 5001))
    debug = os.getenv("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)