from flask import Flask, render_template, request, jsonify
import speech_recognition as sr
from pytube import Playlist, YouTube
import requests, uuid
from bs4 import BeautifulSoup

# 🗄️ MongoDB Helper
from mongodb_helper import MongoDBHelper  

app = Flask(__name__, template_folder="templates", static_folder="static")

# 🔌 Connect to DB once
db_helper = MongoDBHelper()


# ============ 🧠 AGENT CORE ==============
def skill_sync_agent(user_input):
    """
    Decide what user wants: roadmap, playlists, jobs, etc.
    """
    user_input = user_input.lower()

    # 1️⃣ Roadmap request
    if "roadmap" in user_input or "goal" in user_input:
        db_helper.select_db("SkillSyncDB", "roadmaps")
        roadmap = db_helper.collection.find_one({"name": "fullstack"})  # Example roadmap
        return {
            "type": "roadmap",
            "message": "Here’s a suggested roadmap 🚀",
            "steps": roadmap["steps"] if roadmap else ["No roadmap found"]
        }

    # 2️⃣ Playlist request
    if "playlist" in user_input or "video" in user_input:
        lang = "Hindi" if "hindi" in user_input else "English"
        db_helper.select_db("SkillSyncDB", "playlists")
        playlists = list(db_helper.collection.find({"language": lang}).sort("rating", -1).limit(3))
        return {
            "type": "playlist",
            "message": f"Top {lang} playlists for you 🎥",
            "playlists": playlists
        }

    # 3️⃣ Jobs request
    if "job" in user_input or "internship" in user_input:
        jobs = scrape_jobs("python developer")  
        return {
            "type": "jobs",
            "message": "Here are some fresh job opportunities 💼",
            "jobs": jobs
        }

    # Default fallback
    return {
        "type": "chat",
        "message": f"I understood: {user_input}. I’ll improve to assist you better 🙌"
    }


# ============ 🎤 VOICE INPUT ROUTE ==============
@app.route("/voice-input", methods=["POST"])
def voice_input():
    recognizer = sr.Recognizer()
    audio_file = request.files["audio"]

    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio)
            agent_response = skill_sync_agent(text)

            # Save chat in DB
            db_helper.select_db("SkillSyncDB", "chat_history")
            session_id = str(uuid.uuid4())
            db_helper.insert_chat(session_id, "user", text)
            db_helper.insert_chat(session_id, "agent", str(agent_response))

            return jsonify({"input": text, "response": agent_response})
        except sr.UnknownValueError:
            return jsonify({"error": "Could not understand audio"}), 400
        except sr.RequestError:
            return jsonify({"error": "Speech service not available"}), 500


# ============ 📺 GENERATE STUDY PLAN ==============
@app.route("/generate-plan", methods=["POST"])
def generate_plan():
    data = request.json
    playlist_url = data.get("playlist_url")
    daily_time = int(data.get("daily_time"))  # minutes

    try:
        videos = []
        if "playlist" in playlist_url.lower():
            playlist = Playlist(playlist_url)
            playlist._video_regex = r"\"url\":\"(/watch\?v=[\w-]*)"
            for url in playlist.video_urls:
                try:
                    yt = YouTube(url)
                    videos.append((yt.title, yt.length // 60))
                except Exception:
                    continue
        else:
            yt = YouTube(playlist_url)
            videos.append((yt.title, yt.length // 60))

        plan, current_day, time_left = [], [], daily_time
        for title, duration in videos:
            if duration <= time_left:
                current_day.append(f"{title} ({duration} min)")
                time_left -= duration
            else:
                plan.append(current_day)
                current_day = [f"{title} ({duration} min)"]
                time_left = daily_time - duration
        if current_day:
            plan.append(current_day)

        return jsonify({"plan": plan})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ============ 💼 JOB SCRAPER ==============
def scrape_jobs(keyword):
    url = f"https://in.indeed.com/jobs?q={keyword}&l=India"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.text, "html.parser")

    job_list = []
    for div in soup.select("div.job_seen_beacon")[:5]:
        title = div.find("h2").get_text(strip=True)
        company = div.find("span", class_="companyName").get_text(strip=True)
        job_list.append({"title": title, "company": company})
    return job_list


# ============ ROUTES ==============
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agent", methods=["POST"])
def agent_route():
    data = request.json
    user_input = data.get("query", "")
    response = skill_sync_agent(user_input)
    return jsonify({"response": response})


@app.route("/playlists")
def playlists():
    db_helper.select_db("SkillSyncDB", "playlists")
    playlists = list(db_helper.collection.find())
    return render_template("playlists.html", playlists=playlists)


@app.route("/jobs")
def jobs():
    jobs = scrape_jobs("python developer")
    return render_template("jobs.html", jobs=jobs)


@app.route("/roadmap")
def roadmap():
    roadmap_steps = [
        "Learn HTML & CSS",
        "JavaScript Fundamentals",
        "Build 3 Mini Projects",
        "Learn React",
        "Apply for Internships"
    ]
    return render_template("roadmap.html", roadmap=roadmap_steps)


# ============ MAIN ==============
if __name__ == "__main__":
    print("🚀 SkillSync Agent running at http://127.0.0.1:5000")
    app.run(debug=True)
