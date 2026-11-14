# Flow Agent System

A powerful agent management system built with Google ADK (Agent Development Kit) v1.14.0, FastAPI, and React. This system allows you to define, configure, and execute AI agents through a web interface.

## Features

- **Google ADK Integration**: Leverages Google's Agent Development Kit v1.14.0 for building sophisticated AI agents
- **JSON-based Agent Configuration**: Define agents with system prompts, tools, and output schemas
- **MCP Tools Support**: Integration with Model Context Protocol for external tools
- **Built-in Tools**: Support for Google Search and Code Execution
- **Structured Output**: Define JSON schemas for consistent agent responses
- **Web Interface**: Modern React frontend with Tailwind CSS
- **RESTful API**: FastAPI backend with automatic documentation

## Prerequisites

- Python 3.12+
- Node.js 16+
- Google AI API Key (get from https://makersuite.google.com/app/apikey)

## Project Structure

```
flow-agent/
├── venv/                      # Python virtual environment
├── flow-agent-server/         # Backend (FastAPI)
│   ├── agents/               # Agent JSON configurations
│   │   ├── general_agent.json
│   │   ├── research_agent.json
│   │   └── code_agent.json
│   ├── app/
│   │   ├── models.py        # Pydantic models
│   │   ├── main.py          # FastAPI application
│   │   ├── services/        # Business logic
│   │   └── api/             # API routes
│   └── .env.example         # Environment variables template
├── flow-agent-client/         # Frontend (React)
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API client
│   │   └── App.js          # Main application
│   └── package.json
├── test-scripts/             # Testing utilities
│   └── test_agent.py
└── docs/                     # Documentation
```

## Installation

### 1. Clone the repository
```bash
cd flow-agent
```

### 2. Set up the Backend

```bash
# Activate virtual environment
source venv/bin/activate

# Dependencies are already installed including:
# - google-adk==1.14.0
# - fastapi
# - uvicorn
# - pydantic

# Configure environment variables
cd flow-agent-server
cp .env.example .env
# Edit .env and add your GOOGLE_AI_API_KEY
```

### 3. Set up the Frontend

```bash
cd flow-agent-client
# Dependencies are already installed
```

## Running the Application

### Start the Backend Server

```bash
# From the flow-agent directory
./run_backend.sh

# Or manually:
source venv/bin/activate
cd flow-agent-server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Start the Frontend

```bash
# From the flow-agent directory
./run_frontend.sh

# Or manually:
cd flow-agent-client
npm start
```

The frontend will be available at http://localhost:3000

## Agent Configuration

Agents are defined using JSON files in `flow-agent-server/agents/`. Each agent configuration includes:

```json
{
  "id": "unique_agent_id",
  "name": "Agent Display Name",
  "description": "What the agent does",
  "system_prompt": "System instructions for the agent",
  "prompt_template": "Template with {user_input} placeholder",
  "tools": ["search", "code_execution"],  // Optional built-in tools
  "mcp_tools": [                          // Optional MCP tools
    {
      "server_name": "tool_name",
      "server_url": "http://mcp-server-url",
      "server_type": "http"
    }
  ],
  "output_schema": {                      // Optional structured output
    "type": "object",
    "properties": {
      "field1": {"type": "string"},
      "field2": {"type": "array"}
    }
  },
  "agent_model_config": {
    "model": "gemini-2.0-flash-latest",
    "temperature": 0.7,
    "max_tokens": 2048,
    "top_p": 0.95,
    "api_key": "YOUR_API_KEY_HERE"  // Optional: agent-specific API key
  }
}
```

## Available Agents

### 1. General Agent
- **ID**: `general_agent`
- **Purpose**: General-purpose AI assistant
- **Tools**: None
- **Best for**: Simple Q&A, conversations

### 2. Research Agent
- **ID**: `research_agent`
- **Purpose**: Research and information gathering
- **Tools**: Google Search
- **Output**: Structured findings with sources
- **Best for**: Research tasks, fact-finding

### 3. Code Agent
- **ID**: `code_agent`
- **Purpose**: Programming assistance
- **Tools**: Code Execution
- **Output**: Code with explanations and test results
- **Best for**: Code generation, debugging

## API Endpoints

- `GET /api/agents` - List all available agents
- `GET /api/agents/{agent_id}` - Get agent details
- `POST /api/agents/{agent_id}/execute` - Execute an agent
- `GET /api/health` - Health check

## Testing

Run the test script to verify agent functionality:

```bash
source venv/bin/activate
cd test-scripts
python test_agent.py
```

## API Key Configuration

You have two options for configuring Google AI API keys:

### Option 1: Global API Key (Environment Variable)

Create a `.env` file in `flow-agent-server/`:

```env
# Default API key for all agents
GOOGLE_AI_API_KEY=your_api_key_here

# Optional settings
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO
```

### Option 2: Per-Agent API Keys

Configure API keys directly in each agent's JSON file:

```json
{
  "id": "my_agent",
  "name": "My Agent",
  "agent_model_config": {
    "model": "gemini-2.0-flash-latest",
    "api_key": "agent_specific_api_key_here"
  }
}
```

**Priority**: Agent-specific API keys override the environment variable. This allows:
- Different agents to use different API keys
- Separate quota management per agent
- Testing with different API permissions

## Technologies Used

- **Backend**:
  - Google ADK 1.14.0 (Agent Development Kit)
  - FastAPI
  - Pydantic
  - Python 3.12

- **Frontend**:
  - React 19
  - Tailwind CSS
  - Axios

- **AI Model**:
  - Gemini 2.0 Flash (via Google ADK)

## Troubleshooting

1. **Server won't start**: Ensure GOOGLE_AI_API_KEY is set in .env
2. **Frontend can't connect**: Check backend is running on port 8000
3. **Agent execution fails**: Verify API key has proper permissions
4. **MCP tools not working**: Ensure MCP server is running and accessible

## License

MIT

## Contributing

Feel free to submit issues and enhancement requests!