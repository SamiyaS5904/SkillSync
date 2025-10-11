import json
import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import BaseTool
from custom_tool import WebSearchTool, RoadmapGeneratorTool, PlaylistPlannerTool 
# NOTE: Removed direct OpenAI client dependency, as CrewAI manages the LLM.

# --- Global Agent/Tool Instantiation ---
web_search_tool = WebSearchTool()
roadmap_tool = RoadmapGeneratorTool()
playlist_planner_tool = PlaylistPlannerTool()
# Add other necessary tools (e.g., job_scraper, resume_analyzer) here

class SkillSyncCrew:
    def __init__(self):
        # Initialize Agents based on agents.yaml definitions
        self.career_guide = Agent(
            role="Career Mentor",
            goal="Guide users in exploring career paths, clarifying their goals, and suggesting roles.",
            backstory="You are an experienced global career coach with insights across tech and non-tech fields.",
            tools=[web_search_tool, roadmap_tool],
            verbose=True
        )

        self.learning_coach = Agent(
            role="Learning Strategist",
            goal="Create personalized learning roadmaps, recommend resources, and adapt plans to user time constraints.",
            backstory="You are a passionate educator who simplifies complex concepts into achievable steps.",
            tools=[roadmap_tool, playlist_planner_tool],
            verbose=True
        )

        self.job_advisor = Agent(
            role="Job Advisor",
            goal="Help users become job-ready by highlighting missing skills, recommending opportunities, and prep.",
            backstory="You are a recruiter with deep knowledge of hiring across industries.",
            # Placeholder: Add job_scraper and resume_analyzer tools here
            tools=[web_search_tool], 
            verbose=True
        )


    # -------- Workflow 1: Full Roadmap Orchestration (Sequential) --------
    def orchestrate(self, goal: str, skills: list, hours: int, duration: int, weekends: bool = True):
        # 1. Input Analysis Task (Career Guide)
        analysis_task = Task(
            description=f"""
                Analyze the user's career goal ({goal}) and current skills ({skills}). 
                Suggest the 3 most realistic career paths and identify the top 5 missing skills required to achieve the goal.
                Provide a short, motivating message.
                Use the Web Search Tool for market validation.
            """,
            expected_output="A comprehensive JSON object containing analysis (paths, missing_skills, motivation) and initial roadmap ideas.",
            agent=self.career_guide
        )

        # 2. Roadmap Generation Task (Learning Coach)
        # This task receives the analysis from the previous task automatically.
        roadmap_task = Task(
            description=f"""
                Based on the analysis and the user's constraints (Duration: {duration} months, Hours/day: {hours}), 
                generate the detailed learning roadmap. The roadmap must include 3-5 milestones, weekly goals, and 
                at least 2 specific project ideas.
                Use the Roadmap Generator Tool to structure the output.
            """,
            expected_output="A structured JSON object detailing the milestones, weekly_goals, and project ideas.",
            agent=self.learning_coach
        )

        # 3. Create and Run the Crew
        roadmap_crew = Crew(
            agents=[self.career_guide, self.learning_coach],
            tasks=[analysis_task, roadmap_task],
            process=Process.sequential,
            verbose=2 
        )

        # Kickoff returns the final result from the last task
        result = roadmap_crew.kickoff()
        
        # NOTE: You will need robust JSON parsing in main.py for this final output.
        return {"result": result}


    # -------- Workflow 2: Daily Plan Generator (Single Agent) --------
    def run_daily_plan(self, goal: str, skills: list, hours_day: int, hours_weekend: int, start_date: str):
        plan_task = Task(
            description=f"""
                Generate a daily learning plan and 2 recommended playlists for the user's goal ({goal}) and skills ({skills}). 
                The plan must START from {start_date} and use {hours_day} hours on weekdays and {hours_weekend} hours on weekends.
                Return JSON in the exact format: {{"plan": [{{...}}], "playlists": [{{...}}]}}
            """,
            expected_output="A JSON object containing the 'plan' (daily schedule with date field) and 'playlists'.",
            agent=self.learning_coach,
            tools=[self.learning_coach.tools[1]] # Only allow playlist recommender/web search
        )
        
        # Use a mini-crew for isolated task execution
        daily_crew = Crew(
            agents=[self.learning_coach],
            tasks=[plan_task],
            process=Process.sequential,
            verbose=1 
        )
        result = daily_crew.kickoff()
        return {"result": result}


    # -------- Workflow 3: Playlist Planner (Single Agent/Dedicated Tool) --------
    def run_playlist_plan(self, playlist_url: str, daily_hours: float):
        playlist_task = Task(
            description=f"""
                Analyze the playlist URL: {playlist_url}. Using the Playlist Planner Tool, 
                generate a viewing schedule based on the user's daily commitment of {daily_hours} hours.
                Output a JSON schedule.
            """,
            expected_output="A JSON object with a 'schedule' key containing video titles, dates, and minutes.",
            agent=self.learning_coach,
            tools=[playlist_planner_tool] # Explicitly using the specialized tool
        )

        playlist_crew = Crew(
            agents=[self.learning_coach],
            tasks=[playlist_task],
            process=Process.sequential,
            verbose=1
        )
        result = playlist_crew.kickoff()
        return {"result": result}