import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import axios from 'axios';
import { AuthProvider } from './contexts/AuthContext';
import { OnboardingProvider } from './contexts/OnboardingContext';
import { FilterProvider } from './contexts/FilterContext';
import { SidebarProvider } from './contexts/SidebarContext';
import { LayoutProvider } from './contexts/LayoutContext';
import PrivateRoute from './components/auth/PrivateRoute';
import Layout from './components/common/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Activate from './pages/Activate';
import ForgotPassword from './components/auth/ForgotPassword';
import ResetPassword from './components/auth/ResetPassword';
import Dashboard from './pages/Dashboard';
import Applications from './pages/Applications';
import ApplicationForm from './pages/ApplicationForm';
import ApplicationDetails from './pages/ApplicationDetails';
import Flows from './pages/Flows';
import FlowExamples from './pages/FlowExamples';
import FlowDesigner from './pages/FlowDesigner';
import FlowDebugger from './pages/FlowDebugger';
import FlowApiDocs from './pages/FlowApiDocs';
import OrgApiDocumentation from './pages/OrgApiDocumentation';
import Executions from './pages/Executions';
import Settings from './pages/Settings';
import Billing from './pages/Billing';
import UsageDashboard from './pages/UsageDashboard';
import SubscriptionPage from './pages/SubscriptionPage';
import PublishedApplications from './pages/PublishedApplications';
import MicroSaasAppsPage from './pages/MicroSaasAppsPage';
import MicroSaasAppSettings from './pages/MicroSaasAppSettings';
import OAuth2Callback from './pages/OAuth2Callback';
import CollaborationJoin from './pages/CollaborationJoin';
import GoogleAuthCallback from './pages/GoogleAuthCallback';
import TwastaAuthCallback from './pages/TwastaAuthCallback';
import SeedApplications from './pages/admin/SeedApplications';
import TenantManagement from './pages/admin/TenantManagement';
import UserManagement from './pages/admin/UserManagement';
import AgentManagement from './pages/admin/AgentManagement';
import MarketplaceApprovalAdmin from './pages/admin/MarketplaceApprovalAdmin';
import PublicFlowApp from './pages/PublicFlowApp';
import PollingLogs from './pages/PollingLogs';
import MCPServices from './pages/MCPServices';
import IOFlowAssistant from './pages/IOFlowAssistant';
import MarketplaceHome from './pages/Marketplace/MarketplaceHome';
import MarketplaceAppDetail from './pages/Marketplace/MarketplaceAppDetail';
import MarketplaceSubscriptions from './pages/Marketplace/MarketplaceSubscriptions';
import LandingPage from './pages/LandingPage';
import AcceptInvitation from './pages/AcceptInvitation';
import TaskInbox from './pages/TaskInbox';
import { PluginRegistryProvider } from './plugins/registry';
import { FilePreviewDialog } from './components/flow/IsolatedParameterInput';

// Axios defaults are now set in AuthContext.js

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  // Log WebSocket service availability on app start
  useEffect(() => {
    console.log('App started, checking WebSocket service...');
    import('./services/websocketService').then(({ default: ws }) => {
      console.log('WebSocket service loaded:', ws);
      console.log('WebSocket methods available:', Object.keys(ws));
    });
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <PluginRegistryProvider>
        <OnboardingProvider>
          <FilterProvider>
            <LayoutProvider>
              <SidebarProvider>
                <Router>
            <div className="min-h-screen bg-gray-50">
            <Toaster 
              position="top-right"
              // Above modals (which use z-[9999]) so messages stay readable
              containerStyle={{ zIndex: 100000 }}
              toastOptions={{
                // Default options for all toasts
                duration: 4000,
                style: {
                  background: '#363636',
                  color: '#fff',
                },
                // Specific options for success toasts
                success: {
                  duration: 3000,
                  iconTheme: {
                    primary: '#10B981',
                    secondary: '#fff',
                  },
                },
                // Specific options for error toasts
                error: {
                  duration: Infinity, // Persist until dismissed
                  style: {
                    background: '#EF4444',
                    color: '#fff',
                  },
                  iconTheme: {
                    primary: '#fff',
                    secondary: '#EF4444',
                  },
                },
              }}
            />
            <FilePreviewDialog />
            <Routes>
              {/* Public Landing Page */}
              <Route path="/" element={<LandingPage />} />

              {/* Public routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/activate" element={<Activate />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/accept-invitation" element={<AcceptInvitation />} />
              <Route path="/oauth2/callback" element={<OAuth2Callback />} />
              <Route path="/auth/callback" element={<GoogleAuthCallback />} />
              <Route path="/auth/twasta/callback" element={<TwastaAuthCallback />} />
              <Route path="/public-app/:slug" element={<PublicFlowApp />} />

              {/* Marketplace routes (public) */}
              <Route path="/marketplace" element={<MarketplaceHome />} />
              <Route path="/marketplace/app/:slug" element={<MarketplaceAppDetail />} />

              {/* Marketplace subscriptions (protected) */}
              <Route path="/marketplace/subscriptions" element={
                <PrivateRoute>
                  <MarketplaceSubscriptions />
                </PrivateRoute>
              } />
              
              {/* Private routes with Layout */}
              <Route element={
                <PrivateRoute>
                  <Layout />
                </PrivateRoute>
              }>
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="flow-examples" element={<FlowExamples />} />
                <Route path="applications" element={<Applications />} />
                <Route path="applications/new" element={<ApplicationForm />} />
                <Route path="applications/:appId" element={<ApplicationDetails />} />
                <Route path="flows" element={<Flows />} />
                <Route path="flows/new" element={<FlowDesigner />} />
                <Route path="flows/:flowId/edit" element={<FlowDesigner />} />
                <Route path="flows/:flowId/debug" element={<FlowDebugger />} />
                <Route path="flows/:flowId/api-docs" element={<FlowApiDocs />} />
                <Route path="org/api-documentation" element={<OrgApiDocumentation />} />
                <Route path="collaborate/join" element={<CollaborationJoin />} />
                <Route path="published-applications" element={<PublishedApplications />} />
                <Route path="micro-saas" element={<MicroSaasAppsPage />} />
                <Route path="micro-saas/:appId" element={<MicroSaasAppSettings />} />
                <Route path="micro-saas/:appId/analytics" element={<MicroSaasAppSettings />} />
                <Route path="mcp-services" element={<MCPServices />} />
                <Route path="assistant" element={<IOFlowAssistant />} />
                <Route path="tasks" element={<TaskInbox />} />
                <Route path="executions" element={<Executions />} />
                <Route path="polling-logs" element={<PollingLogs />} />
                <Route path="billing" element={<Billing />} />
                <Route path="usage" element={<UsageDashboard />} />
                <Route path="settings" element={<Settings />} />
                <Route path="subscription" element={<SubscriptionPage />} />

                {/* Admin routes */}
                <Route path="admin/users" element={<UserManagement />} />
                <Route path="admin/seed-applications" element={<SeedApplications />} />
                <Route path="admin/tenants" element={<TenantManagement />} />
                <Route path="admin/agents" element={<AgentManagement />} />
                <Route path="admin/marketplace-approvals" element={<MarketplaceApprovalAdmin />} />
              </Route>
            </Routes>
          </div>
              </Router>
              </SidebarProvider>
            </LayoutProvider>
          </FilterProvider>
        </OnboardingProvider>
        </PluginRegistryProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;