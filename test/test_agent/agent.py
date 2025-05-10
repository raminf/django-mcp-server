import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent



# ./adk_agent_samples/mcp_agent/agent.py
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams, StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters


async def create_agent():
  """Gets tools from MCP Server."""
  tools, exit_stack = await MCPToolset.from_server(
      connection_params=StreamableHTTPServerParams(
       #SseServerParams(
          # TODO: IMPORTANT! Change the path below to your remote MCP Server path
          url="http://localhost:8000/mcp"
      )
  )

  agent = LlmAgent(
    name="weather_time_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer questions about the time and weather in a city."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
    ),
    tools=tools,
  )
  return agent, exit_stack


root_agent = create_agent()
