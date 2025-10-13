# main.py
import os
import json
import re
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from openai import OpenAI  # ✅ New import

# ------------------ Setup ------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key")

if not MONGO_URI:
    raise EnvironmentError("Please set MONGO_URI in .env")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. AI calls will fail until you set it.")

# ✅ New OpenAI client (replaces old openai.api_key)
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["SkillSyncDB"]
users_col = db["users"]
roadmaps_col = db["roadmaps"]
dailyplans_col = db["daily_plans"]

# ------------------ Predefined Goals ------------------
PREDEFINED_GOALS = [
    "Data Scientist", "AI Engineer", "Data Analyst", "Machine Learning Engineer",
    "Data Engineer", "Frontend Developer", "Backend Developer", "Fullstack Developer",
    "DevOps Engineer", "Product Analyst", "UX Designer"
]

# ------------------ Helper Functions ------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

def safe_json_loads(s):
    if s is None:
        return None
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", str(s), re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
        return None

def calculate_progress(roadmap):
    if not roadmap or "milestones" not in roadmap:
        return 0
    total = 0
    done = 0
    for m in roadmap.get("milestones", []):
        tasks = m.get("tasks", [])
        total += len(tasks)
        done += sum(1 for t in tasks if t.get("done"))
    return int((done / total) * 100) if total else 0

# ------------------ OpenAI Integration ------------------
def call_openai_generate_roadmap(goal, skills, hours_per_day=2, months=3):
    """Call OpenAI to generate structured roadmap JSON."""
    system_prompt = (
        "You are a 2025-savvy AI Learning Strategist. Output ONLY JSON. "
        "Produce a roadmap for the user's goal including milestones, subtopics, resources, projects, weekly_goals, and timeline_overview. "
        "Use up-to-date 2025 trends. Keep output compact and valid JSON."
    )
    user_prompt = (
        f"Goal: {goal}\n"
        f"Existing Skills: {skills}\n"
        f"Available hours/day: {hours_per_day}\n"
        f"Target duration (months): {months}\n"
        "Return a JSON object like: {\"goal\":\"...\",\"milestones\":[{\"title\":\"...\",\"subtopics\":[...],"
        "\"resources\":[...],\"projects\":[...],\"tasks\":[{\"title\":\"...\",\"duration_minutes\":...}] }],"
        "\"weekly_goals\":[...],\"timeline_overview\":\"...\"}"
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,  # ✅ works with gpt-4o-mini
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1400,
            temperature=0.2
        )
        text = resp.choices[0].message.content
        data = safe_json_loads(text)
        if not data:
            text2 = re.sub(r"^```json|```$", "", text.strip(), flags=re.I)
            data = safe_json_loads(text2)
        if not data:
            raise ValueError("AI returned unparsable content for roadmap.")
        return data
    except Exception as e:
        raise RuntimeError(f"AI generation failed: {e}")

def call_openai_daily_plan(roadmap, start_date=None, hours_per_day=2):
    """Generate daily plan using OpenAI."""
    system = (
        "You are a helpful planner. Given a structured roadmap JSON, generate a day-wise plan "
        "for at least 7 days, mapping milestones/tasks into daily activities. Return JSON only."
    )
    start_date = start_date or datetime.utcnow().date().isoformat()
    user_prompt = f"Start date: {start_date}\nHours/day: {hours_per_day}\nRoadmap: {json.dumps(roadmap)}"

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
            temperature=0.2
        )
        text = resp.choices[0].message.content
        data = safe_json_loads(text)
        if not data:
            text2 = re.sub(r"^```json|```$", "", text.strip(), flags=re.I)
            data = safe_json_loads(text2)
        if not data:
            raise ValueError("AI daily planner returned unparsable content.")
        return data
    except Exception as e:
        raise RuntimeError(f"AI daily plan failed: {e}")

# ------------------ Routes ------------------
@app.route("/")
def index():
    return render_template("index_3.html")

@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirm_password")
    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form", "error")
        return redirect(url_for("index"))
    if users_col.find_one({"email": email}):
        flash("User exists", "error")
        return redirect(url_for("index"))
    hashed = generate_password_hash(password)
    users_col.insert_one({
        "name": name,
        "email": email,
        "password": hashed,
        "created_at": datetime.utcnow(),
        "goal": None,
        "skills": [],
        "roadmap": None,
        "daily_plans": [],
        "is_admin": False
    })
    flash("Signup successful! Please login.", "success")
    return redirect(url_for("index"))

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    user = users_col.find_one({"email": email})
    if user and check_password_hash(user["password"], password):
        session["user"] = user["email"]
        return redirect(url_for("dashboard"))
    flash("Invalid credentials", "error")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = users_col.find_one({"email": session["user"]})
    user_roadmap = user.get("roadmap") or {"goal": user.get("goal") or "", "milestones": []}
    user_skills = user.get("skills") or []
    overall_progress = calculate_progress(user_roadmap)
    return render_template("dashboard.html",
                           user=user,
                           roadmap=user_roadmap,
                           skills=user_skills,
                           predefined_goals=PREDEFINED_GOALS,
                           overall_progress=overall_progress)

@app.route("/generate_roadmap", methods=["POST"])
@login_required
def generate_roadmap():
    payload = request.get_json(force=True)
    goal = payload.get("goal")
    skills = payload.get("skills", [])
    hours = int(payload.get("hours", 2))
    months = int(payload.get("duration_months", 3))
    if not goal:
        return jsonify({"error": "Goal required"}), 400
    try:
        roadmap_data = call_openai_generate_roadmap(goal, skills, hours, months)
        users_col.update_one({"email": session["user"]},
                             {"$set": {"goal": goal, "skills": skills, "roadmap": roadmap_data}})
        roadmaps_col.insert_one({
            "email": session["user"],
            "roadmap": roadmap_data,
            "created_at": datetime.utcnow()
        })
        return jsonify({"success": True, "roadmap": roadmap_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/save_roadmap", methods=["POST"])
@login_required
def save_roadmap():
    payload = request.get_json(force=True)
    roadmap = payload.get("roadmap")
    if not roadmap:
        return jsonify({"error": "No roadmap provided"}), 400
    try:
        users_col.update_one({"email": session["user"]}, {"$set": {"roadmap": roadmap}})
        roadmaps_col.insert_one({
            "email": session["user"],
            "roadmap": roadmap,
            "saved_at": datetime.utcnow()
        })
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/daily_planner", methods=["GET", "POST"])
@login_required
def daily_planner():
    user = users_col.find_one({"email": session["user"]})
    if request.method == "GET":
        daily = dailyplans_col.find_one({"email": session["user"]})
        plan = daily.get("plan") if daily else None
        return render_template("daily_planner.html", user=user, plan=plan or {}, roadmap=user.get("roadmap") or {})
    else:
        data = request.get_json(force=True)
        action = data.get("action")
        if action == "generate":
            roadmap = user.get("roadmap") or {}
            start_date = data.get("start_date") or datetime.utcnow().date().isoformat()
            hours = int(data.get("hours", 2))
            try:
                plan = call_openai_daily_plan(roadmap, start_date, hours)
                dailyplans_col.update_one({"email": session["user"]},
                                          {"$set": {"email": session["user"], "plan": plan, "created_at": datetime.utcnow()}},
                                          upsert=True)
                return jsonify({"success": True, "plan": plan})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        elif action == "save":
            plan = data.get("plan")
            if not plan:
                return jsonify({"error": "No plan provided"}), 400
            dailyplans_col.update_one({"email": session["user"]},
                                      {"$set": {"email": session["user"], "plan": plan, "updated_at": datetime.utcnow()}},
                                      upsert=True)
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Unknown action"}), 400

@app.route("/admin")
@login_required
def admin_panel():
    user = users_col.find_one({"email": session["user"]})
    if not user.get("is_admin"):
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))
    total_users = users_col.count_documents({})
    total_roadmaps = roadmaps_col.count_documents({})
    pipeline = [
        {"$group": {"_id": "$goal", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    goals = list(users_col.aggregate(pipeline))
    skills_count = {}
    for u in users_col.find({}, {"skills": 1}):
        for s in (u.get("skills") or []):
            skills_count[s] = skills_count.get(s, 0) + 1
    top_skills = sorted(skills_count.items(), key=lambda x: x[1], reverse=True)[:20]
    return render_template("admin.html", total_users=total_users, total_roadmaps=total_roadmaps,
                           goals=goals, top_skills=top_skills)

@app.route("/get_roadmap")
@login_required
def get_roadmap():
    user = users_col.find_one({"email": session["user"]})
    return jsonify({"roadmap": user.get("roadmap") or {}})

@app.route("/get_daily_plan")
@login_required
def get_daily_plan():
    daily = dailyplans_col.find_one({"email": session["user"]})
    return jsonify({"plan": daily.get("plan") if daily else {}})

# ------------------ Run Server ------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
