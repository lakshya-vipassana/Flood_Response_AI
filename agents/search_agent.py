from langchain.tools import Tool

def get_search_tool():
    def search_affected_areas(query: str) -> str:
        """
        Search and identify affected areas and people needing assistance
        Args:
            query: The search query/area to investigate
        Returns:
            str: Search results and findings
        """
        if "trapped" in query.lower():
            return "Scanning area for trapped individuals using thermal imaging and drone surveillance."
        elif "damage" in query.lower():
            return "Assessing infrastructure damage and identifying high-risk zones."
        elif "water level" in query.lower():
            return "Monitoring water levels and flood progression in specified areas."
        else:
            return f"Conducting area search and assessment: {query}"

    return Tool(
        name="SearchTool",
        func=search_affected_areas,
        description="Searches and identifies affected areas and people needing assistance"
    )
