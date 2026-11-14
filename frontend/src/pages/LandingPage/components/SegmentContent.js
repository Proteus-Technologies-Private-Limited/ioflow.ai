/**
 * SegmentContent - Dynamic content wrapper for each segment
 * Shows feature grid and interactive demo for the selected segment
 */

import React, { useState } from 'react';
import FeatureGrid from './FeatureGrid';
import DemoWalkthrough from './DemoWalkthrough';
import { segmentData } from '../data/featureContent';
import { demoContent } from '../data/demoContent';

const SegmentContent = ({ segment, onDemoAction }) => {
  const [showDemo, setShowDemo] = useState(false);
  const [activeDemoId, setActiveDemoId] = useState(null);

  const currentSegment = segmentData[segment];
  const currentDemo = demoContent[segment];

  if (!currentSegment) return null;

  const handleFeatureClick = (feature) => {
    setActiveDemoId(feature.demoId);
    setShowDemo(true);
    // Scroll to demo section
    setTimeout(() => {
      const demoSection = document.getElementById('demo-section');
      demoSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const handleCloseDemo = () => {
    setShowDemo(false);
    setActiveDemoId(null);
  };

  return (
    <div className="max-w-7xl mx-auto px-4">
      {/* Segment Header */}
      <div className="text-center mb-12">
        <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          {currentSegment.subtitle}
        </h2>
        <p className="text-lg text-gray-600 max-w-3xl mx-auto">
          {currentSegment.description}
        </p>
      </div>

      {/* Feature Grid */}
      <FeatureGrid
        features={currentSegment.features}
        onFeatureClick={handleFeatureClick}
      />

      {/* Demo Section */}
      <div id="demo-section" className="mt-16" style={{ scrollMarginTop: '120px' }}>
        <div className="text-center mb-8">
          <h3 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
            See It In Action
          </h3>
          <p className="text-gray-600">
            {currentDemo.description}
          </p>
        </div>

        <DemoWalkthrough
          demo={currentDemo}
          isOpen={showDemo}
          onClose={handleCloseDemo}
          onAction={onDemoAction}
        />
      </div>
    </div>
  );
};

export default SegmentContent;
