/**
 * LandingHero - Transforming hero banner with unified messaging
 * Shrinks on scroll similar to MarketplaceHome pattern
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Rocket,
  Briefcase,
  ArrowRight,
  Play
} from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import logo from '../../../assets/logo.png';

const LandingHero = ({ isScrolled, onSegmentClick, activeSegment, onWatchDemo }) => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const segmentQuickLinks = [
    { id: 'enterprise', label: 'Enterprise & ISV', icon: Building2 },
    { id: 'developers', label: 'No-Code Developers', icon: Rocket },
    { id: 'business', label: 'Business Users', icon: Briefcase }
  ];

  return (
    <div
      className={`
        fixed top-0 left-0 right-0 z-50
        bg-gradient-primary
        text-white shadow-lg
        transition-all duration-500 ease-in-out
        ${isScrolled ? 'py-0' : 'py-6 md:py-10'}
      `}
    >
      <div className="max-w-7xl mx-auto px-4">
        {/* Top Bar - Logo and Navigation */}
        <div className={`
          flex items-center justify-between gap-4
          transition-all duration-500 ease-in-out
          ${isScrolled ? 'h-16' : 'h-auto mb-6'}
        `}>
          {/* Logo */}
          <div
            className="flex items-center gap-3 cursor-pointer transition-all duration-500 flex-shrink-0"
            onClick={() => navigate('/')}
          >
            <img
              src={logo}
              alt="IOFlow"
              className={`transition-all duration-500 rounded-[28%] ${isScrolled ? 'w-8 h-8' : 'w-10 h-10 md:w-12 md:h-12'}`}
            />
            <span className={`font-bold transition-all duration-500 ${isScrolled ? 'text-lg' : 'text-xl md:text-2xl'}`}>
              IOFlow
            </span>
          </div>

          {/* Navigation Links (visible when scrolled) */}
          {isScrolled && (
            <div className="hidden md:flex items-center gap-4">
              {segmentQuickLinks.map(link => (
                <button
                  key={link.id}
                  onClick={() => onSegmentClick(link.id)}
                  className={`
                    px-3 py-1.5 rounded-md text-sm font-medium transition-all
                    ${activeSegment === link.id
                      ? 'bg-white/30 text-white'
                      : 'text-white/80 hover:text-white hover:bg-white/10'}
                  `}
                >
                  {link.label}
                </button>
              ))}
            </div>
          )}

          {/* CTA Buttons */}
          <div className="flex items-center gap-3">
            <a
              href="/marketplace"
              target="_blank"
              rel="noopener noreferrer"
              className={`
                px-4 py-2 rounded-lg font-medium
                bg-white/10 hover:bg-white/20
                backdrop-blur-sm border border-white/20
                transition-all duration-300
                ${isScrolled ? 'text-sm' : 'text-base'}
              `}
            >
              Explore Marketplace
            </a>
            {user ? (
              <button
                onClick={() => navigate('/dashboard')}
                className={`
                  px-4 py-2 rounded-lg font-medium
                  bg-white text-primary hover:bg-white/90
                  shadow-lg hover:shadow-xl
                  transition-all duration-300
                  ${isScrolled ? 'text-sm' : 'text-base'}
                `}
              >
                Go to Dashboard
              </button>
            ) : (
              <>
                <button
                  onClick={() => navigate('/login')}
                  className={`
                    hidden sm:block px-4 py-2 rounded-lg font-medium
                    bg-white/10 hover:bg-white/20
                    backdrop-blur-sm border border-white/20
                    transition-all duration-300
                    ${isScrolled ? 'text-sm' : 'text-base'}
                  `}
                >
                  Sign In
                </button>
                <button
                  onClick={() => navigate('/register')}
                  className={`
                    px-4 py-2 rounded-lg font-medium
                    bg-white text-primary hover:bg-white/90
                    shadow-lg hover:shadow-xl
                    transition-all duration-300
                    ${isScrolled ? 'text-sm' : 'text-base'}
                  `}
                >
                  Get Started
                </button>
              </>
            )}
          </div>
        </div>

        {/* Hero Content - Hidden when scrolled */}
        <div className={`
          transition-all duration-500 ease-in-out overflow-hidden
          ${isScrolled ? 'max-h-0 opacity-0' : 'max-h-[500px] opacity-100'}
        `}>
          {/* Main Headline */}
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold mb-4 leading-tight">
              Enterprise-grade automation for everyone
            </h1>
            <p className="text-lg md:text-xl text-white/90 mb-2 leading-relaxed max-w-3xl mx-auto">
              Build workflows with AI assistance, create custom connectors using plain English, and integrate intelligent AI agents - all without coding
            </p>
            <p className="text-base text-white/70 mb-8 max-w-2xl mx-auto">
              Powered by IOFlow Assistant - describe what you want, AI builds it for you
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => navigate('/register')}
                className="group flex items-center gap-2 px-6 py-3 bg-gradient-accent text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 text-lg"
              >
                Start Building Free
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
              <button
                onClick={onWatchDemo}
                className="flex items-center gap-2 px-6 py-3 bg-white/10 backdrop-blur-sm border border-white/30 font-semibold rounded-lg hover:bg-white/20 transition-all duration-300 text-lg"
              >
                <Play className="w-5 h-5" />
                Watch Demo
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingHero;
