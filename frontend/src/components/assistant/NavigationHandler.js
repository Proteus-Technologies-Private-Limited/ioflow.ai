import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { CommandLineIcon } from '@heroicons/react/24/outline';

// Comprehensive navigation dictionary with multiple keywords for each page
const NAVIGATION_DICTIONARY = {
  // Dashboard
  dashboard: {
    path: '/dashboard',
    keywords: ['dashboard', 'home', 'main', 'overview', 'summary', 'stats', 'statistics'],
    description: 'Dashboard - Overview and statistics'
  },

  // Applications Management
  applications: {
    path: '/applications',
    keywords: ['apps', 'application', 'applications', 'app list', 'application list', 'manage apps', 'api apps', 'integrations', 'connectors', 'services'],
    description: 'Applications - Manage your applications'
  },

  newApplication: {
    path: '/applications/new',
    keywords: ['new app', 'create app', 'add app', 'new application', 'create application', 'add application', 'register app'],
    description: 'New Application - Create a new application'
  },

  // Flow Designer
  flows: {
    path: '/flows',
    keywords: ['flow', 'flows', 'flow design', 'design flow', 'io flow', 'ioflow', 'workflow', 'workflows', 'automation', 'automations', 'process', 'processes', 'pipeline', 'pipelines'],
    description: 'Flows - Design and manage workflows'
  },

  newFlow: {
    path: '/flows/new',
    keywords: ['new flow', 'create flow', 'design new flow', 'add flow', 'new workflow', 'create workflow', 'new automation', 'build flow'],
    description: 'New Flow - Create a new workflow'
  },

  // Executions
  executions: {
    path: '/executions',
    keywords: ['executions', 'execution', 'runs', 'flow runs', 'history', 'execution history', 'logs', 'run logs', 'results', 'flow results'],
    description: 'Executions - View flow execution history'
  },

  // Polling Logs
  pollingLogs: {
    path: '/polling-logs',
    keywords: ['polling', 'polling logs', 'poll logs', 'scheduled', 'scheduled tasks', 'cron', 'periodic', 'webhook logs'],
    description: 'Polling Logs - View polling and webhook logs'
  },

  // MCP Services
  mcpServices: {
    path: '/mcp-services',
    keywords: ['mcp', 'mcp services', 'model context', 'model context protocol', 'ai services', 'llm services', 'ai integrations'],
    description: 'MCP Services - Model Context Protocol services'
  },

  // Assistant
  assistant: {
    path: '/assistant',
    keywords: ['assistant', 'ai assistant', 'chat', 'ai chat', 'help', 'ai help', 'copilot', 'ai copilot'],
    description: 'Assistant - AI-powered assistant'
  },

  // Published Applications
  publishedApps: {
    path: '/published-applications',
    keywords: ['published', 'published apps', 'published applications', 'marketplace', 'store', 'app store', 'public apps', 'shared apps'],
    description: 'Published Applications - Browse published apps'
  },

  // Settings
  settings: {
    path: '/settings',
    keywords: ['settings', 'setting', 'preferences', 'config', 'configuration', 'options', 'setup', 'account settings', 'profile'],
    description: 'Settings - Configure your account'
  },

  // Billing
  billing: {
    path: '/billing',
    keywords: ['billing', 'bill', 'payment', 'payments', 'invoice', 'invoices', 'charges', 'cost', 'pricing', 'subscription fee'],
    description: 'Billing - Manage billing and payments'
  },

  // Subscription
  subscription: {
    path: '/subscription',
    keywords: ['subscription', 'subscribe', 'plan', 'plans', 'upgrade', 'downgrade', 'tier', 'package', 'premium', 'pro'],
    description: 'Subscription - Manage your subscription'
  },

  // Admin pages
  adminUsers: {
    path: '/admin/users',
    keywords: ['users', 'user management', 'manage users', 'admin users', 'user admin', 'team', 'team members', 'members'],
    description: 'User Management - Manage users (Admin)'
  },

  adminSeed: {
    path: '/admin/seed-applications',
    keywords: ['seed', 'seed apps', 'seed applications', 'admin seed', 'templates', 'app templates', 'starter apps'],
    description: 'Seed Applications - Manage templates (Admin)'
  },

  adminTenants: {
    path: '/admin/tenants',
    keywords: ['tenants', 'tenant', 'tenant management', 'admin tenants', 'organizations', 'orgs', 'companies'],
    description: 'Tenant Management - Manage tenants (Admin)'
  },

  adminAgents: {
    path: '/admin/agents',
    keywords: ['agents', 'agent', 'agent management', 'admin agents', 'ai agents', 'bots'],
    description: 'Agent Management - Manage AI agents (Admin)'
  }
};

// Helper function to check if input matches any keyword
function findMatchingPages(input) {
  if (!input) return [];

  const searchTerm = input.toLowerCase().trim();
  const matches = [];

  for (const [key, config] of Object.entries(NAVIGATION_DICTIONARY)) {
    // Check for exact match first
    const exactMatch = config.keywords.some(keyword =>
      keyword.toLowerCase() === searchTerm
    );

    if (exactMatch) {
      matches.push({ ...config, key, score: 100 });
      continue;
    }

    // Check for partial matches
    const partialMatch = config.keywords.some(keyword =>
      keyword.toLowerCase().includes(searchTerm) ||
      searchTerm.includes(keyword.toLowerCase())
    );

    if (partialMatch) {
      // Calculate score based on match quality
      const bestMatch = config.keywords.reduce((best, keyword) => {
        const kwLower = keyword.toLowerCase();
        if (kwLower === searchTerm) return 100;
        if (kwLower.startsWith(searchTerm)) return Math.max(best, 80);
        if (kwLower.includes(searchTerm)) return Math.max(best, 60);
        if (searchTerm.includes(kwLower)) return Math.max(best, 40);
        return best;
      }, 0);

      matches.push({ ...config, key, score: bestMatch });
    }
  }

  // Sort by score (highest first)
  return matches.sort((a, b) => b.score - a.score);
}

function NavigationHandler({
  inputText,
  onInputChange,
  onNavigate,
  onNonNavigationInput
}) {
  const navigate = useNavigate();
  const [suggestions, setSuggestions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionsRef = useRef(null);

  // Update suggestions when input changes
  useEffect(() => {
    if (inputText && inputText.trim()) {
      const matches = findMatchingPages(inputText);
      setSuggestions(matches.slice(0, 5)); // Show top 5 suggestions
      setShowSuggestions(matches.length > 0);
      setSelectedIndex(-1);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
      setSelectedIndex(-1);
    }
  }, [inputText]);

  // Handle keyboard navigation in suggestions
  const handleKeyDown = (e) => {
    if (!showSuggestions) return false;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        return true;

      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
        return true;

      case 'Tab':
        if (suggestions.length > 0) {
          e.preventDefault();
          const index = selectedIndex >= 0 ? selectedIndex : 0;
          handleNavigate(suggestions[index]);
          return true;
        }
        break;

      case 'Escape':
        setShowSuggestions(false);
        setSelectedIndex(-1);
        return true;
    }

    return false;
  };

  // Handle Enter key - check if it's a navigation command
  const handleEnter = () => {
    // If a suggestion is selected, navigate to it
    if (showSuggestions && selectedIndex >= 0 && suggestions[selectedIndex]) {
      handleNavigate(suggestions[selectedIndex]);
      return true;
    }

    // Check for exact match
    const trimmedInput = inputText.trim().toLowerCase();
    const matches = findMatchingPages(trimmedInput);

    if (matches.length > 0 && matches[0].score >= 80) {
      // High confidence match - navigate directly
      handleNavigate(matches[0]);
      return true;
    }

    // Not a navigation command
    return false;
  };

  // Navigate to a page
  const handleNavigate = (page) => {
    navigate(page.path);
    onNavigate(page); // Notify parent that navigation occurred
    onInputChange(''); // Clear input
    setShowSuggestions(false);
    setSuggestions([]);
  };

  // Check if current input is a potential navigation command
  const isNavigationCommand = () => {
    const trimmedInput = inputText.trim().toLowerCase();
    return findMatchingPages(trimmedInput).length > 0;
  };

  return {
    suggestions,
    showSuggestions,
    selectedIndex,
    handleKeyDown,
    handleEnter,
    isNavigationCommand,
    navigateToPage: handleNavigate,

    // Render suggestions component
    renderSuggestions: () => (
      showSuggestions && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-y-auto z-50"
        >
          <div className="p-2">
            <div className="text-xs text-gray-500 px-2 py-1 flex items-center gap-1">
              <CommandLineIcon className="h-3 w-3" />
              Quick Navigation
            </div>
            {suggestions.map((suggestion, index) => (
              <button
                key={suggestion.key}
                onClick={() => handleNavigate(suggestion)}
                onMouseEnter={() => setSelectedIndex(index)}
                className={`
                  w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                  ${index === selectedIndex
                    ? 'bg-blue-50 text-blue-700'
                    : 'hover:bg-gray-50 text-gray-700'
                  }
                `}
              >
                <div className="font-medium">{suggestion.description.split(' - ')[0]}</div>
                <div className="text-xs text-gray-500">
                  {suggestion.description.split(' - ')[1]}
                </div>
              </button>
            ))}
            <div className="text-xs text-gray-400 px-2 py-1 mt-1 border-t">
              Press Tab or ↑↓ to navigate, Enter to select
            </div>
          </div>
        </div>
      )
    )
  };
}

// Export the navigation dictionary for external use
export { NAVIGATION_DICTIONARY, findMatchingPages };
export default NavigationHandler;