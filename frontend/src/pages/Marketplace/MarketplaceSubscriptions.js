/**
 * MarketplaceSubscriptions Page
 * Displays user's subscribed marketplace apps
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Heart,
  ArrowLeft,
  ExternalLink,
  Calendar,
  CheckCircle,
  AlertCircle,
  Loader,
  Store,
  User,
  LogOut,
  Settings,
  LayoutDashboard,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Info
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';
import logo from '../../assets/logo.png';
import { getMySubscriptions } from '../../services/marketplaceService';
import RatingDisplay from '../../components/marketplace/RatingDisplay';
import AppDocumentation from '../../components/marketplace/AppDocumentation';

const MarketplaceSubscriptions = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [subscriptionCount, setSubscriptionCount] = useState(0);
  const [expandedAppId, setExpandedAppId] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'documentation', 'usage'

  useEffect(() => {
    loadSubscriptions();
  }, []);

  const loadSubscriptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMySubscriptions();
      setSubscriptions(data);
      setSubscriptionCount(data.length);
    } catch (error) {
      console.error('Error loading subscriptions:', error);
      setError('Failed to load subscriptions');
      toast.error('Failed to load subscriptions');
    } finally {
      setLoading(false);
    }
  };

  const handleViewApp = (slug) => {
    navigate(`/marketplace/app/${slug}`);
  };

  const handleExecuteApp = (publicUrlSlug) => {
    // Open in new tab
    window.open(`/public-app/${publicUrlSlug}`, '_blank', 'noopener,noreferrer');
  };

  const handleViewDocumentation = (slug) => {
    // Navigate to app detail page which shows documentation
    navigate(`/marketplace/app/${slug}#documentation`);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const handleLogout = async () => {
    try {
      await logout();
      toast.success('Logged out successfully');
      setShowUserMenu(false);
      navigate('/marketplace');
    } catch (error) {
      toast.error('Failed to logout');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-12 h-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading your subscriptions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Subscriptions</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={loadSubscriptions}
            className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Bar */}
      <div className="bg-gradient-primary text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            {/* Left: Logo/Brand */}
            <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/marketplace')}>
              <img src={logo} alt="IOFlow" className="w-8 h-8 rounded-[28%]" />
              <span className="text-xl font-bold">IOFlow Marketplace</span>
            </div>

            {/* Right: User Info or Sign In */}
            <div className="flex items-center gap-3">
              {user ? (
                <>
                  {/* My Subscriptions Link */}
                  <button
                    onClick={() => navigate('/marketplace/subscriptions')}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition-all duration-300 backdrop-blur-sm border border-white/20 relative"
                  >
                    <Heart className="w-5 h-5" />
                    <span className="hidden sm:inline font-medium">My Subscriptions</span>
                    {subscriptionCount > 0 && (
                      <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                        {subscriptionCount}
                      </span>
                    )}
                  </button>

                  {/* User Menu */}
                  <div className="relative">
                    <button
                      onClick={() => setShowUserMenu(!showUserMenu)}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 transition-all duration-300 backdrop-blur-sm border border-white/20"
                    >
                      <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center font-bold backdrop-blur-sm border border-white/30">
                        {user.user_name ? user.user_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                      </div>
                      <div className="hidden sm:block text-left">
                        <div className="text-sm font-semibold">
                          {user.user_name || user.email}
                        </div>
                        <div className="text-xs text-white/80">
                          {user.email}
                        </div>
                      </div>
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
                    className="px-4 py-2 rounded-lg font-medium bg-white/10 hover:bg-white/20 backdrop-blur-sm border border-white/20 transition-all duration-300"
                  >
                    Sign In
                  </button>
                  <button
                    onClick={() => navigate('/register')}
                    className="px-4 py-2 rounded-lg font-medium bg-white text-primary hover:bg-white/90 shadow-lg hover:shadow-xl transition-all duration-300"
                  >
                    Sign Up
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <button
            onClick={() => navigate('/marketplace')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-5 h-5" />
            Back to Marketplace
          </button>

          <div className="flex items-center gap-3">
            <Heart className="w-8 h-8 text-primary" />
            <div>
              <h1 className="text-3xl font-bold text-gray-900">My Subscriptions</h1>
              <p className="text-gray-600 mt-1">
                Apps you've subscribed to ({subscriptions.length})
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {subscriptions.length === 0 ? (
          <div className="text-center py-16">
            <Heart className="w-24 h-24 text-gray-300 mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">No Subscriptions Yet</h2>
            <p className="text-gray-600 mb-6">
              You haven't subscribed to any apps yet. Explore the marketplace to find apps that suit your needs.
            </p>
            <button
              onClick={() => navigate('/marketplace')}
              className="px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-dark font-medium"
            >
              Browse Marketplace
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {subscriptions.map((subscription) => {
              const isExpanded = expandedAppId === subscription.subscription_id;

              return (
              <div
                key={subscription.subscription_id}
                className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow overflow-hidden"
              >
                {/* Main Card */}
                <div className="flex flex-col md:flex-row">
                  {/* App Icon */}
                  <div className="relative w-full md:w-64 h-48 bg-gradient-to-br from-primary to-secondary flex-shrink-0">
                    {subscription.icon_url ? (
                      <img
                        src={subscription.icon_url}
                        alt={subscription.app_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Heart className="w-16 h-16 text-white opacity-50" />
                      </div>
                    )}
                    {/* Status Badge */}
                    <div className="absolute top-3 right-3">
                      {subscription.subscription_status === 'active' ? (
                        <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                          <CheckCircle className="w-4 h-4" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm font-medium">
                          {subscription.subscription_status}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* App Info */}
                  <div className="flex-1 p-6">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-xl font-bold text-gray-900">
                        {subscription.app_name}
                      </h3>
                      <button
                        onClick={() => {
                          if (isExpanded) {
                            setExpandedAppId(null);
                          } else {
                            setExpandedAppId(subscription.subscription_id);
                            setActiveTab('overview');
                          }
                        }}
                        className="p-2 text-gray-600 hover:text-primary hover:bg-primary-10 rounded-md transition-colors"
                        title={isExpanded ? "Collapse" : "Expand settings"}
                      >
                        {isExpanded ? <ChevronUp className="w-5 h-5" /> : <Settings className="w-5 h-5" />}
                      </button>
                    </div>

                    {subscription.description && (
                      <p className="text-gray-600 text-sm mb-4">
                        {subscription.description}
                      </p>
                    )}

                    <div className="flex flex-wrap items-center gap-4 mb-4">
                      {/* Rating */}
                      {subscription.avg_rating > 0 && (
                        <RatingDisplay
                          rating={subscription.avg_rating}
                          totalReviews={subscription.total_reviews}
                          size="small"
                        />
                      )}

                      {/* Subscription Date */}
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Calendar className="w-4 h-4" />
                        <span>Subscribed on {formatDate(subscription.subscribed_at)}</span>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => handleExecuteApp(subscription.public_url_slug)}
                        className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark font-medium flex items-center gap-2"
                      >
                        <ExternalLink className="w-4 h-4" />
                        Launch App
                      </button>
                      <button
                        onClick={() => {
                          setExpandedAppId(subscription.subscription_id);
                          setActiveTab('documentation');
                        }}
                        className="px-4 py-2 border border-secondary/30 bg-secondary/10 text-secondary rounded-md hover:bg-secondary/20 font-medium flex items-center gap-2"
                      >
                        <BookOpen className="w-4 h-4" />
                        Documentation
                      </button>
                      <button
                        onClick={() => handleViewApp(subscription.public_url_slug)}
                        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 font-medium"
                      >
                        View Details
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded Section with Tabs */}
                {isExpanded && (
                  <div className="border-t border-gray-200">
                    {/* Tab Navigation */}
                    <div className="flex space-x-1 px-6 pt-4 border-b bg-gray-50">
                      <button
                        onClick={() => setActiveTab('overview')}
                        className={`px-4 py-2 text-sm font-medium rounded-t-lg flex items-center gap-2 ${
                          activeTab === 'overview'
                            ? 'bg-white text-primary border-b-2 border-primary'
                            : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                        }`}
                      >
                        <Info className="w-4 h-4" />
                        Overview
                      </button>
                      <button
                        onClick={() => setActiveTab('documentation')}
                        className={`px-4 py-2 text-sm font-medium rounded-t-lg flex items-center gap-2 ${
                          activeTab === 'documentation'
                            ? 'bg-white text-primary border-b-2 border-primary'
                            : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                        }`}
                      >
                        <BookOpen className="w-4 h-4" />
                        Documentation
                      </button>
                    </div>

                    {/* Tab Content */}
                    <div className="p-6 bg-white">
                      {activeTab === 'overview' && (
                        <div className="space-y-4">
                          <div>
                            <h4 className="text-lg font-semibold mb-2">App Information</h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="font-medium text-gray-700">App Name:</span>
                                <p className="text-gray-600 mt-1">{subscription.app_name}</p>
                              </div>
                              <div>
                                <span className="font-medium text-gray-700">Status:</span>
                                <p className="text-gray-600 mt-1 capitalize">{subscription.subscription_status}</p>
                              </div>
                              <div>
                                <span className="font-medium text-gray-700">Subscribed:</span>
                                <p className="text-gray-600 mt-1">{formatDate(subscription.subscribed_at)}</p>
                              </div>
                              {subscription.avg_rating > 0 && (
                                <div>
                                  <span className="font-medium text-gray-700">Rating:</span>
                                  <div className="mt-1">
                                    <RatingDisplay
                                      rating={subscription.avg_rating}
                                      totalReviews={subscription.total_reviews}
                                      size="small"
                                    />
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                          {subscription.description && (
                            <div>
                              <h4 className="text-lg font-semibold mb-2">Description</h4>
                              <p className="text-gray-600">{subscription.description}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {activeTab === 'documentation' && (
                        <div>
                          <AppDocumentation appSlug={subscription.public_url_slug} />
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default MarketplaceSubscriptions;
