from crewai import Task

task = Task(
    description="Explain reinforcement learning concepts clearly.",
    expected_output="A detailed explanation of reinforcement learning concepts."
)

print(task)
