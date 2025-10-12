from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import re 

# MongoDB helper
from mongodb_helper import MongoDBHelper
# Crew orchestrator
from loader import SkillSyncCrew

# Load env
load_dotenv()

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super_secret_key")

# MongoDB setup
mongo = MongoDBHelper()
mongo.select_db(db_name="SkillSyncDB", collection="users")

# Initialize crew once
crew = SkillSyncCrew()


# -------- Helper: calculate progress --------
def calculate_progress(roadmap):
    if not roadmap or "milestones" not in roadmap:
        return 0, []
    milestone_progress = []
    total_tasks = 0
    completed_tasks = 0
    
    # Safely convert string output from CrewAI into a usable dictionary
    if isinstance(roadmap, str):
         try:
             roadmap = json.loads(roadmap)
         except json.JSONDecodeError:
             return 0, []

    for m in roadmap.get("milestones", []):
        m_tasks = m.get("tasks", [])
        m_completed = sum(1 for t in m_tasks if t.get("done"))
        m_total = len(m_tasks)
        percent = int((m_completed / m_total) * 100) if m_total else 0
        milestone_progress.append(percent)
        total_tasks += m_total
        completed_tasks += m_completed
    overall_progress = int((completed_tasks / total_tasks) * 100) if total_tasks else 0
    return overall_progress, milestone_progress


# -------- Landing Page and Auth Routes --------
@app.route("/")
def home():
    return render_template("index_3.html")

def is_strong_password(password):
    """Checks if password is strong (8+ chars, upper, lower, digit, special)."""
    if len(password) < 8: return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password): return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password): return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password): return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?:{}|<>]", password): return False, "Password must contain at least one special character."
    return True, "Strong password."

@app.route("/login", methods=["POST"])
def login():
    email, password = request.form.get("email"), request.form.get("password")
    user = mongo.collection.find_one({"email": email})
    if user and check_password_hash(user["password"], password):
        session["user"] = user["email"]
        return redirect(url_for("dashboard"))
    flash("Invalid credentials", "error")
    return redirect(url_for("home"))

@app.route("/signup", methods=["POST"])
def signup():
    name, email, password, confirm = request.form.get("name"), request.form.get("email"), request.form.get("password"), request.form.get("confirm_password")
    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form: passwords do not match or fields are missing.", "error"); return redirect(url_for("home"))
    if not is_strong_password(password)[0]:
        flash(f"Weak password: {is_strong_password(password)[1]}", "error"); return redirect(url_for("home"))
    if mongo.collection.find_one({"email": email}):
        flash("User already exists", "error"); return redirect(url_for("home"))
    
    hashed_pw = generate_password_hash(password)
    mongo.insert_document({"name": name, "email": email, "password": hashed_pw, "created_at": datetime.utcnow(), "streak_days": 1, "goal": None, "roadmap": None, "conversations": [], "is_admin": False, "overall_progress": 0 })
    flash("Signup successful! Please login.", "success"); return redirect(url_for("home"))

@app.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    if request.method == "GET": return render_template("signup.html")
    name, email, password, confirm = request.form.get("name"), request.form.get("email"), request.form.get("password"), request.form.get("confirm_password")
    if email != os.getenv("ADMIN_EMAIL", "admin@skillsync.com"): flash("Invalid email for admin registration.", "error"); return redirect(url_for("home"))
    if not all([name, email, password, confirm]) or password != confirm: flash("Invalid signup form.", "error"); return redirect(url_for("home"))
    if mongo.collection.find_one({"email": email}): flash("Admin account already exists.", "error"); return redirect(url_for("home"))
    hashed_pw = generate_password_hash(password)
    mongo.insert_document({"name": name, "email": email, "password": hashed_pw, "created_at": datetime.utcnow(), "streak_days": 1, "goal": None, "roadmap": None, "conversations": [], "is_admin": True, "overall_progress": 0 })
    flash("Admin Signup successful! Please login.", "success"); return redirect(url_for("home"))

def is_user_admin(email): return mongo.collection.find_one({"email": email}) and mongo.collection.find_one({"email": email}).get("is_admin", False)

@app.route("/admin")
def admin_dashboard():
    if "user" not in session or not is_user_admin(session["user"]): flash("Access Denied.", "error"); return redirect(url_for("dashboard"))
    total_users = mongo.collection.count_documents({})
    onboarded_users = mongo.collection.count_documents({"roadmap": {"$ne": None}})
    recent_users = list(mongo.collection.find({}, {"name": 1, "email": 1, "created_at": 1, "is_admin": 1}).sort("created_at", -1).limit(5))
    return render_template("admin_dashboard.html", total_users=total_users, onboarded_users=onboarded_users, recent_users=recent_users)

@app.route("/logout")
def logout(): session.pop("user", None); return redirect(url_for("home"))


# -------- Onboarding Page and Submission (FIXED Serialization) --------
@app.route("/onboarding", methods=["GET"])
def onboarding():
    if "user" not in session: return redirect(url_for("home"))
    user_doc = mongo.collection.find_one({"email": session["user"]})
    if user_doc.get("goal"): return redirect(url_for("dashboard"))
    return render_template("onboarding_form.html")


@app.route("/submit_onboarding", methods=["POST"])
def submit_onboarding():
    if "user" not in session: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(force=True)
    goal = data.get("goal")
    college_year = data.get("college_year") 
    skills = data.get("skills", [])
    hours = int(data.get("hours", 2))
    duration = int(data.get("duration_months", 3))

    if not all([goal, college_year, skills]): return jsonify({"error": "Missing required fields."}), 400
         
    try:
        crew_result = crew.orchestrate(goal, skills, hours, duration, True) 

        # --- FIX: SERIALIZE CREW OUTPUT FOR MONGODB ---
        crew_output_content = crew_result.get("result", "{}") 
        
        # 1. Convert the custom CrewOutput object to a string representation
        roadmap_json_string = str(crew_output_content)
        
        # 2. Safely parse the JSON string into a Python dictionary for MongoDB
        try:
            roadmap_data = json.loads(roadmap_json_string) 
        except json.JSONDecodeError:
            # If the agent returns malformed JSON, save the raw string output as a fallback.
            roadmap_data = {"result": roadmap_json_string, "error": "Agent output failed to parse as JSON."}

        # 3. This dictionary/safe structure is now safe to save to MongoDB
        overall_progress, _ = calculate_progress(roadmap_data)
        
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$set": {
                "goal": goal, 
                "college_year": college_year, 
                "roadmap": roadmap_data, 
                "overall_progress": overall_progress
            }}
        )
        return jsonify({"success": True, "message": "Onboarding complete. Redirecting..."})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- Dashboard --------
@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect(url_for("home"))
    user_doc = mongo.collection.find_one({"email": session["user"]})
    if not user_doc: return redirect(url_for("home"))
    if not user_doc.get("goal"): return redirect(url_for("onboarding"))
         
    overall_progress, milestone_progress = calculate_progress(user_doc.get("roadmap"))
    
    missing_skills = []
    if user_doc.get("roadmap") and user_doc["roadmap"].get("result"):
        try:
            roadmap_json = json.loads(user_doc["roadmap"].get("result"))
            missing_skills = roadmap_json.get("analysis", {}).get("missing_skills", [])
        except Exception:
            missing_skills = ["Check Roadmap"] 
            
    return render_template("dashboard.html", user=user_doc, overall_progress=overall_progress, milestone_progress=milestone_progress, missing_skills=missing_skills) 


# -------- API Endpoints (Fully Defined Functions) --------

@app.route("/orchestrate", methods=["POST"])
def orchestrate_api():
    # Placeholder for general orchestration calls
    return jsonify({"error": "Direct orchestration not implemented here. Use submit_onboarding."})

@app.route("/api/generate-roadmap", methods=["POST"])
def api_generate_roadmap():
    # Placeholder: Call crew.orchestrate again, similar to submit_onboarding logic
    return jsonify({"error": "Roadmap regeneration API not fully implemented."})

@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    # Placeholder: Call crew.run_daily_plan
    return jsonify({"error": "Daily plan API not fully implemented."})

@app.route("/api/generate-playlist-plan", methods=["POST"])
def api_generate_playlist_plan():
    # Placeholder: Call crew.run_playlist_plan
    return jsonify({"error": "Playlist plan API not fully implemented."})

@app.route("/api/get-readiness", methods=["GET"])
def api_get_readiness():
    # Placeholder: Call crew.run_job_readiness
    return jsonify({"error": "Readiness API not fully implemented."})

@app.route("/api/reschedule_task", methods=["POST"])
def api_reschedule_task():
    # Placeholder for client-side logging (already implemented in main.py)
    return jsonify({"success": True, "message": "Task marked for next day."})

@app.route("/roadmap")
def roadmap():
    # Placeholder for separate roadmap page
    return jsonify({"error": "Roadmap page not implemented."})

@app.route("/update_task", methods=["POST"])
def update_task():
    # Placeholder for task update logic
    return jsonify({"error": "Update task logic not fully implemented."})


# -------- Run App --------
if __name__ == "__main__":
    app.run(debug=True)