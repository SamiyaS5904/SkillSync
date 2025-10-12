import json
import os
from crewai import Agent, Task, Crew, Process 
from custom_tool import WebSearchTool, RoadmapGeneratorTool, PlaylistPlannerTool 

# --- Defensive Verbose Setting (To fix previous Pydantic error) ---
def get_safe_verbose(default_level=1):
    """Safely returns a valid integer for the Crew/Agent verbose setting."""
    try:
        env_verbose = os.getenv('CREWAI_VERBOSE') or os.getenv('CREW_VERBOSE')
        if env_verbose:
            return int(env_verbose)
        return default_level
    except ValueError:
        return default_level

SAFE_VERBOSE_LEVEL = get_safe_verbose(1)

# --- Global Agent/Tool Instantiation ---
web_search_tool = WebSearchTool()
roadmap_tool = RoadmapGeneratorTool()
playlist_planner_tool = PlaylistPlannerTool()

class SkillSyncCrew:
    def __init__(self):
        # Initialize Agents
        self.career_guide = Agent(
            role="Career Mentor",
            goal="Guide users in exploring career paths, clarifying their goals, and suggesting roles. Always use the Web Search Tool for current market requirements (like Matplotlib/Python versions).",
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

        # 1. ANALYSIS TASK DEFINED FIRST (Fixes the NameError)
        analysis_task = Task(
            description=f"""
                Analyze the user's profile based on this input: {user_input}. Identify the top 5 missing skills required for {goal} based on current job market standards. Provide a short, motivating message. Use the Web Search Tool for current market validation (e.g., check required Python libraries like Matplotlib).
            """,
            expected_output="A JSON object containing analysis (paths, missing_skills, motivation) and initial roadmap ideas.",
            agent=self.career_guide
        )

        # 2. ROADMAP TASK DEFINED SECOND (Uses the defined analysis_task)
        roadmap_task = Task(
            description=f"""
                Based on the analysis and the user's constraints, generate the detailed learning roadmap. The roadmap must include 3-5 milestones, weekly goals, and at least 2 specific project ideas. Use the Roadmap Generator Tool to structure the output.
            """,
            expected_output="A structured JSON object detailing the milestones, weekly_goals, and project ideas.",
            agent=self.learning_coach,
            context=[analysis_task] # analysis_task is guaranteed to be defined here
        )

        roadmap_crew = Crew(
            agents=[self.career_guide, self.learning_coach],
            tasks=[analysis_task, roadmap_task],
            process=Process.sequential,
            verbose=SAFE_VERBOSE_LEVEL
        )

        result = roadmap_crew.kickoff()
        return {"result": result}

    # ... (Rest of run_daily_plan, run_playlist_plan, run_job_readiness remain the same) ...