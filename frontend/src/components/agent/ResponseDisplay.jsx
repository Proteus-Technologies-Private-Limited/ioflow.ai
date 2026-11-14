import React from 'react';

const ResponseDisplay = ({ response, error }) => {
  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <h3 className="font-semibold text-red-900 mb-2">Error</h3>
        <p className="text-red-700">{error}</p>
      </div>
    );
  }

  if (!response) {
    return (
      <div className="p-8 bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg text-center">
        <p className="text-gray-500">No response yet. Select an agent and submit a request to get started.</p>
      </div>
    );
  }

  const renderResponse = () => {
    // If response is a string, display it directly
    if (typeof response === 'string') {
      return (
        <div className="whitespace-pre-wrap text-gray-800">
          {response}
        </div>
      );
    }

    // If response is an object, display it as formatted JSON
    if (typeof response === 'object') {
      // Check if it has a specific structure (from our schema)
      if (response.summary || response.explanation || response.findings) {
        return (
          <div className="space-y-4">
            {response.summary && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Summary</h4>
                <p className="text-gray-700">{response.summary}</p>
              </div>
            )}

            {response.explanation && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Explanation</h4>
                <p className="text-gray-700">{response.explanation}</p>
              </div>
            )}

            {response.code && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Code</h4>
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
                  <code>{response.code}</code>
                </pre>
              </div>
            )}

            {response.findings && Array.isArray(response.findings) && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Findings</h4>
                <ul className="space-y-2">
                  {response.findings.map((finding, index) => (
                    <li key={index} className="bg-white p-3 rounded border border-gray-200">
                      <strong className="text-gray-900">{finding.topic}</strong>
                      <p className="text-gray-700 mt-1">{finding.details}</p>
                      {finding.source && (
                        <p className="text-sm text-gray-500 mt-1">Source: {finding.source}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {response.conclusion && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Conclusion</h4>
                <p className="text-gray-700">{response.conclusion}</p>
              </div>
            )}

            {response.test_results && (
              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Test Results</h4>
                <div className="bg-gray-100 p-3 rounded">
                  {response.test_results.executed && (
                    <p className="text-sm text-gray-600">Executed: ✓</p>
                  )}
                  {response.test_results.output && (
                    <pre className="mt-2 text-sm text-gray-800">{response.test_results.output}</pre>
                  )}
                  {response.test_results.errors && (
                    <pre className="mt-2 text-sm text-red-600">{response.test_results.errors}</pre>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      }

      // Default: display as formatted JSON
      return (
        <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
          <code>{JSON.stringify(response, null, 2)}</code>
        </pre>
      );
    }

    return <p className="text-gray-700">{String(response)}</p>;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="font-semibold text-gray-900 mb-4">Agent Response</h3>
      {renderResponse()}
    </div>
  );
};

export default ResponseDisplay;