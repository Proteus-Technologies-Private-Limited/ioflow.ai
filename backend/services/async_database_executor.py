"""
Truly asynchronous database executor using native async drivers
This prevents blocking the event loop during database operations
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import re
from datetime import datetime, date
from decimal import Decimal

# Async database drivers
try:
    import asyncpg  # PostgreSQL async driver
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import aiomysql  # MySQL async driver
    HAS_AIOMYSQL = True
except ImportError:
    HAS_AIOMYSQL = False

try:
    import aiosqlite  # SQLite async driver
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

from services.service_executors import ServiceExecutor

logger = logging.getLogger(__name__)

# Connection pools per application subscription
ASYNC_CONNECTION_POOLS = {}


class AsyncDatabaseConnectionPool:
    """Manages async database connections for a specific database"""

    def __init__(self, connection_string: str, auth_credentials: Dict[str, Any],
                 auth_config: Dict[str, Any], pool_size: int = 10):
        self.connection_string = connection_string
        self.auth_credentials = auth_credentials
        self.auth_config = auth_config
        self.pool_size = pool_size
        self.database_type = auth_config.get('database_type', 'postgresql')
        self.pool = None
        self._closed = False

    async def initialize(self):
        """Initialize the async connection pool"""
        parsed = urlparse(self.connection_string)
        username = self.auth_credentials.get('username') or parsed.username
        password = self.auth_credentials.get('password') or parsed.password
        host = parsed.hostname
        port = parsed.port
        database = parsed.path.lstrip('/')

        connection_timeout = self.auth_config.get('connection_timeout', 30)

        try:
            if self.database_type == 'postgresql' and HAS_ASYNCPG:
                # Create PostgreSQL async connection pool
                self.pool = await asyncpg.create_pool(
                    host=host,
                    port=port or 5432,
                    user=username,
                    password=password,
                    database=database,
                    min_size=2,
                    max_size=self.pool_size,
                    command_timeout=connection_timeout,
                    timeout=connection_timeout
                )
                logger.info(f"Created async PostgreSQL connection pool with {self.pool_size} connections")

            elif self.database_type == 'mysql' and HAS_AIOMYSQL:
                # Create MySQL async connection pool
                self.pool = await aiomysql.create_pool(
                    host=host,
                    port=port or 3306,
                    user=username,
                    password=password,
                    db=database,
                    minsize=2,
                    maxsize=self.pool_size,
                    connect_timeout=connection_timeout,
                    autocommit=True
                )
                logger.info(f"Created async MySQL connection pool with {self.pool_size} connections")

            elif self.database_type == 'sqlite' and HAS_AIOSQLITE:
                # For SQLite, we'll manage connections differently
                self.pool = database  # Store the database path
                logger.info(f"Configured async SQLite database: {database}")

            else:
                # Fallback to sync with warning
                logger.warning(f"No async driver available for {self.database_type}. Install the appropriate async driver:")
                if self.database_type == 'postgresql':
                    logger.warning("pip install asyncpg")
                elif self.database_type == 'mysql':
                    logger.warning("pip install aiomysql")
                elif self.database_type == 'sqlite':
                    logger.warning("pip install aiosqlite")
                raise ValueError(f"Async driver not available for {self.database_type}")

        except Exception as e:
            logger.error(f"Failed to create async connection pool: {str(e)}")
            raise

    async def execute_query(self, query: str, params: Any = None, max_rows: int = 10000) -> List[Dict]:
        """Execute a query using async database connection"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        try:
            if self.database_type == 'postgresql' and HAS_ASYNCPG:
                async with self.pool.acquire() as conn:
                    # Execute query with timeout
                    rows = await conn.fetch(query, *params if params else [])
                    # Convert Record objects to dicts
                    return [dict(row) for row in rows[:max_rows]]

            elif self.database_type == 'mysql' and HAS_AIOMYSQL:
                async with self.pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        await cursor.execute(query, params)
                        rows = await cursor.fetchmany(max_rows)
                        return rows

            elif self.database_type == 'sqlite' and HAS_AIOSQLITE:
                # SQLite uses a different pattern
                async with aiosqlite.connect(self.pool) as conn:
                    conn.row_factory = aiosqlite.Row
                    async with conn.execute(query, params or []) as cursor:
                        rows = await cursor.fetchmany(max_rows)
                        return [dict(row) for row in rows]

            else:
                raise ValueError(f"No async support for {self.database_type}")

        except asyncio.TimeoutError:
            logger.error(f"Query execution timed out")
            raise
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise

    async def execute_command(self, query: str, params: Any = None) -> int:
        """Execute an INSERT/UPDATE/DELETE command"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        try:
            if self.database_type == 'postgresql' and HAS_ASYNCPG:
                async with self.pool.acquire() as conn:
                    result = await conn.execute(query, *params if params else [])
                    # Extract affected rows from result string like "UPDATE 5"
                    if result:
                        parts = result.split()
                        if len(parts) > 1 and parts[1].isdigit():
                            return int(parts[1])
                    return 0

            elif self.database_type == 'mysql' and HAS_AIOMYSQL:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(query, params)
                        await conn.commit()
                        return cursor.rowcount

            elif self.database_type == 'sqlite' and HAS_AIOSQLITE:
                async with aiosqlite.connect(self.pool) as conn:
                    async with conn.execute(query, params or []) as cursor:
                        await conn.commit()
                        return cursor.rowcount

            else:
                raise ValueError(f"No async support for {self.database_type}")

        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            raise

    async def close(self):
        """Close the connection pool"""
        self._closed = True

        if self.pool:
            try:
                if self.database_type == 'postgresql' and HAS_ASYNCPG:
                    await self.pool.close()
                elif self.database_type == 'mysql' and HAS_AIOMYSQL:
                    self.pool.close()
                    await self.pool.wait_closed()
                # SQLite doesn't need pool closing

                logger.info(f"Closed async connection pool for {self.database_type}")
            except Exception as e:
                logger.error(f"Error closing connection pool: {str(e)}")


class AsyncDatabaseQueryExecutor(ServiceExecutor):
    """Truly async executor for Database Query service type"""

    def _resolve_autocommit_flag(self, config: Dict[str, Any]) -> bool:
        """Whether each statement commits on its own (default True), matching the
        sync executor's resolution: service_config -> app auth_config -> True."""
        raw = config.get('autocommit', self.auth_config.get('autocommit', True))
        if isinstance(raw, str):
            return raw.strip().lower() not in ('false', '0', 'no', 'off')
        return bool(raw)

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database query asynchronously without blocking"""
        config = self.service_config

        # Flow-scoped transaction mode (autocommit=false) needs a single
        # connection pinned across nodes and committed by an explicit step. That
        # lives in the sync executor (db_transaction_manager), so delegate to it
        # when autocommit is disabled. The truly-async path stays for the
        # autocommit=true firehose (e.g. MQTT ingestion).
        if not self._resolve_autocommit_flag(config):
            logger.info("autocommit=false configured - delegating to sync executor for flow-scoped transaction support")
            from services.database_executor import DatabaseQueryExecutor
            sync_executor = DatabaseQueryExecutor(
                self.service_config,
                self.auth_credentials,
                self.subscription_id,
                self.auth_config
            )
            return await sync_executor.execute(parameters, context)

        # Get SQL query
        sql_query = parameters.get('sql')
        query_params = {k: v for k, v in parameters.items() if k != 'sql'}

        if not sql_query:
            return {
                'error': True,
                'message': 'SQL query is required'
            }

        # Check for Arrow Flight connection by URL scheme
        base_url = context.get('application_base_url', '')
        if base_url and (base_url.startswith('grpc://') or base_url.startswith('grpc+tls://')):
            # Use Arrow Flight executor for databases with grpc/grpc+tls URL scheme
            logger.info("Arrow Flight connection detected via URL scheme - using ArrowFlightExecutor")
            try:
                from services.arrow_flight_executor import ArrowFlightExecutor
                arrow_executor = ArrowFlightExecutor(
                    self.service_config,
                    self.auth_credentials,
                    self.subscription_id,
                    self.auth_config
                )
                return await arrow_executor.execute(parameters, context)
            except ImportError as e:
                logger.error(f"Arrow Flight executor not available: {e}")
                return {
                    'error': True,
                    'message': 'Arrow Flight support not available. Install pyarrow: pip install pyarrow'
                }

        # Get or create async connection pool — keyed per subscription (tenant
        # + application instance) and per connection fingerprint, so credential
        # or URL updates rotate to a fresh pool instead of reusing stale ones
        from services.database_executor import connection_fingerprint, evict_stale_pools

        database_type = self.auth_config.get('database_type', 'postgresql')
        pool_prefix = f"{self.subscription_id}_{database_type}_async_"
        pool_key = pool_prefix + connection_fingerprint(
            context.get('application_base_url', ''), self.auth_credentials, self.auth_config)
        pool = ASYNC_CONNECTION_POOLS.get(pool_key)

        if not pool:
            # Create new async pool
            base_url = context.get('application_base_url', '')
            if not base_url:
                return {
                    'error': True,
                    'message': 'Database connection URL not configured'
                }

            # Check if async driver is available
            if database_type == 'oracle':
                # No async driver for Oracle, fall back to sync executor
                logger.info("Oracle database detected - using sync executor (no async driver available for Oracle)")
                from services.database_executor import DatabaseQueryExecutor
                sync_executor = DatabaseQueryExecutor(
                    self.service_config,
                    self.auth_credentials,
                    self.subscription_id,
                    self.auth_config
                )
                return await sync_executor.execute(parameters, context)

            elif database_type == 'sqlserver':
                # No good async driver for SQL Server, fall back to sync executor
                logger.info("SQL Server database detected - using sync executor")
                from services.database_executor import DatabaseQueryExecutor
                sync_executor = DatabaseQueryExecutor(
                    self.service_config,
                    self.auth_credentials,
                    self.subscription_id,
                    self.auth_config
                )
                return await sync_executor.execute(parameters, context)

            elif database_type == 'mysql' and not HAS_AIOMYSQL:
                logger.warning("aiomysql not installed, install it for true async: pip install aiomysql")
                # Fall back to sync executor
                from services.database_executor import DatabaseQueryExecutor
                sync_executor = DatabaseQueryExecutor(
                    self.service_config,
                    self.auth_credentials,
                    self.subscription_id,
                    self.auth_config
                )
                return await sync_executor.execute(parameters, context)

            elif database_type == 'postgresql' and not HAS_ASYNCPG:
                logger.warning("asyncpg not installed, install it for true async: pip install asyncpg")
                # Fall back to sync executor
                from services.database_executor import DatabaseQueryExecutor
                sync_executor = DatabaseQueryExecutor(
                    self.service_config,
                    self.auth_credentials,
                    self.subscription_id,
                    self.auth_config
                )
                return await sync_executor.execute(parameters, context)

            # Connection config changed for this subscription — close the old
            # pool first so we don't leak server-side connection slots
            await evict_stale_pools(ASYNC_CONNECTION_POOLS, pool_prefix, pool_key)

            pool = AsyncDatabaseConnectionPool(
                base_url,
                self.auth_credentials,
                self.auth_config,
                self.auth_config.get('connection_pool_size', 10)
            )

            try:
                await pool.initialize()
                ASYNC_CONNECTION_POOLS[pool_key] = pool
                logger.info(f"Initialized async connection pool for {database_type}")
            except Exception as e:
                logger.error(f"Failed to initialize async database pool: {str(e)}")
                return {
                    'error': True,
                    'message': str(e),
                    'error_type': 'connection_error'
                }

        # Execute query with timeout
        # Default to 180 seconds for database queries (3 minutes)
        query_timeout = config.get('query_timeout', self.auth_config.get('query_timeout', 180))

        try:
            # Process parameters
            processed_query, processed_params = self._process_query_parameters(
                sql_query, query_params, database_type
            )

            # Execute with timeout - this is truly async!
            result_rows = await asyncio.wait_for(
                pool.execute_query(
                    processed_query,
                    processed_params,
                    config.get('max_rows', 10000)
                ),
                timeout=query_timeout
            )

            # Format results
            result_format = config.get('result_format', 'json_array')
            if result_format == 'json_array':
                result_data = self._serialize_results(result_rows)
            elif result_format == 'json_object':
                result_data = self._serialize_results(result_rows[0] if result_rows else {})
            else:
                result_data = result_rows

            return {
                'success': True,
                'data': result_data,
                'row_count': len(result_rows),
                'message': f'Query executed successfully, returned {len(result_rows)} rows'
            }

        except asyncio.TimeoutError:
            logger.error(f"Query execution timed out after {query_timeout} seconds")
            return {
                'error': True,
                'message': f'Query execution timed out after {query_timeout} seconds',
                'error_type': 'timeout'
            }
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {
                'error': True,
                'message': f'Query execution failed: {str(e)}'
            }

    def _process_query_parameters(self, query: str, params: Dict[str, Any],
                                 database_type: str) -> tuple:
        """Convert named parameters to database-specific format"""
        if not params:
            return query, None

        if database_type == 'postgresql':
            # PostgreSQL uses $1, $2, etc.
            processed_query = query
            processed_params = []
            param_count = 1

            for param_name, param_value in params.items():
                pattern = f':{param_name}\\b'
                replacement = f'${param_count}'
                processed_query = re.sub(pattern, replacement, processed_query)
                processed_params.append(param_value)
                param_count += 1

            return processed_query, processed_params

        elif database_type == 'mysql':
            # MySQL uses %s placeholders
            processed_query = query
            processed_params = []

            for param_name, param_value in params.items():
                pattern = f':{param_name}\\b'
                processed_query = re.sub(pattern, '%s', processed_query)
                processed_params.append(param_value)

            return processed_query, tuple(processed_params)

        elif database_type == 'sqlite':
            # SQLite uses ? placeholders
            processed_query = query
            processed_params = []

            for param_name, param_value in params.items():
                pattern = f':{param_name}\\b'
                processed_query = re.sub(pattern, '?', processed_query)
                processed_params.append(param_value)

            return processed_query, processed_params

        else:
            return query, params

    def _serialize_results(self, data: Any) -> Any:
        """Convert database results to JSON-serializable format"""
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
                import base64
                return base64.b64encode(data).decode('ascii')
        else:
            return data


# Cleanup function
async def cleanup_async_pools():
    """Close all async connection pools"""
    for pool_key, pool in ASYNC_CONNECTION_POOLS.items():
        try:
            await pool.close()
        except Exception as e:
            logger.error(f"Error closing async pool {pool_key}: {str(e)}")

    ASYNC_CONNECTION_POOLS.clear()
    logger.info("All async connection pools closed")