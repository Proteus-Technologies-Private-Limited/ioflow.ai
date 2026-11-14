import React, { createContext, useContext, useState, useEffect } from 'react';

const LayoutContext = createContext();

export const LAYOUT_MODES = {
  ASSISTANT_PANEL: 'assistant_panel',
  CLASSIC: 'classic'
};

export const LayoutProvider = ({ children }) => {
  // Initialize from localStorage or use default (classic)
  const [layoutMode, setLayoutMode] = useState(() => {
    const saved = localStorage.getItem('layout_mode');
    return saved || LAYOUT_MODES.CLASSIC;
  });

  // Track if assistant panel is open (for mobile/tablet views in assistant layout)
  const [isAssistantPanelOpen, setIsAssistantPanelOpen] = useState(false);

  // Track if floating assistant is open (for classic layout)
  const [isFloatingAssistantOpen, setIsFloatingAssistantOpen] = useState(false);

  // Pending message to be sent to assistant when panel opens
  const [pendingAssistantMessage, setPendingAssistantMessage] = useState(null);

  // Save to localStorage whenever layout mode changes
  useEffect(() => {
    localStorage.setItem('layout_mode', layoutMode);
  }, [layoutMode]);

  const toggleLayoutMode = () => {
    const newMode = layoutMode === LAYOUT_MODES.ASSISTANT_PANEL
      ? LAYOUT_MODES.CLASSIC
      : LAYOUT_MODES.ASSISTANT_PANEL;

    setLayoutMode(newMode);

    // Reset assistant states when switching modes
    setIsAssistantPanelOpen(false);
    setIsFloatingAssistantOpen(false);
  };

  const value = {
    layoutMode,
    setLayoutMode,
    toggleLayoutMode,
    isAssistantLayout: layoutMode === LAYOUT_MODES.ASSISTANT_PANEL,
    isClassicLayout: layoutMode === LAYOUT_MODES.CLASSIC,
    isAssistantPanelOpen,
    setIsAssistantPanelOpen,
    isFloatingAssistantOpen,
    setIsFloatingAssistantOpen,
    pendingAssistantMessage,
    setPendingAssistantMessage
  };

  return (
    <LayoutContext.Provider value={value}>
      {children}
    </LayoutContext.Provider>
  );
};

export const useLayout = () => {
  const context = useContext(LayoutContext);
  if (!context) {
    throw new Error('useLayout must be used within a LayoutProvider');
  }
  return context;
};