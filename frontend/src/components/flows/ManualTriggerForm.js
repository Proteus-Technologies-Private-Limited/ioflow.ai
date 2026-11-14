import React, { useState, useCallback, useEffect, useRef } from 'react';
import ManualTriggerField from './ManualTriggerField';

const ManualTriggerForm = React.memo(({ manualVariables, onFormDataChange }) => {
  const formDataRef = useRef({});
  const [, forceUpdate] = useState({});

  // Initialize form data with default values only once
  useEffect(() => {
    if (Array.isArray(manualVariables) && manualVariables.length > 0) {
      const initialData = {};
      manualVariables.forEach(variable => {
        // Parse default values for JSON/array types
        if (variable.dataType === 'json' || variable.dataType === 'array') {
          try {
            initialData[variable.name] = variable.defaultValue ? JSON.parse(variable.defaultValue) : (variable.dataType === 'array' ? [] : {});
          } catch {
            initialData[variable.name] = variable.defaultValue || '';
          }
        } else {
          initialData[variable.name] = variable.defaultValue || '';
        }
      });
      formDataRef.current = initialData;
      onFormDataChange(initialData);
      forceUpdate({});
    }
  }, []); // Empty deps to run only once

  const handleFieldChange = useCallback((name, value) => {
    formDataRef.current[name] = value;
    onFormDataChange({ ...formDataRef.current });
  }, [onFormDataChange]);

  return (
    <div className="space-y-4">
      {Array.isArray(manualVariables) && manualVariables.map((variable) => (
        <ManualTriggerField
          key={variable.id || variable.name}
          variable={variable}
          value={formDataRef.current[variable.name] || ''}
          onChange={handleFieldChange}
        />
      ))}
    </div>
  );
});

ManualTriggerForm.displayName = 'ManualTriggerForm';

export default ManualTriggerForm;