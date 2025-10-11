import json
import os
from crewai import Agent, Task, Crew, Process 
from custom_tool import WebSearchTool, RoadmapGeneratorTool, PlaylistPlannerTool 
# NOTE: Removed direct OpenAI client dependency, as CrewAI manages the LLM.

# --- Global Agent/Tool Instantiation ---
web_search_tool = WebSearchTool()
roadmap_tool = RoadmapGeneratorTool()
playlist_planner_tool = PlaylistPlannerTool()

class SkillSyncCrew:
    def __init__(self):
        # Initialize Agents based on agents.yaml definitions
        self.career_guide = Agent(
            role="Career Mentor",
            goal="Guide users in exploring career paths, clarifying their goals, and suggesting roles. Always use the Web Search Tool for current market requirements (like Matplotlib/Python versions).", # Added explicit instruction
            backstory="You are an experienced global career coach with insights across tech and non-tech fields.",
            tools=[web_search_tool, roadmap_tool],
            verbose=True
        )

        self.learning_coach = Agent(
            role="Learning Strategist",
            goal="Create personalized learning roadmaps, recommend resources, generate daily plans, and adapt plans to user time constraints.",
            backstory="You are a passionate educator who simplifies complex concepts into achievable steps.",
            tools=[roadmap_tool, playlist_planner_tool],
            verbose=True
        )

        self.job_advisor = Agent(
            role="Job Advisor",
            goal="Help users become job-ready by highlighting missing skills, recommending opportunities, and prep for interviews.",
            backstory="You are a recruiter with deep knowledge of hiring across industries.",
            tools=[web_search_tool], 
            verbose=True
        )


    # -------- Workflow 1: Full Roadmap Orchestration (Sequential) --------
    def orchestrate(self, goal: str, skills: list, hours: int, duration: int, weekends: bool = True):
        user_input = f"Goal: {goal}, Current Skills: {skills}, Available Daily Hours: {hours}, Duration: {duration} months."

        analysis_task = Task(
            description=f"""
                Analyze the user's profile based on this input: {user_input}. Identify the top 5 missing skills required for {goal} based on current job market standards. Provide a short, motivating message. Use the Web Search Tool for current market validation (e.g., check required Python libraries like Matplotlib).
            """,
            expected_output="A JSON object containing analysis (paths, missing_skills, motivation) and initial roadmap ideas.",
            agent=self.career_guide
        )

        roadmap_task = Task(
            description=f"""
                Based on the analysis and the user's constraints, generate the detailed learning roadmap. The roadmap must include 3-5 milestones, weekly goals, and at least 2 specific project ideas. Use the Roadmap Generator Tool to structure the output.
            """,
            expected_output="A structured JSON object detailing the milestones, weekly_goals, and project ideas.",
            agent=self.learning_coach,
            context=[analysis_task]
        )

        roadmap_crew = Crew(
            agents=[self.career_guide, self.learning_coach],
            tasks=[analysis_task, roadmap_task],
            process=Process.sequential,
            verbose=2 
        )

        result = roadmap_crew.kickoff()
        return {"result": result}


    # -------- Workflow 2: Daily Plan Generator (Single Agent) --------
    def run_daily_plan(self, goal: str, skills: list, hours_day: int, hours_weekend: int, start_date: str):
        
        plan_task = Task(
            description=f"""
                Generate a daily learning plan and 2 recommended playlists for the user's goal ({goal}) and skills ({skills}). The plan must START from {start_date} and use {hours_day} hours on weekdays and {hours_weekend} hours on weekends.
                Return JSON in the exact format: {{"plan": [{{...}}], "playlists": [{{...}}]}}.
            """,
            expected_output="A JSON object containing the 'plan' (daily schedule with date field) and 'playlists'.",
            agent=self.learning_coach,
        )
        
        daily_crew = Crew(
            agents=[self.learning_coach],
            tasks=[plan_task],
            process=Process.sequential,
            verbose=1 
        )
        result = daily_crew.kickoff()
        return {"result": result}


    # -------- Workflow 3: Multi-Playlist Planner (Dedicated Tool) --------
    def run_playlist_plan(self, playlists: list):
        
        playlist_task = Task(
            description=f"""
                Use the Playlist Planner Tool to analyze this list of playlists and user time commitment: {playlists}.
                Generate a single, unified viewing schedule by dividing the required viewing time across the playlists day-wise.
                Output a JSON schedule.
            """,
            expected_output="A JSON object with a 'schedule' key containing video titles, dates, and minutes.",
            agent=self.learning_coach,
            tools=[playlist_planner_tool] 
        )

        playlist_crew = Crew(
            agents=[self.learning_coach],
            tasks=[playlist_task],
            process=Process.sequential,
            verbose=1
        )
        result = playlist_crew.kickoff()
        return {"result": result}


    # -------- Workflow 4: Job Readiness Check (Dedicated Tool) --------
    def run_job_readiness(self, goal: str, current_progress: int):
        
        readiness_task = Task(
            description=f"""
                Based on the user's goal ({goal}) and their current progress ({current_progress}%), generate a career readiness report.
                Provide a readiness percentage, a motivational message, and suggest 3 relevant internships/jobs.
                Use the Web Search Tool for current job market data.
                Return JSON in the format: {{"readiness_percent": int, "message": str, "internships": [{{title, company, link, missing_skills}}]}}
            """,
            expected_output="A JSON object containing readiness metrics and job/internship suggestions.",
            agent=self.job_advisor,
            tools=[web_search_tool] 
        )
        
        readiness_crew = Crew(
            agents=[self.job_advisor],
            tasks=[readiness_task],
            process=Process.sequential,
            verbose=1
        )
        result = readiness_crew.kickoff()
        return {"result": result}