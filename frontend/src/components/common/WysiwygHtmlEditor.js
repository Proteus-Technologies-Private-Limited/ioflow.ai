import React, { useRef, useEffect, useState } from 'react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import {
  CodeBracketIcon,
  EyeIcon,
  PencilIcon
} from '@heroicons/react/24/outline';

const WysiwygHtmlEditor = ({ 
  value = '', 
  onChange, 
  placeholder = 'Enter HTML content...', 
  disabled = false,
  height = 200 
}) => {
  const [mode, setMode] = useState('wysiwyg'); // 'wysiwyg', 'code', 'preview'
  const [localValue, setLocalValue] = useState(value);
  const quillRef = useRef(null);

  // Update local value when prop changes
  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  // Quill modules configuration
  const modules = {
    toolbar: [
      [{ 'header': [1, 2, 3, false] }],
      ['bold', 'italic', 'underline', 'strike'],
      [{ 'color': [] }, { 'background': [] }],
      [{ 'list': 'ordered'}, { 'list': 'bullet' }],
      [{ 'indent': '-1'}, { 'indent': '+1' }],
      ['link', 'image'],
      [{ 'align': [] }],
      ['blockquote', 'code-block'],
      ['clean']
    ],
  };

  // Quill formats
  const formats = [
    'header', 'bold', 'italic', 'underline', 'strike',
    'color', 'background', 'list', 'bullet', 'indent',
    'link', 'image', 'align', 'blockquote', 'code-block'
  ];

  const handleWysiwygChange = (content) => {
    setLocalValue(content);
    onChange(content);
  };

  const handleCodeChange = (e) => {
    const content = e.target.value;
    setLocalValue(content);
    onChange(content);
  };

  const renderModeButtons = () => (
    <div className="flex space-x-1 mb-2">
      <button
        type="button"
        onClick={() => setMode('wysiwyg')}
        className={`flex items-center space-x-1 px-2 py-1 text-xs rounded ${
          mode === 'wysiwyg' 
            ? 'bg-blue-100 text-blue-700' 
            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
        }`}
        disabled={disabled}
      >
        <PencilIcon className="w-3 h-3" />
        <span>WYSIWYG</span>
      </button>
      
      <button
        type="button"
        onClick={() => setMode('code')}
        className={`flex items-center space-x-1 px-2 py-1 text-xs rounded ${
          mode === 'code' 
            ? 'bg-blue-100 text-blue-700' 
            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
        }`}
        disabled={disabled}
      >
        <CodeBracketIcon className="w-3 h-3" />
        <span>HTML</span>
      </button>
      
      <button
        type="button"
        onClick={() => setMode('preview')}
        className={`flex items-center space-x-1 px-2 py-1 text-xs rounded ${
          mode === 'preview' 
            ? 'bg-blue-100 text-blue-700' 
            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
        }`}
        disabled={disabled}
      >
        <EyeIcon className="w-3 h-3" />
        <span>Preview</span>
      </button>
    </div>
  );

  const renderEditor = () => {
    switch (mode) {
      case 'wysiwyg':
        return (
          <div className="border border-gray-300 rounded-md">
            <ReactQuill
              ref={quillRef}
              theme="snow"
              value={localValue}
              onChange={handleWysiwygChange}
              placeholder={placeholder}
              readOnly={disabled}
              modules={modules}
              formats={formats}
              style={{ height: `${height}px` }}
            />
          </div>
        );

      case 'code':
        return (
          <textarea
            value={localValue}
            onChange={handleCodeChange}
            rows={Math.max(8, height / 25)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
            placeholder={placeholder}
            disabled={disabled}
          />
        );

      case 'preview':
        return (
          <div 
            className="border border-gray-300 rounded-md p-3 bg-white overflow-auto"
            style={{ minHeight: `${height}px`, maxHeight: `${height * 1.5}px` }}
          >
            {localValue ? (
              <div 
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: localValue }} 
              />
            ) : (
              <div className="text-gray-400 italic">No content to preview</div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="wysiwyg-html-editor">
      {renderModeButtons()}
      
      <div className="editor-container">
        {renderEditor()}
      </div>
      
      {mode === 'wysiwyg' && (
        <div className="mt-1 text-xs text-gray-500">
          💡 Use the toolbar to format your content visually
        </div>
      )}
      
      {mode === 'code' && (
        <div className="mt-1 text-xs text-gray-500">
          💡 Edit HTML code directly - changes will be reflected in WYSIWYG mode
        </div>
      )}
      
      {mode === 'preview' && (
        <div className="mt-1 text-xs text-gray-500">
          👁️ Preview how your HTML content will be displayed
        </div>
      )}

      {/* Additional CSS for Quill customization */}
      <style jsx>{`
        .ql-editor {
          min-height: ${height - 42}px;
        }
        
        .ql-toolbar.ql-snow {
          border-top: 1px solid #e5e7eb;
          border-left: 1px solid #e5e7eb;
          border-right: 1px solid #e5e7eb;
          border-top-left-radius: 0.375rem;
          border-top-right-radius: 0.375rem;
        }
        
        .ql-container.ql-snow {
          border-bottom: 1px solid #e5e7eb;
          border-left: 1px solid #e5e7eb;
          border-right: 1px solid #e5e7eb;
          border-bottom-left-radius: 0.375rem;
          border-bottom-right-radius: 0.375rem;
        }
        
        .prose h1 {
          font-size: 1.5rem;
          font-weight: bold;
          margin-bottom: 0.5rem;
        }
        
        .prose h2 {
          font-size: 1.25rem;
          font-weight: bold;
          margin-bottom: 0.5rem;
        }
        
        .prose h3 {
          font-size: 1.125rem;
          font-weight: bold;
          margin-bottom: 0.5rem;
        }
        
        .prose p {
          margin-bottom: 0.75rem;
        }
        
        .prose ul, .prose ol {
          margin-bottom: 0.75rem;
          padding-left: 1.5rem;
        }
        
        .prose blockquote {
          border-left: 4px solid #e5e7eb;
          padding-left: 1rem;
          margin: 1rem 0;
          font-style: italic;
          color: #6b7280;
        }
        
        .prose code {
          background-color: #f3f4f6;
          padding: 0.125rem 0.25rem;
          border-radius: 0.25rem;
          font-family: monospace;
          font-size: 0.875rem;
        }
        
        .prose pre {
          background-color: #f3f4f6;
          padding: 1rem;
          border-radius: 0.375rem;
          overflow-x: auto;
          margin: 1rem 0;
        }
        
        .prose a {
          color: #2563eb;
          text-decoration: underline;
        }
        
        .prose a:hover {
          color: #1d4ed8;
        }
        
        .prose img {
          max-width: 100%;
          height: auto;
          border-radius: 0.375rem;
        }
      `}</style>
    </div>
  );
};

export default WysiwygHtmlEditor;