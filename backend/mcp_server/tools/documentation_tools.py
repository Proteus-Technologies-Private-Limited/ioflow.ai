"""
MCP Tools for IOFlow Application Documentation
"""

from typing import Dict, Any, Optional
from mcp.types import Tool, TextContent
from ..services.documentation_service import DocumentationService

class DocumentationTools:
    """MCP tools for accessing IOFlow application documentation"""
    
    def __init__(self):
        self.doc_service = DocumentationService()
    
    def get_tools(self) -> list[Tool]:
        """Return list of documentation tools"""
        return [
            Tool(
                name="ioflow_get_service_docs",
                description="Get documentation for creating IOFlow application services. Optionally specify a service_type (api_call, webhook, database_query, email_send, llm_api_call, mcp_call) for detailed information.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service_type": {
                            "type": "string",
                            "description": "Optional: Specific service type to get detailed documentation for",
                            "enum": ["api_call", "webhook", "database_query", "email_send", "llm_api_call", "mcp_call"]
                        }
                    }
                }
            ),
            Tool(
                name="ioflow_get_event_docs",
                description="Get documentation for creating IOFlow application events. Optionally specify an event_type (webhook, schedule, polling, api_call, manual, email, form) for detailed information.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "description": "Optional: Specific event type to get detailed documentation for",
                            "enum": ["webhook", "schedule", "polling", "api_call", "manual", "email", "form", "mqtt"]
                        }
                    }
                }
            ),
            Tool(
                name="ioflow_get_app_guide",
                description="Get complete guide for creating IOFlow applications with services and events, including best practices and examples.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="ioflow_search_docs",
                description="Search IOFlow documentation for specific terms or concepts.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        }
                    },
                    "required": ["query"]
                }
            )
        ]
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> list[TextContent]:
        """Handle documentation tool calls"""
        
        try:
            if name == "ioflow_get_service_docs":
                service_type = arguments.get("service_type")
                result = self.doc_service.get_service_documentation(service_type)
                
                if service_type:
                    # Format detailed service documentation
                    content = self._format_service_details(result)
                else:
                    # Format service overview
                    content = self._format_service_overview(result)
                
            elif name == "ioflow_get_event_docs":
                event_type = arguments.get("event_type")
                result = self.doc_service.get_event_documentation(event_type)
                
                if event_type:
                    # Format detailed event documentation
                    content = self._format_event_details(result)
                else:
                    # Format event overview
                    content = self._format_event_overview(result)
                
            elif name == "ioflow_get_app_guide":
                result = self.doc_service.get_complete_guide()
                content = self._format_complete_guide(result)
                
            elif name == "ioflow_search_docs":
                query = arguments.get("query", "")
                result = self.doc_service.search_documentation(query)
                content = self._format_search_results(result)
                
            else:
                content = f"Unknown documentation tool: {name}"
            
            return [TextContent(type="text", text=content)]
            
        except Exception as e:
            error_msg = f"Error in documentation tool '{name}': {str(e)}"
            return [TextContent(type="text", text=error_msg)]
    
    def _format_service_details(self, doc: Dict[str, Any]) -> str:
        """Format detailed service documentation"""
        
        if "error" in doc:
            return f"❌ {doc['error']}\n\nAvailable types: {', '.join(doc['available_types'])}"
        
        content = f"# {doc['name']} Documentation\n\n"
        content += f"**Type:** `{doc['service_type']}`\n"
        content += f"**Description:** {doc['description']}\n\n"
        
        content += "## Configuration\n\n"
        content += "### Required Fields\n"
        for field in doc['configuration']['required']:
            content += f"- `{field}`\n"
        
        if doc['configuration']['optional']:
            content += "\n### Optional Fields\n"
            for field in doc['configuration']['optional']:
                content += f"- `{field}`\n"
        
        content += "\n## Schema\n```json\n"
        content += self._pretty_json(doc['schema'])
        content += "\n```\n"
        
        # Add special notes for database_query
        if doc.get('service_type') == 'database_query':
            content += "\n## Important Notes\n"
            content += "- **SQL Query**: The SQL query is passed as the `sql` parameter in the input, NOT as a configuration field\n"
            content += "- **Database Type**: Specify the database type (postgresql, mysql, etc.) in `auth_config.database_type`, NOT in service_config\n"
            content += "- **Named Parameters**: Use `:param_name` syntax in SQL queries for parameter placeholders\n"
            content += "- **Additional Properties**: Always set `additionalProperties: true` in parameter_schema for dynamic SQL parameters\n"
            content += "- **Authentication**: Database credentials are configured at the application level in auth_config\n\n"
        
        if doc.get('examples'):
            content += "\n## Examples\n"
            for example in doc['examples']:
                content += f"\n### {example['name']}\n```json\n"
                content += self._pretty_json(example['config'])
                content += "\n```\n"
        
        return content
    
    def _format_event_details(self, doc: Dict[str, Any]) -> str:
        """Format detailed event documentation"""
        
        if "error" in doc:
            return f"❌ {doc['error']}\n\nAvailable types: {', '.join(doc['available_types'])}"
        
        content = f"# {doc['name']} Documentation\n\n"
        content += f"**Type:** `{doc['event_type']}`\n"
        content += f"**Description:** {doc['description']}\n\n"
        
        content += "## Configuration\n\n"
        if doc['configuration']['required']:
            content += "### Required Fields\n"
            for field in doc['configuration']['required']:
                content += f"- `{field}`\n"
        else:
            content += "No required configuration fields.\n"
        
        if doc['configuration']['optional']:
            content += "\n### Optional Fields\n"
            for field in doc['configuration']['optional']:
                content += f"- `{field}`\n"
        
        content += "\n## Schema\n```json\n"
        content += self._pretty_json(doc['schema'])
        content += "\n```\n"
        
        # Add notes section if available
        if doc.get('notes'):
            content += "\n## Important Notes\n"
            for note in doc['notes']:
                content += f"- {note}\n"
        
        if doc.get('examples'):
            content += "\n## Examples\n"
            for example in doc['examples']:
                content += f"\n### {example['name']}\n```json\n"
                content += self._pretty_json(example['config'])
                content += "\n```\n"
        
        return content
    
    def _format_service_overview(self, doc: Dict[str, Any]) -> str:
        """Format service types overview"""
        
        content = f"# IOFlow Service Types\n\n"
        content += f"{doc['overview']}\n\n"
        
        content += "## Available Service Types\n\n"
        for stype, info in doc['service_types'].items():
            content += f"### `{stype}`\n"
            content += f"**{info['name']}** - {info['description']}\n\n"
        
        content += f"\n💡 **Tip:** {doc['usage']}\n"
        content += "\nExample: `ioflow_get_service_docs(service_type='api_call')`"
        
        return content
    
    def _format_event_overview(self, doc: Dict[str, Any]) -> str:
        """Format event types overview"""
        
        content = f"# IOFlow Event Types\n\n"
        content += f"{doc['overview']}\n\n"
        
        content += "## Available Event Types\n\n"
        for etype, info in doc['event_types'].items():
            content += f"### `{etype}`\n"
            content += f"**{info['name']}** - {info['description']}\n\n"
        
        content += f"\n💡 **Tip:** {doc['usage']}\n"
        content += "\nExample: `ioflow_get_event_docs(event_type='webhook')`"
        
        return content
    
    def _format_complete_guide(self, guide: Dict[str, Any]) -> str:
        """Format complete application guide"""
        
        content = f"# {guide['title']}\n"
        content += f"Version: {guide['version']}\n\n"
        
        # Overview
        content += "## Overview\n"
        content += f"{guide['overview']['description']}\n\n"
        content += "### Key Concepts\n"
        for concept, desc in guide['overview']['key_concepts'].items():
            content += f"- **{concept.title()}**: {desc}\n"
        
        # Application Structure
        content += "\n## Application Structure\n\n"
        content += "### Required Fields\n"
        content += self._format_nested_fields(guide['application_structure']['required_fields'])
        
        content += "\n### Optional Fields\n"
        content += self._format_nested_fields(guide['application_structure']['optional_fields'])
        
        # Service Creation
        content += "\n## Creating Services\n"
        content += f"{guide['service_creation']['overview']}\n\n"
        content += "### Common Service Fields\n"
        for field, desc in guide['service_creation']['common_fields'].items():
            content += f"- `{field}`: {desc}\n"
        
        # Event Creation
        content += "\n## Creating Events\n"
        content += f"{guide['event_creation']['overview']}\n\n"
        content += "### Common Event Fields\n"
        for field, desc in guide['event_creation']['common_fields'].items():
            content += f"- `{field}`: {desc}\n"
        
        # Best Practices
        content += "\n## Best Practices\n"
        for category, practices in guide['best_practices'].items():
            content += f"\n### {category.title()}\n"
            for practice in practices:
                content += f"- {practice}\n"
        
        # Examples
        content += "\n## Examples\n"
        content += "\n### Minimal Application\n```json\n"
        content += self._pretty_json(guide['examples']['minimal_application'])
        content += "\n```\n"
        
        content += "\n### Full Application\n```json\n"
        content += self._pretty_json(guide['examples']['full_application'])
        content += "\n```\n"
        
        return content
    
    def _format_search_results(self, results: Dict[str, Any]) -> str:
        """Format search results"""
        
        content = f"# Search Results for '{results['query']}'\n\n"
        
        if results['count'] == 0:
            content += "No results found.\n"
            if results['suggestion']:
                content += f"\n💡 {results['suggestion']}"
        else:
            content += f"Found {results['count']} results:\n\n"
            
            # Group results by type
            grouped = {}
            for result in results['results']:
                result_type = result['type']
                if result_type not in grouped:
                    grouped[result_type] = []
                grouped[result_type].append(result)
            
            # Format each group
            type_labels = {
                'concept': '📚 Concepts',
                'service_type': '⚙️ Service Types',
                'event_type': '📅 Event Types'
            }
            
            for result_type, items in grouped.items():
                content += f"### {type_labels.get(result_type, result_type)}\n\n"
                
                for result in items:
                    content += f"**{result['name']}**"
                    if result.get('score'):
                        content += f" (relevance: {result['score']})"
                    content += f"\n{result['description']}\n"
                    
                    # Show matches for debugging/transparency
                    if result.get('matches') and len(result['matches']) > 0:
                        content += f"*Matched: {', '.join(result['matches'][:3])}*\n"
                    
                    # Show related terms for concepts
                    if result.get('related_terms'):
                        content += f"Related: {', '.join(result['related_terms'])}\n"
                    
                    # Show examples for concepts
                    if result.get('examples'):
                        content += f"Examples: {', '.join(result['examples'][:2])}\n"
                    
                    # Show fields for service types
                    if result.get('fields'):
                        content += f"Fields: {', '.join(result['fields'][:5])}\n"
                    
                    if 'details' in result:
                        content += f"\n📖 {result['details']}\n"
                    
                    content += "\n"
        
        return content
    
    def _format_nested_fields(self, fields: Dict[str, Any], indent: int = 0) -> str:
        """Format nested field structure"""
        
        content = ""
        indent_str = "  " * indent
        
        for key, value in fields.items():
            if isinstance(value, dict):
                content += f"{indent_str}- `{key}`:\n"
                content += self._format_nested_fields(value, indent + 1)
            else:
                content += f"{indent_str}- `{key}`: {value}\n"
        
        return content
    
    def _pretty_json(self, obj: Any) -> str:
        """Pretty print JSON object"""
        
        import json
        return json.dumps(obj, indent=2, ensure_ascii=False)