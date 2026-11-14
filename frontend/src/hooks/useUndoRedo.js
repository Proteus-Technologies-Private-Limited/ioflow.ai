import { useState, useCallback, useEffect } from 'react';

const MAX_HISTORY_SIZE = 50;

export const useUndoRedo = (initialState) => {
  const [history, setHistory] = useState([initialState]);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Get current state
  const state = history[currentIndex];

  // Check if can undo/redo
  const canUndo = currentIndex > 0;
  const canRedo = currentIndex < history.length - 1;

  // Set new state and add to history
  const setState = useCallback((newState) => {
    setHistory(prev => {
      // Remove any states after current index (lose redo history on new change)
      const newHistory = prev.slice(0, currentIndex + 1);
      
      // Add new state
      newHistory.push(newState);
      
      // Limit history size
      if (newHistory.length > MAX_HISTORY_SIZE) {
        newHistory.shift();
        // Don't need to adjust currentIndex since we removed from beginning
      } else {
        setCurrentIndex(newHistory.length - 1);
      }
      
      return newHistory;
    });
  }, [currentIndex]);

  // Undo action
  const undo = useCallback(() => {
    if (canUndo) {
      setCurrentIndex(prev => prev - 1);
    }
  }, [canUndo]);

  // Redo action
  const redo = useCallback(() => {
    if (canRedo) {
      setCurrentIndex(prev => prev + 1);
    }
  }, [canRedo]);

  // Reset history
  const reset = useCallback((newInitialState) => {
    setHistory([newInitialState]);
    setCurrentIndex(0);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl+Z or Cmd+Z for undo
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
      }
      // Ctrl+Y or Ctrl+Shift+Z or Cmd+Shift+Z for redo
      else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        redo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo]);

  return {
    state,
    setState,
    undo,
    redo,
    canUndo,
    canRedo,
    reset,
  };
};