
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StreamableHTTPServerParams



root_agent = LlmAgent(
    name="weather_time_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer questions about the time and weather in a city."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
    ),
    tools=[MCPToolset(
      connection_params=StreamableHTTPServerParams(
          url="http://localhost:8000/mcp"
      )
    )],
  )
