import React from 'react';
import { ChatBubbleBottomCenterTextIcon, SignalIcon, SignalSlashIcon } from '@heroicons/react/24/outline';
import { useLayout } from '../../contexts/LayoutContext';

function FloatingAssistantButton({ connectionStatus = 'disconnected' }) {
  const { setIsFloatingAssistantOpen } = useLayout();

  return (
    <button
      onClick={() => setIsFloatingAssistantOpen(true)}
      className="fixed bottom-6 right-6 z-40 bg-primary-600 text-white rounded-full p-4 shadow-lg hover:bg-primary-700 transition-all transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
      title="Open Assistant"
    >
      <div className="relative">
        <ChatBubbleBottomCenterTextIcon className="h-6 w-6" />

        {/* Connection Status Indicator */}
        <div className="absolute -top-1 -right-1">
          {connectionStatus === 'connected' ? (
            <span className="flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
            </span>
          ) : connectionStatus === 'connecting' ? (
            <span className="flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span>
            </span>
          ) : (
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          )}
        </div>
      </div>
    </button>
  );
}

export default FloatingAssistantButton;