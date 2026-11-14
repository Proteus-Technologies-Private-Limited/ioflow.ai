# Flow Designer V2 Agent - User Guide

## Overview

Flow Designer V2 is now available as a standalone agent in the IOFlow Assistant that you can select and use directly.

## How to Access

1. Open **IOFlow Assistant**
2. Look for **"Flow Designer V2"** in the agent list
3. Select it to start using the optimized flow builder

## Why Use Flow Designer V2?

### Performance Benefits
- 🚀 **99.7% token reduction** - Much more efficient
- 💰 **Works with cheaper models** - Gemini Flash, GPT-3.5+ (not just GPT-4)
- ⚡ **75% faster** - Cached operations and optimized workflows
- 💾 **Session-based** - Can resume if interrupted

### Features
- ✅ **Incremental building** - See progress step-by-step
- ✅ **Checkpoints** - Save progress and restore if needed
- ✅ **Recovery** - Resume from failures automatically
- ✅ **Progress tracking** - Know exactly where you are
- ✅ **Token optimized** - Better for complex flows

## When to Use V2 vs V1

### Use V2 For:
- ✅ Complex flows (3+ nodes)
- ✅ Large flows that need many steps
- ✅ When you want checkpoints/recovery
- ✅ When using mid-tier models to save money
- ✅ When you need to see progress
- ✅ Token-sensitive applications

### Use V1 (flow_designer) For:
- ✅ Very simple 1-2 node flows
- ✅ Quick prototypes
- ✅ When you need immediate complete result
- ✅ When using high-end models (GPT-4, Gemini Pro)

## Example Conversations

### Example 1: Basic Flow

**You:**
```
Create a flow that takes user input and sends it to Google Gemini AI
```

**Flow Designer V2 will:**
1. Create a session
2. Add manual trigger with input field
3. Find Google Gemini application
4. Add Generate Content action
5. Connect trigger to action
6. Complete and return flow JSON

**You'll see each step:**
```
✅ Session created: abc-123
✅ Trigger added: trigger_1
✅ Action added: action_1 (Gemini Generate Content)
✅ Connected: trigger_1 → action_1
✅ Flow completed!
```

### Example 2: Flow with Checkpoints

**You:**
```
Create a complex flow with multiple steps. Add checkpoints so we can recover if something fails.
```

**Flow Designer V2 will:**
1. Create session
2. Add trigger → **Checkpoint 1**
3. Add first action → **Checkpoint 2**
4. Add second action → **Checkpoint 3**
5. Connect nodes
6. Complete with full recovery capability

### Example 3: Resume a Session

**You:**
```
Resume session abc-123 and add another action node
```

**Flow Designer V2 will:**
1. Resume the session
2. Show current state (nodes, edges, checkpoints)
3. Add the requested node
4. Connect it appropriately
5. Can complete or continue building

### Example 4: Multi-Step Complex Flow

**You:**
```
Create a flow that:
1. Takes a CSV file as input
2. Parses it
3. For each row, calls Google Gemini
4. Collects results
5. Saves to Google Sheets
```

**Flow Designer V2 will:**
Build this incrementally with checkpoints at each major step, making it easy to see progress and recover from any issues.

## How V2 Works (Behind the Scenes)

### Session-Based Architecture
```
1. CREATE SESSION
   ↓
2. ADD NODES (one at a time)
   ↓
3. CONNECT NODES
   ↓
4. CREATE CHECKPOINTS (optional)
   ↓
5. COMPLETE SESSION
   ↓
6. GET FLOW JSON
```

### What You See
```
Creating session...
✅ Session: abc-123

Adding trigger node...
✅ Trigger: trigger_1

Finding Google Gemini...
✅ Found app: gemini-app-id

Adding Generate Content action...
✅ Action: action_1

Connecting nodes...
✅ Edge: e1 (trigger_1 → action_1)

Creating checkpoint...
✅ Checkpoint: cp_1

Completing flow...
✅ Flow complete! [JSON follows]
```

## Advanced Features

### Checkpoints
```
You: "Create a checkpoint here"
V2: ✅ Checkpoint created: cp_2

[later, if something goes wrong]
You: "Restore from checkpoint cp_2"
V2: ✅ Restored to checkpoint cp_2
```

### Resume Sessions
```
You: "What's the status of session abc-123?"
V2: Shows:
- Nodes: 3
- Edges: 2
- Checkpoints: 2
- Status: active

You: "Add another node to that session"
V2: Resumes and adds the node
```

### Parameter Mapping
V2 automatically handles variable references:
```javascript
// From trigger input
{{input.user_question}}

// From previous node
{{node_outputs.action_1.response}}

// Static values
"gemini-2.5-flash"
```

## Tips for Best Results

### 1. Be Specific About Requirements
**Good:**
```
Create a flow with a manual trigger that has fields:
- "name" (string, required)
- "email" (string, required)
Then send this data to Google Sheets
```

**Less Good:**
```
Make a flow for Google Sheets
```

### 2. Ask for Checkpoints on Complex Flows
```
Create a complex flow with 5 steps. Add a checkpoint after each major step.
```

### 3. Request Progress Updates
```
Show me the progress as you build this flow
```

### 4. Leverage Resume Capability
If something fails:
```
Resume the last session and fix the issue
```

## Comparison Table

| Feature | V1 (flow_designer) | V2 (flow_designer_v2) |
|---------|-------------------|----------------------|
| Token Usage | 57,308 | 166 (99.7% less) |
| Speed | 2-3 seconds | < 500ms |
| Model Support | GPT-4, Gemini Pro | GPT-3.5+, Gemini Flash+ |
| Checkpoints | ❌ | ✅ |
| Resume | ❌ | ✅ |
| Progress Tracking | ❌ | ✅ |
| Incremental Build | ❌ | ✅ |
| Cost per Flow | Higher | 10-20x cheaper |
| Best For | Simple flows | Complex flows |

## Troubleshooting

### "Session not found"
**Problem:** Session expired (default 30 min TTL)
**Solution:** Create a new session or ask to increase TTL

### "Can't connect nodes"
**Problem:** Node IDs not found
**Solution:** V2 will check session state and use correct IDs

### "Agent not appearing"
**Problem:** Backend needs restart
**Solution:** Restart backend server:
```bash
cd backend
./start_backend.sh
```

## FAQs

**Q: Will my existing flows break?**
A: No. V2 only affects how NEW flows are created. Existing flows work unchanged.

**Q: Can I switch between V1 and V2?**
A: Yes! They coexist. Just select the agent you want to use.

**Q: Is V2 harder to use?**
A: No. From a user perspective, you just talk to it normally. V2 handles the complexity.

**Q: What if I need to modify an existing flow?**
A: Both V1 and V2 can modify flows. V2 does it with sessions and checkpoints.

**Q: Does V2 work with all applications?**
A: Yes! V2 works with all IOFlow applications and services.

**Q: How do I know which agent I'm using?**
A: Look at the agent selector in the assistant. It will show "Flow Designer V2" when selected.

## Next Steps

1. **Try it now:** Select Flow Designer V2 in the assistant
2. **Start simple:** Create a basic 2-node flow
3. **Go complex:** Try a multi-step flow with checkpoints
4. **Compare:** Try the same flow with V1 and V2 to see the difference

## Support

- **Documentation:** See `/docs/FLOW_DESIGNER_V2_*.md`
- **Examples:** Ask V2 directly: "Show me an example flow"
- **Issues:** Report on GitHub

---

**Flow Designer V2** - Making flow creation accessible to everyone, on any model! 🚀