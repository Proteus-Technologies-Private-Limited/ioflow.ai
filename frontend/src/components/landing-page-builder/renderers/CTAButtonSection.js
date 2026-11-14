import React from 'react';

export default function CTAButtonSection({ config, onCTAClick }) {
  const alignClass = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  }[config.alignment || 'center'];

  const styleClass = {
    primary: 'bg-gradient-primary text-white hover:shadow-lg',
    secondary: 'bg-white text-gray-900 border border-gray-300 hover:bg-gray-50',
    accent: 'bg-gradient-accent text-white hover:shadow-lg',
  }[config.style || 'primary'];

  const handleClick = () => {
    if (config.externalUrl) {
      window.open(config.externalUrl, '_blank', 'noopener,noreferrer');
    } else if (config.scrollTo) {
      onCTAClick?.(config.scrollTo);
    }
  };

  return (
    <div className={`py-4 ${alignClass}`}>
      <button
        onClick={handleClick}
        className={`inline-flex items-center px-8 py-3 font-semibold rounded-lg shadow transition-all duration-200 ${styleClass}`}
      >
        {config.text || 'Click Here'}
      </button>
    </div>
  );
}
