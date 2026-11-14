"""File Operation service executor plugin.

Handles special dispatch based on URL scheme: image://, pdf://, web://, or file protocol.
"""
import logging
from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


def _get_file_operation_executor(service_config, auth_credentials=None,
                                 subscription_id=None, auth_config=None,
                                 application_base_url=None):
    """Factory for file operation executors with URL-scheme dispatch."""
    from services.file_protocol_executor import FileProtocolExecutor
    from services.image_processing_executor import ImageProcessingExecutor
    from services.pdf_processing_executor import PDFProcessingExecutor
    from services.web_scraping_executor import WebScrapingExecutor

    base_url = service_config.get('base_url', '')
    if base_url.startswith('image://'):
        return ImageProcessingExecutor(service_config, auth_credentials, subscription_id, auth_config)
    elif base_url.startswith('pdf://'):
        return PDFProcessingExecutor(service_config, auth_credentials, subscription_id, auth_config)
    elif base_url.startswith('web://'):
        return WebScrapingExecutor(service_config, auth_credentials, subscription_id, auth_config)
    else:
        return FileProtocolExecutor(service_config, auth_credentials, subscription_id, auth_config)


PluginRegistry.register_service_executor("file_operation", _get_file_operation_executor)
