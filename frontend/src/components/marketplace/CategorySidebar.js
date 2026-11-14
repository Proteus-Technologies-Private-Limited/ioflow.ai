/**
 * CategorySidebar Component
 * Category and tag filter sidebar for marketplace
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Folder, Tag as TagIcon } from 'lucide-react';
import { getCategories, getTags } from '../../services/marketplaceService';
import toast from 'react-hot-toast';

const CategorySidebar = ({ selectedCategory, selectedTags = [], onCategorySelect, onTagToggle }) => {
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showTags, setShowTags] = useState(true);

  useEffect(() => {
    loadCategoriesAndTags();
  }, []);

  const loadCategoriesAndTags = async () => {
    try {
      setLoading(true);
      const [categoriesData, tagsData] = await Promise.all([
        getCategories(true),
        getTags(true)
      ]);
      setCategories(categoriesData);
      setTags(tagsData);
    } catch (error) {
      console.error('Error loading categories and tags:', error);
      toast.error('Failed to load filters');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      {/* Categories Section */}
      <div className="border-b border-gray-200">
        <div className="p-4 bg-gray-50">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Folder className="w-5 h-5" />
            Categories
          </h3>
        </div>

        <div className="p-2">
          {/* All Categories option */}
          <button
            onClick={() => onCategorySelect(null)}
            className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
              !selectedCategory
                ? 'bg-primary-10 text-primary font-medium'
                : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between">
              <span>All Categories</span>
              <span className="text-xs text-gray-500">
                {categories.reduce((sum, cat) => sum + cat.app_count, 0)}
              </span>
            </div>
          </button>

          {/* Category list */}
          {categories.map((category) => (
            <button
              key={category.category_id}
              onClick={() => onCategorySelect(category.slug)}
              className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                selectedCategory === category.slug
                  ? 'bg-primary-10 text-primary font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm">{category.name}</span>
                <span className="text-xs text-gray-500">{category.app_count}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Tags Section */}
      <div>
        <button
          onClick={() => setShowTags(!showTags)}
          className="w-full p-4 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors"
        >
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <TagIcon className="w-5 h-5" />
            Tags
          </h3>
          {showTags ? (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          )}
        </button>

        {showTags && (
          <div className="p-2">
            {tags.map((tag) => {
              const isSelected = selectedTags.includes(tag.slug);
              return (
                <button
                  key={tag.tag_id}
                  onClick={() => onTagToggle(tag.slug)}
                  className={`w-full text-left px-3 py-2 rounded-md transition-colors mb-1 ${
                    isSelected
                      ? 'bg-primary-10 text-primary font-medium border border-primary/20'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: tag.color || '#6366f1' }}
                      ></div>
                      <span className="text-sm">{tag.name}</span>
                    </div>
                    <span className="text-xs text-gray-500">{tag.usage_count}</span>
                  </div>
                </button>
              );
            })}

            {/* Clear tags button */}
            {selectedTags.length > 0 && (
              <button
                onClick={() => selectedTags.forEach(tag => onTagToggle(tag))}
                className="w-full mt-2 px-3 py-2 text-sm text-primary hover:bg-primary-10 rounded-md transition-colors"
              >
                Clear All Tags
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CategorySidebar;
