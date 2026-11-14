/**
 * MarketplaceHome Page
 * Main marketplace landing page with featured apps, search, filters, and app grid
 * Enhanced with transforming hero banner that shrinks on scroll
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Store, TrendingUp, Sparkles, Heart, User, LogOut, Settings, LayoutDashboard, ChevronDown, Search, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';
import logo from '../../assets/logo.png';
import AppCard from '../../components/marketplace/AppCard';
import CategorySidebar from '../../components/marketplace/CategorySidebar';
import SearchBar from '../../components/marketplace/SearchBar';
import {
  browseMarketplaceApps,
  getFeaturedApps,
  getTrendingApps,
  getMySubscriptions
} from '../../services/marketplaceService';

const MarketplaceHome = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [featuredApps, setFeaturedApps] = useState([]);
  const [trendingApps, setTrendingApps] = useState([]);
  const [apps, setApps] = useState([]);
  const [totalApps, setTotalApps] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [subscriptionCount, setSubscriptionCount] = useState(0);
  const [headerSearchTerm, setHeaderSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState('all'); // 'all', 'featured', 'trending'
  const subscriptionLoadedRef = useRef(false);

  const [filters, setFilters] = useState({
    search: '',
    category_slug: null,
    tags: [],
    min_rating: null,
    billing_preference: null,
    sort_by: 'popular',
    page: 1,
    page_size: 12
  });

  const totalPages = Math.ceil(totalApps / filters.page_size);

  // Scroll listener for banner transformation with improved stability to prevent flickering
  useEffect(() => {
    let ticking = false;
    let lastKnownScrollPosition = 0;
    let lastChangeTime = 0;
    const MIN_CHANGE_INTERVAL = 100; // Minimum time between state changes in ms

    const handleScroll = () => {
      lastKnownScrollPosition = window.scrollY;

      if (!ticking) {
        window.requestAnimationFrame(() => {
          const now = Date.now();
          const scrollPosition = lastKnownScrollPosition;

          // Use larger hysteresis zone and time-based debouncing
          // Collapse at 120px, expand at 60px to have a larger dead zone
          setIsScrolled(prev => {
            const shouldBeScrolled = scrollPosition > 120;
            const shouldBeExpanded = scrollPosition < 60;

            // Only change state if we're clearly in one zone or the other
            // AND enough time has passed since last change
            if (shouldBeScrolled && !prev && (now - lastChangeTime) > MIN_CHANGE_INTERVAL) {
              lastChangeTime = now;
              return true;
            }
            if (shouldBeExpanded && prev && (now - lastChangeTime) > MIN_CHANGE_INTERVAL) {
              lastChangeTime = now;
              return false;
            }
            // In the dead zone (60-120px) or too soon after last change - keep current state
            return prev;
          });

          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  useEffect(() => {
    loadFeaturedAndTrending();
  }, []);

  useEffect(() => {
    loadApps();
  }, [filters]);

  useEffect(() => {
    if (user) {
      // Small delay to ensure scroll handler is set up first and page is stable
      const timer = setTimeout(() => {
        loadSubscriptionCount();
      }, 100);
      return () => clearTimeout(timer);
    } else {
      // Reset when user logs out
      subscriptionLoadedRef.current = false;
      setSubscriptionCount(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const loadFeaturedAndTrending = async () => {
    try {
      const [featured, trending] = await Promise.all([
        getFeaturedApps(6),
        getTrendingApps(6)
      ]);
      setFeaturedApps(featured);
      setTrendingApps(trending);
    } catch (error) {
      console.error('Error loading featured/trending:', error);
    }
  };

  const loadApps = async () => {
    try {
      if (filters.page === 1) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }

      const result = await browseMarketplaceApps(filters);
      setApps(result.apps);
      setTotalApps(result.total);
    } catch (error) {
      console.error('Error loading apps:', error);
      toast.error('Failed to load marketplace apps');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const loadSubscriptionCount = useCallback(async () => {
    if (!user || subscriptionLoadedRef.current) return;

    try {
      subscriptionLoadedRef.current = true;
      const subscriptions = await getMySubscriptions();
      setSubscriptionCount(subscriptions.length);
    } catch (error) {
      console.error('Error loading subscription count:', error);
      subscriptionLoadedRef.current = false;
      // Silently fail - don't show error toast for this
    }
  }, [user]);

  const handleCategorySelect = (categorySlug) => {
    setFilters({ ...filters, category_slug: categorySlug, page: 1 });
  };

  const handleTagToggle = (tagSlug) => {
    const newTags = filters.tags.includes(tagSlug)
      ? filters.tags.filter(t => t !== tagSlug)
      : [...filters.tags, tagSlug];
    setFilters({ ...filters, tags: newTags, page: 1 });
  };

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  const handlePageChange = (newPage) => {
    setFilters({ ...filters, page: newPage });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleLogout = async () => {
    try {
      await logout();
      toast.success('Logged out successfully');
      setShowUserMenu(false);
    } catch (error) {
      toast.error('Failed to logout');
    }
  };

  const handleHeaderSearch = (e) => {
    e.preventDefault();
    setFilters({ ...filters, search: headerSearchTerm, page: 1 });
    setViewMode('all');
  };

  const handleViewModeChange = (mode) => {
    setViewMode(mode);
    // Clear search and category filters when switching view modes
    if (mode === 'featured' || mode === 'trending') {
      setFilters({
        ...filters,
        search: '',
        category_slug: null,
        page: 1
      });
      setHeaderSearchTerm('');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Transforming Hero Banner / Navigation Bar */}
      <div
        className={`
          fixed top-0 left-0 right-0 z-50
          bg-gradient-primary
          text-white shadow-lg
          transition-all duration-500 ease-in-out
          ${isScrolled ? 'py-0' : 'py-4 md:py-8'}
        `}
      >
        <div className="max-w-7xl mx-auto px-4">
          {/* Top Bar - Logo, Title, Navigation, Search, User Menu */}
          <div className={`
            flex items-center justify-between gap-4
            transition-all duration-500 ease-in-out
            ${isScrolled ? 'h-16' : 'h-auto mb-4'}
          `}>
            {/* Left: Logo and Title */}
            <div
              className="flex items-center gap-3 cursor-pointer transition-all duration-500 flex-shrink-0"
              onClick={() => {
                navigate('/marketplace');
                setViewMode('all');
              }}
            >
              <img
                src={logo}
                alt="IOFlow"
                className={`transition-all duration-500 rounded-[28%] ${isScrolled ? 'w-8 h-8' : 'w-10 h-10 md:w-12 md:h-12'}`}
              />
              <span className={`font-bold transition-all duration-500 ${isScrolled ? 'text-lg' : 'text-xl md:text-2xl'}`}>
                IOFlow Marketplace
              </span>
            </div>

            {/* Center: Search Bar (visible when scrolled) */}
            {isScrolled && (
              <form onSubmit={handleHeaderSearch} className="flex-1 max-w-md mx-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-white/60 w-4 h-4" />
                  <input
                    type="text"
                    value={headerSearchTerm}
                    onChange={(e) => setHeaderSearchTerm(e.target.value)}
                    placeholder="Search apps..."
                    className="w-full pl-10 pr-10 py-2 bg-white/10 backdrop-blur-sm border border-white/20 rounded-lg text-white placeholder-white/60 focus:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white/30 transition-all"
                  />
                  {headerSearchTerm && (
                    <button
                      type="button"
                      onClick={() => {
                        setHeaderSearchTerm('');
                        setFilters({ ...filters, search: '', page: 1 });
                      }}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-white/60 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </form>
            )}

            {/* Right: User Menu and Subscriptions */}
            <div className="flex items-center gap-3">
              {user ? (
                <>
                  {/* My Subscriptions Button */}
                  <button
                    onClick={() => navigate('/marketplace/subscriptions')}
                    className={`
                      flex items-center gap-2 px-4 rounded-lg
                      bg-white/10 hover:bg-white/20
                      transition-all duration-300
                      backdrop-blur-sm border border-white/20
                      ${isScrolled ? 'text-sm py-2' : 'text-base py-2.5'}
                      relative
                    `}
                  >
                    <Heart className={`${isScrolled ? 'w-4 h-4' : 'w-5 h-5'}`} />
                    <span className="hidden sm:inline font-medium">My Subscriptions</span>
                    {subscriptionCount > 0 && (
                      <span
                        className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center pointer-events-none"
                        style={{ transform: 'translateZ(0)', willChange: 'contents' }}
                      >
                        {subscriptionCount}
                      </span>
                    )}
                  </button>

                  {/* User Menu Dropdown */}
                  <div className="relative">
                    <button
                      onClick={() => setShowUserMenu(!showUserMenu)}
                      className={`
                        flex items-center gap-2 px-3 rounded-lg
                        bg-white/10 hover:bg-white/20
                        transition-all duration-300
                        backdrop-blur-sm border border-white/20
                        ${isScrolled ? 'py-2' : 'py-2.5'}
                      `}
                    >
                      <div className={`
                        rounded-full bg-white/20 flex items-center justify-center
                        font-bold backdrop-blur-sm border border-white/30
                        transition-all duration-500
                        ${isScrolled ? 'w-8 h-8 text-sm' : 'w-8 h-8 text-sm'}
                      `}>
                        {user.user_name ? user.user_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                      </div>
                      <ChevronDown className={`transition-all duration-300 ${showUserMenu ? 'rotate-180' : ''} ${isScrolled ? 'w-4 h-4' : 'w-5 h-5'}`} />
                    </button>

                    {/* Dropdown Menu */}
                    {showUserMenu && (
                      <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-xl border border-gray-200 py-2 text-gray-900">
                        <div className="px-4 py-2 border-b border-gray-100">
                          <div className="text-sm font-semibold text-gray-900">
                            {user.user_name || 'User'}
                          </div>
                          <div className="text-xs text-gray-500">
                            {user.email}
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            navigate('/dashboard');
                            setShowUserMenu(false);
                          }}
                          className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-primary-10 flex items-center gap-3 transition-colors"
                        >
                          <LayoutDashboard className="w-4 h-4 text-primary" />
                          <span>Go to Dashboard</span>
                        </button>
                        <button
                          onClick={() => {
                            navigate('/settings');
                            setShowUserMenu(false);
                          }}
                          className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-primary-10 flex items-center gap-3 transition-colors"
                        >
                          <Settings className="w-4 h-4 text-primary" />
                          <span>Settings</span>
                        </button>
                        <div className="border-t border-gray-100 my-1"></div>
                        <button
                          onClick={handleLogout}
                          className="w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-3 transition-colors"
                        >
                          <LogOut className="w-4 h-4" />
                          <span>Sign Out</span>
                        </button>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <button
                    onClick={() => navigate('/login')}
                    className={`
                      px-4 rounded-lg font-medium
                      bg-white/10 hover:bg-white/20
                      backdrop-blur-sm border border-white/20
                      transition-all duration-300
                      ${isScrolled ? 'text-sm py-2' : 'text-base py-2.5'}
                    `}
                  >
                    Sign In
                  </button>
                  <button
                    onClick={() => navigate('/register')}
                    className={`
                      px-4 rounded-lg font-medium
                      bg-white text-primary hover:bg-white/90
                      shadow-lg hover:shadow-xl
                      transition-all duration-300
                      ${isScrolled ? 'text-sm py-2' : 'text-base py-2.5'}
                    `}
                  >
                    Sign Up
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Hero Content / Navigation Links - Transforms when scrolled */}
          <div className={`
            transition-all duration-500 ease-in-out overflow-hidden
            ${isScrolled ? 'max-h-0 opacity-0' : 'max-h-96 opacity-100'}
          `}>
            {/* Hero text */}
            <div className="text-center">
              <p className="text-base md:text-lg text-white/90 max-w-2xl mx-auto leading-relaxed mb-4">
                Discover and subscribe to powerful Micro SaaS applications.
                Build workflows faster with pre-built integrations.
              </p>

              {/* Hero Search Bar */}
              <form onSubmit={handleHeaderSearch} className="max-w-xl mx-auto">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    type="text"
                    value={headerSearchTerm}
                    onChange={(e) => setHeaderSearchTerm(e.target.value)}
                    placeholder="Search apps..."
                    className="w-full pl-11 pr-11 py-3 bg-white rounded-lg text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white/30 shadow-lg text-base"
                  />
                  {headerSearchTerm && (
                    <button
                      type="button"
                      onClick={() => {
                        setHeaderSearchTerm('');
                        setFilters({ ...filters, search: '', page: 1 });
                      }}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </form>
            </div>

            {/* Clickable navigation badges */}
            <div className="mt-5 flex flex-wrap items-center justify-center gap-3 text-sm">
              <button
                onClick={() => handleViewModeChange('all')}
                className={`
                  flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-sm border transition-all
                  ${viewMode === 'all'
                    ? 'bg-white/30 border-white/40 shadow-lg'
                    : 'bg-white/10 border-white/20 hover:bg-white/20'}
                `}
              >
                <Store className="w-5 h-5" />
                <span>{totalApps}+ Apps</span>
              </button>
              <button
                onClick={() => handleViewModeChange('featured')}
                className={`
                  flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-sm border transition-all
                  ${viewMode === 'featured'
                    ? 'bg-white/30 border-white/40 shadow-lg'
                    : 'bg-white/10 border-white/20 hover:bg-white/20'}
                `}
              >
                <Sparkles className="w-5 h-5" />
                <span>Featured Apps</span>
              </button>
              <button
                onClick={() => handleViewModeChange('trending')}
                className={`
                  flex items-center gap-2 px-4 py-2 rounded-full backdrop-blur-sm border transition-all
                  ${viewMode === 'trending'
                    ? 'bg-white/30 border-white/40 shadow-lg'
                    : 'bg-white/10 border-white/20 hover:bg-white/20'}
                `}
              >
                <TrendingUp className="w-5 h-5" />
                <span>Trending Now</span>
              </button>
            </div>
          </div>

          {/* Navigation links when scrolled */}
          {isScrolled && (
            <div className="flex items-center gap-2 mt-3 justify-center">
              <button
                onClick={() => handleViewModeChange('all')}
                className={`
                  px-3 py-1.5 rounded-md text-sm font-medium transition-all
                  ${viewMode === 'all'
                    ? 'bg-white/30 text-white'
                    : 'text-white/80 hover:text-white hover:bg-white/10'}
                `}
              >
                All Apps
              </button>
              <button
                onClick={() => handleViewModeChange('featured')}
                className={`
                  px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1
                  ${viewMode === 'featured'
                    ? 'bg-white/30 text-white'
                    : 'text-white/80 hover:text-white hover:bg-white/10'}
                `}
              >
                <Sparkles className="w-4 h-4" />
                Featured
              </button>
              <button
                onClick={() => handleViewModeChange('trending')}
                className={`
                  px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1
                  ${viewMode === 'trending'
                    ? 'bg-white/30 text-white'
                    : 'text-white/80 hover:text-white hover:bg-white/10'}
                `}
              >
                <TrendingUp className="w-4 h-4" />
                Trending
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Spacer to prevent content from going under fixed header */}
      {/* When expanded: hero content ~280px, when collapsed: nav bar 64px + nav links ~48px = 112px + buffer */}
      <div className={`transition-all duration-500 ${isScrolled ? 'h-36' : 'h-[280px] md:h-[300px]'}`} />

      {/* Content Wrapper with proper spacing */}
      <div>
        {/* Filter Bar - Available on all view modes */}
        <SearchBar
          filters={filters}
          onFilterChange={handleFilterChange}
        />

        {/* Featured Apps Section */}
        {viewMode === 'featured' && featuredApps.length > 0 && (
          <div className="max-w-7xl mx-auto px-4 pt-6 pb-8">
            <div className="flex items-center gap-2 mb-6">
              <Sparkles className="w-6 h-6 text-yellow-500" />
              <h2 className="text-2xl font-bold text-gray-900">Featured Apps</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {featuredApps.map(app => (
                <AppCard key={app.frontend_app_id} app={app} />
              ))}
            </div>
          </div>
        )}

        {/* Trending Apps Section */}
        {viewMode === 'trending' && trendingApps.length > 0 && (
          <div className="max-w-7xl mx-auto px-4 pt-6 pb-8">
            <div className="flex items-center gap-2 mb-6">
              <TrendingUp className="w-6 h-6 text-green-500" />
              <h2 className="text-2xl font-bold text-gray-900">Trending Apps</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {trendingApps.map(app => (
                <AppCard key={app.frontend_app_id} app={app} />
              ))}
            </div>
          </div>
        )}

      {/* Main Content with Sidebar - Only show for 'all' view mode */}
      {viewMode === 'all' && (
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar */}
            <div className="lg:col-span-1">
              <CategorySidebar
                selectedCategory={filters.category_slug}
                selectedTags={filters.tags}
                onCategorySelect={handleCategorySelect}
                onTagToggle={handleTagToggle}
              />
            </div>

            {/* App Grid */}
            <div className="lg:col-span-3">
            {/* Results header */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">
                {filters.search ? `Search results for "${filters.search}"` : 'All Apps'}
                <span className="text-gray-500 font-normal ml-2">
                  ({totalApps} {totalApps === 1 ? 'app' : 'apps'})
                </span>
              </h2>
            </div>

            {/* Loading state */}
            {loading && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="bg-white rounded-lg shadow-md p-6 animate-pulse">
                    <div className="bg-gray-200 h-48 rounded mb-4"></div>
                    <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                    <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                  </div>
                ))}
              </div>
            )}

            {/* Apps grid */}
            {!loading && apps.length > 0 && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {apps.map(app => (
                    <AppCard key={app.frontend_app_id} app={app} />
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-8 flex items-center justify-center gap-2">
                    <button
                      onClick={() => handlePageChange(filters.page - 1)}
                      disabled={filters.page === 1}
                      className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>

                    {/* Page numbers */}
                    <div className="flex gap-1">
                      {[...Array(Math.min(5, totalPages))].map((_, i) => {
                        const pageNum = i + 1;
                        return (
                          <button
                            key={pageNum}
                            onClick={() => handlePageChange(pageNum)}
                            className={`w-10 h-10 rounded-md ${
                              filters.page === pageNum
                                ? 'bg-primary text-white'
                                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                    </div>

                    <button
                      onClick={() => handlePageChange(filters.page + 1)}
                      disabled={filters.page === totalPages}
                      className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}

            {/* No results */}
            {!loading && apps.length === 0 && (
              <div className="text-center py-12">
                <Store className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No apps found</h3>
                <p className="text-gray-500">
                  Try adjusting your search or filters to find what you're looking for.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
      )}
      </div>
    </div>
  );
};

export default MarketplaceHome;
