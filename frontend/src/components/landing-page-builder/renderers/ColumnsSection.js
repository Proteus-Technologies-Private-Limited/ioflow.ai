import React from 'react';

/**
 * ColumnsSection - Multi-column layout that renders nested sections
 * Uses SectionRenderer for nested content (passed as a render prop to avoid circular imports)
 */
export default function ColumnsSection({ config, renderSection }) {
  const columns = config.columns || 2;
  const children = config.children || [];

  const gapClass = {
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
    xl: 'gap-8',
  }[config.gap || 'lg'];

  return (
    <div className="py-4">
      <div
        className={`grid grid-cols-1 md:grid-cols-${Math.min(columns, 4)} ${gapClass}`}
        style={{
          gridTemplateColumns: `repeat(${Math.min(columns, 4)}, minmax(0, 1fr))`,
        }}
      >
        {children.map((col, colIdx) => (
          <div key={colIdx} className="min-h-[50px]">
            {(col.sections || []).map((section) => renderSection(section))}
          </div>
        ))}
      </div>
    </div>
  );
}
