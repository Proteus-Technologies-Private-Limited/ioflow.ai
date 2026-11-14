/**
 * FeatureCard - Individual feature display card
 */

import React from 'react';
import {
  Plug,
  Brain,
  FileStack,
  Database,
  Code2,
  Webhook,
  Workflow,
  Store,
  CreditCard,
  BarChart3,
  BookOpen,
  Users,
  Search,
  MousePointerClick,
  Play,
  FileText,
  Link,
  Clock,
  ArrowRight,
  Sparkles
} from 'lucide-react';

// Icon mapping
const iconMap = {
  Plug,
  Brain,
  FileStack,
  Database,
  Code2,
  Webhook,
  Workflow,
  Store,
  CreditCard,
  BarChart3,
  BookOpen,
  Users,
  Search,
  MousePointerClick,
  Play,
  FileText,
  Link,
  Clock,
  Sparkles
};

const FeatureCard = ({ feature, onClick, delay = 0 }) => {
  const Icon = iconMap[feature.icon] || Plug;

  return (
    <div
      onClick={onClick}
      className="group bg-white rounded-xl shadow-md hover:shadow-xl border border-gray-200 p-6 cursor-pointer transition-all duration-300 hover:-translate-y-1"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Icon */}
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-gradient-to-br from-primary/20 to-secondary/20 text-primary mb-4 group-hover:from-primary group-hover:to-secondary group-hover:text-white transition-all duration-300">
        <Icon className="w-6 h-6" />
      </div>

      {/* Title */}
      <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-primary transition-colors">
        {feature.title}
      </h3>

      {/* Description */}
      <p className="text-gray-600 text-sm mb-4 leading-relaxed">
        {feature.description}
      </p>

      {/* See Demo Link */}
      <div className="flex items-center gap-1 text-primary text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity">
        <span>See demo</span>
        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
      </div>
    </div>
  );
};

export default FeatureCard;
