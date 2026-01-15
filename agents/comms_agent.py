from langchain.agents import Tool

def get_comms_tool():
    def draft_alert(message_type: str) -> str:
        return f"[CommsAgent] Public Alert ({message_type}): Evacuation notice has been issued. Please follow instructions from local authorities."

    return Tool(
        name="Public Alert Generator",
        func=draft_alert,
        description="Generates flood alerts, warnings, and public advisories for residents."
    )
