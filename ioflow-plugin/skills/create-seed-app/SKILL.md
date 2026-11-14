---
description: Create a new seed application in IOFlow. Provide the application name and description as arguments.
---

# Create Seed Application

Create a new seed application in IOFlow based on the user's requirements: "$ARGUMENTS"

Delegate to the `seed-app-designer` agent, which follows this workflow:

1. Read the format once each: `get_seed_application_guide()`, `get_service_guide()`, and `get_event_guide()` if the application can trigger flows
2. Check for an existing one: `list_tenant_seed_applications()` (your tenant) and `list_seed_applications()` (global catalog, a good structural reference)
3. Author the FULL seed JSON (`key`, `application`, `services`, `events`)
4. `validate_tenant_seed_application(seed)` until clean
5. `save_tenant_seed_application(seed, install=true)` — saves and installs it for your tenant
6. Show a summary of what was created

Important:
- Your tenant's catalog is the default; the global catalog is instance-admin only
- Use `parameter_schema` NOT `input_schema` for service arguments
- Never put credentials in the seed JSON — they are entered when the application is connected
- Always increment the version when editing an existing application
