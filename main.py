import os
from dotenv import load_dotenv
from langchain.agents import initialize_agent, Tool, AgentType
from langchain_community.chat_models import ChatLiteLLM

def main():
    # Load environment variables
    load_dotenv()
    
    # Get API key from environment variables
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key not found in environment variables. Please add OPENAI_API_KEY to your .env file.")

    # Set OpenAI endpoint
    api_base = "https://api.openai.com/v1"

    # Initialize LLM
    llm = ChatLiteLLM(
        model="gpt-4.1-nano",
        temperature=0.5,
        OPENAI_API_KEY=OPENAI_API_KEY,
        api_base=api_base
    )

    # Import tools
    from agents.search_agent import get_search_tool
    from agents.rescue_agent import get_rescue_tool
    from agents.comms_agent import get_comms_tool
    from agents.commander_agent import get_commander_tool
    # Define a simple tool
    def greet(name: str = "User"):
        return f"Hello, {name}!"

    tools = [
        Tool(name="Greeter", func=greet, description="Greets the user."),
        get_search_tool(),
        get_rescue_tool(),
        get_comms_tool(),
    ]

    # Initialize agent
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    # Run a test query
    query = "Draft a flood evacuation alert for Magarlod block."
    response = agent.run(query)
    print("🧠 Agent Response:", response)

if __name__ == "__main__":
    main()
