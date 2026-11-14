/**
 * Feature content data for each customer segment
 */

export const segmentData = {
  enterprise: {
    id: 'enterprise',
    title: 'Enterprise & ISV',
    subtitle: 'Build powerful integrations without limits',
    description: 'Connect any system, automate complex workflows, and leverage AI - even without ready-made connectors.',
    icon: 'Building2',
    features: [
      {
        id: 'ioflow-assistant',
        title: 'IOFlow Assistant',
        description: 'Create custom connectors by describing the API in plain English - no coding required.',
        icon: 'Sparkles',
        demoId: 'enterprise-assistant'
      },
      {
        id: 'ai-agents',
        title: 'AI Agent Builder',
        description: 'Build intelligent AI agents that make decisions and take actions within your workflows.',
        icon: 'Brain',
        demoId: 'enterprise-ai'
      },
      {
        id: 'connectors',
        title: '40+ Pre-built Connectors',
        description: 'Connect to databases, APIs, cloud services, and enterprise systems out of the box.',
        icon: 'Plug',
        demoId: 'enterprise-connectors'
      },
      {
        id: 'file-processing',
        title: '56+ File Operations',
        description: 'Process PDFs, images, spreadsheets with OCR, extraction, and transformation.',
        icon: 'FileStack',
        demoId: 'enterprise-files'
      },
      {
        id: 'databases',
        title: 'Database Management',
        description: 'Direct connections to PostgreSQL, MySQL, Oracle, and more.',
        icon: 'Database',
        demoId: 'enterprise-db'
      },
      {
        id: 'custom-apis',
        title: 'Custom API Builder',
        description: 'Create integrations for any API - REST, GraphQL, or custom protocols.',
        icon: 'Code2',
        demoId: 'enterprise-api'
      },
      {
        id: 'webhooks',
        title: 'Real-time Webhooks',
        description: 'Trigger workflows from any external event with secure webhook endpoints.',
        icon: 'Webhook',
        demoId: 'enterprise-webhooks'
      }
    ]
  },
  developers: {
    id: 'developers',
    title: 'No-Code Developers',
    subtitle: 'Build and monetize your own Micro SaaS',
    description: 'Design workflows visually, publish them as products, and earn from every user or execution.',
    icon: 'Rocket',
    features: [
      {
        id: 'ioflow-assistant',
        title: 'IOFlow Assistant',
        description: 'Design entire workflow automations using simple descriptions - AI builds it for you.',
        icon: 'Sparkles',
        demoId: 'dev-assistant'
      },
      {
        id: 'ai-agents',
        title: 'AI Agent Builder',
        description: 'Add Claude, GPT, or Gemini-powered intelligence to your Micro SaaS apps.',
        icon: 'Brain',
        demoId: 'dev-ai'
      },
      {
        id: 'visual-builder',
        title: 'Visual Flow Builder',
        description: 'Drag-and-drop interface to design complex workflows without writing code.',
        icon: 'Workflow',
        demoId: 'dev-builder'
      },
      {
        id: 'marketplace',
        title: 'Marketplace Publishing',
        description: 'Publish your apps to the marketplace and reach thousands of users.',
        icon: 'Store',
        demoId: 'dev-publish'
      },
      {
        id: 'billing',
        title: 'Flexible Billing Models',
        description: 'Charge per user, per execution, or offer free tiers - you decide.',
        icon: 'CreditCard',
        demoId: 'dev-billing'
      },
      {
        id: 'analytics',
        title: 'Usage Analytics',
        description: 'Track executions, revenue, and user engagement with detailed dashboards.',
        icon: 'BarChart3',
        demoId: 'dev-analytics'
      },
      {
        id: 'documentation',
        title: 'Built-in Documentation',
        description: 'Create user guides and API docs that appear alongside your app.',
        icon: 'BookOpen',
        demoId: 'dev-docs'
      },
      {
        id: 'subscribers',
        title: 'Subscriber Management',
        description: 'View and manage your subscribers, grant access, and handle support.',
        icon: 'Users',
        demoId: 'dev-subscribers'
      }
    ]
  },
  business: {
    id: 'business',
    title: 'Business Users',
    subtitle: 'Automate your daily tasks in minutes',
    description: 'Browse ready-made workflows, subscribe with one click, and start automating immediately.',
    icon: 'Briefcase',
    features: [
      {
        id: 'ioflow-assistant',
        title: 'IOFlow Assistant',
        description: 'Modify and customize workflows just by describing what you need - no technical skills required.',
        icon: 'Sparkles',
        demoId: 'biz-assistant'
      },
      {
        id: 'ai-automation',
        title: 'AI-Powered Automation',
        description: 'Let AI handle complex decision-making in your automations automatically.',
        icon: 'Brain',
        demoId: 'biz-ai'
      },
      {
        id: 'marketplace-browse',
        title: 'Browse Ready-Made Apps',
        description: 'Explore hundreds of pre-built automation apps for common business tasks.',
        icon: 'Search',
        demoId: 'biz-browse'
      },
      {
        id: 'one-click',
        title: 'One-Click Subscribe',
        description: 'Subscribe to any app instantly and start using it right away.',
        icon: 'MousePointerClick',
        demoId: 'biz-subscribe'
      },
      {
        id: 'simple-execute',
        title: 'Simple Execution',
        description: 'Run automations with easy forms - no technical knowledge required.',
        icon: 'Play',
        demoId: 'biz-execute'
      },
      {
        id: 'file-automation',
        title: 'File Automation',
        description: 'Process invoices, extract data from PDFs, convert documents automatically.',
        icon: 'FileText',
        demoId: 'biz-files'
      },
      {
        id: 'integrations',
        title: 'Connect Your Tools',
        description: 'Link your Google Sheets, email, CRM, and other daily tools.',
        icon: 'Link',
        demoId: 'biz-integrate'
      },
      {
        id: 'scheduling',
        title: 'Schedule & Forget',
        description: 'Set up recurring automations that run on your schedule.',
        icon: 'Clock',
        demoId: 'biz-schedule'
      }
    ]
  }
};

export const segments = ['enterprise', 'developers', 'business'];

export default segmentData;
