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
    for m in roadmap["milestones"]:
        m_tasks = m.get("tasks", [])
        m_completed = sum(1 for t in m_tasks if t.get("done"))
        m_total = len(m_tasks)
        percent = int((m_completed / m_total) * 100) if m_total else 0
        milestone_progress.append(percent)
        total_tasks += m_total
        completed_tasks += m_completed
    overall_progress = int((completed_tasks / total_tasks) * 100) if total_tasks else 0
    return overall_progress, milestone_progress


# -------- Landing Page --------
@app.route("/")
def home():
    # Renders the updated marketing page
    return render_template("index_3.html")

def is_strong_password(password):
    """Checks if password is strong (8+ chars, upper, lower, digit, special)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?:{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, "Strong password."


# -------- Authentication (Standard User Sign Up) --------
@app.route("/signup", methods=["POST"])
def signup():
    # This route is used by the modal/standard flow for regular users
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")
    
    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form: passwords do not match or fields are missing.", "error")
        return redirect(url_for("home"))
    
    is_valid, reason = is_strong_password(password)
    if not is_valid:
        flash(f"Weak password: {reason}", "error")
        return redirect(url_for("home"))

    if mongo.collection.find_one({"email": email}):
        flash("User already exists", "error")
        return redirect(url_for("home"))
    
    hashed_pw = generate_password_hash(password)
    is_admin = False

    mongo.insert_document({
        "name": name,
        "email": email,
        "password": hashed_pw,
        "created_at": datetime.utcnow(),
        "streak_days": 1,
        "goal": None,
        "roadmap": None,
        "conversations": [],
        "is_admin": is_admin,
        "overall_progress": 0 
    })
    flash("Signup successful! Please login.", "success")
    return redirect(url_for("home"))


@app.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    # Display the standard signup page for GET requests
    if request.method == "GET":
        return render_template("signup.html")

    # Process admin signup form submission
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")
    
    # Check against hardcoded admin email
    if email != os.getenv("ADMIN_EMAIL", "admin@skillsync.com"):
        flash("Invalid email for admin registration.", "error")
        return redirect(url_for("home"))
    
    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form.", "error")
        return redirect(url_for("home"))

    if mongo.collection.find_one({"email": email}):
        flash("Admin account already exists.", "error")
        return redirect(url_for("home"))

    hashed_pw = generate_password_hash(password)
    mongo.insert_document({
        "name": name,
        "email": email,
        "password": hashed_pw,
        "created_at": datetime.utcnow(),
        "streak_days": 1,
        "goal": None,
        "roadmap": None,
        "conversations": [],
        "is_admin": True,
        "overall_progress": 0 
    })
    flash("Admin Signup successful! Please login.", "success")
    return redirect(url_for("home"))


@app.route("/login", methods=["POST"])
def login():
    email, password = request.form.get("email"), request.form.get("password")
    user = mongo.collection.find_one({"email": email})
    if user and check_password_hash(user["password"], password):
        session["user"] = user["email"]
        return redirect(url_for("dashboard"))
    flash("Invalid credentials", "error")
    return redirect(url_for("home"))

def is_user_admin(email):
    user = mongo.collection.find_one({"email": email})
    return user and user.get("is_admin", False)

@app.route("/admin")
def admin_dashboard():
    if "user" not in session:
        flash("Please log in to access this page.", "error")
        return redirect(url_for("home"))

    if not is_user_admin(session["user"]):
        flash("Access Denied: You must be an administrator.", "error")
        return redirect(url_for("dashboard"))

    total_users = mongo.collection.count_documents({})
    onboarded_users = mongo.collection.count_documents({"roadmap": {"$ne": None}})

    recent_users = list(mongo.collection.find(
        {},
        {"name": 1, "email": 1, "created_at": 1, "is_admin": 1}
    ).sort("created_at", -1).limit(5))

    return render_template("admin_dashboard.html", 
                           total_users=total_users,
                           onboarded_users=onboarded_users,
                           recent_users=recent_users)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


# -------- Dashboard --------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("home"))
    user_doc = mongo.collection.find_one({"email": session["user"]})
    if not user_doc:
        return redirect(url_for("home"))
    
    overall_progress, milestone_progress = calculate_progress(user_doc.get("roadmap"))
    
    # Extract missing skills for the interactive area
    missing_skills = []
    if user_doc.get("roadmap") and user_doc["roadmap"].get("result"):
        try:
            # The crew result is a string, so we must parse it to get the analysis data
            roadmap_json = json.loads(user_doc["roadmap"].get("result"))
            # Assuming the structure is result -> analysis -> missing_skills
            missing_skills = roadmap_json.get("analysis", {}).get("missing_skills", [])
        except Exception:
            missing_skills = ["Check Roadmap"] 
            
    return render_template("dashboard.html", user=user_doc,
                           overall_progress=overall_progress,
                           milestone_progress=milestone_progress,
                           missing_skills=missing_skills) # Pass missing skills to dashboard


# ... (agent_auto, orchestrate, api_generate_roadmap, api_generate_plan routes remain the same) ...

@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    onboarding = data.get("onboarding", {})

    try:
        crew_result = crew.run_daily_plan(
            goal=onboarding.get("goal"),
            skills=onboarding.get("skills", []),
            hours_day=int(onboarding.get('hoursDay', 2)),
            hours_weekend=int(onboarding.get('hoursWeekend', 0)),
            start_date=onboarding.get('startDate', datetime.utcnow().strftime('%Y-%m-%d'))
        )

        result_str = crew_result.get("result", "{}")
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {"plan": [], "playlists": [], "error": "Agent returned non-JSON data."}
            
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$push": {"conversations": {"input": onboarding, "response": result, "ts": datetime.utcnow()}}}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-playlist-plan", methods=["POST"])
def api_generate_playlist_plan():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    playlists = data.get("playlists") 

    if not playlists or not isinstance(playlists, list):
         return jsonify({"error": "Missing or invalid playlist list"}), 400

    try:
        crew_result = crew.run_playlist_plan(playlists)
        
        result_str = crew_result.get("result", "{}")
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {"schedule": [], "error": "Agent returned non-JSON data."}
            
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$push": {"conversations": {"input": data, "response": result, "ts": datetime.utcnow()}}}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/get-readiness", methods=["GET"])
def api_get_readiness():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_doc = mongo.collection.find_one({"email": session["user"]})
    if not user_doc or not user_doc.get("goal"):
        return jsonify({"error": "User goal not set for readiness check."}), 400

    current_progress = user_doc.get("overall_progress", 0) 
    career_goal = user_doc["goal"]

    try:
        crew_result = crew.run_job_readiness(career_goal, current_progress)
        
        result_str = crew_result.get("result", "{}")
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {"readiness_percent": 0, "message": "Readiness agent output failed.", "internships": []}
            
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$push": {"conversations": {"goal": career_goal, "progress": current_progress, "response": result, "ts": datetime.utcnow()}}}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- NEW: API for Rescheduling Undone Task (Client-side visualization helper) --------
@app.route("/api/reschedule_task", methods=["POST"])
def api_reschedule_task():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # This API is purely for logging the reschedule request and confirming to the client
    return jsonify({"success": True, "message": "Task marked for next day."})


# -------- Roadmap Page --------
@app.route("/roadmap")
def roadmap():
    if "user" not in session:
        return redirect(url_for("home"))
    user_doc = mongo.collection.find_one({"email": session["user"]})
    if not user_doc or not user_doc.get("roadmap"):
        flash("No roadmap found. Generate one from dashboard.", "error")
        return redirect(url_for("dashboard"))
    return render_template("roadmap.html", user=user_doc, roadmap=user_doc["roadmap"])


# -------- Update Task (UPDATED TO RECALCULATE PROGRESS) --------
@app.route("/update_task", methods=["POST"])
def update_task():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    milestone_index = int(data.get("milestone_index"))
    task_index = int(data.get("task_index"))
    done = data.get("done")
    resource = data.get("resource")
    user_doc = mongo.collection.find_one({"email": session["user"]})
    if not user_doc or not user_doc.get("roadmap"):
        return jsonify({"error": "Roadmap not found"}), 404
    try:
        if resource:
            task = user_doc["roadmap"]["milestones"][milestone_index]["tasks"][task_index]
            if "user_resources" not in task:
                task["user_resources"] = []
            task["user_resources"].append(resource)
        elif done is not None:
            user_doc["roadmap"]["milestones"][milestone_index]["tasks"][task_index]["done"] = bool(done)

        overall_progress, milestone_progress = calculate_progress(user_doc["roadmap"])

        mongo.collection.update_one(
            {"email": session["user"]},
            {"$set": {"roadmap": user_doc["roadmap"], 
                      "overall_progress": overall_progress}}
        )
        
        if milestone_progress[milestone_index] == 100:
            flash(f"Milestone {milestone_index + 1} completed! Great job!", "success")
            
        return jsonify({"success": True, "overall_progress": overall_progress, "milestone_progress": milestone_progress})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- Run App --------
if __name__ == "__main__":
    app.run(debug=True)