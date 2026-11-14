# URL Configuration Guide for IOFlow

## Overview
IOFlow can be deployed in various environments (local development, staging, production) and accessed through different URLs. This guide explains how to configure URLs properly, especially when running behind nginx or other reverse proxies.

## Environment Variables

The following environment variables control URL generation in IOFlow:

### Primary URL Settings

1. **`FRONTEND_URL`** (Recommended for production)
   - The public-facing URL where users access your IOFlow instance
   - Used for generating collaboration links, OAuth callbacks, etc.
   - Example: `https://ioflow.yourdomain.com`

2. **`SERVER_URL`** 
   - The base server URL for API access
   - Falls back to this if `FRONTEND_URL` is not set
   - Example: `https://api.ioflow.yourdomain.com`

3. **`BASE_URL`**
   - Alias for `SERVER_URL` for backward compatibility
   - Used as a fallback if neither `FRONTEND_URL` nor `SERVER_URL` is set

## Configuration Priority

The system uses the following priority order for URL generation:
1. `FRONTEND_URL` (if set)
2. `SERVER_URL` (if set)
3. `BASE_URL` (if set)
4. `http://localhost:7001` (default fallback)

## Setting Up for Production with Nginx

### 1. Update your `.env` file

```bash
# Add to backend/.env
FRONTEND_URL=https://ioflow.yourdomain.com
SERVER_URL=https://ioflow.yourdomain.com
BASE_URL=https://ioflow.yourdomain.com
```

### 2. Nginx Configuration Example

```nginx
server {
    listen 443 ssl http2;
    server_name ioflow.yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Frontend (React)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://localhost:7001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket support
    location /ws/ {
        proxy_pass http://localhost:7001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 3. Restart Services

After updating the configuration:

```bash
# Restart backend
cd backend
./start_backend.sh

# Restart nginx
sudo nginx -s reload
```

## Features Affected by URL Configuration

The following features use the configured URLs:

1. **Collaboration Links**: Share links for collaborative editing
2. **OAuth Callbacks**: Google, GitHub, and other OAuth providers
3. **Email Links**: Password reset, invitation links
4. **Webhook URLs**: External service callbacks
5. **Embed Codes**: Frontend application embedding

## Troubleshooting

### Issue: Collaboration links still show localhost:7001

**Solution**: Ensure you've set the `FRONTEND_URL` environment variable and restarted the backend service.

### Issue: OAuth callbacks fail

**Solution**: 
1. Update `OAUTH_CALLBACK_BASE_URL` in your `.env` file
2. Update the callback URL in your OAuth provider settings (Google Console, GitHub, etc.)

### Issue: Links in emails are incorrect

**Solution**: Check that `SERVER_URL` or `BASE_URL` is properly set in your environment.

## Development vs Production

### Development
```bash
# .env.development
FRONTEND_URL=http://localhost:3000
SERVER_URL=http://localhost:7001
```

### Production
```bash
# .env.production
FRONTEND_URL=https://ioflow.yourdomain.com
SERVER_URL=https://ioflow.yourdomain.com
```

## Docker Deployment

If using Docker, pass environment variables through docker-compose:

```yaml
version: '3.8'
services:
  backend:
    image: ioflow-backend
    environment:
      - FRONTEND_URL=https://ioflow.yourdomain.com
      - SERVER_URL=https://ioflow.yourdomain.com
      - DATABASE_URL=postgresql://...
    ports:
      - "7001:7001"
```

## Verification

To verify your configuration is working:

1. Create a collaboration session for a flow
2. Check the generated share link - it should use your configured domain
3. Test OAuth login if configured
4. Check email links if email service is configured

## Security Considerations

1. Always use HTTPS in production
2. Ensure `ALLOWED_ORIGINS` includes your frontend URL for CORS
3. Keep internal service URLs (database, redis) private
4. Use environment-specific configuration files