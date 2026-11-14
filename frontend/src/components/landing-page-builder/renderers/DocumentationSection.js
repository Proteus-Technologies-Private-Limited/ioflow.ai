import React, { useState, useEffect } from 'react';
import DOMPurify from 'dompurify';

const getPageSlug = (page) => page?.page_slug || page?.slug || '';

export default function DocumentationSection({ config, slug, documentationPages, previewMode }) {
  const [pages, setPages] = useState([]);
  const [activePageIdx, setActivePageIdx] = useState(0);
  const [pageContents, setPageContents] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (config.showAllPages && documentationPages) {
      setPages(documentationPages);
    } else if (config.pageIds?.length > 0 && documentationPages) {
      const filtered = documentationPages.filter((p) => config.pageIds.includes(p.page_id));
      setPages(filtered);
    } else if (documentationPages) {
      setPages(documentationPages);
    }
  }, [config, documentationPages]);

  const fetchPageContent = async (pageSlug) => {
    if (pageContents[pageSlug] || !slug) return;
    setLoading(true);
    try {
      const resp = await fetch(`/api/v1/marketplace/apps/${slug}/documentation/${pageSlug}`);
      if (resp.ok) {
        const data = await resp.json();
        setPageContents((prev) => ({ ...prev, [pageSlug]: data.content }));
      } else {
        setPageContents((prev) => ({ ...prev, [pageSlug]: '<p>Content not available</p>' }));
      }
    } catch {
      setPageContents((prev) => ({ ...prev, [pageSlug]: '<p>Failed to load content</p>' }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (pages.length > 0 && pages[activePageIdx]) {
      const ps = pages[activePageIdx].page_slug || pages[activePageIdx].slug;
      if (ps) fetchPageContent(ps);
    }
  }, [activePageIdx, pages]);

  if (pages.length === 0) {
    return previewMode ? (
      <div className="py-6">
        {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-400 text-sm">Documentation pages will appear here</p>
        </div>
      </div>
    ) : null;
  }

  const layout = config.layout || 'tabs';

  return (
    <div className="py-6">
      {config.title && (
        <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>
      )}

      {layout === 'tabs' ? (
        <div>
          <div className="border-b border-gray-200 mb-4">
            <nav className="-mb-px flex space-x-6 overflow-x-auto">
              {pages.map((page, idx) => (
                <button
                  key={page.page_id}
                  onClick={() => setActivePageIdx(idx)}
                  className={`whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activePageIdx === idx
                      ? 'border-primary text-primary'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {page.title}
                </button>
              ))}
            </nav>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-6 min-h-[200px]">
            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : (
              <div
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(
                    pageContents[getPageSlug(pages[activePageIdx])] || '<p>Loading...</p>'
                  ),
                }}
              />
            )}
          </div>
        </div>
      ) : (
        /* Accordion layout */
        <div className="space-y-3">
          {pages.map((page, idx) => (
            <div key={page.page_id} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => {
                  setActivePageIdx(activePageIdx === idx ? -1 : idx);
                  fetchPageContent(getPageSlug(page));
                }}
                className="w-full flex items-center justify-between p-4 text-left font-medium text-gray-900 hover:bg-gray-50"
              >
                {page.title}
                <span className="text-gray-400">{activePageIdx === idx ? '-' : '+'}</span>
              </button>
              {activePageIdx === idx && (
                <div className="p-4 border-t border-gray-100">
                  <div
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: DOMPurify.sanitize(pageContents[getPageSlug(page)] || '<p>Loading...</p>'),
                    }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
