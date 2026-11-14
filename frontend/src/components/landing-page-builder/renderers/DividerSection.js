import React from 'react';

export default function DividerSection({ config }) {
  const marginClass = {
    sm: 'my-4',
    md: 'my-8',
    lg: 'my-12',
  }[config.margin || 'md'];

  return (
    <hr
      className={marginClass}
      style={{ borderColor: config.color || '#e5e7eb' }}
    />
  );
}
