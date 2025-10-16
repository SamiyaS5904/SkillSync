import os
import json
import re
from datetime import datetime, timezone, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from openai import OpenAI
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ------------------ Initialization ------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key")

if not MONGO_URI:
    raise EnvironmentError("Please set MONGO_URI in .env")

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. AI calls will fail until you set it.")

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)
app.secret_key = SECRET_KEY

# ------------------ MongoDB Setup ------------------
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["SkillSyncDB"]
users_col = db["users"]
roadmaps_col = db["roadmaps"]
dailyplans_col = db["daily_plans"]

# ------------------ Predefined Goals ------------------
PREDEFINED_GOALS = [
    "Software Developer", "Full Stack Developer", "Frontend Developer", "Backend Developer",
    "Data Scientist", "AI Engineer", "Machine Learning Engineer", "Data Analyst", "DevOps Engineer"
]

# ------------------ Helpers ------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

def safe_json_loads(s):
    """Try to parse JSON from a string or return None."""
    if s is None:
        return None
    if isinstance(s, dict):
        return s
    if isinstance(s, list):
        return s
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"(\{(?:.|\s)*\}|\[(?:.|\s)*\])", str(s))
    if not m:
        return None
    candidate = m.group(1)
    candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
    candidate = re.sub(r"\s*```$", "", candidate, flags=re.I)
    try:
        return json.loads(candidate)
    except Exception:
        return None

def calculate_progress(roadmap):
    if not roadmap or "weeks" not in roadmap:
        return 0
    total = done = 0
    for w in roadmap.get("weeks", []):
        for t in w.get("tasks", []):
            total += 1
            if t.get("done"):
                done += 1
    return int((done / total) * 100) if total else 0

def attach_weekly_dates(roadmap, start_date=None):
    """Add week start/end date strings to each week in roadmap."""
    if not roadmap or "weeks" not in roadmap:
        return roadmap
    start = start_date or datetime.now(timezone.utc).date()
    for i, week in enumerate(roadmap["weeks"]):
        s = start + timedelta(weeks=i)
        e = s + timedelta(days=6)
        week["start_date_str"] = s.strftime("%b %d")
        week["end_date_str"] = e.strftime("%b %d")
    return roadmap

# ------------------ AI Roadmap Generation ------------------
def call_openai_generate_roadmap(goal, skills, hours_per_day=2, months=3):
    """Call OpenAI to generate a roadmap JSON. Raises RuntimeError on failure."""
    if not goal:
        raise RuntimeError("Goal is required for roadmap generation.")
    system_prompt = (
        "You are an expert AI career coach. Produce a JSON object with the structure:\n"
        "{\n"
        "  \"goal\": \"...\",\n"
        "  \"weeks\": [\n"
        "    {\"title\": \"Week 1 - ...\", \"tasks\": [{\"title\":\"...\",\"done\":false}], \"resources\": [\"...\"], \"weekend_challenge\":\"...\"}\n"
        "  ]\n"
        "}\n"
        "Each week should have 6-8 tasks, at least one 'weekend_challenge', and resources (URLs when possible). Output only valid JSON (no markdown fences)."
    )
    user_prompt = f"Goal: {goal}\nExisting Skills: {skills}\nHours/day: {hours_per_day}\nDuration (months): {months}\nGenerate the roadmap now."

    try:
        print("[AI Agent] Generating roadmap for goal:", goal)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.25,
            max_tokens=2000
        )
        raw = resp.choices[0].message.content
        parsed = safe_json_loads(raw)
        if not parsed:
            raise RuntimeError("AI returned unparsable JSON. Raw output logged.")
        if "weeks" not in parsed:
            raise RuntimeError("AI JSON missing 'weeks' key.")
        print("[AI Agent] Roadmap parsed with", len(parsed.get("weeks", [])), "weeks.")
        return parsed
    except Exception as e:
        print("[AI Agent] Error:", e)
        raise RuntimeError(f"AI generation failed: {e}")

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
        flash("Invalid form input.", "error")
        return redirect(url_for("index"))
    if users_col.find_one({"email": email}):
        flash("User already exists.", "error")
        return redirect(url_for("index"))

    hashed = generate_password_hash(password)
    users_col.insert_one({
        "name": name,
        "email": email,
        "password": hashed,
        "created_at": datetime.now(timezone.utc),
        "goal": None,
        "skills": [],
        "roadmap": {"goal": None, "weeks": []},
        "daily_plans": [],
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
    flash("Invalid credentials.", "error")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = users_col.find_one({"email": session["user"]})
    roadmap = user.get("roadmap") or {"goal": user.get("goal"), "weeks": []}
    roadmap = attach_weekly_dates(roadmap)
    skills = user.get("skills", [])
    progress = calculate_progress(roadmap)
    return render_template(
        "dashboard.html",
        user=user,
        roadmap=roadmap,
        predefined_goals=PREDEFINED_GOALS,
        overall_progress=progress
    )

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
        roadmap = call_openai_generate_roadmap(goal, skills, hours, months)
        roadmap = attach_weekly_dates(roadmap)
        users_col.update_one(
            {"email": session["user"]},
            {"$set": {"goal": goal, "skills": skills, "roadmap": roadmap}}
        )
        roadmaps_col.insert_one({
            "email": session["user"],
            "roadmap": roadmap,
            "created_at": datetime.now(timezone.utc)
        })
        print("[Server] Roadmap saved to database.")
        return jsonify({"success": True, "roadmap": roadmap})
    except RuntimeError as e:
        print("[Server] Roadmap generation error:", str(e))
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print("[Server] Unexpected error:", e)
        return jsonify({"error": f"Unexpected server error: {e}"}), 500

@app.route("/update_task_status", methods=["POST"])
@login_required
def update_task_status():
    data = request.get_json(force=True)
    try:
        week_idx = int(data.get("weekIdx"))
        task_idx = int(data.get("taskIdx"))
        done = bool(data.get("done"))
    except Exception:
        return jsonify({"error": "Invalid indices"}), 400

    user = users_col.find_one({"email": session["user"]})
    roadmap = user.get("roadmap", {})
    weeks = roadmap.get("weeks", [])

    if week_idx < 0 or week_idx >= len(weeks):
        return jsonify({"error": "week index out of range"}), 400
    tasks = weeks[week_idx].get("tasks", [])
    if task_idx < 0 or task_idx >= len(tasks):
        return jsonify({"error": "task index out of range"}), 400

    tasks[task_idx]["done"] = done
    users_col.update_one({"email": session["user"]}, {"$set": {"roadmap": roadmap}})
    progress = calculate_progress(roadmap)
    return jsonify({"success": True, "progress": progress})

@app.route("/generate_daily_tasks", methods=["POST"])
@login_required
def generate_daily_tasks():
    data = request.get_json(force=True)
    week_title = data.get("week_title")
    if not week_title:
        return jsonify({"error": "week_title required"}), 400

    user = users_col.find_one({"email": session["user"]})
    roadmap = user.get("roadmap", {})
    goal = roadmap.get("goal", "Skill Development")

    prompt = f"Based on the week titled '{week_title}' for the goal '{goal}', generate 5 daily learning tasks with short descriptions. Output as a JSON array of objects with keys 'day' and 'tasks' (tasks array of strings)."

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a productivity AI coach."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.35,
            max_tokens=800
        )
        raw = resp.choices[0].message.content
        parsed = safe_json_loads(raw)
        if parsed:
            return jsonify({"success": True, "daily_tasks": parsed})
        return jsonify({"success": True, "daily_tasks": raw})
    except Exception as e:
        print("[AI] generate_daily_tasks error:", e)
        return jsonify({"error": str(e)}), 500

# ------------------ PDF Download Route ------------------
@app.route("/download_pdf")
@login_required
def download_pdf():
    """Generate and download the user's roadmap as a PDF (white background)."""
    user = users_col.find_one({"email": session["user"]})
    if not user:
        return jsonify({"error": "User not found"}), 404

    roadmap = user.get("roadmap", {})
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>SkillSync AI Roadmap</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Name: {user.get('name', 'Unknown')}", styles["Normal"]))
    story.append(Paragraph(f"Goal: {roadmap.get('goal', 'N/A')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    weeks = roadmap.get("weeks", [])
    if not weeks:
        story.append(Paragraph("No roadmap found. Please generate one first.", styles["BodyText"]))
    else:
        for week in weeks:
            story.append(Paragraph(f"<b>{week.get('title', 'Untitled')}</b>", styles["Heading2"]))
            story.append(Spacer(1, 6))
            for t in week.get("tasks", []):
                done = "✅" if t.get("done") else "⬜"
                story.append(Paragraph(f"{done} {t.get('title', '')}", styles["BodyText"]))
            story.append(Spacer(1, 6))
            resources = week.get("resources", [])
            if resources:
                story.append(Paragraph("<b>Resources:</b>", styles["Heading4"]))
                for r in resources:
                    story.append(Paragraph(f"{r}", styles["BodyText"]))
            story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="SkillSync_Roadmap.pdf", mimetype="application/pdf")

# ------------------ Run ------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
