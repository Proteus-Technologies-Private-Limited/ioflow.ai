# Flow Tutorial Improvements

## Overview
Fixed the incorrect on-screen guidance for flow creation and added multiple ways for users to invoke the tutorial.

## Issues Fixed

### 1. Incorrect Tutorial Steps
**Problem**: 
- Step 1 asked users to create a trigger node, but it's already created by default
- Tutorial only showed 2 steps and stopped
- Referenced a non-existent "Test/Run" button

**Solution**:
- Updated tutorial to acknowledge the pre-created trigger node
- Expanded to 5 comprehensive steps covering the complete flow
- Changed final step to point to the actual Save button

### 2. No Way to Manually Invoke Tutorial
**Problem**:
- Tutorial only ran automatically for first-time users
- No way to re-run tutorial after completion
- Users couldn't get help when needed

**Solution**:
- Added "Show Tutorial" option in the settings menu (⋮)
- Added keyboard shortcut (?) to invoke tutorial
- Tutorial can now be run multiple times

## New Tutorial Flow (5 Steps)

### Step 1: Define Your Trigger
- **Target**: `.react-flow__node-trigger`
- **Content**: Acknowledges trigger node already exists, explains configuration options
- **Action**: User clicks on trigger node to configure it

### Step 2: Select Action and Choose App/Service
- **Target**: `.flow-add-node-button`
- **Content**: Guides user to add an Action node
- **Action**: User clicks "+ Add Node" button

### Step 3: Configure Your Action
- **Target**: `.flow-canvas`
- **Content**: Lists steps to configure action (select app, choose service, set parameters)
- **Action**: User clicks on action node

### Step 4: Map Service Parameters
- **Target**: `.parameter-input-container`
- **Content**: Explains data mapping using the + button
- **Action**: User maps data between nodes

### Step 5: Save Your Flow
- **Target**: `.bg-blue-600` (Save button)
- **Content**: Explains saving and next steps
- **Action**: User clicks Save button

## Ways to Invoke Tutorial

### 1. Automatic (First-time users)
- Triggers automatically for new flows when `localStorage.getItem('ioflow_flow_tutorial_completed')` is not set
- 1-second delay to ensure UI is ready

### 2. Settings Menu
- Click the three-dot menu (⋮) in the top-right corner
- Select "Show Tutorial" (with question mark icon)

### 3. Keyboard Shortcut
- Press `?` key (Shift + /) anywhere in Flow Designer
- Disabled when typing in input/textarea fields

## Files Modified

1. **frontend/src/components/onboarding/FlowTutorial.js**
   - Updated all 5 tutorial steps with correct guidance
   - Fixed CSS selectors to target actual elements
   - Improved step descriptions and explanations

2. **frontend/src/pages/FlowDesigner.js**
   - Added `QuestionMarkCircleIcon` import
   - Added `startTutorial()` function
   - Added "Show Tutorial" menu item in settings dropdown
   - Added keyboard shortcut handler (? key)
   - Tutorial state management (`runTutorial`, `handleTutorialComplete`)

## Technical Details

### State Management
```javascript
const [runTutorial, setRunTutorial] = useState(false);

const startTutorial = () => {
  setRunTutorial(true);
};

const handleTutorialComplete = () => {
  setRunTutorial(false);
  localStorage.setItem('ioflow_flow_tutorial_completed', 'true');
};
```

### Keyboard Shortcut Handler
```javascript
useEffect(() => {
  const handleKeyPress = (e) => {
    if (e.key === '?' && !e.ctrlKey && !e.altKey && !e.metaKey) {
      const target = e.target;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return;
      }
      e.preventDefault();
      startTutorial();
    }
  };
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

## Testing

See `test-script/test_tutorial_invocation.md` for detailed testing instructions.

## User Benefits

1. **Accurate Guidance**: Tutorial now correctly reflects the actual flow creation process
2. **Always Available**: Users can access tutorial help anytime via menu or keyboard
3. **Complete Coverage**: All essential steps are covered (trigger → action → parameters → save)
4. **Better UX**: Clear step labels, detailed explanations, and helpful tips
5. **Quick Access**: Keyboard shortcut (?) for power users

## Future Enhancements

Potential improvements for consideration:
- Add context-sensitive help (different tutorials for different scenarios)
- Add video tutorials or animated GIFs
- Add interactive tooltips for specific UI elements
- Add a help center with searchable documentation
- Track tutorial completion per feature (not just one global flag)
