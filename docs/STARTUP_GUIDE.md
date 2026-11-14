# IOFlow Startup Guide

> **Outdated.** This guide predates the current scripts and lists old ports and commands. Use [GETTING_STARTED.md](GETTING_STARTED.md) instead.

## Quick Start (Development)

### Prerequisites
1. **Python 3.11+** - [Download](https://www.python.org/downloads/)
2. **Node.js 16+** - [Download](https://nodejs.org/)
3. **PostgreSQL 12+** - [Download](https://www.postgresql.org/download/)
4. **Redis** (optional for background tasks) - [Download](https://redis.io/download/)

### Option 1: Automatic Setup (Recommended)

Run the all-in-one script:
```bash
./run_local.sh
```

This will:
- Check all dependencies
- Install Python and Node packages
- Start both backend and frontend
- Backend: http://localhost:8000
- Frontend: http://localhost:3000

### Option 2: Manual Setup

#### 1. Database Setup
```bash
# Create database and user
psql -U postgres
CREATE DATABASE ioflow;
CREATE USER ioflow WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE ioflow TO ioflow;
\q
```

#### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and update DATABASE_URL with your credentials

# Initialize database
python init_db.py

# Run backend
python run.py
```

Backend will be available at http://localhost:8000

#### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

Frontend will be available at http://localhost:3000

### Option 3: Docker Setup

```bash
# Start all services with Docker Compose
docker-compose up

# Or run in background
docker-compose up -d
```

This will start:
- PostgreSQL on port 5432
- Redis on port 6379
- Backend on port 8000
- Frontend on port 3000

## First Steps

1. **Register an Account**
   - Go to http://localhost:3000/register
   - Fill in your details
   - Check console/logs for activation code (email service not configured)
   - Enter activation code

2. **Login**
   - Use your email and password to login
   - You'll be redirected to the dashboard

3. **Explore the API**
   - Visit http://localhost:8000/docs for interactive API documentation
   - Try out the endpoints with the "Try it out" button

## Default Credentials (Docker)
- PostgreSQL:
  - User: `ioflow`
  - Password: `password`
  - Database: `ioflow`

## Troubleshooting

### Backend won't start
1. Check PostgreSQL is running: `pg_isready`
2. Verify database credentials in `.env`
3. Check port 8000 is not in use: `lsof -i :8000`

### Frontend won't start
1. Delete `node_modules` and run `npm install` again
2. Check port 3000 is not in use: `lsof -i :3000`
3. Clear npm cache: `npm cache clean --force`

### Database connection errors
1. Ensure PostgreSQL is running
2. Check credentials in `.env` match your PostgreSQL setup
3. Try connecting manually: `psql -U ioflow -d ioflow -h localhost`

### Module import errors
1. Ensure you're in the virtual environment
2. Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
3. Check Python version: `python --version` (should be 3.11+)

## Development Tips

1. **API Documentation**: Always available at http://localhost:8000/docs
2. **Database Viewer**: Use pgAdmin or DBeaver to inspect the database
3. **Hot Reload**: Both backend and frontend support hot reload in development
4. **Logs**: Check terminal output for detailed error messages

## Next Steps

1. Create your first application in the Applications section
2. Design a flow in the Flow Designer
3. Test webhook integrations using the API
4. Monitor executions in the Executions page