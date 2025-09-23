def get_recommendations(candidate, internships):
    recommendations = []
    candidate_skills = set(s.lower().strip() for s in candidate["skills"])
    preferred_locations = set(loc.lower().strip() for loc in candidate["preferred_locations"])

    for internship in internships:
        internship_skills = set(s.lower().strip() for s in internship.get("skills_required", []))
        location = internship.get("location", "").lower().strip()

        # Skill match
        overlap = candidate_skills.intersection(internship_skills)
        skill_score = len(overlap) / max(len(internship_skills), 1)

        # Location bonus
        location_bonus = 0.3 if location in preferred_locations else 0.0

        # Education bonus (optional)
        education_bonus = 0.2 if candidate.get("education", "").lower() in internship.get("job_title", "").lower() else 0.0

        total_score = skill_score + location_bonus + education_bonus

        recommendations.append({
            "internship_id": internship["internship_id"],
            "company": internship["company"],
            "job_title": internship["job_title"],
            "location": internship["location"],
            "score": round(total_score, 4)
        })

    # Sort by score
    recommendations = sorted(recommendations, key=lambda x: x["score"], reverse=True)
    return recommendations[:4]
