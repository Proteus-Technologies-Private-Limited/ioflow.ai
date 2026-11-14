#!/usr/bin/env node
/**
 * IOFlow MCP Proxy - Translates MCP stdio protocol to IOFlow HTTP bridge API
 *
 * No external dependencies required - uses Node.js built-in fetch.
 * Connects to IOFlow server via HTTP, exposes tools via MCP stdio.
 */

const BASE_URL = process.env.IOFLOW_BASE_URL || 'http://localhost:7001';
const API_KEY = process.env.IOFLOW_API_KEY || '';

if (!API_KEY) {
  process.stderr.write('ERROR: IOFLOW_API_KEY not set\n');
  process.exit(1);
}

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json'
};

// Cached tool list
let cachedTools = null;

async function fetchTools() {
  if (cachedTools) return cachedTools;
  try {
    const res = await fetch(`${BASE_URL}/api/mcp/tools`, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    cachedTools = await res.json();
    process.stderr.write(`IOFlow MCP Proxy: Loaded ${cachedTools.length} tools from ${BASE_URL}\n`);
    return cachedTools;
  } catch (e) {
    process.stderr.write(`ERROR fetching tools: ${e.message}\n`);
    return [];
  }
}

async function executeTool(name, params) {
  try {
    const res = await fetch(`${BASE_URL}/api/mcp/tools/execute`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ tool: name, parameters: params || {} })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    const data = await res.json();
    return data;
  } catch (e) {
    return { success: false, error: e.message, tool: name };
  }
}

function sendResponse(id, result) {
  const msg = JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n';
  process.stdout.write(msg);
}

function sendError(id, code, message) {
  const msg = JSON.stringify({ jsonrpc: '2.0', id, error: { code, message } }) + '\n';
  process.stdout.write(msg);
}

async function handleRequest(req) {
  const { id, method, params } = req;

  switch (method) {
    case 'initialize': {
      sendResponse(id, {
        protocolVersion: '2024-11-05',
        capabilities: {
          tools: { listChanged: false }
        },
        serverInfo: {
          name: 'ioflow-mcp-proxy',
          version: '1.0.0'
        }
      });
      break;
    }

    case 'notifications/initialized': {
      // No response needed for notifications
      break;
    }

    case 'tools/list': {
      const tools = await fetchTools();
      const mcpTools = tools.map(t => ({
        name: t.name,
        description: t.description || '',
        inputSchema: t.input_schema || { type: 'object', properties: {} }
      }));
      sendResponse(id, { tools: mcpTools });
      break;
    }

    case 'tools/call': {
      const toolName = params?.name;
      const toolArgs = params?.arguments || {};
      const result = await executeTool(toolName, toolArgs);

      const content = [{
        type: 'text',
        text: JSON.stringify(result.result || result, null, 2)
      }];

      sendResponse(id, {
        content,
        isError: result.success === false
      });
      break;
    }

    case 'resources/list': {
      sendResponse(id, { resources: [] });
      break;
    }

    case 'prompts/list': {
      sendResponse(id, { prompts: [] });
      break;
    }

    case 'ping': {
      sendResponse(id, {});
      break;
    }

    default: {
      if (id !== undefined) {
        sendError(id, -32601, `Method not found: ${method}`);
      }
    }
  }
}

// Read JSON-RPC messages from stdin
let buffer = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buffer += chunk;

  // Process complete lines
  let newlineIdx;
  while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
    const line = buffer.slice(0, newlineIdx).trim();
    buffer = buffer.slice(newlineIdx + 1);

    if (!line) continue;

    try {
      const req = JSON.parse(line);
      handleRequest(req).catch(e => {
        process.stderr.write(`Error handling request: ${e.message}\n`);
        if (req.id !== undefined) {
          sendError(req.id, -32603, e.message);
        }
      });
    } catch (e) {
      process.stderr.write(`Invalid JSON: ${line}\n`);
    }
  }
});

process.stdin.on('end', () => {
  process.exit(0);
});

process.stderr.write(`IOFlow MCP Proxy starting - connecting to ${BASE_URL}\n`);
