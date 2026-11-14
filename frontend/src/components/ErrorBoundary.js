import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  componentDidUpdate(prevProps) {
    // Clear the error when the content changes (e.g. a different node is selected),
    // otherwise one bad render keeps the fallback on screen for everything after it.
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null });
    }
  }

  componentDidCatch(error, errorInfo) {
    // You can also log the error to an error reporting service
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md">
          <h3 className="text-red-800 font-medium mb-2">Something went wrong</h3>
          <p className="text-red-600 text-sm">{this.state.error?.message || 'An error occurred'}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-2 text-sm text-red-700 underline"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;