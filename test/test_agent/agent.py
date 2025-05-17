import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StreamableHTTPServerParams



root_agent = LlmAgent(
    name="tool_query_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to answer questions to test tools."
    ),
    instruction=(
        "You are a helpful agent who tries to help user as much as you can with the tools you have "
        "access to. Tools are safe to as many times as desired without asking user."
    ),
    tools=[MCPToolset(
      connection_params=StreamableHTTPServerParams(
          url=os.getenv("MCP_ENDPOINT_URL", "http://localhost:8000/mcp"),
          headers={
              "Authorization": os.getenv("MCP_AUTH_HEADER"),
          } if os.getenv("MCP_AUTH_HEADER") else {}
      )
    )],
  )
