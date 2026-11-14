import React from 'react';

export default function HeroSection({ config, onCTAClick }) {
  const style = {
    backgroundColor: config.backgroundColor || '#1e293b',
    color: config.textColor || '#ffffff',
    backgroundImage: config.backgroundImage ? `url(${config.backgroundImage})` : undefined,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  };

  const paddingClass = {
    sm: 'py-8 px-4',
    md: 'py-12 px-6',
    lg: 'py-20 px-8',
    xl: 'py-28 px-8',
  }[config.padding || 'lg'];

  const alignClass = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  }[config.alignment || 'center'];

  return (
    <div className={`relative ${paddingClass}`} style={style}>
      {config.backgroundImage && (
        <div className="absolute inset-0 bg-black/40" />
      )}
      <div className={`relative max-w-4xl mx-auto ${alignClass}`}>
        {config.title && (
          <h1 className="text-3xl md:text-5xl font-bold mb-4 leading-tight">
            {config.title}
          </h1>
        )}
        {config.subtitle && (
          <p className="text-lg md:text-xl opacity-90 mb-8 max-w-2xl mx-auto">
            {config.subtitle}
          </p>
        )}
        {config.showCTA && config.ctaText && (
          <button
            onClick={() => onCTAClick?.(config.ctaScrollTo)}
            className="inline-flex items-center px-6 py-3 bg-white text-gray-900 font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105"
          >
            {config.ctaText}
          </button>
        )}
      </div>
    </div>
  );
}
