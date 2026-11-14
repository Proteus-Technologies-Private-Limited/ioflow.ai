/**
 * RatingDisplay Component
 * Displays star ratings with filled, half, and empty stars
 */

import React from 'react';
import { Star, StarHalf } from 'lucide-react';

const RatingDisplay = ({
  rating = 0,
  totalReviews = 0,
  size = 'medium',
  showNumber = true,
  showCount = true
}) => {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  const sizeClasses = {
    small: 'w-4 h-4',
    medium: 'w-5 h-5',
    large: 'w-6 h-6'
  };

  const starSize = sizeClasses[size] || sizeClasses.medium;

  return (
    <div className="flex items-center gap-2">
      {/* Star icons */}
      <div className="flex items-center gap-0.5">
        {/* Full stars */}
        {[...Array(fullStars)].map((_, i) => (
          <Star
            key={`full-${i}`}
            className={`${starSize} fill-yellow-400 text-yellow-400`}
          />
        ))}

        {/* Half star */}
        {hasHalfStar && (
          <StarHalf
            key="half"
            className={`${starSize} fill-yellow-400 text-yellow-400`}
          />
        )}

        {/* Empty stars */}
        {[...Array(emptyStars)].map((_, i) => (
          <Star
            key={`empty-${i}`}
            className={`${starSize} text-gray-300`}
          />
        ))}
      </div>

      {/* Rating number */}
      {showNumber && (
        <span className="text-sm font-medium text-gray-700">
          {rating.toFixed(1)}
        </span>
      )}

      {/* Review count */}
      {showCount && totalReviews > 0 && (
        <span className="text-sm text-gray-500">
          ({totalReviews} {totalReviews === 1 ? 'review' : 'reviews'})
        </span>
      )}
    </div>
  );
};

export default RatingDisplay;
