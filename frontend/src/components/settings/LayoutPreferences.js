import React from 'react';
import { useLayout, LAYOUT_MODES } from '../../contexts/LayoutContext';
import { RadioGroup } from '@headlessui/react';
import { CheckCircleIcon, Squares2X2Icon, ViewColumnsIcon } from '@heroicons/react/24/outline';

const layoutOptions = [
  {
    id: LAYOUT_MODES.ASSISTANT_PANEL,
    name: 'Assistant Panel Layout',
    description: 'Sidebar with integrated assistant panel for quick access',
    icon: ViewColumnsIcon,
  },
  {
    id: LAYOUT_MODES.CLASSIC,
    name: 'Classic Layout',
    description: 'Traditional sidebar with floating assistant button',
    icon: Squares2X2Icon,
  },
];

function classNames(...classes) {
  return classes.filter(Boolean).join(' ');
}

function LayoutPreferences() {
  const { layoutMode, setLayoutMode } = useLayout();

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900">Layout Preferences</h3>
        <p className="mt-1 text-sm text-gray-600">
          Choose how you want the application interface to be displayed
        </p>
      </div>

      <RadioGroup value={layoutMode} onChange={setLayoutMode}>
        <RadioGroup.Label className="sr-only">Choose a layout</RadioGroup.Label>
        <div className="space-y-4">
          {layoutOptions.map((option) => (
            <RadioGroup.Option
              key={option.id}
              value={option.id}
              className={({ active, checked }) =>
                classNames(
                  active ? 'ring-2 ring-offset-2 ring-primary-500' : '',
                  checked ? 'border-primary-600 bg-primary-50' : 'border-gray-300',
                  'relative flex cursor-pointer rounded-lg border bg-white px-6 py-4 shadow-sm hover:border-primary-400 focus:outline-none'
                )
              }
            >
              {({ checked }) => (
                <>
                  <div className="flex items-center">
                    <div className="flex-shrink-0">
                      <option.icon
                        className={classNames(
                          checked ? 'text-primary-600' : 'text-gray-400',
                          'h-6 w-6'
                        )}
                        aria-hidden="true"
                      />
                    </div>
                    <div className="ml-4">
                      <RadioGroup.Label
                        as="p"
                        className={classNames(
                          checked ? 'text-primary-900' : 'text-gray-900',
                          'text-base font-medium'
                        )}
                      >
                        {option.name}
                      </RadioGroup.Label>
                      <RadioGroup.Description
                        as="span"
                        className={classNames(
                          checked ? 'text-primary-700' : 'text-gray-500',
                          'text-sm'
                        )}
                      >
                        {option.description}
                      </RadioGroup.Description>
                    </div>
                  </div>
                  {checked && (
                    <div className="absolute right-4 top-1/2 -translate-y-1/2">
                      <CheckCircleIcon className="h-5 w-5 text-primary-600" aria-hidden="true" />
                    </div>
                  )}
                </>
              )}
            </RadioGroup.Option>
          ))}
        </div>
      </RadioGroup>

      <div className="mt-6 rounded-lg bg-blue-50 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg
              className="h-5 w-5 text-blue-400"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">Layout Tips</h3>
            <div className="mt-2 text-sm text-blue-700">
              <ul className="list-disc space-y-1 pl-5">
                <li>
                  <strong>Assistant Panel Layout:</strong> Best for users who frequently use the assistant. The sidebar can be expanded by hovering over it.
                </li>
                <li>
                  <strong>Classic Layout:</strong> Traditional layout with more screen space for content. Assistant opens as a modal when needed.
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LayoutPreferences;