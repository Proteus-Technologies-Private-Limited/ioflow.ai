/**
 * Demo walkthrough content for each segment
 */

export const demoContent = {
  enterprise: {
    title: 'Build a Customer Onboarding Workflow',
    description: 'See how enterprise teams automate complex processes',
    steps: [
      {
        id: 1,
        title: 'Configure Webhook Trigger',
        description: 'Set up an API endpoint that receives customer data from your CRM or signup form.',
        animation: 'trigger-pulse',
        nodeType: 'trigger',
        icon: 'Webhook',
        mockData: {
          input: '{ "name": "John Doe", "email": "john@company.com", "plan": "enterprise" }'
        }
      },
      {
        id: 2,
        title: 'Validate with AI',
        description: 'Use Claude or GPT to validate the data, enrich it, and detect potential issues.',
        animation: 'ai-process',
        nodeType: 'ai',
        icon: 'Brain',
        mockData: {
          prompt: 'Validate customer data and check for completeness',
          result: '{ "valid": true, "enriched": { "company_size": "50-200", "industry": "Tech" } }'
        }
      },
      {
        id: 3,
        title: 'Store in Database',
        description: 'Save the validated customer record to your PostgreSQL or MySQL database.',
        animation: 'db-write',
        nodeType: 'database',
        icon: 'Database',
        mockData: {
          query: 'INSERT INTO customers (name, email, plan, metadata) VALUES (...)',
          result: 'Customer record created with ID: 12345'
        }
      },
      {
        id: 4,
        title: 'Send Welcome Email',
        description: 'Trigger a personalized welcome email with onboarding instructions.',
        animation: 'email-send',
        nodeType: 'action',
        icon: 'Mail',
        mockData: {
          to: 'john@company.com',
          subject: 'Welcome to our platform!'
        }
      },
      {
        id: 5,
        title: 'View Execution Results',
        description: 'See the complete execution flow with timing, logs, and results.',
        animation: 'result-display',
        nodeType: 'result',
        icon: 'CheckCircle',
        mockData: {
          status: 'Success',
          duration: '1.2s',
          steps: 4
        }
      }
    ]
  },
  developers: {
    title: 'Publish Your First Micro SaaS App',
    description: 'Turn your workflow into a revenue-generating product',
    steps: [
      {
        id: 1,
        title: 'Design Your Flow',
        description: 'Use the visual editor to create your automation with drag-and-drop nodes.',
        animation: 'flow-build',
        nodeType: 'design',
        icon: 'Workflow',
        mockData: {
          nodes: 5,
          type: 'PDF Invoice Processor'
        }
      },
      {
        id: 2,
        title: 'Configure Input Form',
        description: 'Define what inputs your users need to provide - files, text, options.',
        animation: 'form-setup',
        nodeType: 'form',
        icon: 'FormInput',
        mockData: {
          fields: ['Upload PDF', 'Select Output Format', 'Email Results']
        }
      },
      {
        id: 3,
        title: 'Set Pricing Model',
        description: 'Choose how to charge - per user monthly, per execution, or offer a free tier.',
        animation: 'pricing-config',
        nodeType: 'pricing',
        icon: 'DollarSign',
        mockData: {
          model: 'Per Execution',
          price: '$0.05/run',
          freeQuota: '10 free/month'
        }
      },
      {
        id: 4,
        title: 'Publish to Marketplace',
        description: 'Submit for review and once approved, your app goes live for all users.',
        animation: 'publish',
        nodeType: 'publish',
        icon: 'Rocket',
        mockData: {
          visibility: 'Public',
          category: 'Document Processing'
        }
      },
      {
        id: 5,
        title: 'Track Your Analytics',
        description: 'Monitor subscribers, executions, and revenue from your dashboard.',
        animation: 'analytics-show',
        nodeType: 'analytics',
        icon: 'TrendingUp',
        mockData: {
          subscribers: 127,
          executions: '2,340',
          revenue: '$117.00'
        }
      }
    ]
  },
  business: {
    title: 'Automate Invoice Processing',
    description: 'See how easy it is to automate repetitive tasks',
    steps: [
      {
        id: 1,
        title: 'Browse the Marketplace',
        description: 'Find an invoice processing app from our curated marketplace.',
        animation: 'browse-search',
        nodeType: 'browse',
        icon: 'Search',
        mockData: {
          query: 'invoice processing',
          results: 12
        }
      },
      {
        id: 2,
        title: 'Subscribe Instantly',
        description: 'Click subscribe - no credit card required for free apps.',
        animation: 'subscribe-click',
        nodeType: 'subscribe',
        icon: 'CheckCircle',
        mockData: {
          app: 'Smart Invoice Extractor',
          price: 'Free'
        }
      },
      {
        id: 3,
        title: 'Upload Your File',
        description: 'Simply drag and drop your invoice PDF to the app.',
        animation: 'file-upload',
        nodeType: 'upload',
        icon: 'Upload',
        mockData: {
          file: 'invoice_march_2024.pdf',
          size: '245 KB'
        }
      },
      {
        id: 4,
        title: 'View Extracted Data',
        description: 'The app automatically extracts vendor, amount, date, and line items.',
        animation: 'data-extract',
        nodeType: 'extract',
        icon: 'FileSpreadsheet',
        mockData: {
          vendor: 'ACME Corp',
          amount: '$1,234.56',
          date: '2024-03-15',
          items: 5
        }
      },
      {
        id: 5,
        title: 'Export to Spreadsheet',
        description: 'Send the data directly to your Google Sheets or download as Excel.',
        animation: 'export',
        nodeType: 'export',
        icon: 'Download',
        mockData: {
          format: 'Google Sheets',
          rows: 5,
          status: 'Exported!'
        }
      }
    ]
  }
};

export default demoContent;
