from crewai import Agent, Task, Crew

# Define an agent
agent = Agent(
    role="Researcher",
    goal="Find and share knowledge about AI",
    backstory="You are an AI assistant specializing in explaining concepts clearly."
)

# Define a task
task = Task(
    description="Explain what CrewAI is in simple terms.",
    agent=agent
)

# Create a crew and run the task
crew = Crew(
    agents=[agent],
    tasks=[task]
)

result = crew.kickoff()
print("Result:", result)
