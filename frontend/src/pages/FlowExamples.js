import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { showErrorToast, showSuccessToast, showInfoToast } from '../utils/customToast';
import { getFullErrorMessage } from '../utils/errorHandler';
import { getIconByName, getColorClasses, getDifficultyBadge } from '../utils/categoryIcons';
import FlowPreviewModal from '../components/flows/FlowPreviewModal';
import MissingApplicationsModal from '../components/flows/MissingApplicationsModal';
import ApplicationInstallationWizard from '../components/flows/ApplicationInstallationWizard';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
  ArrowDownTrayIcon,
  ClockIcon,
  AcademicCapIcon,
  EyeIcon,
  HeartIcon as HeartIconSolid,
  StarIcon as StarIconSolid,
  FireIcon,
  ChartBarIcon,
  EllipsisVerticalIcon,
  TrashIcon,
} from '@heroicons/react/24/solid';
import {
  HeartIcon,
  StarIcon,
} from '@heroicons/react/24/outline';

const FlowExamples = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedDifficulty, setSelectedDifficulty] = useState('all');
  const [sortBy, setSortBy] = useState('name'); // name, rating, imports, favorites
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [importingExampleId, setImportingExampleId] = useState(null);
  const [previewExample, setPreviewExample] = useState(null);
  const [previewFlowData, setPreviewFlowData] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState(null);

  // Missing applications modal state
  const [showMissingAppsModal, setShowMissingAppsModal] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [selectedExampleForImport, setSelectedExampleForImport] = useState(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardValidationData, setWizardValidationData] = useState(null);

  // Get current user to check if instance admin
  const { data: userData } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const response = await axios.get('/api/v1/auth/me');
      return response.data;
    },
  });

  const isInstanceAdmin = userData?.role === 'INSTANCE_ADMIN';

  // Fetch flow examples with filters and sorting
  const { data: examplesData, isLoading, error, refetch } = useQuery({
    queryKey: ['flow-examples', selectedCategory, selectedDifficulty, sortBy, showFavoritesOnly],
    queryFn: async () => {
      let url = '/api/v1/flow-examples/';
      const params = new URLSearchParams();

      if (selectedCategory !== 'all') {
        params.append('category', selectedCategory);
      }

      if (selectedDifficulty !== 'all') {
        params.append('difficulty', selectedDifficulty);
      }

      if (sortBy) {
        params.append('sort_by', sortBy);
      }

      if (showFavoritesOnly) {
        params.append('favorites_only', 'true');
      }

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const response = await axios.get(url);
      return response.data;
    },
  });

  // Import flow example mutation
  const importExampleMutation = useMutation({
    mutationFn: (exampleId) =>
      axios.post(`/api/v1/flow-examples/${exampleId}/import`),
    onSuccess: (response) => {
      const flowId = response.data.flow_id;
      const flowName = response.data.flow_name;
      showSuccessToast(`Successfully imported "${flowName}"`);
      queryClient.invalidateQueries(['flows']);
      queryClient.invalidateQueries(['flow-examples']); // Refresh to update import count
      setTimeout(() => {
        navigate(`/flows/${flowId}/edit`);
      }, 500);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to import flow example');
      showErrorToast(errorMessage);
      setImportingExampleId(null);
    },
  });

  // Rate example mutation
  const rateExampleMutation = useMutation({
    mutationFn: ({ exampleId, rating }) =>
      axios.post(`/api/v1/flow-examples/${exampleId}/rate`, { rating }),
    onSuccess: () => {
      showSuccessToast('Rating submitted successfully');
      queryClient.invalidateQueries(['flow-examples']);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to submit rating');
      showErrorToast(errorMessage);
    },
  });

  // Toggle favorite mutation
  const toggleFavoriteMutation = useMutation({
    mutationFn: (exampleId) =>
      axios.post(`/api/v1/flow-examples/${exampleId}/favorite`),
    onSuccess: (response) => {
      const message = response.data.message;
      showSuccessToast(message);
      queryClient.invalidateQueries(['flow-examples']);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to update favorite');
      showErrorToast(errorMessage);
    },
  });

  // Delete example mutation
  const deleteExampleMutation = useMutation({
    mutationFn: (exampleId) =>
      axios.delete(`/api/v1/flow-examples/${exampleId}`),
    onSuccess: (response) => {
      showSuccessToast(response.data.message);
      queryClient.invalidateQueries(['flow-examples']);
      setOpenDropdownId(null);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to delete flow example');
      showErrorToast(errorMessage);
    },
  });

  const handleImportExample = async (example) => {
    try {
      // First validate requirements
      const response = await axios.post(`/api/v1/flow-examples/${example.id}/validate`);
      const validation = response.data;

      // Store validation data and example info
      setValidationData(validation);
      setSelectedExampleForImport(example);

      if (validation.can_import) {
        // All requirements met, import directly
        setImportingExampleId(example.id);
        importExampleMutation.mutate(example.id);
      } else {
        // Missing applications - use the installation wizard
        // Transform validation data to match wizard expectations
        const wizardData = {
          success: true,
          can_import: false,
          required_applications: validation.required_applications,
          missing_applications: validation.missing_applications,
          message: validation.message,
          flow_name: example.name
        };
        setWizardValidationData(wizardData);
        setShowWizard(true);
      }
    } catch (error) {
      const errorMessage = getFullErrorMessage(error, 'Failed to validate flow requirements');
      showErrorToast(errorMessage);
    }
  };

  const handleProceedWithImport = () => {
    if (selectedExampleForImport && validationData?.can_import) {
      setShowMissingAppsModal(false);
      setImportingExampleId(selectedExampleForImport.id);
      importExampleMutation.mutate(selectedExampleForImport.id);
    }
  };

  const handleAllAppsReady = () => {
    // After all apps are installed, proceed with import
    if (selectedExampleForImport) {
      setShowWizard(false);
      setImportingExampleId(selectedExampleForImport.id);
      importExampleMutation.mutate(selectedExampleForImport.id);
    }
  };

  const handleRateExample = (exampleId, rating) => {
    rateExampleMutation.mutate({ exampleId, rating });
  };

  const handleToggleFavorite = (exampleId) => {
    toggleFavoriteMutation.mutate(exampleId);
  };

  const handlePreview = async (example) => {
    try {
      const response = await axios.get(`/api/v1/flow-examples/${example.id}`);
      setPreviewExample(response.data.metadata);
      setPreviewFlowData(response.data.flow_data);
      setShowPreview(true);
    } catch (error) {
      showErrorToast('Failed to load flow preview');
    }
  };

  const handleDeleteExample = (exampleId) => {
    if (window.confirm('Are you sure you want to delete this flow example? This action cannot be undone.')) {
      deleteExampleMutation.mutate(exampleId);
    }
  };

  // Filter examples by search term
  const filteredExamples = examplesData?.examples?.filter((example) => {
    const matchesSearch =
      searchTerm === '' ||
      example.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      example.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      example.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));

    return matchesSearch;
  }) || [];

  // Get unique categories from data
  const categories = examplesData?.categories || [];

  // Get category stats
  const categoryStats = {};
  examplesData?.examples?.forEach((example) => {
    categoryStats[example.category] = (categoryStats[example.category] || 0) + 1;
  });

  // Rating component
  const StarRating = ({ rating, userRating, onRate, exampleId }) => {
    const [hoverRating, setHoverRating] = useState(0);

    return (
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => {
          const isFilled = (hoverRating || userRating || 0) >= star;
          const StarComponent = isFilled ? StarIconSolid : StarIcon;

          return (
            <button
              key={star}
              onClick={() => onRate(exampleId, star)}
              onMouseEnter={() => setHoverRating(star)}
              onMouseLeave={() => setHoverRating(0)}
              className="focus:outline-none transition-all duration-150"
            >
              <StarComponent
                className={`h-5 w-5 ${
                  isFilled
                    ? 'text-yellow-400'
                    : 'text-gray-300 hover:text-yellow-300'
                }`}
              />
            </button>
          );
        })}
        {rating && (
          <span className="text-xs text-gray-600 ml-1">
            {rating.toFixed(1)}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <AcademicCapIcon className="h-8 w-8 text-primary mr-3" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Flow Examples</h1>
                <p className="mt-1 text-sm text-gray-500">
                  Browse and import pre-built flow templates to get started quickly
                </p>
              </div>
            </div>
          </div>

          {/* Search, Filters, and Sort */}
          <div className="mt-6 flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-primary focus:border-primary sm:text-sm"
                placeholder="Search examples by name, description, or tags..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            {/* Sort Dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="block w-40 pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
            >
              <option value="name">Sort by Name</option>
              <option value="rating">Sort by Rating</option>
              <option value="imports">Most Popular</option>
              <option value="favorites">Most Favorited</option>
            </select>

            {/* Favorites Toggle */}
            <button
              onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
              className={`inline-flex items-center px-4 py-2 border rounded-md shadow-sm text-sm font-medium transition-colors ${
                showFavoritesOnly
                  ? 'bg-pink-50 border-pink-300 text-pink-700 hover:bg-pink-100'
                  : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              <HeartIconSolid className={`h-5 w-5 mr-2 ${showFavoritesOnly ? 'text-pink-500' : 'text-gray-400'}`} />
              Favorites
            </button>

            {/* Filter Toggle */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              <FunnelIcon className="h-5 w-5 mr-2 text-gray-400" />
              Filters
              {(selectedCategory !== 'all' || selectedDifficulty !== 'all') && (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary-10 text-primary">
                  {(selectedCategory !== 'all' ? 1 : 0) + (selectedDifficulty !== 'all' ? 1 : 0)}
                </span>
              )}
            </button>
          </div>

          {/* Filter Dropdowns */}
          {showFilters && (
            <div className="mt-4 flex flex-wrap gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              {/* Category Filter */}
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Category
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
                >
                  <option value="all">All Categories</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.name}>
                      {category.name} ({categoryStats[category.name] || 0})
                    </option>
                  ))}
                </select>
              </div>

              {/* Difficulty Filter */}
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Difficulty
                </label>
                <select
                  value={selectedDifficulty}
                  onChange={(e) => setSelectedDifficulty(e.target.value)}
                  className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
                >
                  <option value="all">All Levels</option>
                  <option value="Beginner">Beginner</option>
                  <option value="Intermediate">Intermediate</option>
                  <option value="Advanced">Advanced</option>
                </select>
              </div>

              {/* Clear Filters */}
              {(selectedCategory !== 'all' || selectedDifficulty !== 'all') && (
                <div className="flex items-end">
                  <button
                    onClick={() => {
                      setSelectedCategory('all');
                      setSelectedDifficulty('all');
                    }}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
                  >
                    <XMarkIcon className="h-4 w-4 mr-1" />
                    Clear
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Loading State */}
        {isLoading && (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-800">
              {getFullErrorMessage(error, 'Failed to load flow examples')}
            </p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredExamples.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
            <AcademicCapIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No examples found</h3>
            <p className="mt-1 text-sm text-gray-500">
              {searchTerm || selectedCategory !== 'all' || selectedDifficulty !== 'all' || showFavoritesOnly
                ? 'Try adjusting your filters or search term.'
                : 'No flow examples are available at the moment.'}
            </p>
          </div>
        )}

        {/* Examples Grid */}
        {!isLoading && !error && filteredExamples.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredExamples.map((example) => {
              const Icon = getIconByName(example.icon);
              const colorClasses = getColorClasses(example.color);
              const difficultyBadge = getDifficultyBadge(example.difficulty);
              const isImporting = importingExampleId === example.id;

              return (
                <div
                  key={example.id}
                  className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-all duration-200 flex flex-col"
                >
                  <div className="p-6 flex-1 flex flex-col">
                    <div className="flex-grow">
                      {/* Header with Icon and Actions */}
                      <div className="flex items-start justify-between mb-4">
                        <div className={`p-3 rounded-lg ${colorClasses.iconBg}`}>
                          <Icon className={`h-6 w-6 ${colorClasses.iconText}`} />
                        </div>
                        <div className="flex items-center gap-2">
                        {/* Difficulty Badge */}
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                            difficultyBadge.color === 'green'
                              ? 'bg-green-100 text-green-800'
                              : difficultyBadge.color === 'yellow'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {difficultyBadge.label}
                        </span>
                        {/* Favorite Button */}
                        <button
                          onClick={() => handleToggleFavorite(example.id)}
                          className="p-1 rounded-full hover:bg-white/50 transition-colors"
                          title={example.is_favorited ? 'Remove from favorites' : 'Add to favorites'}
                        >
                          {example.is_favorited ? (
                            <HeartIconSolid className="h-5 w-5 text-pink-500" />
                          ) : (
                            <HeartIcon className="h-5 w-5 text-gray-400 hover:text-pink-500" />
                          )}
                        </button>
                        {/* Admin Menu */}
                        {isInstanceAdmin && (
                          <div className="relative">
                            <button
                              onClick={() => setOpenDropdownId(openDropdownId === example.id ? null : example.id)}
                              className="p-1 rounded-full hover:bg-white/50 transition-colors"
                              title="More options"
                            >
                              <EllipsisVerticalIcon className="h-5 w-5 text-gray-600" />
                            </button>
                            {openDropdownId === example.id && (
                              <>
                                <div
                                  className="fixed inset-0 z-10"
                                  onClick={() => setOpenDropdownId(null)}
                                />
                                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg z-20 border border-gray-200">
                                  <div className="py-1">
                                    <button
                                      onClick={() => handleDeleteExample(example.id)}
                                      className="flex items-center w-full px-4 py-2 text-sm text-red-700 hover:bg-red-50 transition-colors"
                                    >
                                      <TrashIcon className="h-4 w-4 mr-2" />
                                      Delete Example
                                    </button>
                                  </div>
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                      {/* Flow Name */}
                      <h3 className={`text-lg font-semibold ${colorClasses.text} mb-2`}>
                        {example.name}
                      </h3>

                      {/* Description */}
                      <p className="text-sm text-gray-600 mb-4 line-clamp-3">
                        {example.description}
                      </p>

                      {/* Stats */}
                      <div className="flex items-center gap-4 mb-4 text-xs text-gray-600">
                        <div className="flex items-center gap-1" title="Import count">
                          <ChartBarIcon className="h-4 w-4" />
                          {example.import_count}
                        </div>
                        <div className="flex items-center gap-1" title="Favorites">
                          <HeartIconSolid className="h-4 w-4 text-pink-400" />
                          {example.favorite_count}
                        </div>
                        <div className="flex items-center gap-1" title="Estimated time">
                          <ClockIcon className="h-4 w-4" />
                          {example.estimated_time}
                        </div>
                        {example.import_count >= 10 && (
                          <div className="flex items-center gap-1 text-orange-600 font-medium" title="Popular">
                            <FireIcon className="h-4 w-4" />
                            Popular
                          </div>
                        )}
                      </div>

                      {/* Rating */}
                      <div className="mb-4">
                        <StarRating
                          rating={example.average_rating}
                          userRating={example.user_rating}
                          onRate={handleRateExample}
                          exampleId={example.id}
                        />
                        {example.rating_count > 0 && (
                          <p className="text-xs text-gray-500 mt-1">
                            {example.rating_count} {example.rating_count === 1 ? 'rating' : 'ratings'}
                          </p>
                        )}
                      </div>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        {example.tags.slice(0, 3).map((tag, index) => (
                          <span
                            key={index}
                            className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${colorClasses.badge}`}
                          >
                            {tag}
                          </span>
                        ))}
                        {example.tags.length > 3 && (
                          <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-700">
                            +{example.tags.length - 3}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 mt-auto">
                      {/* Preview Button */}
                      <button
                        onClick={() => handlePreview(example)}
                        className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors duration-200"
                      >
                        <EyeIcon className="h-4 w-4 mr-2" />
                        Preview
                      </button>

                      {/* Import Button */}
                      <button
                        onClick={() => handleImportExample(example)}
                        disabled={isImporting}
                        className={`flex-1 inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white ${
                          isImporting
                            ? 'bg-gray-400 cursor-not-allowed'
                            : `bg-gradient-accent hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent`
                        } transition-colors duration-200`}
                      >
                        {isImporting ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                            Importing...
                          </>
                        ) : (
                          <>
                            <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                            Import
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Flow Preview Modal */}
      {showPreview && previewExample && (
        <FlowPreviewModal
          open={showPreview}
          onClose={() => {
            setShowPreview(false);
            setPreviewExample(null);
            setPreviewFlowData(null);
          }}
          example={previewExample}
          flowData={previewFlowData}
        />
      )}

      {/* Missing Applications Modal */}
      {showMissingAppsModal && validationData && (
        <MissingApplicationsModal
          open={showMissingAppsModal}
          onClose={() => {
            setShowMissingAppsModal(false);
            setValidationData(null);
            setSelectedExampleForImport(null);
          }}
          requiredApplications={validationData.required_applications || []}
          missingApplications={validationData.missing_applications || []}
          exampleName={selectedExampleForImport?.name}
          onProceedWithImport={handleProceedWithImport}
        />
      )}

      {/* Application Installation Wizard */}
      <ApplicationInstallationWizard
        open={showWizard}
        onClose={() => {
          setShowWizard(false);
          setWizardValidationData(null);
        }}
        validationData={wizardValidationData}
        flowName={wizardValidationData?.flow_name || selectedExampleForImport?.name || 'Flow Example'}
        onAllAppsReady={handleAllAppsReady}
      />
    </div>
  );
};

export default FlowExamples;
