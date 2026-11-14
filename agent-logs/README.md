# Agent Validation Logs

This directory contains validation attempt logs from the Flow Designer Agent.

## Structure

```
agent-logs/
└── {user_email}/
    ├── validation_latest.log          # Most recent validation (overwritten each time)
    └── validation_YYYYMMDD_HHMMSS.log # Timestamped history of all validations
```

## Purpose

These logs help debug issues when the agent validates flow JSON:
- Shows what parameters were passed to `validate_flow_json()`
- Captures validation results, errors, and warnings
- Maintains history of all validation attempts per user
- The `validation_latest.log` is always the most recent attempt (convenient for quick checks)

## Privacy

These logs are user-specific and contain flow JSON snippets. They are ignored by git (see `.gitignore`).

## Usage

After running a flow validation in the UI:
1. Navigate to `agent-logs/{your_email}/`
2. Check `validation_latest.log` for the most recent attempt
3. Review timestamped logs for validation history
