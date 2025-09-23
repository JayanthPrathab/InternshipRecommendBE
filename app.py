from flask import Flask, request, jsonify, render_template
from flask_babel import Babel, _
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.security import generate_password_hash, check_password_hash

import os

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
babel = Babel(app)
CORS(app)
CORS(app, resources={r"/*": {"origins": "*"}})

# MongoDB connection
MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["sih_db"]  # Database name
candidates_col = db["candidates"]
companies_col = db["companies"]

# -------------------------------
# Pydantic Schemas
# -------------------------------

class UserModel(BaseModel):
    email: str
    password: str
    role: str  # "candidate" or "admin"

class CandidateModel(BaseModel):
    user_id: str   # Mongo ObjectId as string (from users collection)
    name: str
    skills: list[str] = Field(default_factory=list)
    education: str
    stream: str
    location: str


class CompanyModel(BaseModel):
    companyName: str
    jobTitle: str
    jobDescription: str
    skillsRequired: list[str] = Field(default_factory=list)
    location: str
    womenPreference: bool = False


# -------------------------------
# Routes
# -------------------------------
# @babel.locale_selector
# def get_locale():
#     return request.args.get('lang') or 'en'

@app.route('/')
def home():
    return render_template("index.html", message=_("Welcome to Internship Finder"))

@app.route("/api/register", methods=["POST"])
def register_user():
    data = request.json
    user = UserModel(**data)

    if user.role == "candidate":
        users_col = db["candidate_users"]
    else:
        users_col = db["company_users"]

    # Check if email already exists
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

    if role == "candidate":
        users_col = db["candidate_users"]
    else:
        users_col = db["company_users"]

    user = users_col.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "role": role
    }), 200

@app.route("/api/candidates", methods=["POST"])
def add_or_update_candidate():
    try:
        data = request.json
        candidate = CandidateModel(**data)

        # Check if candidate profile already exists for this user
        existing = candidates_col.find_one({"user_id": candidate.user_id})

        if existing:
            # Update the existing profile
            candidates_col.update_one(
                {"user_id": candidate.user_id},
                {"$set": candidate.dict()}
            )
            return jsonify({"message": "Candidate profile updated", "id": str(existing["_id"])})
        else:
            # Insert new profile
            result = candidates_col.insert_one(candidate.dict())
            return jsonify({"message": "Candidate profile created", "id": str(result.inserted_id)}), 201

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

@app.route("/api/candidates/<user_id>", methods=["GET"])
def get_candidate_by_user(user_id):
    candidate = candidates_col.find_one({"user_id": user_id})
    if not candidate:
        return jsonify({"error": "Profile not found"}), 404
    
    candidate["_id"] = str(candidate["_id"])
    return jsonify(candidate)


@app.route("/api/internships", methods=["POST"])
def add_internship():
    try:
        data = request.json
        company = CompanyModel(**data)
        result = companies_col.insert_one(company.dict())
        return jsonify({"message": "Internship added", "id": str(result.inserted_id)}), 201
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400


@app.route("/api/candidates", methods=["GET"])
def get_candidates():
    candidates = list(candidates_col.find())
    for c in candidates:
        c["_id"] = str(c["_id"])
    return jsonify(candidates)


@app.route("/api/internships", methods=["GET"])
def get_internships():
    jobs = list(companies_col.find())
    for j in jobs:
        j["_id"] = str(j["_id"])
    return jsonify(jobs)


# -------------------------------
# AI Recommendation Engine
# -------------------------------

@app.route("/api/recommendations/<candidate_id>", methods=["GET"])
def recommend_internships(candidate_id):
    candidate = candidates_col.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    internships = list(companies_col.find())
    if not internships:
        return jsonify([])

    candidate_loc = candidate.get("location", "").lower()

    # ✅ Strict location filter
    filtered = [job for job in internships if job.get("location", "").lower() == candidate_loc]

    if not filtered:
        # No jobs in candidate's preferred location
        return jsonify([])

    candidate_skills = candidate.get("skills", [])
    candidate_skill_set = set(candidate_skills)

    results = []
    for job in filtered:
        job["_id"] = str(job["_id"])

        required_skills = set(job.get("skillsRequired", []))

        # ✅ Percentage skill match
        if required_skills:
            matched_skills = candidate_skill_set.intersection(required_skills)
            score = (len(matched_skills) / len(required_skills)) * 100
        else:
            score = 0

        if score == 0:
            continue  # skip irrelevant jobs

        job["score"] = score

        # Predicted improvement
        missing_skills = required_skills - candidate_skill_set
        predicted_skill = None
        predicted_score = score

        if missing_skills:
            test_skill = list(missing_skills)[0]  # suggest one missing skill
            improved_matches = len(matched_skills) + 1
            predicted_score = (improved_matches / len(required_skills)) * 100
            predicted_skill = test_skill

        job["predictedSkill"] = predicted_skill
        job["predictedScore"] = predicted_score
        results.append(job)

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    return jsonify(ranked[:5])



# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
