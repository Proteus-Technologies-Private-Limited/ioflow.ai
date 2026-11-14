---
description: List all seed applications available in IOFlow. Optionally filter by name.
---

# List IOFlow Applications

List all available seed applications from IOFlow.

If the user provided arguments ("$ARGUMENTS"), use them as a filter with `list_tenant_seed_applications()` (your tenant's own), `list_seed_applications()` (global catalog) or `list_applications(app_names="$ARGUMENTS")`.

If no arguments provided, call `list_tenant_seed_applications()` and `list_seed_applications()` and show both (mark which are your tenant's own).

Display the results in a clear table format showing: app key, app name, category, version, and number of services.
