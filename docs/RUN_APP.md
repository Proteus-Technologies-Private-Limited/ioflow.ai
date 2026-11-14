# Running IOFlow Application

> **Outdated.** This guide predates the current scripts and lists old ports and commands. Use [GETTING_STARTED.md](GETTING_STARTED.md) instead.

## Quick Start

The application is now ready to run! Follow these steps:

### 1. Start the Backend (Terminal 1)

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python app_simple.py
```

The backend will start at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 2. Start the Frontend (Terminal 2)

```bash
cd frontend
npm install  # First time only
npm start
```

The frontend will start at:
- Web App: http://localhost:3000

## Test the Application

1. **Register a new account**:
   - Go to http://localhost:3000/register
   - Fill in your details
   - Note the activation code shown (in production, this would be emailed)
   
2. **Activate your account**:
   - Enter the activation code when prompted
   
3. **Login**:
   - Use your email and password to login
   - You'll be redirected to the dashboard

## Current Status

### ✅ Working Features:
- User registration with multi-tenant support
- Account activation
- JWT-based authentication
- Basic dashboard
- API documentation at /docs

### 🚧 In Progress:
- Application registry management
- Flow designer with React Flow
- Execution monitoring
- Webhook handling

## API Endpoints

The backend provides these endpoints:
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/activate` - Activate account
- `GET /api/v1/flows` - List flows (placeholder)
- `GET /api/v1/applications` - List applications (placeholder)

## Notes

- The simplified backend (`app_simple.py`) uses SQLite for easy testing
- In production, use the full backend with PostgreSQL
- The frontend is configured to proxy API requests to http://localhost:8000