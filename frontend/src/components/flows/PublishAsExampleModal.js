import React, { useState, useEffect } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { AcademicCapIcon, XMarkIcon } from '@heroicons/react/24/outline';
import axios from 'axios';

const PublishAsExampleModal = ({ open, onClose, flow, onPublish, publishing }) => {
  const [formData, setFormData] = useState({
    example_name: '',
    description: '',
    category: '',
    tags: '',
    difficulty: 'Intermediate',
    estimated_time: '10-15 minutes'
  });
  const [categories, setCategories] = useState([]);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const [errors, setErrors] = useState({});

  // Load categories when modal opens
  useEffect(() => {
    if (open) {
      loadCategories();
      // Initialize form with flow data
      if (flow) {
        setFormData({
          example_name: flow.flow_name || '',
          description: flow.description || '',
          category: flow.category || '',
          tags: '',
          difficulty: 'Intermediate',
          estimated_time: '10-15 minutes'
        });
      }
    }
  }, [open, flow]);

  const loadCategories = async () => {
    setLoadingCategories(true);
    try {
      const response = await axios.get('/api/v1/flow-examples/categories/list');
      setCategories(response.data.categories || []);
    } catch (error) {
      console.error('Failed to load categories:', error);
    } finally {
      setLoadingCategories(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: null
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.example_name.trim()) {
      newErrors.example_name = 'Example name is required';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }

    if (!formData.category) {
      newErrors.category = 'Category is required';
    }

    if (!formData.tags.trim()) {
      newErrors.tags = 'At least one tag is required';
    }

    if (!formData.difficulty) {
      newErrors.difficulty = 'Difficulty level is required';
    }

    if (!formData.estimated_time.trim()) {
      newErrors.estimated_time = 'Estimated time is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    // Convert tags string to array
    const tagsArray = formData.tags
      .split(',')
      .map(tag => tag.trim())
      .filter(tag => tag.length > 0);

    const publishData = {
      flow_id: flow.flow_id,
      example_name: formData.example_name.trim(),
      description: formData.description.trim(),
      category: formData.category,
      tags: tagsArray,
      difficulty: formData.difficulty,
      estimated_time: formData.estimated_time.trim()
    };

    onPublish(publishData);
  };

  if (!flow) return null;

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
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl sm:p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center">
                    <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100">
                      <AcademicCapIcon className="h-6 w-6 text-indigo-600" aria-hidden="true" />
                    </div>
                    <div className="ml-4">
                      <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                        Publish Flow as Example
                      </Dialog.Title>
                      <p className="mt-1 text-sm text-gray-500">
                        Make this flow available in the Flow Examples gallery
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
                    onClick={onClose}
                    disabled={publishing}
                  >
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="space-y-6">
                  {/* Example Name */}
                  <div>
                    <label htmlFor="example_name" className="block text-sm font-medium text-gray-700">
                      Example Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="example_name"
                      name="example_name"
                      value={formData.example_name}
                      onChange={handleChange}
                      className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm ${
                        errors.example_name
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                          : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                      }`}
                      placeholder="e.g., Email Notification Workflow"
                      disabled={publishing}
                    />
                    {errors.example_name && (
                      <p className="mt-1 text-sm text-red-600">{errors.example_name}</p>
                    )}
                  </div>

                  {/* Description */}
                  <div>
                    <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                      Description <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      id="description"
                      name="description"
                      rows={3}
                      value={formData.description}
                      onChange={handleChange}
                      className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm ${
                        errors.description
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                          : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                      }`}
                      placeholder="Describe what this flow does and its use cases..."
                      disabled={publishing}
                    />
                    {errors.description && (
                      <p className="mt-1 text-sm text-red-600">{errors.description}</p>
                    )}
                  </div>

                  {/* Category */}
                  <div>
                    <label htmlFor="category" className="block text-sm font-medium text-gray-700">
                      Category <span className="text-red-500">*</span>
                    </label>
                    <select
                      id="category"
                      name="category"
                      value={formData.category}
                      onChange={handleChange}
                      className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm ${
                        errors.category
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                          : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                      }`}
                      disabled={publishing || loadingCategories}
                    >
                      <option value="">Select a category</option>
                      {categories.map((cat) => (
                        <option key={cat.id} value={cat.name}>
                          {cat.name}
                        </option>
                      ))}
                    </select>
                    {errors.category && (
                      <p className="mt-1 text-sm text-red-600">{errors.category}</p>
                    )}
                  </div>

                  {/* Tags */}
                  <div>
                    <label htmlFor="tags" className="block text-sm font-medium text-gray-700">
                      Tags <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="tags"
                      name="tags"
                      value={formData.tags}
                      onChange={handleChange}
                      className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm ${
                        errors.tags
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                          : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                      }`}
                      placeholder="e.g., Email, Notifications, Automation (comma-separated)"
                      disabled={publishing}
                    />
                    {errors.tags && (
                      <p className="mt-1 text-sm text-red-600">{errors.tags}</p>
                    )}
                    <p className="mt-1 text-xs text-gray-500">Separate multiple tags with commas</p>
                  </div>

                  {/* Difficulty and Estimated Time - Side by Side */}
                  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                    {/* Difficulty */}
                    <div>
                      <label htmlFor="difficulty" className="block text-sm font-medium text-gray-700">
                        Difficulty Level <span className="text-red-500">*</span>
                      </label>
                      <select
                        id="difficulty"
                        name="difficulty"
                        value={formData.difficulty}
                        onChange={handleChange}
                        className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm ${
                          errors.difficulty
                            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                        }`}
                        disabled={publishing}
                      >
                        <option value="Beginner">Beginner</option>
                        <option value="Intermediate">Intermediate</option>
                        <option value="Advanced">Advanced</option>
                      </select>
                      {errors.difficulty && (
                        <p className="mt-1 text-sm text-red-600">{errors.difficulty}</p>
                      )}
                    </div>

                    {/* Estimated Time */}
                    <div>
                      <label htmlFor="estimated_time" className="block text-sm font-medium text-gray-700">
                        Estimated Time <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="estimated_time"
                        name="estimated_time"
                        value={formData.estimated_time}
                        onChange={handleChange}
                        className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm ${
                          errors.estimated_time
                            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                        }`}
                        placeholder="e.g., 10-15 minutes"
                        disabled={publishing}
                      />
                      {errors.estimated_time && (
                        <p className="mt-1 text-sm text-red-600">{errors.estimated_time}</p>
                      )}
                    </div>
                  </div>

                  {/* Info Box */}
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                    <p className="text-sm text-blue-800">
                      <strong>Note:</strong> Publishing this flow will make it available to all users in the Flow Examples gallery.
                      The flow will be exported with its current configuration.
                    </p>
                  </div>

                  {/* Buttons */}
                  <div className="flex flex-row-reverse gap-3 mt-6">
                    <button
                      type="submit"
                      disabled={publishing}
                      className="inline-flex justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {publishing ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          Publishing...
                        </>
                      ) : (
                        'Publish as Example'
                      )}
                    </button>
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                      onClick={onClose}
                      disabled={publishing}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default PublishAsExampleModal;
