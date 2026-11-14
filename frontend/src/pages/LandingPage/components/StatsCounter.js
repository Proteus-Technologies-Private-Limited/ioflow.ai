/**
 * StatsCounter - Animated statistics counters with scroll-triggered animation
 */

import React, { useState, useEffect, useRef } from 'react';
import { Workflow, Users, Plug, Zap } from 'lucide-react';

const stats = [
  {
    id: 'apps',
    label: 'Apps Created',
    value: 500,
    suffix: '+',
    icon: Workflow,
    color: 'text-blue-400'
  },
  {
    id: 'users',
    label: 'Active Users',
    value: 2500,
    suffix: '+',
    icon: Users,
    color: 'text-green-400'
  },
  {
    id: 'integrations',
    label: 'Integrations',
    value: 40,
    suffix: '+',
    icon: Plug,
    color: 'text-purple-400'
  },
  {
    id: 'executions',
    label: 'Daily Executions',
    value: 10000,
    suffix: '+',
    icon: Zap,
    color: 'text-yellow-400'
  }
];

const AnimatedNumber = ({ target, duration = 2000, suffix = '' }) => {
  const [count, setCount] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !isVisible) {
          setIsVisible(true);
        }
      },
      { threshold: 0.3 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [isVisible]);

  useEffect(() => {
    if (!isVisible) return;

    let startTime;
    let animationFrame;

    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);

      // Easing function for smooth animation
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      setCount(Math.floor(easeOutQuart * target));

      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate);
      }
    };

    animationFrame = requestAnimationFrame(animate);

    return () => {
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [isVisible, target, duration]);

  const formatNumber = (num) => {
    if (num >= 1000) {
      return num.toLocaleString();
    }
    return num;
  };

  return (
    <span ref={ref} className="tabular-nums">
      {formatNumber(count)}{suffix}
    </span>
  );
};

const StatsCounter = () => {
  return (
    <div className="max-w-7xl mx-auto px-4">
      <div className="text-center mb-12">
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Trusted by Thousands
        </h2>
        <p className="text-white/80 text-lg max-w-2xl mx-auto">
          Join the growing community of businesses automating their workflows with IOFlow
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.id}
              className="text-center bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20"
            >
              <div className="flex justify-center mb-4">
                <div className="p-3 rounded-full bg-white/10">
                  <Icon className={`w-8 h-8 ${stat.color}`} />
                </div>
              </div>
              <div className="text-3xl md:text-4xl font-bold text-white mb-2">
                <AnimatedNumber target={stat.value} suffix={stat.suffix} />
              </div>
              <div className="text-white/70 text-sm md:text-base">
                {stat.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default StatsCounter;
