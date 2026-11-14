import React from 'react';

// Simple syntax highlighting component
function CodeBlock({ code, language, title }) {
  // Get language-specific styles
  const getLanguageClass = (lang) => {
    const langClasses = {
      curl: 'language-bash',
      python: 'language-python',
      javascript: 'language-javascript',
      java: 'language-java',
      json: 'language-json'
    };
    return langClasses[lang] || 'language-text';
  };
  
  return (
    <div>
      {title && (
        <div className="bg-gray-800 text-gray-300 px-4 py-2 text-xs font-medium rounded-t-lg">
          {title}
        </div>
      )}
      <pre className={`bg-gray-900 text-gray-100 p-4 ${title ? 'rounded-b-lg' : 'rounded-lg'} overflow-x-auto text-sm leading-relaxed font-mono`}>
        <code className={getLanguageClass(language)}>
          {code}
        </code>
      </pre>
    </div>
  );
}

export default CodeBlock;