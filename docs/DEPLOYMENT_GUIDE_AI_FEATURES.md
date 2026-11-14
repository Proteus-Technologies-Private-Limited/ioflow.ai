# AI Features Deployment Guide

## Overview

This guide covers deploying the new AI-powered transformation features to IOFlow.

## Files Added/Modified

### Backend Files Added
- `backend/schemas/ai_settings_schemas.py` - Pydantic schemas for AI settings
- `backend/api/ai_settings.py` - API endpoints for AI settings management  
- `backend/services/ai_transformation_service.py` - Core AI transformation service
- `backend/migrations/add_ai_settings_to_users.sql` - Database migration

### Backend Files Modified
- `backend/db/models.py` - Added AI configuration fields to User model
- `backend/db/models_sqlite.py` - Added AI configuration fields to User model (SQLite)
- `backend/main.py` - Added AI settings router

### Frontend Files Added
- `frontend/src/components/flow/EnhancedTransformCodeEditor.js` - Multi-tab transform editor with AI
- `frontend/src/components/settings/AISettings.js` - AI settings configuration page

### Test Files Added
- `test-script/test_ai_settings_db.py` - Database integration tests
- `test-script/test_ai_gmail_transformation.py` - End-to-end AI transformation test

### Documentation Added
- `docs/AI_POWERED_TRANSFORMATIONS.md` - Complete feature documentation

## Deployment Steps

### 1. Database Migration

#### For PostgreSQL
```sql
-- Create user_settings table
CREATE TABLE ioflow.user_settings (
  id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id VARCHAR(36) NOT NULL REFERENCES ioflow.users(user_id) ON DELETE CASCADE,
  setting_type VARCHAR(50) NOT NULL,
  setting_data JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT unique_user_setting_type UNIQUE (user_id, setting_type)
);

-- Create indexes for performance
CREATE INDEX idx_user_settings_user_id ON ioflow.user_settings(user_id);
CREATE INDEX idx_user_settings_type ON ioflow.user_settings(setting_type);
```

#### For SQLite
```sql
-- Create user_settings table
CREATE TABLE user_settings (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  setting_type TEXT NOT NULL,
  setting_data TEXT NOT NULL, -- JSON stored as TEXT
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, setting_type)
);

-- Create indexes
CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX idx_user_settings_type ON user_settings(setting_type);
```

### 2. Backend Deployment

1. **Install Dependencies** (if any new ones were added):
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Restart Backend Server**:
   ```bash
   ./start_backend.sh
   ```

3. **Verify API Endpoints**:
   ```bash
   curl -X GET http://localhost:7001/api/v1/ai-settings/providers
   ```

### 3. Frontend Deployment

1. **Add AI Settings to Navigation** (modify your existing settings menu):
   ```javascript
   // Add to your user settings menu
   import AISettings from '../components/settings/AISettings';
   
   // Add route
   <Route path="/settings/ai" component={AISettings} />
   ```

2. **Update Transform Node** (replace existing TransformCodeEditor):
   ```javascript
   // In your flow designer, replace TransformCodeEditor with:
   import EnhancedTransformCodeEditor from '../components/flow/EnhancedTransformCodeEditor';
   
   // Use the enhanced version
   <EnhancedTransformCodeEditor
     value={transformCode}
     onChange={setTransformCode}
     availableVariables={availableVariables}
     flowContext={flowContext}
     nodeContext={nodeContext}
   />
   ```

3. **Build and Deploy Frontend**:
   ```bash
   cd frontend
   npm run build
   # Deploy build/ directory to your web server
   ```

### 4. Testing Deployment

#### Test 1: Database Schema
```bash
# Check if new columns exist
# PostgreSQL:
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'users' AND table_schema = 'ioflow' 
AND column_name LIKE 'ai_%';

# SQLite:
PRAGMA table_info(users);
```

#### Test 2: API Endpoints
```bash
# Test providers endpoint
curl -X GET http://localhost:7001/api/v1/ai-settings/providers

# Test user AI settings (requires authentication)
curl -X GET http://localhost:7001/api/v1/ai-settings/ \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Test 3: Frontend Integration
1. Login to IOFlow
2. Navigate to User Settings > AI Settings
3. Configure an AI provider
4. Test connection
5. Create a new flow with a Transform node
6. Try the AI Assistant tab

## Configuration

### Environment Variables
No new environment variables required. Users provide their own AI API keys through the UI.

### Security Considerations
- AI API keys are encrypted using IOFlow's existing crypto system
- No IOFlow API keys needed - users provide their own
- AI requests are made directly from backend to AI providers
- No sensitive data stored in plain text

## User Instructions

### For End Users

1. **Configure AI Settings**:
   - Go to User Settings → AI Settings
   - Choose your AI provider (OpenAI, Claude, etc.)
   - Enter your API key
   - Test connection
   - Save settings

2. **Use AI in Flows**:
   - Add a Transform node to your flow
   - Click "AI Assistant" tab
   - Describe your transformation in natural language
   - Generate and apply code

### For Administrators

1. **Monitor Usage**:
   - AI calls are logged in IOFlow's standard logging
   - No additional monitoring setup required
   - Costs are borne by individual users

2. **Support Users**:
   - Help users obtain API keys from AI providers
   - Troubleshoot connection issues
   - Guide users on writing effective prompts

## Rollback Plan

If issues arise, the changes can be rolled back:

### Backend Rollback
1. **Remove AI router from main.py**:
   ```python
   # Comment out this line in main.py:
   # app.include_router(ai_settings.router)
   ```

2. **Revert to previous backend version** or restart without AI files

### Frontend Rollback
1. **Revert to original TransformCodeEditor**:
   ```javascript
   // Replace EnhancedTransformCodeEditor with TransformCodeEditor
   import TransformCodeEditor from '../components/flow/TransformCodeEditor';
   ```

2. **Remove AI Settings from navigation**

### Database Rollback (if needed)
```sql
-- PostgreSQL
ALTER TABLE ioflow.users 
DROP COLUMN ai_model_provider,
DROP COLUMN ai_model_name,
DROP COLUMN ai_api_key_hash,
DROP COLUMN ai_api_endpoint,
DROP COLUMN ai_settings;

-- SQLite (more complex - backup recommended before adding columns)
-- Best to restore from backup if rollback needed
```

## Performance Impact

### Backend
- Minimal impact when AI features not used
- AI calls are asynchronous and don't block flow execution
- Uses existing authentication and database systems

### Frontend
- New components only loaded when used
- No performance impact on existing flows
- Enhanced transform editor has same performance as original

### Database
- 5 new optional columns per user (minimal storage impact)
- No additional indexes required
- No impact on existing queries

## Monitoring and Maintenance

### Logs to Monitor
- AI API call success/failure rates
- User AI configuration errors
- Transform code generation requests

### Regular Maintenance
- Monitor user feedback on AI code quality
- Update AI provider integrations as APIs evolve
- Review and update system prompts for better code generation

## Troubleshooting Common Issues

### "AI settings not saving"
- Check database connection
- Verify encryption key is set
- Check server logs for crypto errors

### "AI connection test fails"
- Verify user's API key is correct
- Check AI provider service status
- Review proxy/firewall settings

### "Generated code has errors"
- Review system prompts in ai_transformation_service.py
- Check if AI provider returns expected format
- Verify RestrictedPython compatibility

## Success Criteria

✅ Database migration completed without errors  
✅ All API endpoints respond correctly  
✅ Frontend components load and function  
✅ Users can configure AI settings  
✅ AI code generation works with sample data  
✅ Existing flows continue to work unchanged  
✅ No performance degradation observed  

## Support Resources

- Full documentation: `docs/AI_POWERED_TRANSFORMATIONS.md`
- Test scripts: `test-script/test_ai_*`
- API documentation: Available at `/docs` endpoint after deployment
- User guide: Included in the main documentation