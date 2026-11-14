import React, { useState, useEffect } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { XMarkIcon, DocumentDuplicateIcon } from '@heroicons/react/24/outline';
import { showSuccessToast } from '../../utils/customToast';

const JsonEditorModal = ({ open, onClose, application, onSave, loading = false }) => {
  const [jsonContent, setJsonContent] = useState('');
  const [error, setError] = useState(null);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (application && open) {
      // Format the JSON with proper indentation
      try {
        const formatted = JSON.stringify(application.json_data || application, null, 2);
        setJsonContent(formatted);
        setIsDirty(false);
        setError(null);
      } catch (err) {
        setError('Failed to format JSON');
      }
    }
  }, [application, open]);

  const handleJsonChange = (e) => {
    setJsonContent(e.target.value);
    setIsDirty(true);
    setError(null);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonContent);
    showSuccessToast('JSON copied to clipboard');
  };

  const validateJson = () => {
    try {
      JSON.parse(jsonContent);
      return true;
    } catch (err) {
      setError(`Invalid JSON: ${err.message}`);
      return false;
    }
  };

  const handleSave = () => {
    if (!validateJson()) return;

    try {
      const parsedJson = JSON.parse(jsonContent);
      onSave(parsedJson);
    } catch (err) {
      setError(`Failed to parse JSON: ${err.message}`);
    }
  };

  const handleFormat = () => {
    if (!validateJson()) return;

    try {
      const parsed = JSON.parse(jsonContent);
      setJsonContent(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (err) {
      setError(`Failed to format JSON: ${err.message}`);
    }
  };

  if (!application) return null;

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-4xl">
                <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <div className="sm:flex sm:items-start">
                    <div className="w-full">
                      <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900 mb-4">
                        Edit JSON - {application.name || application.key}
                      </Dialog.Title>
                      
                      {error && (
                        <div className="mb-4 bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md">
                          <p className="text-sm">{error}</p>
                        </div>
                      )}

                      <div className="relative">
                        <textarea
                          value={jsonContent}
                          onChange={handleJsonChange}
                          className="w-full h-96 p-4 text-sm font-mono bg-gray-50 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                          spellCheck="false"
                        />
                        
                        <div className="absolute top-2 right-2 flex gap-2">
                          <button
                            type="button"
                            onClick={handleCopy}
                            className="inline-flex items-center rounded bg-white px-2 py-1 text-xs font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                            title="Copy to clipboard"
                          >
                            <DocumentDuplicateIcon className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={handleFormat}
                            className="inline-flex items-center rounded bg-white px-2 py-1 text-xs font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                          >
                            Format
                          </button>
                        </div>
                      </div>

                      {isDirty && (
                        <p className="mt-2 text-sm text-yellow-600">
                          You have unsaved changes
                        </p>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                  <button
                    type="button"
                    disabled={loading || !isDirty}
                    onClick={handleSave}
                    className="inline-flex w-full justify-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 sm:ml-3 sm:w-auto disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={loading}
                    className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default JsonEditorModal;