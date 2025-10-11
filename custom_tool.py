from typing import Type
from crewai.tools import BaseTool # FIX: BaseTool is correctly imported from crewai.tools
from pydantic import BaseModel, Field
import json
import requests 

# --- Tool Input Schemas ---
class WebSearchInput(BaseModel):
    """Input schema for WebSearchTool."""
    query: str = Field(description="The search term to find job market data or required skills.")

class PlaylistInput(BaseModel):
    """Input schema for PlaylistPlannerTool."""
    playlists: list[dict] = Field(description="List of playlists, each with 'url' and 'hours' to analyze.")


# --- Specialized Tool Classes ---

class WebSearchTool(BaseTool):
    name: str = "Web Search Tool"
    # FIX: Added str annotation for Pydantic V2 compliance
    description: str = "Searches the internet for the latest career paths, job requirements, and skill prerequisites." 
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str) -> str:
        # Placeholder
        return f"Found latest market data on '{query}'. The key requirement is deep practice."


class RoadmapGeneratorTool(BaseTool):
    name: str = "Roadmap Structure Tool"
    description: str = "Generates a structured learning plan framework, converting abstract goals into defined milestones and tasks."
    
    def _run(self, goal_and_skills: str) -> str:
        return f"Successfully generated a structural outline for: {goal_and_skills}. Ready for task filling."


class PlaylistPlannerTool(BaseTool):
    name: str = "Playlist Planner Tool"
    description: str = "Analyzes a list of video playlist URLs and user time commitments, generating a single, unified daily viewing schedule."
    args_schema: Type[BaseModel] = PlaylistInput
    
    def _run(self, playlists: list[dict]) -> str:
        # Placeholder: Returns simulated JSON schedule
        if playlists and any("youtube.com" in p.get("url", "") for p in playlists):
             total_hours = sum(p.get('hours', 0) for p in playlists)
             
             return json.dumps({
                 "schedule": [
                     {"date": "2025-10-15", "video_title": f"Video 1 from List {i}", "time_needed_minutes": 60, "url": p.get("url", "#") }
                     for i, p in enumerate(playlists)
                 ],
                 "schedule_summary": f"Total commitment analyzed: {total_hours} hours daily.",
             })
        return '{"schedule": [], "error": "Playlist URL not supported or analysis failed."}'