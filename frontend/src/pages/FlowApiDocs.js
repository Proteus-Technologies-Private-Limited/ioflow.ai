import React, { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { showSuccessToast } from '../utils/customToast';
import {
  ArrowLeftIcon,
  ArrowDownTrayIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  LockClosedIcon,
  ServerIcon,
  CodeBracketIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  BoltIcon,
  ClockIcon,
  DocumentTextIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    showSuccessToast('Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="p-1.5 text-gray-400 hover:text-white rounded transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <ClipboardDocumentCheckIcon className="h-4 w-4 text-green-400" />
      ) : (
        <ClipboardDocumentIcon className="h-4 w-4" />
      )}
    </button>
  );
}

function CodeBlock({ code, language, title }) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-700">
      {title && (
        <div className="bg-gray-800 px-4 py-2 flex items-center justify-between border-b border-gray-700">
          <span className="text-xs font-medium text-gray-300">{title}</span>
          <CopyButton text={code} />
        </div>
      )}
      <div className="relative">
        {!title && (
          <div className="absolute top-2 right-2 z-10">
            <CopyButton text={code} />
          </div>
        )}
        <SyntaxHighlighter
          language={language === 'curl' ? 'bash' : language}
          style={oneDark}
          customStyle={{ margin: 0, borderRadius: title ? '0' : '0.5rem', fontSize: '0.8rem' }}
          showLineNumbers={false}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

function Section({ id, icon: Icon, title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div id={id} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        </div>
        {open ? (
          <ChevronDownIcon className="h-5 w-5 text-gray-400" />
        ) : (
          <ChevronRightIcon className="h-5 w-5 text-gray-400" />
        )}
      </button>
      {open && <div className="px-6 pb-6 border-t border-gray-100">{children}</div>}
    </div>
  );
}

function ParamRow({ param }) {
  return (
    <tr className="border-b border-gray-100 last:border-0">
      <td className="py-3 pr-4">
        <code className="text-sm font-mono text-primary bg-primary/5 px-1.5 py-0.5 rounded">
          {param.name}
        </code>
      </td>
      <td className="py-3 pr-4">
        <span className="text-sm text-gray-600">{param.type}</span>
        {param.is_file && (
          <span className="ml-1.5 text-xs bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">file</span>
        )}
      </td>
      <td className="py-3 pr-4">
        {param.required ? (
          <span className="text-xs font-medium bg-red-50 text-red-600 px-2 py-0.5 rounded">Required</span>
        ) : (
          <span className="text-xs font-medium bg-gray-50 text-gray-500 px-2 py-0.5 rounded">Optional</span>
        )}
      </td>
      <td className="py-3 pr-4 text-sm text-gray-500">
        {param.default !== null && param.default !== undefined && param.default !== '' ? (
          <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">{String(param.default)}</code>
        ) : (
          <span className="text-gray-300">—</span>
        )}
      </td>
      <td className="py-3 text-sm text-gray-600">
        {param.description || <span className="text-gray-300">—</span>}
        {param.validation && (
          <div className="mt-1 text-xs text-gray-400">
            {param.validation.min_length && <span className="mr-2">Min length: {param.validation.min_length}</span>}
            {param.validation.max_length && <span className="mr-2">Max length: {param.validation.max_length}</span>}
            {param.validation.pattern && <span className="mr-2">Pattern: {param.validation.pattern}</span>}
            {param.validation.accepted_file_types && <span>Accepts: {param.validation.accepted_file_types}</span>}
          </div>
        )}
        {param.options && param.options.length > 0 && (
          <div className="mt-1 text-xs text-gray-400">
            Options: {param.options.map(o => typeof o === 'object' ? o.label || o.value : o).join(', ')}
          </div>
        )}
      </td>
    </tr>
  );
}

function generateMarkdown(doc, baseUrl) {
  const lines = [];
  const fence = (code, lang = '') => ['```' + lang, code, '```'].join('\n');
  const json = (v) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2));

  lines.push(`# ${doc.flow_name} — API Documentation`);
  if (doc.description) lines.push('', doc.description);
  lines.push('');
  lines.push(`- **Flow ID:** \`${doc.flow_id}\``);
  lines.push(`- **Status:** ${doc.status}`);
  lines.push(`- **Execution mode:** ${doc.execution_mode.is_synchronous ? 'Synchronous' : 'Asynchronous'}`);
  if (doc.execution_mode.is_synchronous) {
    lines.push(`- **Timeout:** ${doc.execution_mode.sync_timeout}s`);
  }
  lines.push(`- **Recommended endpoint:** \`POST ${doc.execution_mode.is_synchronous ? doc.endpoints.sync.path : doc.endpoints.async.path}\``);
  lines.push('', `Generated from \`${baseUrl}\``, '');

  // Authentication
  lines.push('## Authentication', '', doc.authentication.note || '');
  (doc.authentication.methods || []).forEach((m, i) => {
    lines.push('', `### Method ${i + 1}: ${m.name}`, '', m.description || '');
    if (m.login_endpoint) {
      lines.push('', `\`${m.login_endpoint.method} ${m.login_endpoint.path}\``);
      lines.push('', 'Login response example:', '', fence(json(m.login_endpoint.response_example), 'json'));
    }
    if (m.key_format) {
      lines.push('', `Key format: \`${m.key_format}\``);
    }
    lines.push('', `Header: \`${m.header_format}\``);
  });

  // Endpoints
  lines.push('', '## Endpoints', '');
  ['async', 'sync'].forEach((t) => {
    const ep = doc.endpoints[t];
    lines.push(`- **${ep.method} \`${ep.path}\`**${ep.recommended ? ' _(recommended)_' : ''} — ${ep.description}`);
  });

  // Parameters
  lines.push('', '## Flow Parameters', '');
  if (!doc.parameters || doc.parameters.length === 0) {
    lines.push('_No input parameters configured._');
  } else {
    lines.push('| Name | Type | Required | Default | Description |');
    lines.push('|------|------|----------|---------|-------------|');
    doc.parameters.forEach((p) => {
      lines.push(`| \`${p.name}\` | ${p.type} | ${p.required ? 'Yes' : 'No'} | ${p.default ?? ''} | ${(p.description || '').replace(/\|/g, '\\|')} |`);
    });
  }

  // Request body
  lines.push('', '## Request Body', '', 'Content-Type: `application/json`', '');
  lines.push('| Field | Type | Required | Description |');
  lines.push('|-------|------|----------|-------------|');
  Object.entries(doc.request.body_schema || {}).forEach(([f, info]) => {
    const desc = (info.description || '') + (info.default !== undefined ? ` (default: \`${info.default}\`)` : '');
    lines.push(`| \`${f}\` | ${info.type} | ${info.required ? 'Yes' : 'No'} | ${desc.replace(/\|/g, '\\|')} |`);
  });
  lines.push('', 'Example:', '', fence(json(doc.request.example), 'json'));

  // Code sample (curl)
  lines.push('', '## Sample Request (cURL)', '', fence(generateSampleCode(doc, 'curl', baseUrl), 'bash'));

  // Responses
  lines.push('', '## Responses', '');
  if (doc.sample_response) {
    lines.push('### Sample Response (from actual execution)', '');
    lines.push('_Masked response from the last successful execution. Sensitive values are redacted._', '');
    lines.push(fence(json(doc.sample_response), 'json'));
  }
  lines.push('', `### Async Execution (200 OK)`, '', doc.responses.async_success.description || '');
  lines.push('', fence(json(doc.responses.async_success.example), 'json'));

  const variants = (doc.responses.sync_success.variants && doc.responses.sync_success.variants.length > 0)
    ? doc.responses.sync_success.variants
    : [doc.responses.sync_success];
  variants.forEach((v) => {
    const label = v.label ? ` — ${v.label}` : '';
    lines.push('', `### Sync Execution (${v.status || 200}${label})`, '', v.description || '');
    if (v.output_format && v.output_format !== 'text') {
      lines.push('', `Output format: \`${v.output_format}\``);
    }
    if (Array.isArray(v.fields) && v.fields.length > 0) {
      lines.push('', '| Field | Type | Description |');
      lines.push('|-------|------|-------------|');
      v.fields.forEach((f) => {
        lines.push(`| \`${f.name}\` | ${f.type} | ${(f.description || '').replace(/\|/g, '\\|') || '—'} |`);
      });
    }
    lines.push('', fence(json(v.example), v.output_format === 'xml' ? 'xml' : 'json'));
  });

  // Errors
  lines.push('', '## Error Codes', '');
  lines.push('| Status | Description |');
  lines.push('|--------|-------------|');
  (doc.responses.errors || []).forEach((err) => {
    lines.push(`| ${err.status} | ${(err.description || '').replace(/\|/g, '\\|')} |`);
  });

  return lines.join('\n') + '\n';
}

function downloadMarkdown(doc, baseUrl) {
  const safeName = (doc.flow_name || 'flow').replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'flow';
  const md = generateMarkdown(doc, baseUrl);
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${safeName}-api-docs.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function generateSampleCode(doc, language, baseUrl) {
  const flowId = doc.flow_id;
  const variables = doc.variable_examples || {};
  const varsJson = JSON.stringify(variables, null, 4);
  const endpoint = doc.execution_mode.is_synchronous ? 'execute-direct-sync' : 'execute-direct';

  if (language === 'curl') {
    return `curl -X POST "${baseUrl}/api/v1/flows/${flowId}/${endpoint}" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
  "trigger_type": "manual",
  "variables": ${varsJson.split('\n').map((l, i) => i === 0 ? l : '  ' + l).join('\n')},
  "is_simulation": false
}'`;
  }

  if (language === 'python') {
    return `import requests

BASE_URL = "${baseUrl}"
API_KEY = "YOUR_API_KEY"  # Replace with your actual API key
FLOW_ID = "${flowId}"

response = requests.post(
    f"{BASE_URL}/api/v1/flows/{FLOW_ID}/${endpoint}",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "trigger_type": "manual",
        "variables": ${varsJson.split('\n').map((l, i) => i === 0 ? l : '        ' + l).join('\n')},
        "is_simulation": False
    }
)

print(response.status_code)
print(response.json())`;
  }

  if (language === 'javascript') {
    return `const response = await fetch(
  "${baseUrl}/api/v1/flows/${flowId}/${endpoint}",
  {
    method: "POST",
    headers: {
      "Authorization": "Bearer YOUR_API_KEY",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      trigger_type: "manual",
      variables: ${varsJson.split('\n').map((l, i) => i === 0 ? l : '      ' + l).join('\n')},
      is_simulation: false
    })
  }
);

const data = await response.json();
console.log(data);`;
  }

  if (language === 'php') {
    const phpVars = Object.entries(variables)
      .map(([k, v]) => `        "${k}" => ${JSON.stringify(v)}`)
      .join(",\n");
    return `<?php
$ch = curl_init();

$url = "${baseUrl}/api/v1/flows/${flowId}/${endpoint}";
$payload = json_encode([
    "trigger_type" => "manual",
    "variables" => [
${phpVars}
    ],
    "is_simulation" => false
]);

curl_setopt_array($ch, [
    CURLOPT_URL => $url,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $payload,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer YOUR_API_KEY",
        "Content-Type: application/json"
    ]
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

echo "Status: $httpCode\\n";
echo $response;`;
  }

  return '';
}

const LANGUAGES = [
  { key: 'curl', label: 'cURL' },
  { key: 'python', label: 'Python' },
  { key: 'javascript', label: 'JavaScript' },
  { key: 'php', label: 'PHP' },
];

const NAV_SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'authentication', label: 'Authentication' },
  { id: 'endpoints', label: 'Endpoints' },
  { id: 'parameters', label: 'Parameters' },
  { id: 'request', label: 'Request Body' },
  { id: 'code-samples', label: 'Code Samples' },
  { id: 'responses', label: 'Responses & Sample Output' },
  { id: 'errors', label: 'Error Codes' },
];

export default function FlowApiDocs() {
  const { flowId } = useParams();
  const navigate = useNavigate();
  const [activeLanguage, setActiveLanguage] = useState('curl');
  const token = localStorage.getItem('access_token');
  const contentRef = useRef(null);

  const { data: doc, isLoading, error } = useQuery({
    queryKey: ['flow-api-docs', flowId],
    queryFn: async () => {
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/flows/${flowId}/api-documentation`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      return response.data;
    },
  });

  const baseUrl = window.location.origin;

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <ExclamationTriangleIcon className="h-12 w-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900">Failed to load API documentation</h2>
        <p className="text-gray-500 mt-2">{error.message}</p>
        <button onClick={() => navigate('/flows')} className="mt-4 text-primary hover:underline">
          Back to Flows
        </button>
      </div>
    );
  }

  if (!doc) return null;

  return (
    <div className="flex min-h-full">
      {/* Sidebar Navigation */}
      <div className="hidden lg:block w-56 flex-shrink-0">
        <div className="sticky top-4 p-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">On this page</h3>
          <nav className="space-y-1">
            {NAV_SECTIONS.map((section) => (
              <button
                key={section.id}
                onClick={() => scrollTo(section.id)}
                className="block w-full text-left text-sm text-gray-600 hover:text-primary px-2 py-1.5 rounded hover:bg-primary/5 transition-colors"
              >
                {section.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div ref={contentRef} className="flex-1 max-w-4xl px-4 sm:px-6 py-6 space-y-6">
        {/* Header */}
        <div>
          <button
            onClick={() => navigate('/flows')}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary mb-4 transition-colors"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back to Flows
          </button>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{doc.flow_name}</h1>
              {doc.description && (
                <p className="mt-1 text-gray-500">{doc.description}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => downloadMarkdown(doc, baseUrl)}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
                title="Download API documentation as Markdown"
              >
                <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                Download
              </button>
              <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${
                doc.execution_mode.is_synchronous
                  ? 'bg-blue-50 text-blue-700'
                  : 'bg-purple-50 text-purple-700'
              }`}>
                {doc.execution_mode.is_synchronous ? (
                  <><BoltIcon className="h-3.5 w-3.5" /> Synchronous</>
                ) : (
                  <><ClockIcon className="h-3.5 w-3.5" /> Asynchronous</>
                )}
              </span>
              <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full ${
                doc.status === 'active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
              }`}>
                {doc.status}
              </span>
            </div>
          </div>

          {/* Quick-copy flow ID */}
          <div className="mt-4 flex items-center gap-2 text-sm bg-gray-50 rounded-lg px-4 py-2.5 border border-gray-200">
            <span className="text-gray-500 font-medium">Flow ID:</span>
            <code className="text-sm font-mono text-gray-800">{doc.flow_id}</code>
            <CopyButton text={doc.flow_id} />
          </div>
        </div>

        {/* Overview */}
        <div id="overview" className="bg-blue-50 border border-blue-200 rounded-lg p-5">
          <div className="flex items-start gap-3">
            <InformationCircleIcon className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-blue-800 space-y-2">
              <p><strong>Execution mode:</strong> {doc.execution_mode.description}</p>
              {doc.execution_mode.is_synchronous && (
                <p><strong>Timeout:</strong> {doc.execution_mode.sync_timeout} seconds</p>
              )}
              <p><strong>Recommended endpoint:</strong>{' '}
                <code className="bg-blue-100 px-1.5 py-0.5 rounded text-xs font-mono">
                  POST {doc.execution_mode.is_synchronous ? doc.endpoints.sync.path : doc.endpoints.async.path}
                </code>
              </p>
            </div>
          </div>
        </div>

        {/* Authentication */}
        <Section id="authentication" icon={LockClosedIcon} title="Authentication">
          <div className="mt-4 space-y-6">
            <p className="text-sm text-gray-600">
              {doc.authentication.note} Both methods use the <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">Authorization: Bearer &lt;token&gt;</code> header.
            </p>

            {/* Method 1: Access Token via Login */}
            {doc.authentication.methods?.map((method, idx) => (
              <div key={idx} className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center gap-2">
                  <span className="text-xs font-bold bg-primary/10 text-primary px-2 py-0.5 rounded">Method {idx + 1}</span>
                  <h3 className="text-sm font-semibold text-gray-800">{method.name}</h3>
                </div>
                <div className="p-4 space-y-3">
                  <p className="text-sm text-gray-600">{method.description}</p>

                  {/* Login endpoint details */}
                  {method.login_endpoint && (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold bg-green-100 text-green-700 px-2 py-0.5 rounded">{method.login_endpoint.method}</span>
                        <code className="text-sm font-mono text-gray-800">{method.login_endpoint.path}</code>
                      </div>
                      <p className="text-xs text-gray-500">
                        Content-Type: <code className="bg-gray-100 px-1 py-0.5 rounded">{method.login_endpoint.content_type}</code>
                      </p>
                      <CodeBlock
                        code={`curl -X POST "${window.location.origin}${method.login_endpoint.path}" \\\n  -H "Content-Type: ${method.login_endpoint.content_type}" \\\n  -d "username=your_email@example.com&password=your_password"`}
                        language="bash"
                        title="Login Request"
                      />
                      <CodeBlock
                        code={JSON.stringify(method.login_endpoint.response_example, null, 2)}
                        language="json"
                        title="Login Response"
                      />
                      <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-800">
                        Use the <code className="bg-amber-100 px-1 py-0.5 rounded">access_token</code> from the response in subsequent API calls.
                      </div>
                    </div>
                  )}

                  {/* API Key details */}
                  {method.key_format && (
                    <div className="space-y-2">
                      <div className="bg-gray-50 rounded-md p-3 text-sm">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <span className="text-gray-500 text-xs block mb-1">Key Format</span>
                            <code className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">{method.key_format}</code>
                          </div>
                          <div>
                            <span className="text-gray-500 text-xs block mb-1">Where to Get</span>
                            <span className="text-xs text-gray-800">Settings &rarr; API Keys</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <CodeBlock
                    code={method.header_format}
                    language="text"
                    title="Header Format"
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Endpoints */}
        <Section id="endpoints" icon={ServerIcon} title="Endpoints">
          <div className="mt-4 space-y-4">
            {['async', 'sync'].map((type) => {
              const ep = doc.endpoints[type];
              return (
                <div key={type} className={`rounded-lg border p-4 ${ep.recommended ? 'border-primary bg-primary/5' : 'border-gray-200'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold bg-green-100 text-green-700 px-2 py-0.5 rounded">{ep.method}</span>
                    <code className="text-sm font-mono text-gray-800">{ep.path}</code>
                    {ep.recommended && (
                      <span className="text-xs bg-primary text-white px-2 py-0.5 rounded-full ml-auto">Recommended</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600">{ep.description}</p>
                </div>
              );
            })}
          </div>
        </Section>

        {/* Parameters */}
        <Section id="parameters" icon={DocumentTextIcon} title="Flow Parameters">
          <div className="mt-4">
            {doc.parameters.length === 0 ? (
              <p className="text-sm text-gray-500 italic">This flow has no input parameters configured.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Name</th>
                      <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Type</th>
                      <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Required</th>
                      <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Default</th>
                      <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doc.parameters.map((param) => (
                      <ParamRow key={param.name} param={param} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Section>

        {/* Request Body */}
        <Section id="request" icon={CodeBracketIcon} title="Request Body">
          <div className="mt-4 space-y-4">
            <p className="text-sm text-gray-600">
              Content-Type: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">application/json</code>
            </p>

            {/* Body schema table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Field</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Type</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Required</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(doc.request.body_schema).map(([field, info]) => (
                    <tr key={field} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 pr-4">
                        <code className="font-mono text-sm text-primary bg-primary/5 px-1.5 py-0.5 rounded">{field}</code>
                      </td>
                      <td className="py-2 pr-4 text-gray-600">{info.type}</td>
                      <td className="py-2 pr-4">
                        {info.required ? (
                          <span className="text-xs font-medium bg-red-50 text-red-600 px-2 py-0.5 rounded">Yes</span>
                        ) : (
                          <span className="text-xs font-medium bg-gray-50 text-gray-500 px-2 py-0.5 rounded">No</span>
                        )}
                      </td>
                      <td className="py-2 text-gray-600">
                        {info.description}
                        {info.default !== undefined && (
                          <span className="ml-1 text-gray-400">(default: <code className="text-xs">{String(info.default)}</code>)</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <CodeBlock
              code={JSON.stringify(doc.request.example, null, 2)}
              language="json"
              title="Example Request Body"
            />
          </div>
        </Section>

        {/* Code Samples */}
        <Section id="code-samples" icon={CodeBracketIcon} title="Code Samples">
          <div className="mt-4 space-y-4">
            {/* Language tabs */}
            <div className="flex border-b border-gray-200">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.key}
                  onClick={() => setActiveLanguage(lang.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeLanguage === lang.key
                      ? 'border-primary text-primary'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>

            <CodeBlock
              code={generateSampleCode(doc, activeLanguage, baseUrl)}
              language={activeLanguage}
              title={`${LANGUAGES.find(l => l.key === activeLanguage)?.label} Example`}
            />
          </div>
        </Section>

        {/* Responses */}
        <Section id="responses" icon={CheckCircleIcon} title="Responses">
          <div className="mt-4 space-y-6">
            {/* Sample Response from actual execution */}
            {doc.sample_response && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">Sample Response (from actual execution)</h3>
                  <span className="text-xs bg-green-50 text-green-600 px-2 py-0.5 rounded-full">Live Data</span>
                </div>
                <p className="text-sm text-gray-500 mb-2">
                  This is a masked response from the last successful execution of this flow. Sensitive values have been redacted.
                </p>
                <CodeBlock
                  code={JSON.stringify(doc.sample_response, null, 2)}
                  language="json"
                  title={`Status: ${doc.sample_response.response_status || 200}`}
                />
              </div>
            )}

            <hr className="border-gray-200" />

            {/* Async success */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Async Execution (200 OK)</h3>
              <p className="text-sm text-gray-500 mb-2">{doc.responses.async_success.description}</p>
              <CodeBlock
                code={JSON.stringify(doc.responses.async_success.example, null, 2)}
                language="json"
              />
            </div>

            {/* Sync success - one block per Response node */}
            {(doc.responses.sync_success.variants && doc.responses.sync_success.variants.length > 0
              ? doc.responses.sync_success.variants
              : [doc.responses.sync_success]
            ).map((variant, vIdx) => (
              <div key={vIdx}>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-gray-700">
                    Sync Execution ({variant.status || 200} {variant.label ? `— ${variant.label}` : 'OK'})
                  </h3>
                  {variant.output_format && variant.output_format !== 'text' && (
                    <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full uppercase">
                      {variant.output_format}
                    </span>
                  )}
                  {variant.has_schema === false && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                      No schema defined
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500 mb-2">{variant.description}</p>

                {/* Output field descriptions table */}
                {Array.isArray(variant.fields) && variant.fields.length > 0 && (
                  <div className="overflow-x-auto mb-3">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Field</th>
                          <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Type</th>
                          <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {variant.fields.map((f) => (
                          <tr key={f.name} className="border-b border-gray-100 last:border-0">
                            <td className="py-2 pr-4">
                              <code className="font-mono text-sm text-primary bg-primary/5 px-1.5 py-0.5 rounded">{f.name}</code>
                            </td>
                            <td className="py-2 pr-4 text-gray-600">{f.type}</td>
                            <td className="py-2 text-gray-600">{f.description || <span className="text-gray-400 italic">—</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <CodeBlock
                  code={typeof variant.example === 'string' ? variant.example : JSON.stringify(variant.example, null, 2)}
                  language={variant.output_format === 'xml' ? 'xml' : 'json'}
                />
              </div>
            ))}
          </div>
        </Section>

        {/* Error Codes */}
        <Section id="errors" icon={ExclamationTriangleIcon} title="Error Codes">
          <div className="mt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="pb-2 text-xs font-semibold text-gray-500 uppercase w-24">Status</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 uppercase">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.responses.errors.map((err) => (
                    <tr key={err.status} className="border-b border-gray-100 last:border-0">
                      <td className="py-3 pr-4">
                        <span className={`text-sm font-mono font-bold ${
                          err.status >= 500 ? 'text-red-600' : err.status >= 400 ? 'text-amber-600' : 'text-gray-600'
                        }`}>
                          {err.status}
                        </span>
                      </td>
                      <td className="py-3 text-sm text-gray-600">{err.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 402 example */}
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">402 Payment Required Example</h3>
              <CodeBlock
                code={JSON.stringify(
                  doc.responses.errors.find(e => e.status === 402)?.example || {},
                  null,
                  2
                )}
                language="json"
              />
            </div>
          </div>
        </Section>
      </div>
    </div>
  );
}
