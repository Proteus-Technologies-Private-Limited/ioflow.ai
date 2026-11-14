# IOFlow - Integration Platform

IOFlow is an integration platform that allows different applications to integrate with each other in an easy and reliable way. The integration process may involve multiple steps and conditional workflows to complete the process.

## Features

- **Application Registry**: Define and manage integrations with various applications
- **Flow Designer**: Visual workflow designer using React Flow
- **Event-driven Execution**: Trigger flows based on webhooks, schedules, or manual triggers
- **Multi-tenancy**: Complete isolation between different organizations
- **Conditional Logic**: Build complex workflows with conditions and parallel execution
- **Monitoring**: Track executions with detailed logs and statistics

## Technology Stack

### Backend
- Python 3.11+
- FastAPI
- PostgreSQL (multi-schema for tenancy)
- SQLAlchemy ORM
- Celery (for async tasks)
- APScheduler (for scheduled tasks)

### Frontend
- React 18
- React Flow (for workflow designer)
- Tailwind CSS
- React Query
- React Hook Form

## Project Structure

```
IOFlow/
├── backend/
│   ├── api/           # API endpoints
│   ├── core/          # Core configuration and security
│   ├── db/            # Database models and utilities
│   ├── services/      # Business logic (execution engine, scheduler)
│   └── utils/         # Utility functions
├── frontend/
│   ├── public/        # Static files
│   └── src/
│       ├── components/  # Reusable components
│       ├── contexts/    # React contexts
│       ├── pages/       # Page components
│       └── services/    # API services
└── docs/              # Documentation
```

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 16+
- PostgreSQL 12+
- Redis (for Celery)

### Backend Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize the database:
```bash
python -c "from db.database import init_db; init_db()"
```

5. Run the backend server:
```bash
python main.py
```

The backend will be available at http://localhost:8000

### Frontend Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm start
```

The frontend will be available at http://localhost:3000

## API Documentation

Once the backend is running, you can access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Key Concepts

### Applications
Applications are external services that can be integrated (e.g., Salesforce, Slack, etc.). They define:
- Authentication methods
- Available events (triggers)
- Available services (actions)

### Flows
Flows are the integration workflows that connect applications. They consist of:
- Trigger: What starts the flow (webhook, schedule, manual)
- Nodes: Actions, conditions, or parallel branches
- Edges: Connections between nodes

### Executions
Each time a flow runs, it creates an execution record with:
- Status tracking
- Detailed logs
- Execution data

### Multi-tenancy
Each organization (tenant) has:
- Isolated database schema
- Own set of flows and subscriptions
- Separate execution history

## Development

### Adding a New Application

1. Define the application in the admin interface or via API
2. Specify authentication configuration
3. Define available events and services
4. Subscribe tenants to use the application

### Creating a Flow

1. Select a trigger (event, schedule, or manual)
2. Add action nodes for API calls
3. Add conditions for branching logic
4. Connect nodes to define execution order
5. Test and activate the flow

## License

IOFlow is open source software released under the [MIT License](LICENSE).

Copyright (c) 2026 Proteus Technologies Private Limited.