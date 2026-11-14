# Role-Based Access Control (RBAC) Implementation

## Overview

This document describes the enhanced role-based access control system implemented in IOFlow. The system provides granular permission management with multi-tenancy support.

## User Roles

### 1. INSTANCE_ADMIN
- **Description**: System-wide administrator with full access
- **Key Permissions**:
  - Access to all tenants and their data
  - Create and manage tenants
  - Manage global applications
  - Assign any role to users
  - Access billing and pricing for all tenants
  - Manage seed applications
- **Assignment**: First user registered in the system automatically becomes INSTANCE_ADMIN

### 2. TENANT_ADMIN
- **Description**: Administrator for a specific tenant
- **Key Permissions**:
  - Full access within their tenant
  - Manage users within their tenant (except other tenant admins)
  - Create and manage tenant-specific applications
  - View and manage flows within their tenant
  - Access billing for their tenant
- **Assignment**: Can be assigned by INSTANCE_ADMIN or promoted by existing TENANT_ADMIN

### 3. APPLICATION_PROVIDER
- **Description**: User who can create and manage applications
- **Key Permissions**:
  - Create and edit applications for their tenant
  - Set pricing for their applications
  - View application usage metrics
  - Read-only access to flows
- **Assignment**: Assigned by TENANT_ADMIN or INSTANCE_ADMIN

### 4. FLOW_DESIGNER
- **Description**: User who can design and manage flows
- **Key Permissions**:
  - Create, edit, and delete flows
  - Execute flows
  - View execution logs
  - Read applications
- **Assignment**: Default role for new users (after activation)

### 5. EXECUTION_MONITOR
- **Description**: User with limited access to execute and monitor flows
- **Key Permissions**:
  - Execute existing flows
  - View execution logs
  - Read-only access to flows and applications
- **Assignment**: Assigned by TENANT_ADMIN or INSTANCE_ADMIN

## Permission Matrix

| Action | INSTANCE_ADMIN | TENANT_ADMIN | APPLICATION_PROVIDER | FLOW_DESIGNER | EXECUTION_MONITOR |
|--------|----------------|--------------|---------------------|---------------|-------------------|
| **Tenants** |
| Create Tenant | ✅ | ❌ | ❌ | ❌ | ❌ |
| Edit Tenant | ✅ | ✅* | ❌ | ❌ | ❌ |
| Delete Tenant | ✅ | ❌ | ❌ | ❌ | ❌ |
| View All Tenants | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Users** |
| Create User | ✅ | ✅* | ❌ | ❌ | ❌ |
| Edit User | ✅ | ✅* | ❌ | ❌ | ❌ |
| Delete User | ✅ | ✅* | ❌ | ❌ | ❌ |
| Change Roles | ✅ | ✅** | ❌ | ❌ | ❌ |
| **Applications** |
| Create Global App | ✅ | ❌ | ❌ | ❌ | ❌ |
| Create Tenant App | ✅ | ✅ | ✅ | ❌ | ❌ |
| Edit Global App | ✅ | ❌ | ❌ | ❌ | ❌ |
| Edit Tenant App | ✅ | ✅ | ✅*** | ❌ | ❌ |
| Delete App | ✅ | ✅* | ✅*** | ❌ | ❌ |
| **Flows** |
| Create Flow | ✅ | ✅ | ❌ | ✅ | ❌ |
| Edit Flow | ✅ | ✅ | ❌ | ✅ | ❌ |
| Delete Flow | ✅ | ✅ | ❌ | ✅ | ❌ |
| Execute Flow | ✅ | ✅ | ✅ | ✅ | ✅ |
| View Logs | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Billing** |
| View All Billing | ✅ | ❌ | ❌ | ❌ | ❌ |
| View Tenant Billing | ✅ | ✅ | ✅ | ❌ | ❌ |
| Manage Pricing | ✅ | ❌ | ✅*** | ❌ | ❌ |

*Within their tenant only
**Cannot assign INSTANCE_ADMIN role or modify other TENANT_ADMINs
***Only for applications they created

## User Registration Flow

### First User Registration
1. No tenant validation required
2. User provides organization name
3. System creates:
   - User with INSTANCE_ADMIN role
   - 'proteus-technologies' tenant
   - User is automatically activated

### Subsequent User Registration
1. User must provide valid tenant_id
2. System validates tenant exists
3. User created with:
   - FLOW_DESIGNER role (default)
   - Inactive status
   - Requires activation by TENANT_ADMIN or INSTANCE_ADMIN

## API Endpoints

### Tenant Management
- `GET /api/v1/tenants` - List tenants
- `POST /api/v1/tenants` - Create tenant (INSTANCE_ADMIN only)
- `GET /api/v1/tenants/{id}` - Get tenant details
- `PUT /api/v1/tenants/{id}` - Update tenant
- `DELETE /api/v1/tenants/{id}` - Delete tenant (INSTANCE_ADMIN only)
- `GET /api/v1/tenants/{id}/users` - List tenant users
- `PUT /api/v1/tenants/{id}/users/{user_id}/activate` - Activate/deactivate user

### User Management
- `GET /api/v1/users` - List users (filtered by permissions)
- `GET /api/v1/users/me` - Get current user info
- `GET /api/v1/users/{id}` - Get user details
- `PUT /api/v1/users/{id}` - Update user
- `PUT /api/v1/users/{id}/role` - Change user role
- `DELETE /api/v1/users/{id}` - Delete user

## Middleware and Permission Checking

### Permission Decorators

```python
from middleware.permissions import require_permission, require_role

@router.post("/global-app")
@require_role([UserRole.INSTANCE_ADMIN])
async def create_global_app(...):
    pass

@router.put("/flows/{id}")
@require_permission("flows", "update")
async def update_flow(...):
    pass
```

### Tenant Isolation

```python
from middleware.permissions import require_tenant_access

@router.get("/tenant/{tenant_id}/data")
@require_tenant_access
async def get_tenant_data(...):
    pass
```

## Audit Logging

All permission-related actions are logged:
- User role changes
- Permission denials
- Tenant access attempts
- User management actions

Audit logs include:
- Timestamp
- User information
- Action performed
- Resource affected
- Success/failure status
- IP address and user agent

## Migration Guide

### For Existing Installations

1. Run the role migration script:
   ```bash
   python migrations/update_user_roles.py
   ```

2. Create audit logs table:
   ```bash
   python migrations/create_audit_logs_table.py
   ```

### Role Mapping
- `ADMIN` → `INSTANCE_ADMIN`
- `PROJECT_OWNER` → `FLOW_DESIGNER`
- `EXECUTION_MONITOR` → Unchanged
- `APPLICATION_PROVIDER` → Unchanged

### Post-Migration Steps
1. Review and assign TENANT_ADMIN roles as needed
2. Verify first user has INSTANCE_ADMIN role
3. Ensure 'proteus-technologies' tenant exists
4. Activate users as required

## Security Considerations

1. **Role Hierarchy**: INSTANCE_ADMIN > TENANT_ADMIN > Other roles
2. **Tenant Isolation**: Strictly enforced at API level
3. **Audit Trail**: All sensitive actions logged
4. **Password Policy**: Enforced during registration
5. **Session Management**: JWT tokens with expiration

## Best Practices

1. **Principle of Least Privilege**: Assign minimum required role
2. **Regular Audits**: Review user roles periodically
3. **Tenant Admins**: Have at least one per tenant
4. **Instance Admin**: Limit to trusted personnel
5. **Monitoring**: Regular review of audit logs