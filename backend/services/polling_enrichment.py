"""
Enrichment support for polling service
Allows fetching additional details for each polled item
"""
import logging
import json
from typing import Dict, List, Any, Optional

try:
    from jsonpath_ng import parse
    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False
    logging.warning("jsonpath-ng not installed, using simple extraction")

from db.application_models import ApplicationService
from services.service_executors import ServiceExecutor
from db.database import get_db_context
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class PollingEnrichment:
    """Handle enrichment of polling results"""
    
    @staticmethod
    async def enrich_items(
        items: List[Dict],
        enrichment_config: Dict,
        app_id: str,
        subscription: Any,
        tenant_id: str
    ) -> List[Dict]:
        """
        Enrich polling items with additional data
        
        Args:
            items: List of items from polling service
            enrichment_config: Configuration for enrichment
            app_id: Application ID
            subscription: Application subscription with credentials
            tenant_id: Tenant ID
            
        Returns:
            List of enriched items
        """
        if not enrichment_config or not enrichment_config.get('enabled'):
            return items
            
        service_name = enrichment_config.get('service')
        if not service_name:
            logger.warning("Enrichment enabled but no service specified")
            return items
            
        # Get the enrichment service
        with get_db_context() as db:
            service = db.query(ApplicationService).filter(
                and_(
                    ApplicationService.app_id == app_id,
                    ApplicationService.service_name == service_name
                )
            ).first()
            
            if not service:
                logger.error(f"Enrichment service {service_name} not found")
                return items
        
        enriched_items = []
        batch_size = enrichment_config.get('batch_size', 1)
        parameters_template = enrichment_config.get('parameters_template', {})
        output_mapping = enrichment_config.get('output_mapping', {})
        
        for item in items:
            try:
                # Prepare parameters for enrichment service
                params = {}
                for key, template in parameters_template.items():
                    params[key] = PollingEnrichment._resolve_template(template, item)
                
                # Execute enrichment service
                service_executor = ServiceExecutor(service, subscription)
                result = await service_executor.execute(params)
                
                if result and result.get('success'):
                    enriched_data = result.get('data', {})
                    
                    # Apply output mapping if configured
                    if output_mapping:
                        mapped_item = {}
                        for output_key, json_path in output_mapping.items():
                            if json_path.startswith('$.'):
                                # JSONPath expression
                                value = PollingEnrichment._extract_jsonpath(enriched_data, json_path)
                                if value is not None:
                                    mapped_item[output_key] = value
                            else:
                                # Direct mapping
                                mapped_item[output_key] = enriched_data.get(json_path)
                        
                        # Merge with original item (original values can be overridden)
                        enriched_item = {**item, **mapped_item}
                    else:
                        # No mapping, merge all data
                        enriched_item = {**item, **enriched_data}
                    
                    enriched_items.append(enriched_item)
                    logger.debug(f"Enriched item {item.get('id', 'unknown')}")
                else:
                    # Enrichment failed, keep original item
                    logger.warning(f"Failed to enrich item {item.get('id', 'unknown')}")
                    enriched_items.append(item)
                    
            except Exception as e:
                logger.error(f"Error enriching item {item.get('id', 'unknown')}: {str(e)}")
                enriched_items.append(item)
        
        logger.info(f"Enriched {len(enriched_items)} items")
        return enriched_items
    
    @staticmethod
    def _resolve_template(template: str, context: Dict) -> Any:
        """Resolve template variables like {{item.id}}"""
        if not isinstance(template, str):
            return template
            
        if '{{' not in template:
            return template
            
        # Simple template resolution
        import re
        pattern = r'\{\{([^}]+)\}\}'
        
        def replacer(match):
            path = match.group(1).strip()
            # Handle item.field notation
            if path.startswith('item.'):
                field = path[5:]  # Remove 'item.' prefix
                return str(context.get(field, ''))
            return str(context.get(path, ''))
        
        return re.sub(pattern, replacer, template)
    
    @staticmethod
    def _extract_jsonpath(data: Dict, path: str) -> Any:
        """Extract value using JSONPath expression"""
        # Special handling for Gmail headers
        if 'payload.headers' in path and 'name==' in path:
            return PollingEnrichment._extract_gmail_header(data, path)
            
        if not HAS_JSONPATH:
            # Simple fallback extraction
            return PollingEnrichment._simple_extract(data, path)
            
        try:
            # Handle special case for header extraction
            if '| [0]' in path:
                # Split on pipe and get first element
                path = path.split('|')[0].strip()
                
            jsonpath_expr = parse(path)
            matches = jsonpath_expr.find(data)
            
            if matches:
                # Return first match value
                return matches[0].value
            return None
            
        except Exception as e:
            logger.debug(f"JSONPath extraction failed for {path}: {str(e)}")
            return None
    
    @staticmethod
    def _extract_gmail_header(data: Dict, path: str) -> Any:
        """Extract Gmail header value without JSONPath"""
        # Pattern like: $.payload.headers[?(@.name=='From')].value
        import re
        match = re.search(r"name=='([^']+)'", path)
        if match:
            header_name = match.group(1)
            
            # Navigate to headers
            payload = data.get('payload', {})
            headers = payload.get('headers', [])
            
            # Find the header
            for header in headers:
                if header.get('name') == header_name:
                    return header.get('value')
        return None
    
    @staticmethod
    def _simple_extract(data: Dict, path: str) -> Any:
        """Simple extraction without JSONPath"""
        if path.startswith('$.'):
            path = path[2:]
        
        # Handle simple dot notation
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
                
        return current