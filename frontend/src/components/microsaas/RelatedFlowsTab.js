import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  PlusIcon,
  TrashIcon,
  PencilIcon,
  ArrowsUpDownIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  LinkIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  DocumentTextIcon,
  Cog6ToothIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import microSaasService from '../../services/microSaasService';

const RelatedFlowsTab = ({ app, onRefresh }) => {
  const [loading, setLoading] = useState(true);
  const [relatedFlows, setRelatedFlows] = useState({ prerequisites: [], followups: [] });
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingRelationship, setEditingRelationship] = useState(null);
  const [addingType, setAddingType] = useState('prerequisite');
  const [availableApps, setAvailableApps] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loadingAvailable, setLoadingAvailable] = useState(false);
  const searchTimeoutRef = useRef(null);
  const searchInputRef = useRef(null);

  useEffect(() => {
    loadRelatedFlows();
  }, [app?.frontend_app_id]);

  // Debounced search effect
  useEffect(() => {
    if (!showAddModal) return;

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(() => {
      loadAvailableApps(addingType);
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchTerm, showAddModal, addingType]);

  const loadRelatedFlows = async () => {
    if (!app?.frontend_app_id) return;

    try {
      setLoading(true);
      const data = await microSaasService.getRelatedFlows(app.frontend_app_id);
      setRelatedFlows(data);
    } catch (error) {
      console.error('Error loading related flows:', error);
      toast.error('Failed to load related flows');
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableApps = async (type) => {
    try {
      setLoadingAvailable(true);
      const data = await microSaasService.getAvailableAppsForLinking(
        app.frontend_app_id,
        { relationship_type: type, search: searchTerm }
      );
      setAvailableApps(data.apps || []);
    } catch (error) {
      console.error('Error loading available apps:', error);
      toast.error('Failed to load available apps');
    } finally {
      setLoadingAvailable(false);
    }
  };

  const handleOpenAddModal = (type) => {
    setAddingType(type);
    setSearchTerm('');
    setShowAddModal(true);
    // Initial load will be triggered by the useEffect
  };

  const handleAddRelatedFlow = async (selectedApp) => {
    try {
      await microSaasService.addRelatedFlow(app.frontend_app_id, {
        related_frontend_app_id: selectedApp.frontend_app_id,
        relationship_type: addingType,
        is_mandatory: false,
        auto_map_enabled: true
      });
      toast.success(`Added ${addingType === 'prerequisite' ? 'prerequisite' : 'follow-up'} flow`);
      setShowAddModal(false);
      loadRelatedFlows();
    } catch (error) {
      console.error('Error adding related flow:', error);
      toast.error((error.response?.data?.message || error.response?.data?.detail) || 'Failed to add related flow');
    }
  };

  const handleRemoveRelatedFlow = async (relationshipId, type) => {
    if (!window.confirm('Are you sure you want to remove this relationship?')) return;

    try {
      await microSaasService.removeRelatedFlow(app.frontend_app_id, relationshipId);
      toast.success('Relationship removed');
      loadRelatedFlows();
    } catch (error) {
      console.error('Error removing related flow:', error);
      toast.error('Failed to remove relationship');
    }
  };

  const handleUpdateRelatedFlow = async (relationshipId, updates) => {
    try {
      await microSaasService.updateRelatedFlow(app.frontend_app_id, relationshipId, updates);
      toast.success('Updated successfully');
      loadRelatedFlows();
      setShowEditModal(false);
    } catch (error) {
      console.error('Error updating related flow:', error);
      toast.error('Failed to update');
    }
  };

  const handleMoveUp = async (index, type) => {
    const list = type === 'prerequisite' ? relatedFlows.prerequisites : relatedFlows.followups;
    if (index === 0) return;

    const newOrder = [...list];
    [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];
    const orderedIds = newOrder.map(item => item.relationship_id);

    try {
      await microSaasService.reorderRelatedFlows(app.frontend_app_id, type, orderedIds);
      loadRelatedFlows();
    } catch (error) {
      console.error('Error reordering:', error);
      toast.error('Failed to reorder');
    }
  };

  const handleMoveDown = async (index, type) => {
    const list = type === 'prerequisite' ? relatedFlows.prerequisites : relatedFlows.followups;
    if (index === list.length - 1) return;

    const newOrder = [...list];
    [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
    const orderedIds = newOrder.map(item => item.relationship_id);

    try {
      await microSaasService.reorderRelatedFlows(app.frontend_app_id, type, orderedIds);
      loadRelatedFlows();
    } catch (error) {
      console.error('Error reordering:', error);
      toast.error('Failed to reorder');
    }
  };

  const RelatedFlowCard = ({ item, index, type, totalCount }) => (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3 flex-1">
          {item.related_app_icon_url ? (
            <img
              src={item.related_app_icon_url}
              alt=""
              className="w-10 h-10 rounded-lg object-cover"
            />
          ) : (
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <LinkIcon className="w-5 h-5 text-white" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2">
              <h4 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {item.display_name || item.related_app_name}
              </h4>
              {type === 'prerequisite' && item.is_mandatory && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                  Required
                </span>
              )}
              {!item.is_active && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                  Inactive
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
              {item.related_app_description || 'No description'}
            </p>
            {item.documentation && (
              <p className="text-xs text-blue-600 dark:text-blue-400 mt-1 flex items-center">
                <DocumentTextIcon className="w-3 h-3 mr-1" />
                {item.documentation.substring(0, 50)}{item.documentation.length > 50 ? '...' : ''}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-1 ml-4">
          {/* Reorder buttons */}
          <button
            onClick={() => handleMoveUp(index, type)}
            disabled={index === 0}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
            title="Move up"
          >
            <ArrowUpIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleMoveDown(index, type)}
            disabled={index === totalCount - 1}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
            title="Move down"
          >
            <ArrowDownIcon className="w-4 h-4" />
          </button>

          {/* Edit button */}
          <button
            onClick={() => {
              setEditingRelationship(item);
              setShowEditModal(true);
            }}
            className="p-1 text-gray-400 hover:text-blue-600"
            title="Edit"
          >
            <PencilIcon className="w-4 h-4" />
          </button>

          {/* Delete button */}
          <button
            onClick={() => handleRemoveRelatedFlow(item.relationship_id, type)}
            className="p-1 text-gray-400 hover:text-red-600"
            title="Remove"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Parameter mapping info */}
      <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-4">
            <span className={`flex items-center ${item.auto_map_enabled ? 'text-green-600' : 'text-gray-400'}`}>
              {item.auto_map_enabled ? (
                <CheckCircleIcon className="w-4 h-4 mr-1" />
              ) : (
                <XMarkIcon className="w-4 h-4 mr-1" />
              )}
              Auto-mapping
            </span>
            {item.parameter_mappings?.mappings?.length > 0 && (
              <span className="text-blue-600 flex items-center">
                <Cog6ToothIcon className="w-4 h-4 mr-1" />
                {item.parameter_mappings.mappings.length} manual mapping(s)
              </span>
            )}
          </div>
          <span className="text-gray-400">
            Order: {item.execution_order + 1}
          </span>
        </div>
      </div>
    </div>
  );

  // AddFlowModal is rendered inline below to prevent focus loss issues

  const EditFlowModal = () => {
    const [formData, setFormData] = useState({
      is_mandatory: editingRelationship?.is_mandatory || false,
      display_name: editingRelationship?.display_name || '',
      documentation: editingRelationship?.documentation || '',
      auto_map_enabled: editingRelationship?.auto_map_enabled ?? true,
      is_active: editingRelationship?.is_active ?? true
    });

    if (!editingRelationship) return null;

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Edit Relationship
              </h3>
              <button
                onClick={() => setShowEditModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="p-4 space-y-4">
            {/* Display Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Custom Display Name
              </label>
              <input
                type="text"
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                placeholder={editingRelationship.related_app_name}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            {/* Documentation */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Help Text / Documentation
              </label>
              <textarea
                value={formData.documentation}
                onChange={(e) => setFormData({ ...formData, documentation: e.target.value })}
                rows={3}
                placeholder="Help text shown to users explaining this step..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>

            {/* Toggles */}
            <div className="space-y-3">
              {editingRelationship.relationship_type === 'prerequisite' && (
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    Required (must complete before main flow)
                  </span>
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, is_mandatory: !formData.is_mandatory })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      formData.is_mandatory ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        formData.is_mandatory ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </label>
              )}

              <label className="flex items-center justify-between">
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Auto-map parameters by name
                </span>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, auto_map_enabled: !formData.auto_map_enabled })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    formData.auto_map_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      formData.auto_map_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </label>

              <label className="flex items-center justify-between">
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Active
                </span>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, is_active: !formData.is_active })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    formData.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      formData.is_active ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </label>
            </div>
          </div>

          <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
            <button
              onClick={() => setShowEditModal(false)}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              Cancel
            </button>
            <button
              onClick={() => handleUpdateRelatedFlow(editingRelationship.relationship_id, formData)}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Save Changes
            </button>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex">
          <InformationCircleIcon className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="ml-3">
            <h4 className="text-sm font-medium text-blue-800 dark:text-blue-200">
              About Related Flows
            </h4>
            <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
              <strong>Prerequisites</strong> are flows that should run before the main flow.
              They can be marked as required or optional.
              <br />
              <strong>Follow-ups</strong> are flows that can be triggered after the main flow completes.
              Output parameters are automatically mapped where names match.
            </p>
          </div>
        </div>
      </div>

      {/* Prerequisites Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <ArrowLeftIcon className="w-5 h-5 text-orange-500" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Prerequisites
            </h3>
            <span className="text-sm text-gray-500">
              ({relatedFlows.prerequisites?.length || 0})
            </span>
          </div>
          <button
            onClick={() => handleOpenAddModal('prerequisite')}
            className="inline-flex items-center px-3 py-1.5 text-sm bg-orange-100 text-orange-700 hover:bg-orange-200 dark:bg-orange-900/30 dark:text-orange-300 rounded-lg"
          >
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Prerequisite
          </button>
        </div>

        {relatedFlows.prerequisites?.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
            <ArrowLeftIcon className="w-10 h-10 text-gray-300 mx-auto" />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              No prerequisites configured
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Add flows that should run before the main flow
            </p>
          </div>
        ) : (
          <div>
            {relatedFlows.prerequisites.map((item, index) => (
              <RelatedFlowCard
                key={item.relationship_id}
                item={item}
                index={index}
                type="prerequisite"
                totalCount={relatedFlows.prerequisites.length}
              />
            ))}
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200 dark:border-gray-700"></div>
        </div>
        <div className="relative flex justify-center">
          <div className="bg-white dark:bg-gray-900 px-4 py-2 rounded-full border border-gray-200 dark:border-gray-700">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Main Flow: {app?.frontend_app_name}
            </span>
          </div>
        </div>
      </div>

      {/* Follow-ups Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <ArrowRightIcon className="w-5 h-5 text-green-500" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Follow-ups
            </h3>
            <span className="text-sm text-gray-500">
              ({relatedFlows.followups?.length || 0})
            </span>
          </div>
          <button
            onClick={() => handleOpenAddModal('followup')}
            className="inline-flex items-center px-3 py-1.5 text-sm bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-300 rounded-lg"
          >
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Follow-up
          </button>
        </div>

        {relatedFlows.followups?.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
            <ArrowRightIcon className="w-10 h-10 text-gray-300 mx-auto" />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              No follow-ups configured
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Add flows that can be triggered after the main flow completes
            </p>
          </div>
        ) : (
          <div>
            {relatedFlows.followups.map((item, index) => (
              <RelatedFlowCard
                key={item.relationship_id}
                item={item}
                index={index}
                type="followup"
                totalCount={relatedFlows.followups.length}
              />
            ))}
          </div>
        )}
      </div>

      {/* Add Flow Modal - Rendered inline to prevent focus loss */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Add {addingType === 'prerequisite' ? 'Prerequisite' : 'Follow-up'} Flow
                </h3>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>
              <div className="mt-3">
                <div className="relative">
                  <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Search apps..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    autoFocus
                  />
                </div>
              </div>
            </div>

            <div className="p-4 overflow-y-auto max-h-[50vh]">
              {loadingAvailable ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="mt-2 text-sm text-gray-500">Loading apps...</p>
                </div>
              ) : availableApps.length === 0 ? (
                <div className="text-center py-8">
                  <LinkIcon className="w-12 h-12 text-gray-300 mx-auto" />
                  <p className="mt-2 text-sm text-gray-500">No apps available to link</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {availableApps.map((availableApp) => (
                    <button
                      key={availableApp.frontend_app_id}
                      onClick={() => handleAddRelatedFlow(availableApp)}
                      className="w-full text-left p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                    >
                      <div className="flex items-center space-x-3">
                        {availableApp.icon_url ? (
                          <img
                            src={availableApp.icon_url}
                            alt=""
                            className="w-10 h-10 rounded-lg object-cover"
                          />
                        ) : (
                          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                            <LinkIcon className="w-5 h-5 text-white" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {availableApp.frontend_app_name}
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {availableApp.description || 'No description'}
                          </p>
                          <div className="flex items-center space-x-2 mt-1">
                            {availableApp.has_input_parameters && (
                              <span className="text-xs text-blue-600 dark:text-blue-400">
                                {availableApp.input_parameter_names?.length || 0} inputs
                              </span>
                            )}
                            {availableApp.has_output_parameters && (
                              <span className="text-xs text-green-600 dark:text-green-400">
                                {availableApp.output_parameter_names?.length || 0} outputs
                              </span>
                            )}
                          </div>
                        </div>
                        <ArrowRightIcon className="w-5 h-5 text-gray-400" />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Flow Modal */}
      {showEditModal && <EditFlowModal />}
    </div>
  );
};

export default RelatedFlowsTab;
