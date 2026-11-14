import React, { useState, useEffect, lazy, Suspense } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  HomeIcon,
  CubeIcon,
  BoltIcon,
  PlayIcon,
  CogIcon,
  Bars3Icon,
  XMarkIcon,
  ArrowRightOnRectangleIcon,
  BeakerIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ServerIcon,
  BuildingOfficeIcon,
  UserGroupIcon,
  ShareIcon,
  ClockIcon,
  CreditCardIcon,
  BanknotesIcon,
  SparklesIcon,
  ChatBubbleBottomCenterTextIcon,
  SignalIcon,
  ChartBarIcon,
  AcademicCapIcon,
  ShoppingBagIcon,
  BuildingStorefrontIcon,
  CheckCircleIcon,
  InboxIcon,
  DocumentTextIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '../../contexts/AuthContext';
import { useSidebar } from '../../contexts/SidebarContext';
import { useLayout } from '../../contexts/LayoutContext';
import { useOnboarding } from '../../contexts/OnboardingContext';
import { useAssistantWebSocket } from '../../hooks/useAssistantWebSocket';
import AdminOnboardingWizard from '../onboarding/AdminOnboardingWizard';
import logo from '../../assets/logo.png';
import HITLNotificationBell from './HITLNotificationBell';

// Lazy load assistant components for better performance
const AssistantPanel = lazy(() => import('../assistant/AssistantPanel'));
const AssistantModal = lazy(() => import('../assistant/AssistantModal'));
const FloatingAssistantButton = lazy(() => import('./FloatingAssistantButton'));

const baseNavigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Flow Examples', href: '/flow-examples', icon: AcademicCapIcon, restricted: true },
  { name: 'Applications', href: '/applications', icon: CubeIcon, restricted: true },
  { name: 'Flows', href: '/flows', icon: BoltIcon },
  { name: 'Published Apps', href: '/published-applications', icon: ShareIcon, restricted: true },
  { name: 'Task Inbox', href: '/tasks', icon: InboxIcon, restricted: true },
  { name: 'Executions', href: '/executions', icon: PlayIcon },
  { name: 'Polling Logs', href: '/polling-logs', icon: ClockIcon, restricted: true },
  { name: 'Settings', href: '/settings', icon: CogIcon },
];

const microSaasNavigation = [
  { name: 'Marketplace', href: '/marketplace', icon: BuildingStorefrontIcon, newTab: true },
  { name: 'My Micro SaaS Apps', href: '/micro-saas', icon: ShoppingBagIcon },
];

const baseOrganizationNavigation = [
  { name: 'Team Members', href: '/admin/users', icon: UserGroupIcon, restricted: true },
  { name: 'API Documentation', href: '/org/api-documentation', icon: DocumentTextIcon },
  { name: 'Billing', href: '/billing', icon: CreditCardIcon, restricted: true },
  { name: 'Usage', href: '/usage', icon: ChartBarIcon, restricted: true },
  { name: 'Subscription', href: '/subscription', icon: BanknotesIcon, restricted: true },
];

const adminNavigation = [
  { name: 'User Management', href: '/admin/users', icon: UserGroupIcon },
  { name: 'Tenant Management', href: '/admin/tenants', icon: BuildingOfficeIcon },
  { name: 'Seed Applications', href: '/admin/seed-applications', icon: ServerIcon },
  { name: 'Flow Agents', href: '/admin/agents', icon: SparklesIcon },
  { name: 'Marketplace Approvals', href: '/admin/marketplace-approvals', icon: CheckCircleIcon },
  { name: 'MCP Services', href: '/mcp-services', icon: BeakerIcon },
];

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { sidebarCollapsed, setSidebarCollapsed } = useSidebar();
  const [adminMenuOpen, setAdminMenuOpen] = useState(false);
  const [organizationMenuOpen, setOrganizationMenuOpen] = useState(false);
  const [microSaasMenuOpen, setMicroSaasMenuOpen] = useState(false);
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const [assistantPanelWidth, setAssistantPanelWidth] = useState(() => {
    // Get saved width from localStorage or use default (330px = 300px + 10%)
    const saved = localStorage.getItem('assistantPanelWidth');
    return saved ? parseInt(saved, 10) : 330;
  });
  const [isResizing, setIsResizing] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const {
    isAssistantLayout,
    isClassicLayout,
    isFloatingAssistantOpen,
    setIsFloatingAssistantOpen,
    isAssistantPanelOpen,
    setIsAssistantPanelOpen
  } = useLayout();

  // Get onboarding wizard state
  const { showWizard, canResumeWizard, resumeWizard } = useOnboarding();

  // Get WebSocket connection status for assistant
  const { connectionStatus } = useAssistantWebSocket(null);

  const isAdmin = user?.role === 'INSTANCE_ADMIN';
  const isRestrictedRole = user?.role === 'FLOW_EXECUTOR' || user?.role === 'EXECUTION_MONITOR';
  const navigation = baseNavigation.filter((item) => !(isRestrictedRole && item.restricted));
  const organizationNavigation = baseOrganizationNavigation.filter((item) => !(isRestrictedRole && item.restricted));

  // In assistant layout, sidebar should only expand when explicitly toggled (not on hover)
  const isSidebarExpanded = !sidebarCollapsed;

  // State to force re-render when dimensions change
  const [, forceUpdate] = useState({});

  // Force re-render when sidebar or assistant panel changes
  useEffect(() => {
    forceUpdate({});
  }, [sidebarCollapsed, isAssistantPanelOpen, assistantPanelWidth]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      forceUpdate({});
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  // Handle mouse move for resizing
  const handleMouseMove = (e) => {
    if (!isResizing) return;

    const sidebarWidth = isSidebarExpanded ? 256 : 64;
    const newWidth = e.clientX - sidebarWidth;

    // Set min and max width constraints
    const minWidth = 250;
    const maxWidth = 600;

    if (newWidth >= minWidth && newWidth <= maxWidth) {
      setAssistantPanelWidth(newWidth);
    }
  };

  // Handle mouse up to stop resizing
  const handleMouseUp = () => {
    if (isResizing) {
      setIsResizing(false);
      // Save the new width to localStorage
      localStorage.setItem('assistantPanelWidth', assistantPanelWidth.toString());
    }
  };

  // Add event listeners for resize
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      // Prevent text selection while resizing
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';

      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      };
    }
  }, [isResizing, isSidebarExpanded, assistantPanelWidth]);

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 md:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75 z-50" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 flex w-64 flex-col bg-white z-50 h-screen">
          <div className="flex-shrink-0 flex h-16 items-center justify-between px-4 header-gradient">
            <div className="flex items-center space-x-2">
              <img src={logo} alt="IOFlow" className="h-8 w-8 rounded-[28%]" />
              <h1 className="text-xl font-bold text-white">IOFlow</h1>
            </div>
            <button
              type="button"
              className="text-white/80 hover:text-white"
              onClick={() => setSidebarOpen(false)}
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'bg-primary-100 text-primary-900'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <item.icon
                    className={`mr-3 h-5 w-5 ${
                      isActive ? 'text-primary-600' : 'text-gray-400'
                    }`}
                  />
                  {item.name}
                </Link>
              );
            })}

            {/* Micro SaaS Section */}
            {!isRestrictedRole && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <button
                onClick={() => setMicroSaasMenuOpen(!microSaasMenuOpen)}
                className="group flex items-center justify-between w-full px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <div className="flex items-center">
                  <ShoppingBagIcon className="mr-3 h-5 w-5 text-gray-400" />
                  Micro SaaS
                </div>
                <ChevronDownIcon
                  className={`h-4 w-4 text-gray-400 transform transition-transform ${
                    microSaasMenuOpen ? 'rotate-180' : ''
                  }`}
                />
              </button>
              {microSaasMenuOpen && (
                <div className="mt-1 space-y-1">
                  {microSaasNavigation.map((item) => {
                    const isActive = location.pathname === item.href;
                    const linkClass = `group flex items-center pl-11 pr-2 py-2 text-sm font-medium rounded-md ${
                      isActive
                        ? 'bg-primary-100 text-primary-900'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`;
                    return item.newTab ? (
                      <a
                        key={item.name}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={linkClass}
                        onClick={() => setSidebarOpen(false)}
                      >
                        <item.icon
                          className={`mr-3 h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                        {item.name}
                      </a>
                    ) : (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={linkClass}
                        onClick={() => setSidebarOpen(false)}
                      >
                        <item.icon
                          className={`mr-3 h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
            )}

            {/* Organization Section */}
            <div className="mt-4 pt-4 border-t border-gray-200">
              <button
                onClick={() => setOrganizationMenuOpen(!organizationMenuOpen)}
                className="group flex items-center justify-between w-full px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <div className="flex items-center">
                  <BuildingOfficeIcon className="mr-3 h-5 w-5 text-gray-400" />
                  My Organization
                </div>
                <ChevronDownIcon
                  className={`h-4 w-4 text-gray-400 transform transition-transform ${
                    organizationMenuOpen ? 'rotate-180' : ''
                  }`}
                />
              </button>
              {organizationMenuOpen && (
                <div className="mt-1 space-y-1">
                  {organizationNavigation.map((item) => {
                    const isActive = location.pathname === item.href;
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={`group flex items-center pl-11 pr-2 py-2 text-sm font-medium rounded-md ${
                          isActive
                            ? 'bg-primary-100 text-primary-900'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                        }`}
                        onClick={() => setSidebarOpen(false)}
                      >
                        <item.icon
                          className={`mr-3 h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Admin Section */}
            {isAdmin && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <button
                  onClick={() => setAdminMenuOpen(!adminMenuOpen)}
                  className="group flex items-center justify-between w-full px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                >
                  <div className="flex items-center">
                    <BeakerIcon className="mr-3 h-5 w-5 text-gray-400" />
                    Admin
                  </div>
                  <ChevronDownIcon
                    className={`h-4 w-4 text-gray-400 transform transition-transform ${
                      adminMenuOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {adminMenuOpen && (
                  <div className="mt-1 space-y-1">
                    {adminNavigation.map((item) => {
                      const isActive = location.pathname === item.href;
                      return (
                        <Link
                          key={item.name}
                          to={item.href}
                          className={`group flex items-center pl-11 pr-2 py-2 text-sm font-medium rounded-md ${
                            isActive
                              ? 'bg-primary-100 text-primary-900'
                              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                          }`}
                          onClick={() => setSidebarOpen(false)}
                        >
                          <item.icon
                            className={`mr-3 h-4 w-4 ${
                              isActive ? 'text-primary-600' : 'text-gray-400'
                            }`}
                          />
                          {item.name}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </nav>
          <div className="flex-shrink-0 border-t border-gray-200 p-4">
            <div className="mb-3">
              <p className="text-sm font-medium text-gray-900">{user?.username}</p>
              <p className="text-xs text-gray-500">{user?.tenant?.tenant_name}</p>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center w-full px-2 py-2 text-sm font-medium text-gray-600 rounded-md hover:bg-gray-50 hover:text-gray-900"
            >
              <ArrowRightOnRectangleIcon className="mr-3 h-5 w-5 text-gray-400" />
              Logout
            </button>
          </div>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div
        className={`hidden md:fixed md:inset-y-0 md:flex md:flex-col transition-all duration-300 ${
          isAssistantLayout ? 'z-30' : 'z-20'
        } ${
          isSidebarExpanded ? 'md:w-64' : 'md:w-16'
        }`}
      >
        <div className={`flex flex-1 flex-col bg-white border-r border-gray-200 h-screen ${
          isAssistantLayout && isSidebarExpanded ? 'shadow-xl' : ''
        }`}>
          <div className="flex-shrink-0 flex h-16 items-center justify-between px-4 header-gradient">
            <div className={`flex items-center ${isSidebarExpanded ? 'space-x-2' : 'justify-center w-full'}`}>
              <img src={logo} alt="IOFlow" className="h-8 w-8 rounded-[28%]" />
              {isSidebarExpanded && <h1 className="text-xl font-bold text-white">IOFlow</h1>}
            </div>
            {/* Always show toggle button, position it differently based on layout */}
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className={`absolute top-[3.25rem] bg-white border border-gray-300 rounded-full p-1 hover:bg-gray-50 z-30 ${
                isAssistantLayout
                  ? (sidebarCollapsed ? 'right-2' : '-right-3')
                  : (sidebarCollapsed ? 'right-[-12px]' : '-right-3')
              }`}
            >
              {sidebarCollapsed ? (
                <ChevronRightIcon className="h-4 w-4 text-gray-600" />
              ) : (
                <ChevronLeftIcon className="h-4 w-4 text-gray-600" />
              )}
            </button>
          </div>
          <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'bg-primary-100 text-primary-900'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  } ${!isSidebarExpanded ? 'justify-center' : ''}`}
                  title={!isSidebarExpanded ? item.name : ''}
                >
                  <item.icon
                    className={`h-5 w-5 ${
                      isActive ? 'text-primary-600' : 'text-gray-400'
                    } ${!isSidebarExpanded ? '' : 'mr-3'}`}
                  />
                  {isSidebarExpanded && item.name}
                </Link>
              );
            })}

            {/* Micro SaaS Section - Desktop */}
            {!isRestrictedRole && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <button
                onClick={() => setMicroSaasMenuOpen(!microSaasMenuOpen)}
                className={`group flex items-center justify-between w-full px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900 ${
                  !isSidebarExpanded ? 'justify-center' : ''
                }`}
                title={!isSidebarExpanded ? 'Micro SaaS' : ''}
              >
                <div className={`flex items-center ${!isSidebarExpanded ? '' : ''}`}>
                  <ShoppingBagIcon className={`h-5 w-5 text-gray-400 ${!isSidebarExpanded ? '' : 'mr-3'}`} />
                  {isSidebarExpanded && 'Micro SaaS'}
                </div>
                {isSidebarExpanded && (
                  <ChevronDownIcon
                    className={`h-4 w-4 text-gray-400 transform transition-transform ${
                      microSaasMenuOpen ? 'rotate-180' : ''
                    }`}
                  />
                )}
              </button>
              {microSaasMenuOpen && isSidebarExpanded && (
                <div className="mt-1 space-y-1">
                  {microSaasNavigation.map((item) => {
                    const isActive = location.pathname === item.href;
                    const linkClass = `group flex items-center pl-11 pr-2 py-2 text-sm font-medium rounded-md ${
                      isActive
                        ? 'bg-primary-100 text-primary-900'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`;
                    return item.newTab ? (
                      <a
                        key={item.name}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={linkClass}
                      >
                        <item.icon
                          className={`mr-3 h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                        {item.name}
                      </a>
                    ) : (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={linkClass}
                      >
                        <item.icon
                          className={`mr-3 h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
              {microSaasMenuOpen && !isSidebarExpanded && (
                <div className="mt-1 space-y-1">
                  {microSaasNavigation.map((item) => {
                    const isActive = location.pathname === item.href;
                    const linkClass = `group flex items-center justify-center px-2 py-2 text-sm font-medium rounded-md ${
                      isActive
                        ? 'bg-primary-100 text-primary-900'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`;
                    return item.newTab ? (
                      <a
                        key={item.name}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={linkClass}
                        title={item.name}
                      >
                        <item.icon
                          className={`h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                      </a>
                    ) : (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={linkClass}
                        title={item.name}
                      >
                        <item.icon
                          className={`h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
            )}

            {/* Organization Section - Desktop */}
            <div className="mt-4 pt-4 border-t border-gray-200">
              <button
                onClick={() => setOrganizationMenuOpen(!organizationMenuOpen)}
                className={`group flex items-center justify-between w-full px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900 ${
                  !isSidebarExpanded ? 'justify-center' : ''
                }`}
                title={!isSidebarExpanded ? 'My Organization' : ''}
              >
                <div className={`flex items-center ${!isSidebarExpanded ? '' : ''}`}>
                  <BuildingOfficeIcon className={`h-5 w-5 text-gray-400 ${!isSidebarExpanded ? '' : 'mr-3'}`} />
                  {isSidebarExpanded && 'My Organization'}
                </div>
                {isSidebarExpanded && (
                  <ChevronDownIcon
                    className={`h-4 w-4 text-gray-400 transform transition-transform ${
                      organizationMenuOpen ? 'rotate-180' : ''
                    }`}
                  />
                )}
              </button>
              {organizationMenuOpen && isSidebarExpanded && (
                <div className="mt-1 space-y-1">
                  {organizationNavigation.map((item) => {
                    const isActive = location.pathname === item.href;
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={`group flex items-center pl-11 pr-2 py-2 text-sm font-medium rounded-md ${
                          isActive
                            ? 'bg-primary-100 text-primary-900'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                        }`}
                      >
                        <item.icon
                          className={`mr-3 h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
              {organizationMenuOpen && !isSidebarExpanded && (
                <div className="mt-1 space-y-1">
                  {organizationNavigation.map((item) => {
                    const isActive = location.pathname === item.href;
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={`group flex items-center justify-center px-2 py-2 text-sm font-medium rounded-md ${
                          isActive
                            ? 'bg-primary-100 text-primary-900'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                        }`}
                        title={item.name}
                      >
                        <item.icon
                          className={`h-4 w-4 ${
                            isActive ? 'text-primary-600' : 'text-gray-400'
                          }`}
                        />
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Admin Section - Desktop */}
            {isAdmin && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <button
                  onClick={() => setAdminMenuOpen(!adminMenuOpen)}
                  className={`group flex items-center justify-between w-full px-2 py-2 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900 ${
                    !isSidebarExpanded ? 'justify-center' : ''
                  }`}
                  title={!isSidebarExpanded ? 'Admin' : ''}
                >
                  <div className={`flex items-center ${!isSidebarExpanded ? '' : ''}`}>
                    <BeakerIcon className={`h-5 w-5 text-gray-400 ${!isSidebarExpanded ? '' : 'mr-3'}`} />
                    {isSidebarExpanded && 'Admin'}
                  </div>
                  {isSidebarExpanded && (
                    <ChevronDownIcon
                      className={`h-4 w-4 text-gray-400 transform transition-transform ${
                        adminMenuOpen ? 'rotate-180' : ''
                      }`}
                    />
                  )}
                </button>
                {adminMenuOpen && isSidebarExpanded && (
                  <div className="mt-1 space-y-1">
                    {adminNavigation.map((item) => {
                      const isActive = location.pathname === item.href;
                      return (
                        <Link
                          key={item.name}
                          to={item.href}
                          className={`group flex items-center pl-11 pr-2 py-2 text-sm font-medium rounded-md ${
                            isActive
                              ? 'bg-primary-100 text-primary-900'
                              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                          }`}
                        >
                          <item.icon
                            className={`mr-3 h-4 w-4 ${
                              isActive ? 'text-primary-600' : 'text-gray-400'
                            }`}
                          />
                          {item.name}
                        </Link>
                      );
                    })}
                  </div>
                )}
                {adminMenuOpen && !isSidebarExpanded && (
                  <div className="mt-1 space-y-1">
                    {adminNavigation.map((item) => {
                      const isActive = location.pathname === item.href;
                      return (
                        <Link
                          key={item.name}
                          to={item.href}
                          className={`group flex items-center justify-center px-2 py-2 text-sm font-medium rounded-md ${
                            isActive
                              ? 'bg-primary-100 text-primary-900'
                              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                          }`}
                          title={item.name}
                        >
                          <item.icon
                            className={`h-4 w-4 ${
                              isActive ? 'text-primary-600' : 'text-gray-400'
                            }`}
                          />
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </nav>
          <div className={`flex-shrink-0 border-t border-gray-200 ${!isSidebarExpanded ? 'p-2' : 'p-4'}`}>
            {isSidebarExpanded && (
              <div className="mb-3">
                <p className="text-sm font-medium text-gray-900">{user?.username}</p>
                <p className="text-xs text-gray-500">{user?.tenant?.tenant_name}</p>
              </div>
            )}
            <button
              onClick={handleLogout}
              className={`flex items-center w-full px-2 py-2 text-sm font-medium text-gray-600 rounded-md hover:bg-gray-50 hover:text-gray-900 ${
                !isSidebarExpanded ? 'justify-center' : ''
              }`}
              title={!isSidebarExpanded ? 'Logout' : ''}
            >
              <ArrowRightOnRectangleIcon className={`h-5 w-5 text-gray-400 ${!isSidebarExpanded ? '' : 'mr-3'}`} />
              {isSidebarExpanded && 'Logout'}
            </button>
          </div>
        </div>
      </div>

      {/* Assistant Panel - Always mounted but only visible in assistant layout */}
      <div
        className="fixed top-0 h-screen z-20 bg-white border-r border-gray-200 shadow-lg"
        style={{
          left: isSidebarExpanded ? '256px' : '64px',
          width: `${assistantPanelWidth}px`,
          transition: isResizing ? 'none' : 'left 300ms',
          display: !isRestrictedRole && isAssistantLayout && typeof window !== 'undefined' && window.innerWidth >= 1024 ? 'flex' : 'none'
        }}>
        <div className="flex-1 relative h-full">
          <Suspense fallback={
            <div className="flex items-center justify-center w-full h-full bg-white">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          }>
            <AssistantPanel onClose={() => setIsAssistantPanelOpen(false)} />
          </Suspense>
        </div>

        {/* Resize Handle - Only interactive when in assistant layout */}
        <div
          onMouseDown={() => isAssistantLayout && setIsResizing(true)}
          className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-primary hover:opacity-50 transition-colors"
          style={{
            backgroundColor: isResizing ? 'rgb(59, 130, 246)' : 'transparent',
            opacity: isResizing ? 0.5 : 1,
            pointerEvents: isAssistantLayout ? 'auto' : 'none'
          }}
        >
          <div className="absolute top-1/2 -translate-y-1/2 right-0 w-1 h-8 bg-gray-300 rounded-full" />
        </div>
      </div>

      {/* Floating Assistant Button - Only visible in classic layout */}
      {!isRestrictedRole && (
        <Suspense fallback={null}>
          {isClassicLayout && <FloatingAssistantButton connectionStatus={connectionStatus} />}
        </Suspense>
      )}

      {/* Assistant Modal - Always mounted but only visible when open */}
      {!isRestrictedRole && (
        <Suspense fallback={null}>
          <AssistantModal
            isOpen={isClassicLayout && isFloatingAssistantOpen}
            onClose={() => setIsFloatingAssistantOpen(false)}
          />
        </Suspense>
      )}

      {/* Main content */}
      <div
        className="flex flex-1 flex-col overflow-hidden transition-all duration-300 min-w-0 min-h-0"
        style={typeof window !== 'undefined' ? {
          marginLeft: window.innerWidth >= 768
            ? isAssistantLayout
              ? window.innerWidth >= 1024
                ? `${(isSidebarExpanded ? 256 : 64) + assistantPanelWidth}px`
                : (isSidebarExpanded ? '256px' : '64px')
              : (isSidebarExpanded ? '256px' : '64px')
            : '0',
          width: window.innerWidth >= 768
            ? isAssistantLayout && window.innerWidth >= 1024
              ? `calc(100% - ${(isSidebarExpanded ? 256 : 64) + assistantPanelWidth}px)`
              : `calc(100% - ${isSidebarExpanded ? 256 : 64}px)`
            : '100%',
          transition: isResizing ? 'none' : 'margin-left 300ms, width 300ms'
        } : {}}>
        <div className="sticky top-0 z-30 header-gradient shadow-lg md:hidden">
          <div className="flex h-16 items-center justify-between px-4">
            <button
              type="button"
              className="text-white/80 hover:text-white"
              onClick={() => setSidebarOpen(true)}
            >
              <Bars3Icon className="h-6 w-6" />
            </button>
            <div className="flex items-center space-x-2">
              <img src={logo} alt="IOFlow" className="h-8 w-8 rounded-[28%]" />
              <h1 className="text-xl font-bold text-white">IOFlow</h1>
            </div>
            <HITLNotificationBell />
          </div>
        </div>

        <main id="main-content" className="flex-1 overflow-x-auto min-w-0 min-h-0">
          <Outlet />
        </main>
      </div>

      {/* Resume Setup Button - shows when wizard was dismissed but setup incomplete */}
      {canResumeWizard && (
        <button
          onClick={resumeWizard}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg shadow-lg hover:bg-blue-700 transition-all hover:scale-105"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
          </svg>
          <span className="font-medium">Resume Setup</span>
        </button>
      )}

      {/* Admin Onboarding Wizard */}
      {showWizard && <AdminOnboardingWizard />}
    </div>
  );
};

export default Layout;