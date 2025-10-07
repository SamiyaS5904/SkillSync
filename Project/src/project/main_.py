from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os

# MongoDB helper
from mongodb_helper import MongoDBHelper
# Crew orchestrator
from loader import SkillSyncCrew

# Load env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super_secret_key")

# MongoDB setup
mongo = MongoDBHelper()
mongo.select_db(db_name="SkillSyncDB", collection="users")

crew = SkillSyncCrew()  # initialize once

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
    name, email, password, confirm = (
        request.form.get("name"),
        request.form.get("email"),
        request.form.get("password"),
        request.form.get("confirm_password"),
    )

    if not all([name, email, password, confirm]) or password != confirm:
        flash("Invalid signup form", "error")
        return redirect(url_for("home"))

    if mongo.collection.find_one({"email": email}):
        flash("User already exists", "error")
        return redirect(url_for("home"))

    hashed_pw = generate_password_hash(password)
    mongo.insert_document({
        "name": name, "email": email, "password": hashed_pw,
        "created_at": datetime.utcnow(), "streak_days": 1,
        "goal": None, "roadmap": None
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

    return render_template("dashboard.html", user=user_doc)

# -------- Quick Fast Response --------
@app.route("/quick", methods=["POST"])
def quick():
    data = request.get_json()
    query = data.get("query", "")
    result = crew.run(query)
    return jsonify(result)

# -------- Orchestration Endpoint --------
@app.route("/orchestrate", methods=["POST"])
def orchestrate():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    goal = data.get("goal")
    skills = data.get("skills", [])
    hours = int(data.get("hours", 2))
    duration = int(data.get("duration_months", 3))

    result = crew.orchestrate(goal, skills, hours, duration)

    mongo.collection.update_one(
        {"email": session["user"]},
        {"$set": {"goal": goal, "roadmap": result}}
    )
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
