import React, { useState } from 'react';
import { QuestionMarkCircleIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { ClipboardDocumentIcon } from '@heroicons/react/24/solid';
import { showSuccessToast } from '../../utils/customToast';

const EmailConfigHelp = ({ application }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState('gmail');

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    showSuccessToast('Copied to clipboard!', 2000);
  };

  // Only show for email applications
  if (application?.app_type !== 'email') {
    return null;
  }

  const emailProviders = {
    gmail: {
      name: 'Gmail',
      smtp: 'smtp://smtp.gmail.com:587',
      smtps: 'smtps://smtp.gmail.com:465',
      imap: 'imaps://imap.gmail.com:993',
      pop3: 'pop3s://pop.gmail.com:995',
      steps: [
        'Enable 2-Step Verification in Google Account',
        'Go to Security → 2-Step Verification → App passwords',
        'Generate an app password for "Mail"',
        'Use the 16-character app password (not your regular password)',
        'Enable IMAP/POP in Gmail settings if needed'
      ],
      link: 'https://myaccount.google.com/security'
    },
    outlook: {
      name: 'Outlook/Office 365',
      smtp: 'smtp://smtp-mail.outlook.com:587',
      imap: 'imaps://outlook.office365.com:993',
      pop3: 'pop3s://outlook.office365.com:995',
      steps: [
        'May require app password if 2FA is enabled',
        'Go to Microsoft Account Security',
        'Create an app password under "Advanced security options"',
        'Use your full email address as username'
      ],
      link: 'https://account.microsoft.com/security'
    },
    yahoo: {
      name: 'Yahoo Mail',
      smtp: 'smtp://smtp.mail.yahoo.com:587',
      smtps: 'smtps://smtp.mail.yahoo.com:465',
      imap: 'imaps://imap.mail.yahoo.com:993',
      pop3: 'pop3s://pop.mail.yahoo.com:995',
      steps: [
        'Generate an app password in Yahoo Account settings',
        'Go to Account Security → Generate app password',
        'Select "Mail" as the app',
        'Use the generated password instead of your regular password'
      ],
      link: 'https://login.yahoo.com/account/security'
    }
  };

  return (
    <div className="mt-4 border border-blue-200 rounded-lg bg-blue-50 p-4">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full text-left"
      >
        <div className="flex items-center space-x-2">
          <QuestionMarkCircleIcon className="h-5 w-5 text-blue-600" />
          <span className="text-sm font-medium text-blue-900">
            Email Configuration Help
          </span>
        </div>
        {isExpanded ? (
          <ChevronUpIcon className="h-5 w-5 text-blue-600" />
        ) : (
          <ChevronDownIcon className="h-5 w-5 text-blue-600" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-4">
          {/* Provider Tabs */}
          <div className="flex space-x-2 mb-4">
            {Object.keys(emailProviders).map((key) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  activeTab === key
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-100'
                }`}
              >
                {emailProviders[key].name}
              </button>
            ))}
          </div>

          {/* Provider Content */}
          <div className="bg-white rounded-md p-4">
            <h4 className="font-medium text-gray-900 mb-3">
              {emailProviders[activeTab].name} Configuration
            </h4>

            {/* Server URLs */}
            <div className="space-y-2 mb-4">
              <div className="text-sm">
                <span className="font-medium text-gray-700">SMTP:</span>
                <div className="flex items-center mt-1 space-x-2">
                  <code className="bg-gray-100 px-2 py-1 rounded text-xs flex-1">
                    {emailProviders[activeTab].smtp}
                  </code>
                  <button
                    onClick={() => copyToClipboard(emailProviders[activeTab].smtp)}
                    className="p-1 hover:bg-gray-100 rounded"
                    title="Copy to clipboard"
                  >
                    <ClipboardDocumentIcon className="h-4 w-4 text-gray-600" />
                  </button>
                </div>
                {emailProviders[activeTab].smtps && (
                  <div className="flex items-center mt-1 space-x-2">
                    <code className="bg-gray-100 px-2 py-1 rounded text-xs flex-1">
                      {emailProviders[activeTab].smtps}
                    </code>
                    <button
                      onClick={() => copyToClipboard(emailProviders[activeTab].smtps)}
                      className="p-1 hover:bg-gray-100 rounded"
                      title="Copy to clipboard"
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 text-gray-600" />
                    </button>
                  </div>
                )}
              </div>

              {emailProviders[activeTab].imap && (
                <div className="text-sm">
                  <span className="font-medium text-gray-700">IMAP:</span>
                  <div className="flex items-center mt-1 space-x-2">
                    <code className="bg-gray-100 px-2 py-1 rounded text-xs flex-1">
                      {emailProviders[activeTab].imap}
                    </code>
                    <button
                      onClick={() => copyToClipboard(emailProviders[activeTab].imap)}
                      className="p-1 hover:bg-gray-100 rounded"
                      title="Copy to clipboard"
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 text-gray-600" />
                    </button>
                  </div>
                </div>
              )}

              {emailProviders[activeTab].pop3 && (
                <div className="text-sm">
                  <span className="font-medium text-gray-700">POP3:</span>
                  <div className="flex items-center mt-1 space-x-2">
                    <code className="bg-gray-100 px-2 py-1 rounded text-xs flex-1">
                      {emailProviders[activeTab].pop3}
                    </code>
                    <button
                      onClick={() => copyToClipboard(emailProviders[activeTab].pop3)}
                      className="p-1 hover:bg-gray-100 rounded"
                      title="Copy to clipboard"
                    >
                      <ClipboardDocumentIcon className="h-4 w-4 text-gray-600" />
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Setup Steps */}
            <div className="border-t pt-3">
              <h5 className="font-medium text-gray-900 text-sm mb-2">Setup Steps:</h5>
              <ol className="list-decimal list-inside space-y-1 text-sm text-gray-600">
                {emailProviders[activeTab].steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            </div>

            {/* Account Settings Link */}
            <div className="mt-4 pt-3 border-t">
              <a
                href={emailProviders[activeTab].link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700"
              >
                Open {emailProviders[activeTab].name} Security Settings →
              </a>
            </div>

            {/* Important Note */}
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-sm text-amber-800">
                <strong>Important:</strong> Always use App Passwords, not your regular password, 
                when connecting third-party applications to your email account.
              </p>
            </div>
          </div>

          {/* Port Reference */}
          <div className="mt-4 p-3 bg-gray-50 rounded-md">
            <h5 className="font-medium text-gray-900 text-sm mb-2">Quick Port Reference:</h5>
            <ul className="text-xs text-gray-600 space-y-1">
              <li>• Port 587 → Use <code className="bg-gray-200 px-1">smtp://</code> (STARTTLS)</li>
              <li>• Port 465 → Use <code className="bg-gray-200 px-1">smtps://</code> (Direct SSL)</li>
              <li>• Port 993 → Use <code className="bg-gray-200 px-1">imaps://</code> (IMAP SSL)</li>
              <li>• Port 995 → Use <code className="bg-gray-200 px-1">pop3s://</code> (POP3 SSL)</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailConfigHelp;