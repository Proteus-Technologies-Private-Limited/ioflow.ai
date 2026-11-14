import React, { useState } from 'react';
import IsolatedField from '../../flow/IsolatedParameterInput';
import ApiDropdown from './ApiDropdown';
import { validateAllFields } from './ValidationEngine';
import PrerequisiteCard from '../../microsaas/PrerequisiteCard';
import FollowupCard from '../../microsaas/FollowupCard';

export default function TriggerFormSection({
  config,
  manualVariables,
  formData,
  onFieldChange,
  onSubmit,
  executing,
  slug,
  previewMode,
  // Related flows
  relatedFlows,
  prerequisiteStatuses,
  prerequisiteOutputs,
  onRunPrerequisite,
  onSkipPrerequisite,
  allPrerequisitesComplete,
  followupStatuses,
  onRunFollowup,
  finalResult,
  executionStatus,
}) {
  const [fieldErrors, setFieldErrors] = useState({});

  const handleSubmit = (e) => {
    e.preventDefault();
    if (previewMode) return;

    // Run validations
    const { isValid, fieldErrors: errors } = validateAllFields(formData, config.validations);
    setFieldErrors(errors);
    if (!isValid) return;

    onSubmit(e);
  };

  const getFieldOverride = (fieldName) => {
    return config.field_overrides?.[fieldName] || {};
  };

  const isApiDropdown = (fieldName) => {
    return !!config.api_dropdowns?.[fieldName];
  };

  const layoutClass = config.layout === 'two_column'
    ? 'grid grid-cols-1 md:grid-cols-2 gap-4'
    : 'space-y-4';

  const prerequisites = relatedFlows?.prerequisites || [];
  const followups = relatedFlows?.followups || [];
  const showPrereqs = config.showPrerequisites !== false && prerequisites.length > 0;
  const showFollowupsSection = config.showFollowups !== false && followups.length > 0 && executionStatus === 'completed';

  return (
    <div className="py-6">
      {config.title && (
        <h2 className="text-xl font-semibold text-gray-900 mb-2">{config.title}</h2>
      )}
      {config.description && (
        <p className="text-gray-600 mb-6">{config.description}</p>
      )}

      {/* Prerequisites */}
      {showPrereqs && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Prerequisites</h3>
          <div className="space-y-3">
            {prerequisites.map((prereq) => (
              <PrerequisiteCard
                key={prereq.frontend_app_id}
                prerequisite={prereq}
                status={prerequisiteStatuses?.[prereq.frontend_app_id] || 'not_run'}
                onRun={onRunPrerequisite}
                onSkip={onSkipPrerequisite}
                output={prerequisiteOutputs?.[prereq.frontend_app_id]}
              />
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className={`bg-white rounded-lg border border-gray-200 p-6 ${layoutClass}`}>
          {(manualVariables || []).map((variable) => {
            const override = getFieldOverride(variable.name);
            const enhancedVariable = {
              ...variable,
              ...(override.label && { name: variable.name, displayLabel: override.label }),
            };

            if (isApiDropdown(variable.name)) {
              const dropdownConfig = config.api_dropdowns[variable.name];
              return (
                <div key={variable.id || variable.name}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {override.label || variable.name}
                    {config.validations?.[variable.name]?.required && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </label>
                  {override.helpText && (
                    <p className="text-xs text-gray-500 mb-1">{override.helpText}</p>
                  )}
                  <ApiDropdown
                    slug={slug}
                    config={dropdownConfig}
                    value={formData[variable.name]}
                    onChange={(val) => onFieldChange(variable.name, val)}
                    formData={formData}
                    fieldName={variable.name}
                    disabled={previewMode || executing}
                  />
                  {fieldErrors[variable.name] && (
                    <p className="mt-1 text-xs text-red-500">{fieldErrors[variable.name][0]}</p>
                  )}
                </div>
              );
            }

            return (
              <div key={variable.id || variable.name}>
                {override.label && (
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {override.label}
                    {config.validations?.[variable.name]?.required && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </label>
                )}
                {override.helpText && (
                  <p className="text-xs text-gray-500 mb-1">{override.helpText}</p>
                )}
                <IsolatedField
                  variable={{
                    ...enhancedVariable,
                    ...(override.placeholder && {
                      defaultValue: formData[variable.name] ?? override.placeholder,
                    }),
                  }}
                  value={formData[variable.name]}
                  onChange={onFieldChange}
                />
                {fieldErrors[variable.name] && (
                  <p className="mt-1 text-xs text-red-500">{fieldErrors[variable.name][0]}</p>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-6 flex justify-center">
          <button
            type="submit"
            disabled={previewMode || executing || (!allPrerequisitesComplete)}
            className="px-8 py-3 bg-gradient-primary text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {executing ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Processing...
              </span>
            ) : (
              config.submitButtonText || 'Submit'
            )}
          </button>
        </div>
      </form>

      {/* Follow-ups */}
      {showFollowupsSection && (
        <div className="mt-8">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Follow-up Actions</h3>
          <div className="space-y-3">
            {followups.map((followup) => (
              <FollowupCard
                key={followup.frontend_app_id}
                followup={followup}
                status={followupStatuses?.[followup.frontend_app_id] || 'available'}
                onRun={onRunFollowup}
                mainFlowResult={finalResult}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
