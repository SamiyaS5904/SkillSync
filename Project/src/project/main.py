from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json

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
    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form", "error")
        return redirect(url_for("home"))
    if mongo.collection.find_one({"email": email}):
        flash("User already exists", "error")
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
        "conversations": []
    })
    flash("Signup successful!", "success")
    return redirect(url_for("home"))


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
        result = crew.orchestrate(goal, skills, hours, duration, weekends)
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$set": {"goal": goal, "roadmap": result},
             "$push": {"conversations": {"input": data, "response": result, "ts": datetime.utcnow()}}}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- Roadmap Generator for Dashboard (AJAX) --------
@app.route("/api/generate-roadmap", methods=["POST"])
def api_generate_roadmap():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    onboarding = data.get("onboarding", {})

    try:
        result = crew.orchestrate(
            goal=onboarding.get("goal"),
            skills=onboarding.get("skills", []),
            hours=int(onboarding.get("hoursDay", 2)),
            duration=1,   # dashboard roadmap default 1 month
            weekends=True
        )
        mongo.collection.update_one(
            {"email": session["user"]},
            {"$set": {"goal": onboarding.get("goal"), "roadmap": result},
             "$push": {"conversations": {"input": onboarding, "response": result, "ts": datetime.utcnow()}}}
        )
        return jsonify({"roadmap": result.get("milestones", [])})
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
        query = f"""
Generate a daily learning plan and 2 recommended playlists.

Career Goal: {onboarding.get('goal')}
Skills: {onboarding.get('skills')}
Hours per weekday: {onboarding.get('hoursDay')}
Hours per weekend: {onboarding.get('hoursWeekend')}

Return JSON with two keys:
- "plan": list of {{"time": "HH:MM", "title": "Task", "duration": minutes}}
- "playlists": list of {{"title": str, "provider": str, "url": str, "length": str}}
"""
        result = crew.run_quick(query)

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {"plan": [], "playlists": []}

        mongo.collection.update_one(
            {"email": session["user"]},
            {"$push": {"conversations": {"input": onboarding, "response": result, "ts": datetime.utcnow()}}}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
