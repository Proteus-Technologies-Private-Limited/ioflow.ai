import React from 'react';
import DOMPurify from 'dompurify';

export default function TextSection({ config }) {
  const paddingClass = {
    sm: 'py-4',
    md: 'py-8',
    lg: 'py-12',
  }[config.padding || 'md'];

  const sanitizedContent = DOMPurify.sanitize(config.content || '');

  return (
    <div className={paddingClass}>
      <div
        className="prose prose-sm sm:prose max-w-none"
        dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      />
    </div>
  );
}
