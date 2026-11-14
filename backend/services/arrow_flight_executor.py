"""
Generic Apache Arrow Flight executor for databases supporting Arrow Flight protocol
Supports Dremio, ClickHouse, DuckDB, and any future Arrow Flight compatible databases
Uses thread pool executor for non-blocking async operations until PyArrow adds native async support
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from decimal import Decimal
import base64

# Try to import Arrow Flight
try:
    import pyarrow as pa
    import pyarrow.flight as flight
    HAS_ARROW_FLIGHT = True
except ImportError:
    HAS_ARROW_FLIGHT = False

# Optional data format libraries
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

from services.service_executors import ServiceExecutor
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Thread pool for non-blocking Arrow Flight operations
FLIGHT_THREAD_POOL = ThreadPoolExecutor(max_workers=10, thread_name_prefix="arrow_flight")

# Connection pools per endpoint
ARROW_FLIGHT_CLIENTS = {}


class ArrowFlightConnectionPool:
    """Manages Arrow Flight client connections for a specific endpoint"""

    def __init__(self, endpoint: str, auth_config: Dict[str, Any],
                 auth_credentials: Dict[str, Any], pool_size: int = 5):
        self.endpoint = endpoint
        self.auth_config = auth_config
        self.auth_credentials = auth_credentials
        self.pool_size = pool_size
        self.clients = []
        self._closed = False

    def _create_client(self) -> tuple:
        """Create a new Arrow Flight client with authentication"""
        # Parse endpoint for scheme and location
        if self.endpoint.startswith('grpc+tls://'):
            location = self.endpoint.replace('grpc+tls://', '')
            use_tls = True
        elif self.endpoint.startswith('grpc://'):
            location = self.endpoint.replace('grpc://', '')
            use_tls = False
        else:
            # Default to TLS if no scheme specified
            location = self.endpoint
            use_tls = True

        # Create client with appropriate TLS settings
        if use_tls:
            client = flight.FlightClient(f"grpc+tls://{location}")
        else:
            client = flight.FlightClient(f"grpc+tcp://{location}")

        # Prepare authentication headers using standard ServiceExecutor logic
        headers = []

        # Check for OAuth2/Token Exchange authentication first (highest priority)
        # This is because token exchange also has username/password but should use the access_token
        if 'access_token' in self.auth_credentials:
            token_type = self.auth_credentials.get('token_type', 'Bearer')
            headers.append((b"authorization", f"{token_type} {self.auth_credentials['access_token']}".encode("utf-8")))
            logger.info(f"Using {token_type} token for Arrow Flight authentication")

        # Legacy token fields for backward compatibility
        elif self.auth_credentials.get('pat_token'):
            # Personal Access Token authentication (e.g., Dremio Cloud)
            token = self.auth_credentials.get('pat_token', '')
            headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))
            logger.info("Using PAT token for Arrow Flight authentication")

        elif self.auth_credentials.get('token') or self.auth_credentials.get('bearer_token'):
            # Generic bearer token
            token = self.auth_credentials.get('token', '') or self.auth_credentials.get('bearer_token', '')
            headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))
            logger.info("Using bearer token for Arrow Flight authentication")

        elif self.auth_credentials.get('username') and self.auth_credentials.get('password'):
            # Basic authentication fallback (when token exchange is not configured)
            username = self.auth_credentials.get('username', '')
            password = self.auth_credentials.get('password', '')
            import base64
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers.append((b"authorization", f"Basic {credentials}".encode("utf-8")))
            logger.info("Using basic authentication for Arrow Flight")

        elif self.auth_credentials.get('api_key'):
            # API key authentication
            api_key = self.auth_credentials.get('api_key', '')
            key_header = self.auth_config.get('api_key_header', 'X-API-Key')
            headers.append((key_header.encode(), api_key.encode()))
            logger.info(f"Using API key authentication with {key_header} header")

        # Create flight call options with headers
        options = flight.FlightCallOptions(headers=headers) if headers else None

        return client, options

    def get_client(self) -> tuple:
        """Get a client from the pool or create a new one"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        # For simplicity, create a new client each time
        # In production, you'd want to reuse clients
        return self._create_client()

    def close(self):
        """Close the connection pool"""
        self._closed = True
        self.clients.clear()


class ArrowFlightExecutor(ServiceExecutor):
    """Generic executor for Apache Arrow Flight protocol databases"""

    async def _ensure_valid_token_exchange(self, db=None, context=None):
        """Override to derive HTTP URL from grpc:// URLs for token exchange"""
        # Get the base URL from context
        base_url = None
        if context and context.get('application_base_url'):
            grpc_url = context['application_base_url']

            # If this is a grpc:// or grpc+tls:// URL, derive the HTTP URL
            if grpc_url.startswith('grpc://') or grpc_url.startswith('grpc+tls://'):
                # Parse the URL to get host and port
                if grpc_url.startswith('grpc+tls://'):
                    parsed = urlparse(grpc_url.replace('grpc+tls://', 'https://'))
                    use_https = True
                else:  # grpc://
                    parsed = urlparse(grpc_url.replace('grpc://', 'http://'))
                    use_https = False

                # Extract host
                host = parsed.hostname

                # For Arrow Flight databases, the HTTP REST API typically runs on a different port
                # Common patterns:
                # - Dremio: gRPC on 32010, HTTP on 9047
                # - Default assumption: HTTP API on port 9047 (can be overridden in auth_config)
                http_port = self.auth_config.get('http_api_port', 9047)

                # Construct the HTTP URL
                http_scheme = 'https' if use_https else 'http'
                http_base_url = f"{http_scheme}://{host}:{http_port}"

                logger.info(f"Derived HTTP URL {http_base_url} from gRPC URL {grpc_url}")

                # Add the derived HTTP URL to context for template processing
                if context:
                    context['http_base_url'] = http_base_url

                # Update auth_config BEFORE calling parent method so it's available for token exchange
                if not self.auth_config:
                    self.auth_config = {}
                self.auth_config['http_base_url'] = http_base_url

                logger.info(f"Updated auth_config with http_base_url: {http_base_url}")

        # Call parent method with the updated auth_config
        await super()._ensure_valid_token_exchange(db=db, context=context)

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query using Arrow Flight protocol asynchronously without blocking"""

        if not HAS_ARROW_FLIGHT:
            return {
                'error': True,
                'message': 'Apache Arrow Flight not available. Install pyarrow: pip install pyarrow'
            }

        # Ensure tokens are valid for token exchange authentication
        try:
            await self._ensure_valid_token_exchange(context=context)
        except Exception as e:
            logger.error(f"Token exchange authentication failed: {e}")
            return {
                'error': True,
                'message': f'Authentication failed: {str(e)}'
            }

        config = self.service_config

        # Get SQL query
        sql_query = parameters.get('sql')
        if not sql_query:
            return {
                'error': True,
                'message': 'SQL query is required'
            }

        # Get endpoint from auth config or context
        endpoint = self.auth_config.get('endpoint')
        if not endpoint:
            # Try to get from base_url in context
            base_url = context.get('application_base_url', '')
            if base_url and (base_url.startswith('grpc://') or base_url.startswith('grpc+tls://')):
                endpoint = base_url
            else:
                return {
                    'error': True,
                    'message': 'Arrow Flight endpoint not configured'
                }

        # Get or create connection pool
        pool_key = f"{endpoint}_{self.subscription_id or 'default'}"
        pool = ARROW_FLIGHT_CLIENTS.get(pool_key)

        if not pool:
            pool = ArrowFlightConnectionPool(
                endpoint,
                self.auth_config,
                self.auth_credentials,
                self.auth_config.get('connection_pool_size', 5)
            )
            ARROW_FLIGHT_CLIENTS[pool_key] = pool
            logger.info(f"Created Arrow Flight connection pool for {endpoint}")

        # Get timeout settings (use standard timeout_seconds like all other services)
        # Default to 180 seconds for database queries (3 minutes)
        timeout = config.get('timeout_seconds', 180)

        try:
            # Execute query in thread pool to avoid blocking
            result_data = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    FLIGHT_THREAD_POOL,
                    self._execute_flight_query_sync,
                    pool,
                    sql_query,
                    parameters,
                    config
                ),
                timeout=timeout
            )

            return result_data

        except asyncio.TimeoutError:
            logger.error(f"Query execution timed out after {timeout} seconds")
            return {
                'error': True,
                'message': f'Query execution timed out after {timeout} seconds',
                'error_type': 'timeout'
            }
        except Exception as e:
            logger.error(f"Arrow Flight query execution failed: {str(e)}")
            return {
                'error': True,
                'message': f'Query execution failed: {str(e)}'
            }

    def _execute_flight_query_sync(self, pool: ArrowFlightConnectionPool,
                                   query: str, parameters: Dict[str, Any],
                                   config: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous Arrow Flight query execution (runs in thread pool)"""
        import time
        start_time = time.time()

        try:
            # Get client and options from pool
            client, options = pool.get_client()

            # Create flight descriptor for the query
            descriptor = flight.FlightDescriptor.for_command(query.encode('utf-8'))

            # Get flight info (query plan)
            flight_info = client.get_flight_info(descriptor, options)

            # Execute the query and get results
            # Most Arrow Flight servers return results via endpoints
            if flight_info.endpoints:
                # Get the ticket from the first endpoint
                ticket = flight_info.endpoints[0].ticket

                # Fetch the results
                reader = client.do_get(ticket, options)

                # Read all data into an Arrow table
                table = reader.read_all()

                # Get result format from config
                result_format = config.get('result_format', 'json_array')
                max_rows = config.get('max_rows', 10000)

                # Limit rows if needed
                if len(table) > max_rows:
                    table = table.slice(0, max_rows)
                    truncated = True
                else:
                    truncated = False

                # Convert based on requested format
                if result_format == 'arrow_table':
                    # Return Arrow table metadata (can't serialize actual table)
                    result_data = {
                        'arrow_table': 'pyarrow.Table object',
                        'row_count': len(table),
                        'column_count': len(table.column_names),
                        'columns': table.column_names,
                        'schema': {col: str(table.field(col).type) for col in table.column_names}
                    }

                elif result_format == 'pandas_dataframe' and HAS_PANDAS:
                    # Convert to Pandas DataFrame
                    df = table.to_pandas()
                    result_data = {
                        'dataframe_shape': list(df.shape),
                        'columns': list(df.columns),
                        'row_count': len(df),
                        'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()}
                    }

                elif result_format == 'polars_dataframe' and HAS_POLARS:
                    # Convert to Polars DataFrame
                    df = pl.from_arrow(table)
                    result_data = {
                        'dataframe_shape': list(df.shape),
                        'columns': df.columns,
                        'row_count': len(df),
                        'dtypes': {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)}
                    }

                elif result_format == 'duckdb_relation' and HAS_DUCKDB:
                    # Convert to DuckDB relation
                    conn = duckdb.connect(':memory:')
                    rel = conn.from_arrow(table)
                    result_data = {
                        'duckdb_relation': 'DuckDB Relation object',
                        'row_count': rel.count().fetchone()[0],
                        'columns': rel.columns
                    }
                    conn.close()

                elif result_format == 'json_object':
                    # Return single row as JSON object
                    if len(table) > 0:
                        df = table.to_pandas()
                        result_data = self._serialize_results(df.iloc[0].to_dict())
                    else:
                        result_data = {}

                else:  # Default to json_array
                    # Convert Arrow table to list of dictionaries
                    df = table.to_pandas()
                    records = df.to_dict('records')
                    result_data = self._serialize_results(records)

                execution_time_ms = int((time.time() - start_time) * 1000)

                return {
                    'success': True,
                    'data': result_data,
                    'row_count': len(table),
                    'truncated': truncated,
                    'execution_time_ms': execution_time_ms,
                    'message': f'Query executed successfully via Arrow Flight, returned {len(table)} rows'
                }

            else:
                # No endpoints returned - might be a command that doesn't return data
                return {
                    'success': True,
                    'data': [],
                    'row_count': 0,
                    'message': 'Command executed successfully via Arrow Flight'
                }

        except Exception as e:
            logger.error(f"Arrow Flight query failed: {str(e)}")
            raise

    def _serialize_results(self, data: Any) -> Any:
        """Convert results to JSON-serializable format"""
        if isinstance(data, dict):
            return {k: self._serialize_results(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_results(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, date):
            return data.isoformat()
        elif isinstance(data, Decimal):
            return float(data)
        elif isinstance(data, bytes):
            try:
                return data.decode('utf-8')
            except:
                return base64.b64encode(data).decode('ascii')
        elif HAS_PANDAS and pd.isna(data):
            return None
        else:
            return data


# Cleanup function
async def cleanup_arrow_flight_pools():
    """Close all Arrow Flight connection pools"""
    for pool_key, pool in ARROW_FLIGHT_CLIENTS.items():
        try:
            pool.close()
        except Exception as e:
            logger.error(f"Error closing Arrow Flight pool {pool_key}: {str(e)}")

    ARROW_FLIGHT_CLIENTS.clear()

    # Shutdown thread pool
    FLIGHT_THREAD_POOL.shutdown(wait=False)

    logger.info("All Arrow Flight connection pools closed")