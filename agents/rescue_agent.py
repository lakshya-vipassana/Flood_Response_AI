from langchain.agents import Tool

def get_rescue_tool():
    def suggest_evacuation(block: str) -> str:
        return f"[RescueAgent] Suggested evacuation for {block}: All residents in the affected area should move to designated safe zones."

    return Tool(
        name="Rescue Planner",
        func=suggest_evacuation,
        description="Suggests tactical evacuation plans and safe shelter routes for affected regions."
    )
