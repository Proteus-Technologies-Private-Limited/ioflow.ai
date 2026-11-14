import React from 'react';

const JsonSyntaxHighlighter = ({ json }) => {
  const syntaxHighlight = (json) => {
    if (!json) return '';
    
    // Escape HTML
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Add syntax highlighting
    return json.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = 'text-gray-800'; // default
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'text-blue-700 font-medium'; // key
          } else {
            cls = 'text-green-700'; // string value
          }
        } else if (/true|false/.test(match)) {
          cls = 'text-purple-700 font-medium'; // boolean
        } else if (/null/.test(match)) {
          cls = 'text-gray-500 font-medium'; // null
        } else {
          cls = 'text-orange-700'; // number
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
  };

  return (
    <div 
      className="font-mono text-sm leading-relaxed whitespace-pre"
      style={{ 
        fontFamily: 'Consolas, Monaco, "Courier New", monospace',
        tabSize: 2 
      }}
      dangerouslySetInnerHTML={{ __html: syntaxHighlight(json) }}
    />
  );
};

export default JsonSyntaxHighlighter;