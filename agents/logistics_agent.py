from langchain.tools import Tool

def get_logistics_tool():
    def manage_resources(request: str) -> str:
        """
        Manage and track resources, supplies, and transportation
        Args:
            request: The resource management request
        Returns:
            str: Status of the resource management request
        """
        if "supplies" in request.lower():
            return "Checking supply inventory and dispatching needed materials."
        elif "transport" in request.lower():
            return "Coordinating transportation assets for resource movement."
        elif "shelter" in request.lower():
            return "Managing shelter resources and capacity allocation."
        else:
            return f"Processing logistics request: {request}"

    return Tool(
        name="LogisticsTool",
        func=manage_resources,
        description="Manages resources, supplies, and transportation for flood response"
    ) 