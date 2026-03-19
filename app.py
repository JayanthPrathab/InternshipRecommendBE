import jwt
import datetime
import os
import time
import random
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Security Configuration
# In production, set JWT_SECRET in your .env file
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET", "intern-intel-super-secret-2026")

# MongoDB connection
MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["sih_db"]
candidates_col = db["candidates"]
companies_col = db["companies"]
applications_col = db["applications"]
candidate_users_col = db["candidate_users"]
company_users_col = db["company_users"]

# -------------------------------
# JWT Decorator (Security Guard)
# -------------------------------

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check if "Authorization" header is present
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            # Expected format: "Bearer <token>"
            if " " in auth_header:
                token = auth_header.split(" ")[1]
            else:
                token = auth_header

        if not token:
            return jsonify({'error': 'Token is missing!'}), 401

        try:
            # Decode the token using our secret key
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            # You can optionally pass 'data' to the route if needed
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired! Please login again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token!'}), 401
        except Exception as e:
            return jsonify({'error': str(e)}), 401

        return f(*args, **kwargs)
    return decorated

# -------------------------------
# Pydantic Schemas
# -------------------------------

class UserModel(BaseModel):
    email: str
    password: str
    role: str

class CandidateModel(BaseModel):
    user_id: str
    name: str
    skills: list[str] = Field(default_factory=list)
    education: str
    stream: str
    location: str

class CompanyModel(BaseModel):
    companyId: str
    companyName: str
    jobTitle: str
    jobDescription: str
    skillsRequired: list[str] = Field(default_factory=list)
    location: str
    womenPreference: bool = False
    openings: int = 1
    deadline: int = 30

# -------------------------------
# Routes
# -------------------------------

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Welcome to InternIntel API"})

@app.route("/api/register", methods=["POST"])
def register_user():
    data = request.json
    try:
        name = data.get("name", "") 
        user = UserModel(**data)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    users_col = candidate_users_col if user.role == "candidate" else company_users_col

    if users_col.find_one({"email": user.email}):
        return jsonify({"error": "Email already registered"}), 400

    hashed_pw = generate_password_hash(user.password)
    
    user_doc = {"email": user.email, "password": hashed_pw, "role": user.role}
    if name:
        user_doc["name"] = name

    result = users_col.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Generate token for immediate login after registration
    token = jwt.encode({
        'user_id': user_id,
        'role': user.role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        "message": f"{user.role.capitalize()} registered successfully",
        "token": token,
        "user_id": user_id,
        "role": user.role
    }), 201

@app.route("/api/login", methods=["POST"])
def login_user():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    users_col = candidate_users_col if role == "candidate" else company_users_col
    user = users_col.find_one({"email": email})
    
    if not user:
        return jsonify({"error": "User not found. Please register."}), 404

    if not check_password_hash(user.get("password", ""), password):
        return jsonify({"error": "Incorrect password. Please try again."}), 401

    # Generate JWT Token
    token = jwt.encode({
        'user_id': str(user["_id"]),
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user_id": str(user["_id"]),
        "role": role
    }), 200

@app.route("/api/candidates", methods=["POST"])
@token_required # Protected route
def add_or_update_candidate():
    try:
        data = request.json
        candidate = CandidateModel(**data)
        update_data = candidate.dict(exclude_unset=True)

        existing = candidates_col.find_one_and_update(
            {"user_id": candidate.user_id},
            {"$set": update_data},
            upsert=True,
            return_document=True
        )
        return jsonify({"message": "Candidate profile saved", "id": str(existing["_id"])})
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

@app.route("/api/candidates/<user_id>", methods=["GET"])
@token_required
def get_candidate_by_user(user_id):
    candidate = candidates_col.find_one({"user_id": user_id})
    if not candidate:
        return jsonify({"error": "Profile not found"}), 404
    
    candidate["_id"] = str(candidate["_id"])
    return jsonify(candidate)

@app.route("/api/internships", methods=["POST"])
@token_required
def add_internship():
    try:
        data = request.json
        company = CompanyModel(**data)
        result = companies_col.insert_one(company.dict())
        return jsonify({"message": "Internship added", "id": str(result.inserted_id)}), 201
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

@app.route("/api/internships", methods=["GET"])
def get_internships():
    jobs = list(companies_col.find())
    for j in jobs:
        j["_id"] = str(j["_id"])
    return jsonify(jobs)

@app.route("/api/applications", methods=["POST"])
@token_required
def submit_application():
    data = request.json
    if not all(k in data for k in ["userId", "jobId", "userName"]):
        return jsonify({"error": "Missing required fields"}), 400

    existing_app = applications_col.find_one({"userId": data["userId"], "jobId": data["jobId"]})
    if existing_app:
        return jsonify({"error": "You have already applied for this job"}), 409

    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(100, 999)
    data["applicationNumber"] = f"APP-{timestamp}{random_suffix}"
    data["status"] = "Applied"

    result = applications_col.insert_one(data)
    return jsonify({"message": "Application submitted successfully", "id": str(result.inserted_id)}), 201

@app.route("/api/recommendations/<candidate_id>", methods=["GET"])
@token_required
def recommend_internships(candidate_id):
    try:
        candidate = candidates_col.find_one({"_id": ObjectId(candidate_id)})
    except Exception:
        return jsonify({"error": "Invalid candidate ID format"}), 400

    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    internships = list(companies_col.find())
    if not internships:
        return jsonify([])

    candidate_loc = candidate.get("location", "").lower()
    filtered = [job for job in internships if job.get("location", "").lower() == candidate_loc]

    if not filtered:
        return jsonify([])

    candidate_skill_set = set(candidate.get("skills", []))
    results = []
    for job in filtered:
        job["_id"] = str(job["_id"])
        required_skills = set(job.get("skillsRequired", []))
        
        if not required_skills:
            score = 0
        else:
            matched_skills = candidate_skill_set.intersection(required_skills)
            score = (len(matched_skills) / len(required_skills)) * 100
        
        if score == 0:
            continue

        job["score"] = score
        missing_skills = required_skills - candidate_skill_set
        job["predictedSkill"] = list(missing_skills)[0] if missing_skills else None
        
        if job["predictedSkill"]:
            improved_matches = len(matched_skills) + 1
            job["predictedScore"] = (improved_matches / len(required_skills)) * 100
        else:
            job["predictedScore"] = score

        results.append(job)

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    return jsonify(ranked[:5])

if __name__ == "__main__":
    app.run(debug=True, port=5000)