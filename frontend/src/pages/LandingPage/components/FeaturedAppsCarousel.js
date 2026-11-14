/**
 * FeaturedAppsCarousel - Carousel of featured marketplace apps
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Sparkles, ArrowRight } from 'lucide-react';
import { getFeaturedApps } from '../../../services/marketplaceService';
import AppCard from '../../../components/marketplace/AppCard';

const FeaturedAppsCarousel = ({ onAppClick }) => {
  const navigate = useNavigate();
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    loadFeaturedApps();
  }, []);

  const loadFeaturedApps = async () => {
    try {
      const featured = await getFeaturedApps(6);
      setApps(featured || []);
    } catch (error) {
      console.error('Error loading featured apps:', error);
      setApps([]);
    } finally {
      setLoading(false);
    }
  };

  const handlePrev = () => {
    setCurrentIndex(prev => Math.max(0, prev - 1));
  };

  const handleNext = () => {
    const maxIndex = Math.max(0, apps.length - 3);
    setCurrentIndex(prev => Math.min(maxIndex, prev + 1));
  };

  const handleViewMarketplace = () => {
    navigate('/marketplace');
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
        </div>
      </div>
    );
  }

  if (apps.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4">
        <div className="text-center py-12">
          <Sparkles className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">Featured apps coming soon</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-primary/20 to-secondary/20">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900">
              Featured Apps
            </h2>
            <p className="text-gray-600">
              Popular automations ready to use
            </p>
          </div>
        </div>

        {/* Navigation and CTA */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2">
            <button
              onClick={handlePrev}
              disabled={currentIndex === 0}
              className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-5 h-5 text-gray-600" />
            </button>
            <button
              onClick={handleNext}
              disabled={currentIndex >= apps.length - 3}
              className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-5 h-5 text-gray-600" />
            </button>
          </div>

          <button
            onClick={handleViewMarketplace}
            className="group flex items-center gap-2 px-4 py-2 bg-gradient-primary text-white rounded-lg hover:from-[#0090c0] hover:to-[#00a090] transition-colors"
          >
            View Marketplace
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      {/* Apps Grid */}
      <div className="relative overflow-hidden">
        <div
          className="flex gap-6 transition-transform duration-300 ease-in-out"
          style={{
            transform: `translateX(-${currentIndex * (100 / 3)}%)`
          }}
        >
          {apps.map(app => (
            <div key={app.frontend_app_id} className="w-full md:w-1/2 lg:w-1/3 flex-shrink-0">
              <AppCard app={app} />
            </div>
          ))}
        </div>
      </div>

      {/* Mobile Scroll Indicator */}
      <div className="flex justify-center gap-2 mt-6 sm:hidden">
        {apps.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentIndex(index)}
            className={`w-2 h-2 rounded-full transition-colors ${
              index === currentIndex ? 'bg-primary' : 'bg-gray-300'
            }`}
          />
        ))}
      </div>
    </div>
  );
};

export default FeaturedAppsCarousel;
