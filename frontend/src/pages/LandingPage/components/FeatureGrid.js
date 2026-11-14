/**
 * FeatureGrid - Grid display of features for a segment
 */

import React from 'react';
import FeatureCard from './FeatureCard';

const FeatureGrid = ({ features, onFeatureClick }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {features.map((feature, index) => (
        <FeatureCard
          key={feature.id}
          feature={feature}
          onClick={() => onFeatureClick(feature)}
          delay={index * 100}
        />
      ))}
    </div>
  );
};

export default FeatureGrid;
