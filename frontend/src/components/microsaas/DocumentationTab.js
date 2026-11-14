/**
 * Documentation Tab Component
 * Card-based view with drag-and-drop reordering for documentation pages
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  Plus,
  Edit,
  Trash2,
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
  Eye,
  EyeOff
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

const DocumentationTab = ({ appId, appName }) => {
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

  // Drag and drop state
  const [draggedItem, setDraggedItem] = useState(null);
  const [dragOverItem, setDragOverItem] = useState(null);

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
  };

  const handleEdit = async (page) => {
    try {
      setLoading(true);
      const fullPageData = await getDocumentationPageById(appId, page.page_id);

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
      setLoading(false);
    } catch (error) {
      console.error('Error loading page for edit:', error);
      showErrorToast('Failed to load page content');
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!formData.page_title.trim()) {
      showErrorToast('Page title is required');
      return;
    }
    if (!formData.content.trim()) {
      showErrorToast('Page content is required');
      return;
    }

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

      await loadDocumentationPages();
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

      toast.success(isCreating ? 'Page created successfully' : 'Page updated successfully');
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

  // Drag and drop handlers
  const handleDragStart = (e, page) => {
    setDraggedItem(page);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, page) => {
    e.preventDefault();
    setDragOverItem(page);
  };

  const handleDragEnd = async (e) => {
    e.preventDefault();

    if (!draggedItem || !dragOverItem || draggedItem.page_id === dragOverItem.page_id) {
      setDraggedItem(null);
      setDragOverItem(null);
      return;
    }

    const newPages = [...pages];
    const draggedIndex = newPages.findIndex(p => p.page_id === draggedItem.page_id);
    const dropIndex = newPages.findIndex(p => p.page_id === dragOverItem.page_id);

    // Remove dragged item and insert at new position
    const [removed] = newPages.splice(draggedIndex, 1);
    newPages.splice(dropIndex, 0, removed);

    // Update display_order for all pages
    const reorderedPages = newPages.map((page, index) => ({
      ...page,
      display_order: index
    }));

    setPages(reorderedPages);

    // Save new order to backend
    try {
      const pageOrders = reorderedPages.map(page => ({
        page_id: page.page_id,
        display_order: page.display_order
      }));
      await reorderDocumentationPages(appId, pageOrders);
    } catch (error) {
      console.error('Error reordering pages:', error);
      // Reload pages if reorder failed
      loadDocumentationPages();
    }

    setDraggedItem(null);
    setDragOverItem(null);
  };

  // Render editor form
  if (isCreating || editingPage) {
    return (
      <div className="bg-white rounded-lg shadow-sm">
        <div className="p-6 border-b">
          <h3 className="text-xl font-bold text-gray-900">
            {isCreating ? 'Create Documentation Page' : 'Edit Documentation Page'}
          </h3>
        </div>

        <div className="p-6 space-y-6">
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
            <label htmlFor="is_published" className="text-sm font-medium text-gray-700 flex items-center gap-2">
              {formData.is_published ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
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
            className="px-6 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg"
          >
            {isCreating ? 'Create Page' : 'Save Changes'}
          </button>
        </div>
      </div>
    );
  }

  // Render card list view
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Documentation Pages</h3>
          <p className="text-sm text-gray-600 mt-1">
            {pages.length} {pages.length === 1 ? 'page' : 'pages'} • Drag to reorder
          </p>
        </div>
        <button
          onClick={handleCreateNew}
          className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Page
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader className="w-8 h-8 text-primary animate-spin" />
        </div>
      ) : pages.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {pages.map((page) => {
            const Icon = PAGE_TYPE_ICONS[page.page_type] || File;
            const isDragging = draggedItem?.page_id === page.page_id;
            const isOver = dragOverItem?.page_id === page.page_id;

            return (
              <div
                key={page.page_id}
                draggable
                onDragStart={(e) => handleDragStart(e, page)}
                onDragOver={(e) => handleDragOver(e, page)}
                onDragEnd={handleDragEnd}
                className={`
                  bg-white rounded-lg border-2 transition-all cursor-move
                  ${isDragging ? 'opacity-50 scale-95' : 'opacity-100 scale-100'}
                  ${isOver ? 'border-primary shadow-lg' : 'border-gray-200'}
                  hover:border-primary/70 hover:shadow-md
                `}
              >
                <div className="p-4">
                  {/* Header */}
                  <div className="flex items-start gap-3 mb-3">
                    <div className="flex-shrink-0 mt-1 cursor-grab active:cursor-grabbing">
                      <GripVertical className="w-5 h-5 text-gray-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-5 h-5 text-primary flex-shrink-0" />
                        <h4 className="text-base font-semibold text-gray-900 truncate">
                          {page.page_title}
                        </h4>
                        {!page.is_published && (
                          <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                            Draft
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">
                        {PAGE_TYPE_OPTIONS.find(opt => opt.value === page.page_type)?.label || page.page_type}
                      </p>
                    </div>
                  </div>

                  {/* Preview - Show first 100 characters */}
                  <div className="mb-3 text-sm text-gray-600 line-clamp-2 bg-gray-50 p-2 rounded">
                    {/* Strip HTML tags for preview */}
                    {page.content ?
                      new DOMParser().parseFromString(page.content, 'text/html').body.textContent.substring(0, 100) + '...'
                      : 'No content preview available'}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-3 border-t">
                    <span className="text-xs text-gray-500">
                      Order: {page.display_order + 1}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleEdit(page)}
                        className="p-1.5 text-gray-600 hover:text-primary hover:bg-indigo-50 rounded transition-colors"
                        title="Edit page"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(page.page_id)}
                        className="p-1.5 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="Delete page"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DocumentationTab;
