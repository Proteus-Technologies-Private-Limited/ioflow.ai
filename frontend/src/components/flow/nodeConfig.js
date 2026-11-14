// Default node dimensions configuration
export const DEFAULT_NODE_DIMENSIONS = {
  width: 200,   // Default width
  height: 100,  // Default height
  minWidth: 90,  // Minimum width
  minHeight: 90, // Minimum height
  maxWidth: 800,  // Allow wider nodes
  maxHeight: 300,
};

// Resize handle styles
export const RESIZE_HANDLE_STYLES = {
  lineStyle: {
    borderWidth: 2,
    borderColor: '#3b82f6',
  },
  handleStyle: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: '#3b82f6',
    border: '2px solid #fff',
  },
};