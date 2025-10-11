from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime
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
    return render_template("index_3.html")

def is_strong_password(password):
    """
    Checks if password is strong:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character: !@#$%^&*(),.?:{}|<>
    """
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


# -------- Authentication --------
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
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")
    
    # 1. Basic form validation
    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form: passwords do not match or fields are missing.", "error")
        return redirect(url_for("home"))
    
    # 2. Password Strength Check (Server-side enforcement)
    is_valid, reason = is_strong_password(password)
    if not is_valid:
        flash(f"Weak password: {reason}", "error")
        return redirect(url_for("home"))

    # 3. User existence check
    if mongo.collection.find_one({"email": email}):
        flash("User already exists", "error")
        return redirect(url_for("home"))
    
    # 4. Create User (Admin check added here)
    hashed_pw = generate_password_hash(password)
    # Set the first user or a specific email as admin for initial setup
    is_admin = (email == os.getenv("ADMIN_EMAIL", "admin@skillsync.com")) 

    mongo.insert_document({
        "name": name,
        "email": email,
        "password": hashed_pw,
        "created_at": datetime.utcnow(),
        "streak_days": 1,
        "goal": None,
        "roadmap": None,
        "conversations": [],
        "is_admin": is_admin # <-- ADDED FIELD
    })
    flash("Signup successful!", "success")
    return redirect(url_for("home"))

def is_user_admin(email):
    """Checks if the user document has the is_admin flag set to True."""
    user = mongo.collection.find_one({"email": email})
    # Safely check for 'is_admin' field, defaulting to False if not present
    return user and user.get("is_admin", False)

@app.route("/admin")
def admin_dashboard():
    if "user" not in session:
        flash("Please log in to access this page.", "error")
        return redirect(url_for("home"))

    if not is_user_admin(session["user"]):
        flash("Access Denied: You must be an administrator.", "error")
        return redirect(url_for("dashboard")) # Redirect non-admins

    # Fetch basic statistics for the dashboard
    total_users = mongo.collection.count_documents({})
    # Count of users with a roadmap (i.e., onboarded users)
    onboarded_users = mongo.collection.count_documents({"roadmap": {"$ne": None}})

    # Fetch last 5 signups (projecting only necessary fields)
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
    return render_template("dashboard.html", user=user_doc,
                           overall_progress=overall_progress,
                           milestone_progress=milestone_progress)


# -------- AI Assistant Endpoint --------
@app.route("/agent/auto", methods=["POST"])
def agent_auto():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    query = data.get("query", "")
    try:
        result = crew.run_quick(query)
        response = {
            "agent": result.get("agent", "career"),
            "response": result.get("response", str(result))
        }
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$push": {"conversations": {"query": query, "response": response, "ts": datetime.utcnow()}}}
        )
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- Roadmap Orchestrator (full multi-month) --------
@app.route("/orchestrate", methods=["POST"])
def orchestrate():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    goal = data.get("goal")
    skills = data.get("skills", [])
    hours = int(data.get("hours", 2))
    duration = int(data.get("duration_months", 3))
    weekends = bool(data.get("weekends", True))
    try:
        # --- UPDATED TO CALL NEW CREW METHOD ---
        crew_result = crew.orchestrate(goal, skills, hours, duration, weekends)
        
        # Assuming crew_result contains a dictionary with the final structured roadmap
        # NOTE: You'll need to parse the final JSON from the crew_result['result'] string
        # For simplicity, we save the raw crew output here.
        roadmap_data = crew_result.get("result", {}) 
        
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$set": {"goal": goal, "roadmap": roadmap_data},
             "$push": {"conversations": {"input": data, "response": crew_result, "ts": datetime.utcnow()}}}
        )
        return jsonify({"success": True, "roadmap": roadmap_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------- Roadmap Generator for Dashboard (AJAX) --------
@app.route("/api/generate-roadmap", methods=["POST"])
def api_generate_roadmap():
    # Use the full /orchestrate route for this, as it is the official crew-powered generator
    return orchestrate()


# -------- Daily Plan Generator for Dashboard (AJAX) --------
@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    onboarding = data.get("onboarding", {})

    try:
        # --- UPDATED TO CALL NEW CREW METHOD ---
        crew_result = crew.run_daily_plan(
            goal=onboarding.get("goal"),
            skills=onboarding.get("skills", []),
            hours_day=int(onboarding.get('hoursDay', 2)),
            hours_weekend=int(onboarding.get('hoursWeekend', 0)),
            start_date=onboarding.get('startDate', datetime.utcnow().strftime('%Y-%m-%d'))
        )

        # Parse the JSON string result from the agent output
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



# -------- Daily Plan Generator for Dashboard (AJAX) --------
@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    onboarding = data.get("onboarding", {})

    try:
        # Get start date from onboarding data, defaulting to today
        start_date = onboarding.get('startDate', datetime.utcnow().strftime('%Y-%m-%d'))

        # Enhance the prompt to include the start date and detailed skills
        query = f"""
Generate a daily learning plan and 2 recommended playlists.
The plan must be highly personalized based on the skills and goal, and START from the date: {start_date}.

Career Goal: {onboarding.get('goal')}
Skills/Tools/Experience: {onboarding.get('skills')}
Hours per weekday: {onboarding.get('hoursDay')}
Hours per weekend: {onboarding.get('hoursWeekend')}

Return JSON with two keys:
- "plan": list of {{"time": "HH:MM", "title": "Task", "duration": minutes, "date": "YYYY-MM-DD"}} (The 'date' field is critical and must be present for each task, starting from {start_date})
- "playlists": list of {{"title": str, "provider": str, "url": str, "length": str}}
"""
        result = crew.run_quick(query)

# main.py

# ...
# -------- Playlist Plan Generator Endpoint --------
@app.route("/api/generate-playlist-plan", methods=["POST"])
def api_generate_playlist_plan():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    playlist_url = data.get("playlistUrl")
    daily_hours = float(data.get("dailyHours", 1.5))

    if not playlist_url:
         return jsonify({"error": "Missing playlist URL"}), 400

    try:
        # --- UPDATED TO CALL NEW CREW METHOD ---
        crew_result = crew.run_playlist_plan(playlist_url, daily_hours)
        
        # Parse the JSON string result from the agent output
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

# -------- Roadmap Page --------
@app.route("/roadmap")
# ...

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


# -------- Update Task --------
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
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$set": {"roadmap": user_doc["roadmap"]}}
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- Run App --------
if __name__ == "__main__":
    app.run(debug=True)
