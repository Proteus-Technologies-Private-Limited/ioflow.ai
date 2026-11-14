import React, { useState, useEffect, useCallback } from 'react';
import DesignerToolbar from './DesignerToolbar';
import BlockList from './BlockList';
import ThemeEditor from './ThemeEditor';
import CustomLandingPageRenderer from '../renderers/CustomLandingPageRenderer';
import { getDefaultConfig } from '../blockTypes';
import axios from 'axios';
import { microSaasService } from '../../../services/microSaasService';
import { getAppDocumentationPages } from '../../../services/documentationService';
import { showErrorToast, showSuccessToast } from '../../../utils/customToast';

const DEFAULT_THEME = {
  primaryColor: '#0891b2',
  backgroundColor: '#f9fafb',
  fontFamily: 'Inter, system-ui, sans-serif',
  borderRadius: '8px',
  maxWidth: '1200px',
};

/**
 * LandingPageDesignerTab - Main designer component with split pane
 * Left: Block list with configs | Right: Live preview
 */
export default function LandingPageDesignerTab({ app }) {
  const [definition, setDefinition] = useState(null);
  const [originalDefinition, setOriginalDefinition] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [showThemeEditor, setShowThemeEditor] = useState(false);
  const [manualVariables, setManualVariables] = useState([]);
  const [documentationPages, setDocumentationPages] = useState([]);
  const [hasHITLNode, setHasHITLNode] = useState(false);

  const appId = app?.frontend_app_id;

  // Load existing page definition
  useEffect(() => {
    loadPageDefinition();
    loadManualVariables();
    loadDocumentationPages();
    detectHITLNodes();
  }, [appId]);

  const loadPageDefinition = async () => {
    setLoading(true);
    try {
      const data = await microSaasService.getPageDefinition(appId);
      const pageDef = data.page_definition || createDefaultDefinition();
      setDefinition(pageDef);
      setOriginalDefinition(JSON.stringify(pageDef));
    } catch (err) {
      // No existing definition — start with default
      const defaultDef = createDefaultDefinition();
      setDefinition(defaultDef);
      setOriginalDefinition(JSON.stringify(defaultDef));
    } finally {
      setLoading(false);
    }
  };

  const loadManualVariables = async () => {
    try {
      const slug = app?.public_url_slug;
      if (!slug) return;
      const resp = await fetch(`/api/v1/public-apps/${slug}/info`);
      if (resp.ok) {
        const data = await resp.json();
        setManualVariables(data.manual_variables || []);
      }
    } catch {
      // Ignore
    }
  };

  const detectHITLNodes = async () => {
    try {
      const flowId = app?.flow_id;
      if (!flowId) return;
      const resp = await axios.get(`/api/v1/flows/${flowId}`);
      if (resp.data) {
        const flowDef = resp.data.flow_definition || resp.data;
        const nodes = flowDef.nodes || [];
        const found = nodes.some(
          (n) => n.type === 'humanInLoop' || n.type === 'human_in_loop' || n.data?.type === 'humanInLoop'
        );
        setHasHITLNode(found);
      }
    } catch {
      // Ignore
    }
  };

  const loadDocumentationPages = async () => {
    try {
      if (!appId) return;
      const data = await getAppDocumentationPages(appId);
      const pages = (data.pages || data || [])
        .filter((p) => p.is_published !== false)
        .map((p) => ({
          page_id: p.page_id,
          title: p.title || p.page_title,
          slug: p.slug || p.page_slug,
          page_type: p.page_type,
          display_order: p.display_order || 0,
        }));
      setDocumentationPages(pages);
    } catch {
      // Ignore — app may not have docs
    }
  };

  const createDefaultDefinition = () => ({
    version: '1.0',
    theme: { ...DEFAULT_THEME },
    sections: [
      {
        id: crypto.randomUUID(),
        type: 'hero',
        config: {
          ...getDefaultConfig('hero'),
          title: app?.frontend_app_name || 'Welcome',
          subtitle: app?.description || '',
        },
      },
      {
        id: crypto.randomUUID(),
        type: 'trigger_form',
        config: getDefaultConfig('trigger_form'),
      },
      {
        id: crypto.randomUUID(),
        type: 'execution_display',
        config: getDefaultConfig('execution_display'),
      },
      {
        id: crypto.randomUUID(),
        type: 'result_display',
        config: getDefaultConfig('result_display'),
      },
    ],
  });

  const hasChanges = definition && JSON.stringify(definition) !== originalDefinition;

  const handleAddBlock = useCallback((type) => {
    const newSection = {
      id: crypto.randomUUID(),
      type,
      config: getDefaultConfig(type),
    };
    setDefinition((prev) => ({
      ...prev,
      sections: [...(prev?.sections || []), newSection],
    }));
  }, []);

  const handleSectionsChange = useCallback((newSections) => {
    setDefinition((prev) => ({ ...prev, sections: newSections }));
  }, []);

  const handleThemeChange = useCallback((newTheme) => {
    setDefinition((prev) => ({ ...prev, theme: newTheme }));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await microSaasService.updatePageDefinition(appId, definition);
      setOriginalDefinition(JSON.stringify(definition));
      showSuccessToast('Landing page saved successfully');
    } catch (err) {
      showErrorToast('Failed to save landing page');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset to default layout? This will remove your custom landing page.')) return;
    try {
      await microSaasService.deletePageDefinition(appId);
      const defaultDef = createDefaultDefinition();
      setDefinition(defaultDef);
      setOriginalDefinition(JSON.stringify(null));
      showSuccessToast('Landing page reset to default');
    } catch (err) {
      showErrorToast('Failed to reset landing page');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  // Build mock appInfo for preview
  const mockAppInfo = {
    frontend_app_name: app?.frontend_app_name,
    description: app?.description,
    manual_variables: manualVariables,
    billing_preference: app?.billing_preference,
    documentation_pages: documentationPages,
    flow_id: app?.flow_id,
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <DesignerToolbar
        onAddBlock={handleAddBlock}
        showPreview={showPreview}
        onTogglePreview={() => setShowPreview(!showPreview)}
        onThemeClick={() => setShowThemeEditor(true)}
        onSave={handleSave}
        onReset={handleReset}
        saving={saving}
        hasChanges={hasChanges}
        hasHITLNode={hasHITLNode}
      />

      {/* Split Pane */}
      <div className={`flex gap-4 ${showPreview ? '' : ''}`}>
        {/* Left: Block List */}
        <div className={`${showPreview ? 'w-1/2' : 'w-full'} shrink-0`}>
          <div className="bg-gray-50 rounded-lg border border-gray-200 p-3 max-h-[calc(100vh-220px)] overflow-y-auto">
            <BlockList
              sections={definition?.sections || []}
              onSectionsChange={handleSectionsChange}
              appId={appId}
              manualVariables={manualVariables}
            />
          </div>
        </div>

        {/* Right: Live Preview */}
        {showPreview && (
          <div className="w-1/2 shrink-0">
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden max-h-[calc(100vh-220px)] overflow-y-auto">
              <div className="bg-gray-100 px-3 py-1.5 border-b border-gray-200 flex items-center gap-2">
                <div className="flex gap-1">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
                  <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                </div>
                <span className="text-xs text-gray-500 ml-2">Preview</span>
              </div>
              <div className="transform scale-[0.65] origin-top-left" style={{ width: '153.8%' }}>
                <CustomLandingPageRenderer
                  definition={definition}
                  appInfo={mockAppInfo}
                  slug={app?.public_url_slug}
                  previewMode={true}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Theme Editor Modal */}
      {showThemeEditor && (
        <ThemeEditor
          theme={definition?.theme || DEFAULT_THEME}
          onChange={handleThemeChange}
          onClose={() => setShowThemeEditor(false)}
        />
      )}
    </div>
  );
}
