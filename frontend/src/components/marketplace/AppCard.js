/**
 * AppCard Component
 * Card display for marketplace apps in grid view
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, TrendingUp, Users, Tag } from 'lucide-react';
import RatingDisplay from './RatingDisplay';
import { formatPrice } from '../../services/marketplaceService';

const AppCard = ({ app }) => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/marketplace/app/${app.public_url_slug}`);
  };

  // Get price display
  const priceDisplay = formatPrice(app.pricing_config, app.billing_preference);

  // Check if free
  const isFree = app.billing_preference === 'free';

  return (
    <div
      onClick={handleClick}
      className="bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300 cursor-pointer overflow-hidden border border-gray-200"
    >
      {/* App Icon/Image */}
      <div className="relative bg-gradient-to-br from-primary/10 to-secondary/10 p-6 flex items-center justify-center h-48">
        {app.icon_url ? (
          <img
            src={app.icon_url}
            alt={app.frontend_app_name}
            className="max-w-full max-h-full object-contain"
          />
        ) : (
          <Package className="w-20 h-20 text-primary" />
        )}

        {/* Featured badge */}
        {app.featured_rank && (
          <div className="absolute top-2 right-2 bg-yellow-400 text-yellow-900 text-xs font-bold px-2 py-1 rounded-full">
            Featured
          </div>
        )}

        {/* Free badge */}
        {isFree && (
          <div className="absolute top-2 left-2 bg-green-500 text-white text-xs font-bold px-2 py-1 rounded-full">
            FREE
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-5">
        {/* App name */}
        <h3 className="text-lg font-semibold text-gray-900 mb-2 line-clamp-1">
          {app.frontend_app_name}
        </h3>

        {/* Creator */}
        <p className="text-sm text-gray-600 mb-3">
          by {app.creator_name}
        </p>

        {/* Description */}
        <p className="text-sm text-gray-700 mb-4 line-clamp-2 min-h-[2.5rem]">
          {app.description || 'No description available'}
        </p>

        {/* Rating */}
        <div className="mb-4">
          <RatingDisplay
            rating={app.avg_rating}
            totalReviews={app.total_reviews}
            size="small"
          />
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
          <div className="flex items-center gap-1">
            <Users className="w-4 h-4" />
            <span>{app.total_subscribers || 0}</span>
          </div>
          {app.trending_score > 0 && (
            <div className="flex items-center gap-1">
              <TrendingUp className="w-4 h-4" />
              <span>Trending</span>
            </div>
          )}
        </div>

        {/* Tags */}
        {app.tags && app.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {app.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded-full"
              >
                <Tag className="w-3 h-3" />
                {tag}
              </span>
            ))}
            {app.tags.length > 3 && (
              <span className="text-xs text-gray-500">
                +{app.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Price */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-200">
          <span className={`font-semibold ${isFree ? 'text-green-600' : 'text-primary'}`}>
            {priceDisplay}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleClick();
            }}
            className="bg-primary text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-primary-dark transition-colors"
          >
            View Details
          </button>
        </div>
      </div>
    </div>
  );
};

export default AppCard;
