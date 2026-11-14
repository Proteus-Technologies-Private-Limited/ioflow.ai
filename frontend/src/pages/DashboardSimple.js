import React from 'react';
import { useAuth } from '../contexts/AuthContext';

const DashboardSimple = () => {
  const { user } = useAuth();

  return (
    <div className="py-6 px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">
          Welcome back, {user?.username || 'User'}!
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          Dashboard is loading...
        </p>
        <div className="mt-4 p-4 bg-white rounded shadow">
          <h2 className="text-lg font-medium mb-2">Debug Info:</h2>
          <pre className="text-xs bg-gray-100 p-2 rounded">
            {JSON.stringify(user, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default DashboardSimple;