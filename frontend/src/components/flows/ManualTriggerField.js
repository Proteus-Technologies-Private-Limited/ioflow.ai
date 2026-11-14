import React from 'react';
import StableParameterInput from '../flow/StableParameterInput';

const ManualTriggerField = React.memo(({ variable, value, onChange }) => {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {variable.displayName || variable.name}
        {variable.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <StableParameterInput
        variable={variable}
        value={value}
        onChange={onChange}
      />
      {variable.description && (
        <p className="mt-1 text-xs text-gray-500">{variable.description}</p>
      )}
    </div>
  );
});

ManualTriggerField.displayName = 'ManualTriggerField';

export default ManualTriggerField;