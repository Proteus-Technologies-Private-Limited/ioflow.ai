/**
 * AppDocumentation Component
 * Displays published documentation pages for marketplace apps
 * with tabbed navigation and safe HTML rendering
 */
import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  FileText,
  AlertCircle,
  Code,
  Wrench,
  HelpCircle,
  GitBranch,
  File,
  Loader,
  AlertTriangle
} from 'lucide-react';
import { getMarketplaceDocumentation, getMarketplaceDocumentationPage } from '../../services/documentationService';
import DOMPurify from 'dompurify';

// Icon mapping for page types
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

const AppDocumentation = ({ appSlug }) => {
  const [pages, setPages] = useState([]);
  const [selectedPage, setSelectedPage] = useState(null);
  const [pageContent, setPageContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState(null);

  // Load documentation pages list
  useEffect(() => {
    loadDocumentationPages();
  }, [appSlug]);

  // Load content when page is selected
  useEffect(() => {
    if (selectedPage) {
      loadPageContent(selectedPage.page_slug);
    }
  }, [selectedPage]);

  const loadDocumentationPages = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMarketplaceDocumentation(appSlug);
      setPages(data);

      // Auto-select first page if available
      if (data.length > 0) {
        setSelectedPage(data[0]);
      }
    } catch (err) {
      console.error('Error loading documentation pages:', err);
      setError('Failed to load documentation pages');
    } finally {
      setLoading(false);
    }
  };

  const loadPageContent = async (pageSlug) => {
    try {
      setLoadingContent(true);
      const data = await getMarketplaceDocumentationPage(appSlug, pageSlug);
      setPageContent(data);
    } catch (err) {
      console.error('Error loading page content:', err);
      setPageContent(null);
    } finally {
      setLoadingContent(false);
    }
  };

  const handlePageSelect = (page) => {
    setSelectedPage(page);
    setPageContent(null); // Clear previous content while loading
  };

  // Sanitize HTML content before rendering
  const sanitizeHTML = (html) => {
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        'p', 'br', 'span', 'div',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'em', 'u', 's', 'strike', 'b', 'i',
        'ul', 'ol', 'li',
        'a', 'img',
        'blockquote', 'code', 'pre',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'hr'
      ],
      ALLOWED_ATTR: ['class', 'id', 'style', 'href', 'src', 'alt', 'title', 'target', 'rel', 'width', 'height'],
      ADD_ATTR: ['target', 'rel']
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-3" />
        <p className="text-red-700">{error}</p>
      </div>
    );
  }

  if (pages.length === 0) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
        <BookOpen className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Documentation Available</h3>
        <p className="text-gray-600">
          The developer hasn't added documentation for this app yet.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-4 min-h-[500px]">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1 bg-gray-50 border-r border-gray-200">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <BookOpen className="w-5 h-5" />
              Documentation
            </h3>
          </div>

          <nav className="p-2">
            {pages.map((page) => {
              const Icon = PAGE_TYPE_ICONS[page.page_type] || File;
              const isSelected = selectedPage?.page_id === page.page_id;

              return (
                <button
                  key={page.page_id}
                  onClick={() => handlePageSelect(page)}
                  className={`
                    w-full text-left px-4 py-3 rounded-lg mb-1
                    flex items-center gap-3 transition-colors
                    ${isSelected
                      ? 'bg-primary-10 text-primary font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                    }
                  `}
                >
                  <Icon className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-primary' : 'text-gray-500'}`} />
                  <span className="text-sm truncate">{page.page_title}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content Area */}
        <div className="lg:col-span-3 p-6">
          {loadingContent ? (
            <div className="flex items-center justify-center py-12">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          ) : pageContent ? (
            <div>
              {/* Page Header */}
              <div className="mb-6 pb-4 border-b border-gray-200">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  {pageContent.page_title}
                </h2>
                {pageContent.updated_at && (
                  <p className="text-sm text-gray-500">
                    Last updated: {new Date(pageContent.updated_at).toLocaleDateString()}
                  </p>
                )}
              </div>

              {/* Page Content - Sanitized HTML */}
              <div
                className="prose max-w-none prose-headings:text-gray-900 prose-a:text-primary"
                dangerouslySetInnerHTML={{
                  __html: sanitizeHTML(pageContent.content)
                }}
                style={{
                  /* Custom styles for documentation content */
                  lineHeight: '1.75',
                }}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center py-12 text-gray-500">
              <p>Select a page to view its content</p>
            </div>
          )}
        </div>
      </div>

      {/* Print Styles */}
      <style jsx>{`
        @media print {
          .sidebar {
            display: none;
          }
          .content {
            grid-column: span 4;
          }
        }
      `}</style>
    </div>
  );
};

export default AppDocumentation;
