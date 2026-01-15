from langchain.tools import Tool

def get_commander_tool():
    def execute_command(command: str) -> str:
        """
        Execute high-level command and coordination decisions
        Args:
            command: The command/decision to execute
        Returns:
            str: Result of the command execution
        """
        if "flood" in command.lower():
            return "Coordinating flood response: Dispatching rescue teams and allocating resources."
        elif "evacuation" in command.lower():
            return "Initiating evacuation protocol: Coordinating with rescue teams and shelter management."
        elif "resources" in command.lower():
            return "Managing resource allocation: Optimizing distribution of supplies and personnel."
        else:
            return f"Command received and being processed: {command}"

    return Tool(
        name="CommanderTool",
        func=execute_command,
        description="Coordinates and makes high-level decisions for flood response operations"
    )

