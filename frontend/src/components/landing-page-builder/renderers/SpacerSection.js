import React from 'react';

export default function SpacerSection({ config }) {
  return <div style={{ height: config.height || '48px' }} />;
}
