from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time     # <-- ADDED
import random   # <-- ADDED

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

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
    openings: int = 1  # <-- ADDED
    deadline: int = 30 # <-- ADDED

# -------------------------------
# Routes
# -------------------------------

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "Welcome to the Internship Finder API"})

# ... (register_user and login_user routes are unchanged) ...
@app.route("/api/register", methods=["POST"])
def register_user():
    data = request.json
    try:
        user = UserModel(**data)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    users_col = candidate_users_col if user.role == "candidate" else company_users_col

    if users_col.find_one({"email": user.email}):
        return jsonify({"error": "Email already registered"}), 400

    hashed_pw = generate_password_hash(user.password)
    result = users_col.insert_one({"email": user.email, "password": hashed_pw})
    return jsonify({
        "message": f"{user.role.capitalize()} registered successfully",
        "user_id": str(result.inserted_id)
    }), 201

@app.route("/api/login", methods=["POST"])
def login_user():
    data = request.json
    email, password, role = data.get("email"), data.get("password"), data.get("role")

    users_col = candidate_users_col if role == "candidate" else company_users_col

    user = users_col.find_one({"email": email})
    if not user or not check_password_hash(user.get("password", ""), password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "role": role
    }), 200

# ... (candidate routes are unchanged) ...
@app.route("/api/candidates", methods=["POST"])
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
def get_candidate_by_user(user_id):
    candidate = candidates_col.find_one({"user_id": user_id})
    if not candidate:
        return jsonify({"error": "Profile not found"}), 404
    
    candidate["_id"] = str(candidate["_id"])
    return jsonify(candidate)

# ... (internship routes are unchanged) ...
@app.route("/api/internships", methods=["POST"])
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


# --- Application Routes (MODIFIED) ---

@app.route("/api/applications", methods=["POST"])
def submit_application():
    data = request.json
    if not all(k in data for k in ["userId", "jobId", "userName"]):
        return jsonify({"error": "Missing required fields"}), 400

    existing_app = applications_col.find_one({"userId": data["userId"], "jobId": data["jobId"]})
    if existing_app:
        return jsonify({"error": "You have already applied for this job"}), 409

    # Generate unique application number and set status
    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(100, 999)
    data["applicationNumber"] = f"APP-{timestamp}{random_suffix}" # <-- MODIFIED
    data["status"] = "Applied"                                   # <-- ADDED

    result = applications_col.insert_one(data)
    return jsonify({"message": "Application submitted successfully", "id": str(result.inserted_id)}), 201

# ... (get_applications_by_company route is unchanged) ...
@app.route("/api/applications/company/<company_id>", methods=["GET"])
def get_applications_by_company(company_id):
    posted_jobs = list(companies_col.find({"companyId": company_id}))
    if not posted_jobs:
        return jsonify([])

    job_ids = [str(job["_id"]) for job in posted_jobs]
    applications = list(applications_col.find({"jobId": {"$in": job_ids}}))

    for app in applications:
        app["_id"] = str(app["_id"])

    return jsonify(applications)

# ... (recommendations and main are unchanged) ...
@app.route("/api/recommendations/<candidate_id>", methods=["GET"])
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