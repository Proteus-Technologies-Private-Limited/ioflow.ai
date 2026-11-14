/**
 * DocumentationManager Component
 * Allows app owners to create, edit, delete, and reorder documentation pages
 * Integrates with the existing WYSIWYG HTML editor
 */
import React, { useState, useEffect } from 'react';
import {
  Plus,
  Edit,
  Trash2,
  Eye,
  Save,
  X,
  GripVertical,
  Loader,
  BookOpen,
  FileText,
  AlertCircle,
  Code,
  Wrench,
  HelpCircle,
  GitBranch,
  File,
  ArrowUp,
  ArrowDown
} from 'lucide-react';
import toast from 'react-hot-toast';
import { showErrorToast } from '../../utils/customToast';
import WysiwygHtmlEditor from '../common/WysiwygHtmlEditor';
import {
  getAppDocumentationPages,
  getDocumentationPageById,
  createDocumentationPage,
  updateDocumentationPage,
  deleteDocumentationPage,
  reorderDocumentationPages,
  generateSlug,
  PAGE_TYPE_OPTIONS
} from '../../services/documentationService';

const PAGE_TYPE_ICONS = {
  user_guide: BookOpen,
  specifications: FileText,
  prerequisites: AlertCircle,
  api_docs: Code,
  troubleshooting: Wrench,
  faq: HelpCircle,
  changelog: GitBranch,
  custom: File
};

const DocumentationManager = ({ appId, appName, onClose }) => {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingPage, setEditingPage] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState({
    page_type: 'user_guide',
    page_title: '',
    page_slug: '',
    content: '',
    display_order: 0,
    is_published: true
  });
  const [previewMode, setPreviewMode] = useState(false);

  useEffect(() => {
    if (appId) {
      loadDocumentationPages();
    }
  }, [appId]);

  const loadDocumentationPages = async () => {
    try {
      setLoading(true);
      const data = await getAppDocumentationPages(appId);
      setPages(data.pages || []);
    } catch (error) {
      console.error('Error loading documentation pages:', error);
      showErrorToast('Failed to load documentation pages');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNew = () => {
    setIsCreating(true);
    setEditingPage(null);
    setFormData({
      page_type: 'user_guide',
      page_title: '',
      page_slug: '',
      content: '<h1>Welcome</h1><p>Start writing your documentation here...</p>',
      display_order: pages.length,
      is_published: true
    });
    setPreviewMode(false);
  };

  const handleEdit = async (page) => {
    try {
      setLoading(true);
      console.log('Fetching page data for:', page.page_id);

      // Fetch full page data including content
      const fullPageData = await getDocumentationPageById(appId, page.page_id);
      console.log('Received full page data:', fullPageData);
      console.log('Content length:', fullPageData.content?.length || 0);

      setEditingPage(fullPageData);
      setIsCreating(false);
      setFormData({
        page_type: fullPageData.page_type,
        page_title: fullPageData.page_title,
        page_slug: fullPageData.page_slug,
        content: fullPageData.content || '<p>No content</p>',
        display_order: fullPageData.display_order,
        is_published: fullPageData.is_published
      });
      setPreviewMode(false);
      setLoading(false);
    } catch (error) {
      console.error('Error loading page for edit:', error);
      showErrorToast('Failed to load page content');
      setLoading(false);
    }
  };

  const handleSave = async () => {
    // Validate
    if (!formData.page_title.trim()) {
      showErrorToast('Page title is required');
      return;
    }
    if (!formData.content.trim()) {
      showErrorToast('Page content is required');
      return;
    }

    // Auto-generate slug if not provided
    const slug = formData.page_slug || generateSlug(formData.page_title);

    try {
      if (isCreating) {
        await createDocumentationPage(appId, {
          ...formData,
          page_slug: slug
        });
      } else if (editingPage) {
        await updateDocumentationPage(appId, editingPage.page_id, {
          ...formData,
          page_slug: slug
        });
      }

      // Reload pages
      await loadDocumentationPages();

      // Reset form
      setIsCreating(false);
      setEditingPage(null);
      setFormData({
        page_type: 'user_guide',
        page_title: '',
        page_slug: '',
        content: '',
        display_order: 0,
        is_published: true
      });
    } catch (error) {
      console.error('Error saving page:', error);
    }
  };

  const handleDelete = async (pageId) => {
    if (!window.confirm('Are you sure you want to delete this documentation page?')) {
      return;
    }

    try {
      await deleteDocumentationPage(appId, pageId);
      await loadDocumentationPages();
    } catch (error) {
      console.error('Error deleting page:', error);
    }
  };

  const handleMoveUp = async (index) => {
    if (index === 0) return;

    const newPages = [...pages];
    const temp = newPages[index];
    newPages[index] = newPages[index - 1];
    newPages[index - 1] = temp;

    await updatePageOrders(newPages);
  };

  const handleMoveDown = async (index) => {
    if (index === pages.length - 1) return;

    const newPages = [...pages];
    const temp = newPages[index];
    newPages[index] = newPages[index + 1];
    newPages[index + 1] = temp;

    await updatePageOrders(newPages);
  };

  const updatePageOrders = async (newPages) => {
    const pageOrders = newPages.map((page, index) => ({
      page_id: page.page_id,
      display_order: index
    }));

    try {
      await reorderDocumentationPages(appId, pageOrders);
      setPages(newPages);
    } catch (error) {
      console.error('Error reordering pages:', error);
    }
  };

  const handleCancel = () => {
    setIsCreating(false);
    setEditingPage(null);
    setFormData({
      page_type: 'user_guide',
      page_title: '',
      page_slug: '',
      content: '',
      display_order: 0,
      is_published: true
    });
  };

  // If editing or creating, show editor form
  if (isCreating || editingPage) {
    return (
      <div className="fixed inset-0 bg-gray-900 bg-opacity-50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b">
            <h2 className="text-2xl font-bold text-gray-900">
              {isCreating ? 'Create Documentation Page' : 'Edit Documentation Page'}
            </h2>
            <button
              onClick={handleCancel}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Form */}
          <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
            <div className="space-y-6 pb-4">
              {/* Page Type and Title */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Page Type
                  </label>
                  <select
                    value={formData.page_type}
                    onChange={(e) => setFormData({ ...formData, page_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    {PAGE_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Page Title *
                  </label>
                  <input
                    type="text"
                    value={formData.page_title}
                    onChange={(e) => {
                      const title = e.target.value;
                      setFormData({
                        ...formData,
                        page_title: title,
                        page_slug: generateSlug(title)
                      });
                    }}
                    placeholder="e.g., Getting Started Guide"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>

              {/* Slug */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  URL Slug (auto-generated)
                </label>
                <input
                  type="text"
                  value={formData.page_slug}
                  onChange={(e) => setFormData({ ...formData, page_slug: e.target.value })}
                  placeholder="auto-generated from title"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Used in the URL: /marketplace/app/{appName}/{formData.page_slug || 'page-slug'}
                </p>
              </div>

              {/* Published Toggle */}
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="is_published"
                  checked={formData.is_published}
                  onChange={(e) => setFormData({ ...formData, is_published: e.target.checked })}
                  className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary"
                />
                <label htmlFor="is_published" className="text-sm font-medium text-gray-700">
                  Publish this page (visible in marketplace)
                </label>
              </div>

              {/* Content Editor */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Page Content *
                </label>
                <WysiwygHtmlEditor
                  key={editingPage ? editingPage.page_id : 'new'}
                  value={formData.content}
                  onChange={(content) => setFormData({ ...formData, content })}
                  height={500}
                  placeholder="Write your documentation content here..."
                />
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
            <button
              onClick={handleCancel}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-6 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              {isCreating ? 'Create Page' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Main list view
  return (
    <div className="fixed inset-0 bg-gray-900 bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Manage Documentation</h2>
            <p className="text-sm text-gray-600 mt-1">{appName}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleCreateNew}
              className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              New Page
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          ) : pages.length === 0 ? (
            <div className="text-center py-12">
              <BookOpen className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Documentation Pages</h3>
              <p className="text-gray-600 mb-6">
                Create your first documentation page to help users understand your app.
              </p>
              <button
                onClick={handleCreateNew}
                className="px-6 py-3 bg-gradient-primary text-white rounded-md hover:shadow-lg"
              >
                Create First Page
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {pages.map((page, index) => {
                const Icon = PAGE_TYPE_ICONS[page.page_type] || File;

                return (
                  <div
                    key={page.page_id}
                    className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-center gap-4">
                      {/* Icon */}
                      <Icon className="w-5 h-5 text-gray-500 flex-shrink-0" />

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-gray-900 truncate">
                            {page.page_title}
                          </h3>
                          {!page.is_published && (
                            <span className="px-2 py-0.5 bg-gray-200 text-gray-700 text-xs rounded">
                              Draft
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-500">/{page.page_slug}</p>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        {/* Move Up */}
                        <button
                          onClick={() => handleMoveUp(index)}
                          disabled={index === 0}
                          className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Move up"
                        >
                          <ArrowUp className="w-4 h-4" />
                        </button>

                        {/* Move Down */}
                        <button
                          onClick={() => handleMoveDown(index)}
                          disabled={index === pages.length - 1}
                          className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Move down"
                        >
                          <ArrowDown className="w-4 h-4" />
                        </button>

                        {/* Edit */}
                        <button
                          onClick={() => handleEdit(page)}
                          className="p-2 text-primary hover:bg-primary-10 rounded"
                          title="Edit"
                        >
                          <Edit className="w-4 h-4" />
                        </button>

                        {/* Delete */}
                        <button
                          onClick={() => handleDelete(page.page_id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t bg-gray-50">
          <p className="text-sm text-gray-600">
            {pages.length} {pages.length === 1 ? 'page' : 'pages'}
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-100"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocumentationManager;
