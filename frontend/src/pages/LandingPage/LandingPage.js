/**
 * LandingPage - Main public landing page for IOFlow
 * Serves three customer segments with unified hero and segment-specific content
 */

import React, { useState, useEffect, useRef } from 'react';
import LandingHero from './components/LandingHero';
import SegmentSelector from './components/SegmentSelector';
import SegmentContent from './components/SegmentContent';
import StatsCounter from './components/StatsCounter';
import FeaturedAppsCarousel from './components/FeaturedAppsCarousel';
import PricingPreview from './components/PricingPreview';
import LandingFooter from './components/LandingFooter';
import SignupPrompt from './components/SignupPrompt';

const LandingPage = () => {
  const [activeSegment, setActiveSegment] = useState('enterprise');
  const [isScrolled, setIsScrolled] = useState(false);
  const [showSignupPrompt, setShowSignupPrompt] = useState(false);
  const [signupPromptContext, setSignupPromptContext] = useState(null);
  const scrollPercentageRef = useRef(0);

  // Scroll listener for hero transformation
  useEffect(() => {
    let ticking = false;
    let lastKnownScrollPosition = 0;
    let lastChangeTime = 0;
    const MIN_CHANGE_INTERVAL = 100;

    const handleScroll = () => {
      lastKnownScrollPosition = window.scrollY;

      if (!ticking) {
        window.requestAnimationFrame(() => {
          const now = Date.now();
          const scrollPosition = lastKnownScrollPosition;

          // Calculate scroll percentage for signup prompt
          const docHeight = document.documentElement.scrollHeight - window.innerHeight;
          scrollPercentageRef.current = (scrollPosition / docHeight) * 100;

          // Hero transform with hysteresis
          setIsScrolled(prev => {
            const shouldBeScrolled = scrollPosition > 120;
            const shouldBeExpanded = scrollPosition < 60;

            if (shouldBeScrolled && !prev && (now - lastChangeTime) > MIN_CHANGE_INTERVAL) {
              lastChangeTime = now;
              return true;
            }
            if (shouldBeExpanded && prev && (now - lastChangeTime) > MIN_CHANGE_INTERVAL) {
              lastChangeTime = now;
              return false;
            }
            return prev;
          });

          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleSegmentChange = (segmentId) => {
    setActiveSegment(segmentId);
    // Smooth scroll to segment content with offset for fixed header
    const segmentSection = document.getElementById('segment-content');
    if (segmentSection) {
      const collapsedHeaderHeight = 64;
      // When header is expanded, the spacer shrinks from ~420px to 64px on scroll
      const spacerShrinkage = isScrolled ? 0 : 356;

      const elementPosition = segmentSection.getBoundingClientRect().top + window.pageYOffset;
      const offsetPosition = elementPosition - spacerShrinkage - collapsedHeaderHeight - 20;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
  };

  const handleWatchDemo = () => {
    const demoSection = document.getElementById('demo-section');
    if (demoSection) {
      const collapsedHeaderHeight = 64;
      // When header is expanded, the spacer shrinks from ~420px to 64px on scroll
      const spacerShrinkage = isScrolled ? 0 : 356;

      const elementPosition = demoSection.getBoundingClientRect().top + window.pageYOffset;
      const offsetPosition = elementPosition - spacerShrinkage - collapsedHeaderHeight - 60;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
  };

  const handleDemoAction = (actionType, context) => {
    // Show signup prompt when user tries to execute/interact with demo
    setSignupPromptContext({ action: actionType, ...context });
    setShowSignupPrompt(true);
  };

  const handleCloseSignupPrompt = () => {
    setShowSignupPrompt(false);
    setSignupPromptContext(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <LandingHero
        isScrolled={isScrolled}
        onSegmentClick={handleSegmentChange}
        activeSegment={activeSegment}
        onWatchDemo={handleWatchDemo}
      />

      {/* Spacer for fixed hero - matches hero height */}
      <div className={`transition-all duration-500 ${isScrolled ? 'h-16' : 'h-[420px] md:h-[480px]'}`} />

      {/* Segment Selector */}
      <section className="py-8 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4">
          <SegmentSelector
            activeSegment={activeSegment}
            onSegmentChange={handleSegmentChange}
          />
        </div>
      </section>

      {/* Segment-Specific Content */}
      <section id="segment-content" className="py-12 md:py-16">
        <SegmentContent
          segment={activeSegment}
          onDemoAction={handleDemoAction}
        />
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-gradient-primary">
        <StatsCounter />
      </section>

      {/* Featured Apps Carousel */}
      <section className="py-16 bg-white">
        <FeaturedAppsCarousel onAppClick={handleDemoAction} />
      </section>

      {/* Pricing Preview */}
      <section className="py-16 bg-gray-50">
        <PricingPreview />
      </section>

      {/* Footer */}
      <LandingFooter />

      {/* Signup Prompt Modal */}
      {showSignupPrompt && (
        <SignupPrompt
          context={signupPromptContext}
          onClose={handleCloseSignupPrompt}
        />
      )}
    </div>
  );
};

export default LandingPage;
