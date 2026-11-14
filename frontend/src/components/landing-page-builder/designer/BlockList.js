import React, { useState } from 'react';
import BlockWrapper from './BlockWrapper';

/**
 * BlockList - Drag-drop sortable list of blocks
 */
export default function BlockList({
  sections,
  onSectionsChange,
  appId,
  manualVariables,
}) {
  const [dragIndex, setDragIndex] = useState(null);

  const handleUpdate = (index, updatedSection) => {
    const newSections = [...sections];
    newSections[index] = updatedSection;
    onSectionsChange(newSections);
  };

  const handleDelete = (index) => {
    const newSections = sections.filter((_, i) => i !== index);
    onSectionsChange(newSections);
  };

  const handleDuplicate = (index) => {
    const original = sections[index];
    const duplicate = {
      ...JSON.parse(JSON.stringify(original)),
      id: crypto.randomUUID(),
    };
    const newSections = [...sections];
    newSections.splice(index + 1, 0, duplicate);
    onSectionsChange(newSections);
  };

  const handleMoveUp = (index) => {
    if (index === 0) return;
    const newSections = [...sections];
    [newSections[index - 1], newSections[index]] = [newSections[index], newSections[index - 1]];
    onSectionsChange(newSections);
  };

  const handleMoveDown = (index) => {
    if (index === sections.length - 1) return;
    const newSections = [...sections];
    [newSections[index], newSections[index + 1]] = [newSections[index + 1], newSections[index]];
    onSectionsChange(newSections);
  };

  // Drag handlers
  const handleDragStart = (e, index) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, dropIndex) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === dropIndex) return;

    const newSections = [...sections];
    const [moved] = newSections.splice(dragIndex, 1);
    newSections.splice(dropIndex, 0, moved);
    onSectionsChange(newSections);
    setDragIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
  };

  if (sections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </div>
        <p className="text-sm text-gray-500 mb-1">No sections yet</p>
        <p className="text-xs text-gray-400">Click "Add Block" to start building your landing page</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {sections.map((section, index) => (
        <BlockWrapper
          key={section.id}
          section={section}
          index={index}
          total={sections.length}
          onUpdate={(updated) => handleUpdate(index, updated)}
          onDelete={() => handleDelete(index)}
          onDuplicate={() => handleDuplicate(index)}
          onMoveUp={() => handleMoveUp(index)}
          onMoveDown={() => handleMoveDown(index)}
          appId={appId}
          manualVariables={manualVariables}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onDragEnd={handleDragEnd}
          isDragging={dragIndex === index}
        />
      ))}
    </div>
  );
}
