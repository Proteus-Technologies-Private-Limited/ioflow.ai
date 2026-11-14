# IOFlow - Running Instructions

## If localhost is not working, try these alternatives:

### Option 1: Use 127.0.0.1 instead of localhost

1. **Backend**: http://127.0.0.1:8000
2. **Frontend**: http://127.0.0.1:3000

### Option 2: Use your local IP address

1. **Backend**: http://192.168.1.108:8000
2. **Frontend**: http://192.168.1.108:3000

### Option 3: Check your hosts file

On macOS, check if localhost is properly configured:
```bash
cat /etc/hosts
```

Should contain:
```
127.0.0.1       localhost
::1             localhost
```

## Step-by-Step Instructions

### Terminal 1 - Start Backend:
```bash
cd /path/to/ioflow/backend
source venv/bin/activate
python app_simple.py
```

You should see:
```
Starting IOFlow Backend (Simplified)...
API Documentation: http://localhost:8000/docs
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Terminal 2 - Start Frontend:
```bash
cd /path/to/ioflow/frontend
npm run dev
```

You should see:
```
VITE v5.4.19  ready in XXX ms

➜  Local:   http://localhost:3000/
➜  Network: use --host to expose
```

## Troubleshooting

### 1. Check if ports are in use:
```bash
# Check port 8000
lsof -i :8000

# Check port 3000
lsof -i :3000
```

### 2. Kill processes using the ports:
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

### 3. Try different browsers:
- Safari
- Chrome
- Firefox

### 4. Disable VPN/Proxy:
If you're using a VPN or proxy, try disabling it.

### 5. Check macOS Firewall:
System Preferences > Security & Privacy > Firewall

Make sure it's either off or configured to allow incoming connections.

## Alternative: Run with specific host

### Backend with specific host:
```bash
cd backend
source venv/bin/activate
# Edit app_simple.py and change the last line to:
# uvicorn.run(app, host="127.0.0.1", port=8000)
python app_simple.py
```

### Frontend with specific host:
```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

## Test URLs

Try accessing these URLs in order:

1. http://127.0.0.1:8000 (Backend)
2. http://127.0.0.1:8000/docs (API Documentation)
3. http://127.0.0.1:3000 (Frontend)

If none of these work, there might be a system-level networking issue.