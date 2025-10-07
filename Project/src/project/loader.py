import json
from openai import OpenAI

class SkillSyncCrew:
    def __init__(self):
        # OpenAI client init
        self.client = OpenAI()

    # -------- Quick Agent (Assistant-style) --------
    def run_quick(self, query: str):
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful career assistant."},
                    {"role": "user", "content": query}
                ]
            )
            answer = response.choices[0].message.content
            return {
                "agent": "quick",
                "response": answer
            }
        except Exception as e:
            return {"error": str(e)}

    # -------- Roadmap Orchestration --------
    def orchestrate(self, goal: str, skills: list, hours: int, duration: int, weekends: bool = True):
        try:
            prompt = f"""
You are an AI career mentor. Create a personalized roadmap.

Career Goal: {goal}
Current Skills: {skills}
Available hours per weekday: {hours}
Duration: {duration} months
Include weekends: {weekends}

Return JSON with 3 sections:
{{
  "analysis": {{
    "interpretation": "short analysis of user's profile",
    "missing_skills": ["skill1","skill2"],
    "motivational_message": "short motivation"
  }},
  "roadmap": {{
    "milestones": [
      {{
        "title": "Milestone 1",
        "description": "what to achieve",
        "duration_weeks": 4,
        "tasks": ["task1","task2","task3"]
      }}
    ]
  }},
  "tasks": {{
    "plan": [
      {{
        "week_start": "Week 1",
        "tasks": [{{"title": "Task A", "done": false}}]
      }}
    ]
  }}
}}
"""
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            raw = response.choices[0].message.content
            data = json.loads(raw)

            return data
        except Exception as e:
            return {"error": str(e)}
