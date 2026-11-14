/**
 * MarketplaceAppDetail Page
 * Detailed view of a single marketplace app with subscription option
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  Star,
  Users,
  TrendingUp,
  Calendar,
  Tag as TagIcon,
  ExternalLink,
  Globe,
  Shield,
  CheckCircle,
  AlertCircle,
  Store,
  Heart,
  User,
  LogOut,
  Settings,
  LayoutDashboard
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';
import logo from '../../assets/logo.png';
import RatingDisplay from '../../components/marketplace/RatingDisplay';
import ApplicationInstallationWizard from '../../components/flows/ApplicationInstallationWizard';
import AppDocumentation from '../../components/marketplace/AppDocumentation';
import { getAppDetails, getMySubscriptions } from '../../services/marketplaceService';
import axios from 'axios';

const MarketplaceAppDetail = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [app, setApp] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [subscribing, setSubscribing] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [subscriptionCount, setSubscriptionCount] = useState(0);

  useEffect(() => {
    loadAppDetail();
  }, [slug]);

  // Auto-continue subscription after login
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const shouldSubscribe = params.get('subscribe');

    // Only proceed if we have the subscribe flag, user is loaded, app is loaded, and not already subscribing
    if (shouldSubscribe === 'true' && user && app && !subscribing && !loading) {
      console.log('Auto-triggering subscription for:', app.frontend_app_name);

      // Remove the query parameter first
      params.delete('subscribe');
      const newSearch = params.toString();
      const newUrl = `${location.pathname}${newSearch ? '?' + newSearch : ''}`;
      navigate(newUrl, { replace: true });

      // Small delay to ensure navigation completes before starting subscription
      setTimeout(() => {
        checkAndSubscribe();
      }, 100);
    }
  }, [user, app, location.search, loading]);

  useEffect(() => {
    if (user) {
      loadSubscriptionCount();
    }
  }, [user]);

  // Scroll to documentation if hash is present
  useEffect(() => {
    if (location.hash === '#documentation' && !loading) {
      setTimeout(() => {
        const element = document.getElementById('documentation');
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 500); // Small delay to ensure content is loaded
    }
  }, [location.hash, loading]);

  const loadAppDetail = async () => {
    try {
      setLoading(true);
      const data = await getAppDetails(slug);
      setApp(data);
    } catch (error) {
      console.error('Error loading app details:', error);
      setError('Failed to load app details');
      toast.error('Failed to load app details');
    } finally {
      setLoading(false);
    }
  };

  const loadSubscriptionCount = async () => {
    try {
      const subscriptions = await getMySubscriptions();
      setSubscriptionCount(subscriptions.length);
    } catch (error) {
      console.error('Error loading subscription count:', error);
      // Silently fail - don't show error toast for this
    }
  };

  const checkAndSubscribe = async () => {
    if (!app || !user) return;

    setSubscribing(true);

    try {
      // Step 1: Check subscription requirements
      const requirementsResponse = await axios.get(
        `/api/v1/marketplace/apps/${app.frontend_app_id}/subscription-requirements`
      );

      const requirements = requirementsResponse.data;

      // Step 2: If there are missing apps, show installation wizard
      if (!requirements.ready_to_subscribe && requirements.missing_applications.length > 0) {
        setValidationData(requirements);
        setShowWizard(true);
        setSubscribing(false);
        return;
      }

      // Step 3: All requirements met, subscribe directly
      await performSubscription();

    } catch (error) {
      console.error('Error checking subscription requirements:', error);
      toast.error((error.response?.data?.message || error.response?.data?.detail) || 'Failed to check requirements');
      setSubscribing(false);
    }
  };

  const handleSubscribe = async () => {
    // Check if user is logged in
    if (!user) {
      const redirectUrl = `/marketplace/app/${slug}?subscribe=true`;
      console.log('User not logged in. Storing redirect URL:', redirectUrl);
      toast.error('Please login to subscribe');
      // Store the redirect URL in sessionStorage for reliability
      sessionStorage.setItem('redirectAfterLogin', redirectUrl);
      console.log('Stored in sessionStorage:', sessionStorage.getItem('redirectAfterLogin'));
      navigate('/login');
      return;
    }

    console.log('User is logged in, starting subscription check');
    await checkAndSubscribe();
  };

  const performSubscription = async () => {
    try {
      console.log('Creating subscription for app:', app.frontend_app_id);
      const response = await axios.post(
        `/api/v1/marketplace/apps/${app.frontend_app_id}/subscribe`
      );

      const result = response.data;
      console.log('Subscription response:', result);

      if (result.data.already_subscribed) {
        toast.success('You are already subscribed to this app!');
      } else {
        toast.success(result.message);
      }

      // Open execution page in new tab
      const executionUrl = `/public-app/${app.public_url_slug}`;
      console.log('Opening execution page in new tab:', executionUrl);

      // Open in new tab
      window.open(executionUrl, '_blank', 'noopener,noreferrer');

      // Reload app detail to update subscription status
      loadAppDetail();
      loadSubscriptionCount();

    } catch (error) {
      console.error('Error subscribing:', error);
      toast.error((error.response?.data?.message || error.response?.data?.detail) || 'Failed to subscribe');
    } finally {
      setSubscribing(false);
    }
  };

  const handleAllAppsReady = async () => {
    setShowWizard(false);
    setSubscribing(true);
    await performSubscription();
  };

  const handleExecute = () => {
    // Navigate to execution page
    navigate(`/public-app/${app.public_url_slug}`);
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading app details...</p>
        </div>
      </div>
    );
  }

  if (error || !app) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">App Not Found</h2>
          <p className="text-gray-600 mb-4">{error || 'The app you are looking for does not exist.'}</p>
          <button
            onClick={() => navigate('/marketplace')}
            className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark"
          >
            Back to Marketplace
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

      {/* Back button */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <button
            onClick={() => navigate('/marketplace')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="w-5 h-5" />
            Back to Marketplace
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {/* App Header */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <div className="flex items-start gap-6">
                {/* App Icon */}
                <div className="flex-shrink-0">
                  {app.icon_url ? (
                    <img
                      src={app.icon_url}
                      alt={app.frontend_app_name}
                      className="w-24 h-24 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="w-24 h-24 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                      <Globe className="w-12 h-12 text-white" />
                    </div>
                  )}
                </div>

                {/* App Info */}
                <div className="flex-1">
                  <h1 className="text-3xl font-bold text-gray-900 mb-2">
                    {app.frontend_app_name}
                  </h1>

                  <p className="text-gray-600 mb-4">
                    by <span className="font-medium text-gray-900">{app.creator_name}</span>
                  </p>

                  {/* Rating & Stats */}
                  <div className="flex items-center gap-6 mb-4">
                    <RatingDisplay
                      rating={app.avg_rating}
                      totalReviews={app.total_reviews}
                      size="large"
                    />
                    <div className="flex items-center gap-2 text-gray-600">
                      <Users className="w-5 h-5" />
                      <span>{app.total_subscribers} subscribers</span>
                    </div>
                    {app.trending_score > 0 && (
                      <div className="flex items-center gap-2 text-green-600">
                        <TrendingUp className="w-5 h-5" />
                        <span>Trending</span>
                      </div>
                    )}
                  </div>

                  {/* Categories & Tags */}
                  <div className="space-y-2">
                    {app.categories && app.categories.length > 0 && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-gray-600">Categories:</span>
                        {app.categories.map((category, index) => (
                          <span
                            key={index}
                            className="px-2 py-1 bg-primary/10 text-primary text-sm rounded"
                          >
                            {category}
                          </span>
                        ))}
                      </div>
                    )}

                    {app.tags && app.tags.length > 0 && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <TagIcon className="w-4 h-4 text-gray-600" />
                        {app.tags.map((tag, index) => (
                          <span
                            key={index}
                            className="px-2 py-1 bg-gray-100 text-gray-700 text-sm rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Description */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Description</h2>
              <p className="text-gray-700 whitespace-pre-wrap">
                {app.description || 'No description available.'}
              </p>
            </div>

            {/* Screenshots (if available) */}
            {app.screenshots && app.screenshots.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6 mb-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Screenshots</h2>
                <div className="grid grid-cols-2 gap-4">
                  {app.screenshots.map((screenshot, index) => (
                    <img
                      key={index}
                      src={screenshot}
                      alt={`Screenshot ${index + 1}`}
                      className="rounded-lg border shadow-sm"
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Documentation Section */}
            <div id="documentation" className="mb-6 scroll-mt-20">
              <AppDocumentation appSlug={app.public_url_slug} />
            </div>

            {/* Reviews Section */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Reviews</h2>
              <p className="text-gray-600">
                {app.total_reviews > 0
                  ? `${app.total_reviews} review${app.total_reviews === 1 ? '' : 's'}`
                  : 'No reviews yet. Be the first to review this app!'}
              </p>
              {/* TODO: Add reviews list */}
            </div>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            {/* Pricing Card */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-6 sticky top-4">
              <div className="mb-6">
                {app.billing_preference === 'free' ? (
                  <div className="text-center">
                    <div className="inline-block px-4 py-2 bg-green-100 text-green-800 rounded-full text-lg font-bold mb-2">
                      FREE
                    </div>
                    <p className="text-sm text-gray-600">No cost to use</p>
                  </div>
                ) : (
                  <div className="text-center">
                    <div className="text-3xl font-bold text-gray-900 mb-2">
                      {app.pricing_config?.price || 'Contact for pricing'}
                    </div>
                    <p className="text-sm text-gray-600">
                      {app.billing_preference === 'per_user_per_month'
                        ? 'per user / month'
                        : 'per execution'}
                    </p>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="space-y-3">
                <button
                  onClick={handleExecute}
                  className="w-full px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-dark font-medium flex items-center justify-center gap-2"
                >
                  <ExternalLink className="w-5 h-5" />
                  Try Now
                </button>

                <button
                  onClick={handleSubscribe}
                  disabled={subscribing}
                  className="w-full px-6 py-3 border-2 border-primary text-primary rounded-md hover:bg-primary-10 font-medium flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {subscribing ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                      Subscribing...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      Subscribe
                    </>
                  )}
                </button>
              </div>

              {/* App Info */}
              <div className="mt-6 pt-6 border-t space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Created</span>
                  <span className="text-gray-900">
                    {new Date(app.created_at).toLocaleDateString()}
                  </span>
                </div>

                {app.updated_at && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Last Updated</span>
                    <span className="text-gray-900">
                      {new Date(app.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Visibility</span>
                  <div className="flex items-center gap-1">
                    {app.visibility === 'public' ? (
                      <>
                        <Globe className="w-4 h-4 text-green-600" />
                        <span className="text-green-600">Public</span>
                      </>
                    ) : (
                      <>
                        <Shield className="w-4 h-4 text-gray-600" />
                        <span className="text-gray-600">Private</span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Demo URL */}
              {app.demo_url && (
                <div className="mt-6 pt-6 border-t">
                  <a
                    href={app.demo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:text-primary-dark text-sm flex items-center gap-2"
                  >
                    <ExternalLink className="w-4 h-4" />
                    View Demo
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Application Installation Wizard */}
      {showWizard && validationData && (
        <ApplicationInstallationWizard
          open={showWizard}
          onClose={() => {
            setShowWizard(false);
            setSubscribing(false);
          }}
          validationData={validationData}
          flowName={app?.frontend_app_name}
          onAllAppsReady={handleAllAppsReady}
        />
      )}
    </div>
  );
};

export default MarketplaceAppDetail;
