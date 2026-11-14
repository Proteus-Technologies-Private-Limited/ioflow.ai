# Manual Trigger Test Flows

This directory contains test flows specifically designed to test the ManualTriggerModal component with JSON-type variables.

## Test Flows

### 1. manual-trigger-json-test.json
- **Purpose**: Basic test flow with various data types including JSON
- **Variables**:
  - `userName` (string): Regular text input
  - `userAge` (number): Number input with validation
  - `userPreferences` (json): Simple JSON object
  - `complexData` (json): Deeply nested JSON structure
  - `apiConfig` (json): API configuration object
  - `isActive` (boolean): Checkbox input
  - `notes` (string): Textarea input

### 2. manual-trigger-json-arrays.json
- **Purpose**: Test JSON arrays and different array structures
- **Variables**:
  - `productList` (json): Array of objects
  - `tags` (json): Simple string array
  - `matrixData` (json): 2D array/matrix
  - `emptyObject` (json): Empty object test
  - `nullableJson` (json): Nullable JSON test

### 3. manual-trigger-json-validation.json
- **Purpose**: Edge cases and validation testing
- **Variables**:
  - `simpleText` (string): Control variable
  - `jsonWithSpecialChars` (json): Special characters and escaping
  - `deeplyNested` (json): Deep nesting levels
  - `mixedTypes` (json): Mixed data types in JSON
  - `largeJson` (json): Larger JSON structure
  - `invalidJsonTest` (json): Invalid JSON for error handling

## Testing Instructions

1. Load any of these flows in the Flow Designer
2. Click the "Run" or "Trigger" button to open the ManualTriggerModal
3. Verify that:
   - JSON-type variables show individual JSON editors (textarea with JSON validation)
   - Form mode shows proper inputs for each variable type
   - JSON mode allows editing all variables as a single JSON object
   - Default values are properly loaded
   - JSON validation works correctly
   - Invalid JSON shows appropriate error messages

## Expected Behavior

When `dataType: "json"` or `uiControl: "code"` is set for a variable:
- A dedicated JSON editor (textarea) should appear for that variable
- The editor should validate JSON syntax
- Pretty printing should be applied (2-space indentation)
- Invalid JSON should be caught and shown as an error
- Valid JSON should be parsed and stored as an object, not a string

## Notes

- These test flows use the manual trigger type with `manual_variables` configuration
- Each variable with `dataType: "json"` should render its own JSON editor in form mode
- The JSON mode should still work, showing all variables as a single JSON object