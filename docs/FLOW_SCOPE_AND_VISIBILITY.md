# Flow Scope and Visibility Documentation

## Overview

The Flow Scope system in IOFlow provides granular control over flow visibility and access permissions based on user roles and flow ownership. This document outlines the complete implementation of flow scopes, visibility rules, and permission management.

**Key Principles:**
- Tenant isolation is strictly enforced - users can only access resources within their tenant
- Flow ownership determines edit permissions for user-scoped flows
- Execution visibility is based on both flow ownership and who triggered the execution
- Role-based access control (RBAC) determines what actions users can perform

## Table of Contents

1. [Flow Scope Types](#flow-scope-types)
2. [User Roles and Permissions](#user-roles-and-permissions)
3. [Visibility Rules](#visibility-rules)
4. [Permission Matrix](#permission-matrix)
5. [Implementation Details](#implementation-details)
6. [API Endpoints](#api-endpoints)
7. [Frontend UI](#frontend-ui)
8. [Database Schema](#database-schema)

## Flow Scope Types

Flows can be assigned one of three scope levels:

### 1. **User Scope** (`user`)
- **Description**: Private flows visible only to the creator
- **Default**: This is the default scope for all new flows
- **Visibility**: Only the flow creator can see and use these flows
- **Use Case**: Personal workflows, testing, private automation

### 2. **Tenant Scope** (`tenant`)
- **Description**: Team/Organization level flows
- **Visibility**: All users within the same tenant/organization can see and use these flows
- **Use Case**: Department workflows, shared team automation, organizational processes

### 3. **Global Scope** (`global`)
- **Description**: System-wide flows available to everyone
- **Visibility**: All users across all organizations can see and use these flows
- **Use Case**: Common utilities, system-wide integrations, standard processes

## User Roles and Permissions

IOFlow implements six distinct user roles with different access levels:

### 1. **Instance Admin** (`INSTANCE_ADMIN`)
- **System Access**: Full administrative control across all tenants
- **Flow Access**: Can view and manage ALL flows across ALL tenants
- **Flow Creation**: Can create flows with any scope (global, tenant, user)
- **Flow Editing**: Can edit any flow in the system
- **Execution Access**: Can view all executions and logs across all tenants
- **Special Permissions**: System configuration, tenant management, user management

### 2. **Tenant Admin** (`TENANT_ADMIN`)
- **Tenant Access**: Full administrative control within their tenant only
- **Flow Access**: Can view ALL flows in their tenant (including all user-specific flows created by any user)
- **Flow Creation**: Can create flows with tenant and user scope
- **Flow Editing**: Can edit any flow within their tenant
- **Execution Access**: Can view ALL execution logs within their tenant only
- **Special Permissions**: Tenant settings, user management within tenant

### 3. **Flow Designer** (`FLOW_DESIGNER`)
- **Primary Role**: Create and design automation flows
- **Flow Access**: Can view global flows, tenant flows, and their own user flows
- **Flow Creation**: Can create flows with user scope only
- **Flow Editing**: Can only edit flows they created
- **Execution Access**: Can only view execution logs of flows they created
- **Limitations**: Cannot edit other users' flows, even if tenant-scoped

### 4. **Flow Editor** (`FLOW_EDITOR`)
- **Primary Role**: Edit and maintain existing flows
- **Flow Access**: Same as Flow Designer - global, tenant, and own user flows
- **Flow Creation**: Can create flows with user scope only
- **Flow Editing**: Can only edit flows they created
- **Execution Access**: Can only view execution logs of flows they created
- **Limitations**: Cannot edit other users' flows, even if tenant-scoped

### 5. **Execution Monitor** (`EXECUTION_MONITOR`)
- **Primary Role**: Monitor flow executions without editing capability
- **Flow Access**: Can view global flows, tenant flows, and their own user flows (read-only)
- **Flow Creation**: Cannot create flows
- **Flow Editing**: Cannot edit any flows
- **Execution Access**: Can view execution logs of all accessible flows (global, tenant, own user) within their tenant
- **Use Case**: Operations teams, support staff, auditors

### 6. **Regular User** (`USER`)
- **Primary Role**: End user of published applications
- **Flow Access**: Cannot access the flow designer interface
- **Flow Creation**: Cannot create flows
- **Flow Editing**: Cannot edit flows
- **Execution Access**: Can only view execution logs of executions they personally triggered
- **Allowed Actions**: Execute published applications, view own execution history

## Visibility Rules

### Flow Visibility Matrix

| User Role | Global Flows | Tenant Flows | Other Users' Flows | Own User Flows |
|-----------|--------------|--------------|-------------------|----------------|
| Instance Admin | ✅ All | ✅ All | ✅ All | ✅ All |
| Tenant Admin | ✅ View | ✅ All in tenant | ✅ All in tenant | ✅ All |
| Flow Designer | ✅ View | ✅ View | ❌ No | ✅ All |
| Flow Editor | ✅ View | ✅ View | ❌ No | ✅ All |
| Execution Monitor | ✅ View | ✅ View | ❌ No | ✅ View |
| Regular User | ❌ No | ❌ No | ❌ No | ❌ No |

### Execution Visibility Matrix

| User Role | Can View Executions | Scope Limitations |
|-----------|-------------------|-------------------|
| Instance Admin | All executions across all tenants | No limitations |
| Tenant Admin | All executions in their tenant only | Limited to their tenant |
| Flow Designer/Editor | Only executions of flows they created | Limited to their tenant and their own flows |
| Execution Monitor | Executions of all accessible flows (global, tenant, own user flows) | Limited to their tenant |
| Regular User | Only executions they personally triggered | Limited to their own actions |

### Execution Log Visibility Details

1. **Instance Admin**
   - Can view all execution logs across all tenants
   - No restrictions on flow ownership or scope

2. **Tenant Admin**
   - Can view all execution logs within their tenant only
   - Cannot view logs from other tenants
   - Can see logs regardless of who created the flow or triggered the execution

3. **Flow Designer/Editor**
   - Can only view execution logs of flows they personally created
   - Limited to their own tenant
   - Cannot view logs of flows created by other users, even if those flows are tenant or global scope

4. **Execution Monitor**
   - Can view execution logs of all flows they have access to:
     - Global flows
     - Tenant flows  
     - Their own user flows
   - Limited to their own tenant only
   - Cannot view logs of other users' private flows

5. **Regular User**
   - Can only view execution logs of executions they personally triggered
   - Typically through published applications
   - Cannot view logs of executions triggered by other users

## Permission Matrix

### Flow Creation Permissions

| User Role | Can Create | Allowed Scopes |
|-----------|------------|----------------|
| Instance Admin | ✅ Yes | Global, Tenant, User |
| Tenant Admin | ✅ Yes | Tenant, User |
| Flow Designer | ✅ Yes | User |
| Flow Editor | ✅ Yes | User |
| Execution Monitor | ❌ No | N/A |
| Regular User | ❌ No | N/A |

### Flow Editing Permissions

| User Role | Can Edit |
|-----------|----------|
| Instance Admin | All flows |
| Tenant Admin | All flows in tenant |
| Flow Designer | Only own user flows |
| Flow Editor | Only own user flows |
| Execution Monitor | None |
| Regular User | None |

### Flow Deletion Permissions

| User Role | Can Delete |
|-----------|------------|
| Instance Admin | All flows |
| Tenant Admin | All flows in tenant |
| Flow Designer | Only own user flows |
| Flow Editor | Only own user flows |
| Execution Monitor | None |
| Regular User | None |

## Implementation Details

### Backend Implementation

#### 1. Database Schema

```sql
-- Flow table includes flow_scope column
ALTER TABLE flows ADD COLUMN flow_scope VARCHAR(50) DEFAULT 'user';

-- Possible values: 'global', 'tenant', 'user'
```

#### 2. Model Updates

```python
# In models_sqlite.py
class Flow(Base):
    __tablename__ = 'flows'
    
    flow_id = Column(String(36), primary_key=True)
    flow_name = Column(String(255), nullable=False)
    flow_scope = Column(String(50), default='user')  # New field
    created_by = Column(String(36))
    tenant_id = Column(String(36), nullable=False)
    # ... other fields
```

#### 3. API Models

```python
# In api/flows.py
class FlowCreate(BaseModel):
    flow_name: str
    flow_scope: Optional[str] = 'user'  # 'global', 'tenant', 'user'
    # ... other fields

class FlowUpdate(BaseModel):
    flow_scope: Optional[str] = None
    # ... other fields

class FlowResponse(BaseModel):
    flow_scope: str
    # ... other fields
```

### Frontend Implementation

#### 1. Flow Settings UI

The Flow Settings modal includes a scope selector:

```jsx
<select value={flowScope} onChange={(e) => setFlowScope(e.target.value)}>
  <option value="user">User (Private)</option>
  <option value="tenant">Tenant (Team)</option>
  <option value="global">Global (Everyone)</option>
</select>
```

#### 2. State Management

```javascript
const [flowScope, setFlowScope] = useState('user');

// Include in save payload
const flowData = {
  flow_name: flowName,
  flow_scope: flowScope,
  // ... other fields
};
```

## API Endpoints

### Flow Management Endpoints

#### List Flows
**Endpoint**: `GET /api/v1/flows/`

**Visibility Rules**:
| Role | Returns |
|------|---------|
| Instance Admin | All flows across all tenants |
| Tenant Admin | All flows in their tenant |
| Flow Designer/Editor | Global flows, tenant flows, own user flows |
| Execution Monitor | Global flows, tenant flows, own user flows (read-only) |
| Regular User | Empty list (no access) |

#### Get Flow
**Endpoint**: `GET /api/v1/flows/{flow_id}`

**Permission Checks**:
| Role | Can Access |
|------|------------|
| Instance Admin | Any flow |
| Tenant Admin | Any flow in tenant |
| Flow Designer/Editor | Global, tenant, own user flows |
| Execution Monitor | Global, tenant, own user flows |
| Regular User | No access (403 Forbidden) |

#### Create Flow
**Endpoint**: `POST /api/v1/flows/`

**Permission Matrix**:
| Role | Can Create | Allowed Scopes |
|------|------------|----------------|
| Instance Admin | ✅ | global, tenant, user |
| Tenant Admin | ✅ | tenant, user |
| Flow Designer/Editor | ✅ | user only |
| Execution Monitor | ❌ | N/A |
| Regular User | ❌ | N/A |

#### Update Flow
**Endpoint**: `PUT /api/v1/flows/{flow_id}`

**Permission Checks**:
| Role | Can Update |
|------|------------|
| Instance Admin | Any flow |
| Tenant Admin | Any flow in tenant |
| Flow Designer/Editor | Only own flows |
| Execution Monitor | No flows |
| Regular User | No flows |

#### Delete Flow
**Endpoint**: `DELETE /api/v1/flows/{flow_id}`

**Permission Checks**:
| Role | Can Delete |
|------|------------|
| Instance Admin | Any flow |
| Tenant Admin | Any flow in tenant |
| Flow Designer/Editor | Only own flows |
| Execution Monitor | No flows |
| Regular User | No flows |

### Execution Management Endpoints

#### List Executions
**Endpoint**: `GET /api/v1/executions/`

**Visibility Rules**:
| Role | Returns |
|------|---------|
| Instance Admin | All executions across all tenants |
| Tenant Admin | All executions in tenant |
| Flow Designer/Editor | Only executions of flows they created |
| Execution Monitor | Executions of accessible flows (global, tenant, own) |
| Regular User | Only executions they triggered |

#### Get Execution
**Endpoint**: `GET /api/v1/executions/{execution_id}`

**Permission Checks**:
| Role | Can Access |
|------|------------|
| Instance Admin | Any execution |
| Tenant Admin | Any execution in tenant |
| Flow Designer/Editor | Only executions of flows they created |
| Execution Monitor | Executions of accessible flows |
| Regular User | Only executions they triggered |

#### Get Execution Logs
**Endpoint**: `GET /api/v1/executions/{execution_id}/logs`

**Permission Checks**:
| Role | Can Access Logs |
|------|-----------------|
| Instance Admin | All logs |
| Tenant Admin | All logs in tenant |
| Flow Designer/Editor | Only logs of flows they created |
| Execution Monitor | Logs of accessible flows |
| Regular User | Only logs of executions they triggered |

## Frontend UI

### Flow Settings Modal

The Flow Settings modal displays:
1. **Scope Selector**: Dropdown to choose flow scope
2. **Permission Text**: Dynamic text explaining the selected scope
3. **Validation**: Prevents unauthorized scope selection based on user role

### Visual Indicators

Flows in the list view can display badges or icons indicating their scope:
- 🔒 **Private** (User scope)
- 👥 **Team** (Tenant scope)  
- 🌍 **Global** (Global scope)

## Database Schema

### Flows Table

| Column | Type | Description |
|--------|------|-------------|
| flow_id | VARCHAR(36) | Primary key |
| flow_name | VARCHAR(255) | Flow name |
| flow_scope | VARCHAR(50) | Scope: 'global', 'tenant', 'user' |
| created_by | VARCHAR(36) | User ID of creator |
| tenant_id | VARCHAR(36) | Tenant ID |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

## Security Considerations

### Core Security Principles

1. **Tenant Isolation**
   - Strict isolation between tenants is enforced at all levels
   - No cross-tenant data access except for Instance Admins
   - Database queries are automatically filtered by tenant

2. **Default to Least Privilege**
   - New flows default to 'user' scope (most restrictive)
   - New users get the most restrictive role appropriate for their function
   - Permissions must be explicitly granted, never assumed

3. **Scope Elevation Controls**
   - Changing flow scope requires specific role permissions
   - Only Instance Admin can create global flows
   - Only Tenant/Instance Admin can create tenant flows
   - Audit trail for all scope changes

4. **Execution Security**
   - Execution logs are filtered based on flow ownership and trigger source
   - Regular users can only see their own triggered executions
   - Flow designers can only see executions of their own flows

5. **API-Level Enforcement**
   - All permissions are enforced at the API level
   - Frontend UI restrictions are supplemented by backend validation
   - 403 Forbidden returned for unauthorized access attempts

## Migration Guide

For existing flows without a flow_scope:
1. All existing flows default to 'user' scope
2. Tenant admins can bulk update flows to appropriate scopes
3. Migration script available to categorize flows based on usage patterns

## Best Practices

1. **Start with User Scope**: Create flows with user scope during development
2. **Promote Carefully**: Only promote to tenant/global scope after thorough testing
3. **Document Global Flows**: Global flows should have comprehensive documentation
4. **Regular Audits**: Periodically review flow scopes and adjust as needed
5. **Team Collaboration**: Use tenant scope for team workflows and shared processes

## Troubleshooting

### Common Issues and Solutions

#### 1. Flow Not Visible
**Symptoms**: User cannot see a flow they expect to access

**Checklist**:
- Verify user's role using admin panel
- Check flow's scope setting (user/tenant/global)
- For user-scoped flows, verify the `created_by` field matches user ID
- Ensure user is logged into correct tenant
- Check if flow status is active/inactive

**Resolution Steps**:
```sql
-- Check flow details
SELECT flow_id, flow_name, flow_scope, created_by, tenant_id 
FROM flows WHERE flow_name = 'YOUR_FLOW_NAME';
```

#### 2. Cannot Edit Flow
**Symptoms**: Edit button disabled or returns 403 error

**Checklist**:
- Verify user role is not EXECUTION_MONITOR or USER
- For Flow Designer/Editor, check they own the flow
- Verify flow is not locked or in use
- Check tenant permissions

**Common Causes**:
- Execution Monitors have read-only access
- Flow Designers can only edit their own flows
- Regular Users cannot access flow designer

#### 3. Cannot Create Flow with Desired Scope
**Symptoms**: Scope option is disabled or returns permission error

**Permission Requirements**:
| Desired Scope | Required Role |
|--------------|---------------|
| Global | Instance Admin only |
| Tenant | Instance Admin or Tenant Admin |
| User | Any role with flow creation permission |

#### 4. Execution Logs Not Visible
**Symptoms**: User cannot see execution logs

**Visibility Rules**:
- **Regular Users**: Only see executions they triggered
- **Flow Designer**: Only see executions of flows they created
- **Execution Monitor**: See all accessible flow executions in tenant
- **Tenant Admin**: See all executions in tenant

**Debug Query**:
```sql
-- Check execution ownership
SELECT e.execution_id, e.trigger_data, f.created_by, f.flow_scope 
FROM flow_executions e 
JOIN flows f ON e.flow_id = f.flow_id 
WHERE e.execution_id = 'YOUR_EXECUTION_ID';
```

#### 5. Permission Denied Errors

**HTTP 403 Responses**:
- "Regular users can only access published applications" - User role cannot access flows
- "You can only edit your own flows" - Attempting to edit another user's flow
- "Only instance admins can create global flows" - Insufficient permissions for global scope
- "You can only view executions you triggered" - Regular user accessing others' executions

## Future Enhancements

1. **Group-based Permissions**: Allow specific user groups within tenant
2. **Sharing Mechanism**: Share user flows with specific users
3. **Scope Templates**: Predefined scope configurations for common use cases
4. **Approval Workflow**: Require approval for scope elevation
5. **Scope Analytics**: Track usage patterns across different scopes

## Summary

The Flow Scope and Visibility system provides comprehensive access control for IOFlow:

### Key Takeaways

1. **Role-Based Access**: Six distinct roles with clearly defined permissions
2. **Scope-Based Visibility**: Three scope levels (user, tenant, global) control flow visibility
3. **Tenant Isolation**: Strict boundary enforcement between tenants
4. **Ownership Matters**: Flow creators maintain control over their user-scoped flows
5. **Execution Tracking**: Execution visibility based on both flow ownership and trigger source

### Quick Reference

| Role | Flow Access | Can Create | Can Edit | Execution Logs |
|------|------------|------------|----------|----------------|
| Instance Admin | All | All scopes | All | All |
| Tenant Admin | All in tenant | Tenant, User | All in tenant | All in tenant |
| Flow Designer | Global, Tenant, Own | User only | Own only | Own flows only |
| Flow Editor | Global, Tenant, Own | User only | Own only | Own flows only |
| Execution Monitor | Global, Tenant, Own | No | No | Accessible flows |
| Regular User | None | No | No | Own executions |

---

*Last Updated: 2025-08-28*
*Version: 1.1.0*
*Changes: Updated execution visibility rules to correctly reflect role-based access patterns*