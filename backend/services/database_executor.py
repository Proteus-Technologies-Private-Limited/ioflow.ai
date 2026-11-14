"""
Database query executor for different database types
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse, parse_qs
import re
from datetime import datetime, date
from decimal import Decimal

# Database drivers - import conditionally
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    # Try the new oracledb driver first (replacement for cx_Oracle)
    import oracledb as cx_Oracle
    HAS_ORACLE = True
    ORACLE_DRIVER = 'oracledb'
    # Initialize thick mode once at module level if possible
    ORACLE_THICK_MODE_INITIALIZED = False
except ImportError:
    try:
        # Fall back to old cx_Oracle if oracledb not available
        import cx_Oracle
        HAS_ORACLE = True
        ORACLE_DRIVER = 'cx_Oracle'
        ORACLE_THICK_MODE_INITIALIZED = True  # cx_Oracle is always thick mode
    except ImportError:
        HAS_ORACLE = False
        ORACLE_DRIVER = None
        ORACLE_THICK_MODE_INITIALIZED = False

try:
    import pyodbc
    HAS_SQLSERVER = True
except ImportError:
    HAS_SQLSERVER = False

import hashlib
import sqlite3
from utils.retry_utils import retry_async, NETWORK_RETRY_CONFIG
from services.service_executors import ServiceExecutor

logger = logging.getLogger(__name__)

# Connection pools per application subscription (see connection_fingerprint:
# keys are tenant/instance specific via subscription_id AND credential-aware,
# so updating a connection's URL or credentials rotates to a fresh pool)
CONNECTION_POOLS = {}


def connection_fingerprint(base_url: str, auth_credentials: Dict[str, Any],
                           auth_config: Dict[str, Any]) -> str:
    """Stable fingerprint of everything that defines a physical connection.

    The pool key is `{subscription_id}_{database_type}_{fingerprint}`:
    - subscription_id makes pools tenant-specific AND instance-specific (each
      connection of an application is its own subscription row with its own
      credentials), so tenants/instances never share connections.
    - the fingerprint makes pools credential-aware: when a tenant updates the
      connection's URL or credentials, the key changes, a fresh pool is
      created and the stale one is closed — instead of silently reusing
      connections opened with the old parameters until a restart.
    """
    material = json.dumps({
        'base_url': base_url or '',
        'credentials': auth_credentials or {},
        'database_type': (auth_config or {}).get('database_type'),
        'pool_size': (auth_config or {}).get('connection_pool_size'),
        'connection_timeout': (auth_config or {}).get('connection_timeout'),
    }, sort_keys=True, default=str)
    return hashlib.sha1(material.encode('utf-8')).hexdigest()[:12]


async def evict_stale_pools(pools: Dict[str, Any], pool_prefix: str, keep_key: str):
    """Close and drop pools for the same subscription whose connection config
    changed (different fingerprint). Frees server-side connection slots before
    the replacement pool connects."""
    for key in [k for k in list(pools) if k.startswith(pool_prefix) and k != keep_key]:
        stale = pools.pop(key, None)
        if stale is None:
            continue
        try:
            await stale.close()
            logger.info(f"Closed stale database connection pool {key} (connection config changed)")
        except Exception as e:
            logger.warning(f"Error closing stale connection pool {key}: {str(e)}")


# Error fragments that indicate the database session is no longer usable and
# the connection must be replaced (not just rolled back).
_LOST_CONNECTION_MARKERS = {
    'oracle': (
        'DPI-1080',   # connection was closed by the server
        'DPI-1010',   # not connected
        'ORA-02396',  # exceeded maximum idle time, please connect again
        'ORA-2396',
        'ORA-03113',  # end-of-file on communication channel
        'ORA-3113',
        'ORA-03114',  # not connected to ORACLE
        'ORA-3114',
        'ORA-01012',  # not logged on
        'ORA-1012',
        'ORA-12537',  # TNS: connection closed
        'ORA-12571',  # TNS: packet writer failure
        'ORA-25408',  # cannot safely replay call
    ),
    'postgresql': (
        'server closed the connection unexpectedly',
        'connection already closed',
        'connection has been closed',
        'terminating connection',
        'SSL connection has been closed',
    ),
    'mysql': (
        'MySQL server has gone away',
        'Lost connection to MySQL server',
        'Can\'t connect to MySQL server',
        '2006',  # CR_SERVER_GONE_ERROR
        '2013',  # CR_SERVER_LOST
    ),
    'sqlserver': (
        'Communication link failure',
        'Connection is closed',
        '08S01',  # ODBC communication-link-failure SQLSTATE
    ),
}


def _is_connection_lost_error(exc: Exception, database_type: str) -> bool:
    """Return True if *exc* indicates the database connection was dropped and
    the pooled connection should be discarded rather than reused."""
    markers = _LOST_CONNECTION_MARKERS.get(database_type)
    if not markers:
        return False
    msg = str(exc)
    return any(marker in msg for marker in markers)


class DatabaseConnectionPool:
    """Manages database connections for a specific database"""
    
    def __init__(self, connection_string: str, auth_credentials: Dict[str, Any], 
                 auth_config: Dict[str, Any], pool_size: int = 10):
        self.connection_string = connection_string
        self.auth_credentials = auth_credentials
        self.auth_config = auth_config
        self.pool_size = pool_size
        self.database_type = auth_config.get('database_type', 'postgresql')
        self.connections = []
        self.available_connections = asyncio.Queue(maxsize=pool_size)
        self._closed = False
        
    async def initialize(self):
        """Initialize the connection pool"""
        # Try to create at least one connection to validate configuration
        first_conn = await self._create_connection()
        if first_conn:
            await self.available_connections.put(first_conn)
            self.connections.append(first_conn)
        else:
            raise ValueError("Failed to create initial database connection")
            
        # Create the rest of the pool connections
        for _ in range(self.pool_size - 1):
            try:
                conn = await self._create_connection()
                if conn:
                    await self.available_connections.put(conn)
                    self.connections.append(conn)
            except Exception as e:
                # Log but don't fail if we can't create all pool connections
                logger.warning(f"Failed to create pool connection: {str(e)}")
    
    async def _create_connection(self):
        """Create a new database connection"""
        try:
            # Run synchronous database connection in thread pool with timeout
            loop = asyncio.get_event_loop()
            timeout = self.auth_config.get('connection_timeout', 30)

            # Create connection with timeout
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._create_connection_sync),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Database connection timed out after {timeout} seconds")
            raise TimeoutError(f"Database connection timed out after {timeout} seconds")
        except ValueError as e:
            # Re-raise ValueError for unsupported database types
            raise e
        except Exception as e:
            logger.error(f"Failed to create database connection: {str(e)}")
            raise e
    
    def _create_connection_sync(self):
        """Create a new database connection (synchronous)"""
        # Parse connection string
        parsed = urlparse(self.connection_string)
        
        # Override with auth credentials if provided
        username = self.auth_credentials.get('username') or parsed.username
        password = self.auth_credentials.get('password') or parsed.password
        
        # Check if database type is supported before trying to connect
        if self.database_type == 'oracle' and not HAS_ORACLE:
            raise ValueError(f"Oracle database driver is not installed. Please install it with: pip install oracledb")
        elif self.database_type == 'postgresql' and not HAS_POSTGRES:
            raise ValueError(f"PostgreSQL database driver (psycopg2) is not installed. Please install it with: pip install psycopg2-binary")
        elif self.database_type == 'mysql' and not HAS_MYSQL:
            raise ValueError(f"MySQL database driver (mysql-connector-python) is not installed. Please install it with: pip install mysql-connector-python")
        elif self.database_type == 'sqlserver' and not HAS_SQLSERVER:
            raise ValueError(f"SQL Server database driver (pyodbc) is not installed. Please install it with: pip install pyodbc")
        
        try:
            if self.database_type == 'postgresql' and HAS_POSTGRES:
                # PostgreSQL connection
                conn_params = {
                    'host': parsed.hostname,
                    'port': parsed.port or 5432,
                    'database': parsed.path.lstrip('/'),
                    'user': username,
                    'password': password
                }
                
                # Add SSL if configured
                if self.auth_config.get('ssl_mode'):
                    conn_params['sslmode'] = self.auth_config['ssl_mode']

                conn = psycopg2.connect(**conn_params)
                # psycopg2 defaults to autocommit=False, so the first statement
                # (including the pool's SELECT 1 liveness probe) opens an implicit
                # transaction. Leaving that transaction open makes a later
                # `conn.autocommit = True` raise "set_session cannot be used
                # inside a transaction". Enable autocommit up front (as we already
                # do for MySQL). Flow-scoped transaction mode (autocommit=false on
                # the app) toggles this off explicitly on a pinned connection.
                conn.autocommit = True
                return conn
                
            elif self.database_type == 'mysql' and HAS_MYSQL:
                # MySQL connection
                conn_params = {
                    'host': parsed.hostname,
                    'port': parsed.port or 3306,
                    'database': parsed.path.lstrip('/'),
                    'user': username,
                    'password': password,
                    # Add connection timeouts to prevent hanging
                    'connection_timeout': self.auth_config.get('connection_timeout', 30),
                    'autocommit': True,  # Important for read operations
                    'raise_on_warnings': False
                }

                # Add SSL if configured
                if self.auth_config.get('ssl_mode') == 'require':
                    conn_params['ssl_disabled'] = False

                logger.info(f"Attempting MySQL connection to {parsed.hostname}:{parsed.port or 3306}/{parsed.path.lstrip('/')}")

                return mysql.connector.connect(**conn_params)
                
            elif self.database_type == 'oracle' and HAS_ORACLE:
                # Oracle connection using oracledb/cx_Oracle
                # Parse the connection string to handle different formats
                # Format: oracle://host:port/service_name or oracle://host:port/SID
                service_or_sid = parsed.path.lstrip('/')
                
                # Initialize Oracle client in thick mode if not already done
                # This is required for certain Oracle databases, especially cloud instances
                global ORACLE_THICK_MODE_INITIALIZED
                
                if ORACLE_DRIVER == 'oracledb' and not ORACLE_THICK_MODE_INITIALIZED:
                    try:
                        # This is oracledb (python-oracledb)
                        if cx_Oracle.is_thin_mode():
                            logger.info("Oracle driver is in thin mode, switching to thick mode...")
                            try:
                                # Try to initialize thick mode
                                # This requires Oracle Instant Client to be installed
                                # Get Oracle client path from LD_LIBRARY_PATH environment variable
                                import os
                                lib_path = os.environ.get('LD_LIBRARY_PATH', '').split(':')[0] if os.environ.get('LD_LIBRARY_PATH') else None

                                init_success = False
                                try:
                                    if lib_path and os.path.exists(lib_path):
                                        cx_Oracle.init_oracle_client(lib_dir=lib_path)
                                        logger.info(f"Successfully initialized Oracle thick mode with lib_dir from LD_LIBRARY_PATH: {lib_path}")
                                        init_success = True
                                        ORACLE_THICK_MODE_INITIALIZED = True
                                    else:
                                        # Try without lib_dir (let oracledb auto-detect)
                                        cx_Oracle.init_oracle_client()
                                        logger.info("Successfully initialized Oracle thick mode (auto-detected)")
                                        init_success = True
                                        ORACLE_THICK_MODE_INITIALIZED = True
                                except Exception as init_error:
                                    logger.warning(f"Could not initialize Oracle thick mode: {init_error}")

                                if not init_success:
                                    logger.warning("Could not initialize Oracle thick mode - Oracle Instant Client may not be installed")
                                    logger.warning("Set LD_LIBRARY_PATH to Oracle Instant Client directory")
                                    logger.warning("Continuing with thin mode - this may cause connection issues")
                            except Exception as init_error:
                                logger.warning(f"Could not initialize Oracle thick mode: {init_error}")
                                logger.warning("Continuing with thin mode - this may cause connection issues")
                        else:
                            logger.info("Oracle driver already in thick mode")
                            ORACLE_THICK_MODE_INITIALIZED = True
                    except Exception as check_error:
                        logger.warning(f"Could not check Oracle mode: {check_error}")
                elif ORACLE_DRIVER == 'cx_Oracle':
                    logger.info("Using cx_Oracle driver (thick mode by default)")
                elif ORACLE_THICK_MODE_INITIALIZED:
                    logger.debug("Oracle thick mode already initialized")
                
                # Create connection string - use different approaches for better compatibility
                # Option 1: Try connection string format first (more reliable)
                connection_string = f"{username}/{password}@{parsed.hostname}:{parsed.port or 1521}/{service_or_sid}"
                
                logger.info(f"Attempting Oracle connection to {parsed.hostname}:{parsed.port or 1521}/{service_or_sid}")
                
                # Connect to Oracle database
                try:
                    # Try connection string format first (often more reliable)
                    try:
                        conn = cx_Oracle.connect(connection_string)
                        logger.info("Oracle connection successful using connection string format")
                    except Exception as e1:
                        # Fall back to DSN format
                        logger.debug(f"Connection string format failed: {e1}, trying DSN format...")
                        
                        # Create DSN (Data Source Name)
                        dsn = cx_Oracle.makedsn(
                            parsed.hostname,
                            parsed.port or 1521,
                            service_name=service_or_sid
                        )
                        
                        conn = cx_Oracle.connect(
                            user=username,
                            password=password,
                            dsn=dsn
                        )
                        logger.info("Oracle connection successful using DSN format")
                    
                    # Set session parameters after connection is established
                    if conn:
                        try:
                            # Try to set optimal fetch size
                            cursor = conn.cursor()
                            cursor.arraysize = 100
                            cursor.close()
                        except:
                            pass
                    
                    return conn
                    
                except cx_Oracle.Error as e:
                    error = e.args[0] if e.args else e
                    logger.error(f"Oracle connection failed: {error}")
                    
                    # Check for specific Oracle errors
                    if hasattr(error, 'code'):
                        if error.code == 1017:
                            raise ValueError("Invalid username/password for Oracle database")
                        elif error.code == 12154:
                            raise ValueError("TNS could not resolve the connect identifier - check service name")
                        elif error.code == 12541:
                            raise ValueError("TNS no listener - Oracle listener may not be running")
                        elif error.code == 12547:
                            raise ConnectionError(
                                "TNS:lost contact - This often indicates a library compatibility issue. "
                                "Try: 1) Check Oracle Instant Client permissions (chmod -R 755), "
                                "2) On macOS, allow libraries in System Settings > Privacy & Security, "
                                "3) Ensure ORACLE_HOME and DYLD_LIBRARY_PATH are set correctly"
                            )
                    
                    # Check for DPY-4011 error (connection reset)
                    if "DPY-4011" in str(e):
                        raise ConnectionError(
                            "Oracle connection was reset. This often requires thick mode with Oracle Instant Client. "
                            "Please ensure Oracle Instant Client is installed and accessible. "
                            f"Original error: {str(e)}"
                        )
                    
                    # Check for ORA-12547 (TNS:lost contact)
                    if "ORA-12547" in str(e) or "TNS:lost contact" in str(e):
                        raise ConnectionError(
                            "ORA-12547: TNS:lost contact - This typically indicates Oracle Instant Client compatibility issues. "
                            "Solutions: 1) Ensure client libraries have proper permissions (chmod -R 755 /opt/oracle/instantclient_23_3), "
                            "2) On macOS, check System Settings > Privacy & Security for blocked libraries, "
                            "3) Try restarting the backend server with proper environment variables set"
                        )
                    
                    raise
                
            elif self.database_type == 'sqlserver' and HAS_SQLSERVER:
                # SQL Server connection
                driver = '{ODBC Driver 17 for SQL Server}'
                conn_string = (
                    f"DRIVER={driver};"
                    f"SERVER={parsed.hostname},{parsed.port or 1433};"
                    f"DATABASE={parsed.path.lstrip('/')};"
                    f"UID={username};"
                    f"PWD={password}"
                )
                
                if self.auth_config.get('ssl_mode') == 'require':
                    conn_string += ";Encrypt=yes"
                    
                return pyodbc.connect(conn_string)
                
            elif self.database_type == 'sqlite':
                # SQLite connection
                db_path = parsed.path or ':memory:'
                return sqlite3.connect(db_path)
                
            else:
                raise ValueError(f"Unsupported database type: {self.database_type}")
        except Exception as e:
            # Special handling for Oracle connection errors
            if self.database_type == 'oracle' and "DPY-4011" in str(e):
                logger.error(f"Oracle connection reset error: {str(e)}")
                logger.error("This could be due to:")
                logger.error("1. Network/firewall issues blocking Oracle protocol")
                logger.error("2. Oracle listener configuration issues")
                logger.error("3. Incorrect service name or SID")
                logger.error("4. Need for thick mode client (install Oracle Instant Client)")
                # Try to provide more helpful error message
                raise ConnectionError(
                    f"Oracle connection failed - connection reset by server. "
                    f"This typically indicates network/firewall issues or incorrect service configuration. "
                    f"Original error: {str(e)}"
                )
            else:
                logger.error(f"Failed to create database connection: {str(e)}")
                raise
    
    async def get_connection(self):
        """Get a connection from the pool, validating it first and transparently
        reconnecting if the database has dropped the session (e.g. Oracle ORA-2396
        idle-timeout, DPI-1080 connection-closed)."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        # Try every pooled connection; replace dead ones with fresh sessions.
        attempts = max(len(self.connections), self.pool_size, 1)
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            conn = await self.available_connections.get()
            if await self._is_connection_alive(conn):
                return conn

            logger.warning(
                f"Discarding dead {self.database_type} connection "
                f"(attempt {attempt + 1}/{attempts}); reconnecting"
            )
            self._discard_connection(conn)

            try:
                new_conn = await self._create_connection()
            except Exception as e:
                last_error = e
                logger.error(f"Failed to create replacement connection: {e}")
                continue

            if new_conn:
                self.connections.append(new_conn)
                return new_conn

        if last_error:
            raise last_error
        raise ConnectionError(
            f"Unable to obtain a live {self.database_type} connection from the pool"
        )

    async def return_connection(self, conn):
        """Return a connection to the pool"""
        if not self._closed and conn:
            await self.available_connections.put(conn)

    def discard_connection(self, conn):
        """Close and untrack a connection so it is not returned to the pool.
        Use this when a query failed with an error that suggests the session is
        no longer usable (e.g. Oracle ORA-2396 / DPI-1080)."""
        self._discard_connection(conn)

    def _discard_connection(self, conn):
        """Remove a connection from tracking and close it (best-effort)."""
        if conn is None:
            return
        try:
            self.connections.remove(conn)
        except ValueError:
            pass
        except Exception:
            pass
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Error closing discarded connection: {e}")

    async def _is_connection_alive(self, conn) -> bool:
        """Verify whether a borrowed connection is still usable.

        For Oracle this calls oracledb/cx_Oracle's ``ping()`` which performs a
        round-trip and raises if the session has been terminated by the server
        (the typical cause of DPI-1080 / ORA-2396 after long idle periods).
        """
        if conn is None:
            return False
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._is_connection_alive_sync, conn),
                timeout=10,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"{self.database_type} connection liveness check timed out; "
                f"treating as dead"
            )
            return False
        except Exception as e:
            logger.debug(f"Connection liveness check failed: {e}")
            return False

    def _is_connection_alive_sync(self, conn) -> bool:
        """Synchronous liveness probe (runs in the executor thread)."""
        try:
            if self.database_type == 'oracle' and HAS_ORACLE:
                # oracledb and cx_Oracle both expose Connection.ping(), which
                # forces a server round-trip and raises if the session is dead.
                conn.ping()
                return True

            if self.database_type == 'postgresql' and HAS_POSTGRES:
                if getattr(conn, 'closed', 0):
                    return False
                cur = conn.cursor()
                try:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                finally:
                    cur.close()
                return True

            if self.database_type == 'mysql' and HAS_MYSQL:
                # mysql.connector exposes ping(); pass reconnect=False so a dead
                # connection is reported (rather than silently re-established
                # outside the pool).
                conn.ping(reconnect=False, attempts=1, delay=0)
                return True

            if self.database_type == 'sqlserver' and HAS_SQLSERVER:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                finally:
                    cur.close()
                return True

            if self.database_type == 'sqlite':
                cur = conn.cursor()
                try:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                finally:
                    cur.close()
                return True
        except Exception as e:
            logger.info(
                f"{self.database_type} connection failed liveness check, will reconnect: {e}"
            )
            return False
        return True

    async def close(self):
        """Close all connections in the pool"""
        self._closed = True
        
        # Close all connections
        for conn in self.connections:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
                
        self.connections.clear()


class DatabaseQueryExecutor(ServiceExecutor):
    """Executor for Database Query service type"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = self.service_config
        
        # Log received parameters for debugging
        logger.info(f"DatabaseQueryExecutor.execute received parameters: {parameters}")
        logger.info(f"Parameters type: {type(parameters)}")
        
        # Ensure parameters is a dictionary
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
                logger.info(f"Parsed parameters from string: {parameters}")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse parameters string: {parameters}")
                parameters = {}
        
        # Get SQL query
        sql_query = parameters.get('sql')
        logger.info(f"Extracted SQL query: {sql_query}")
        
        # Extract parameters - all keys except 'sql' are considered bind parameters
        query_params = {k: v for k, v in parameters.items() if k != 'sql'}
        
        # A commit/rollback step (dedicated service) carries no SQL, so only
        # enforce the SQL requirement for real statements.
        if not sql_query and self._transaction_control_op(sql_query, config) is None:
            return {
                'error': True,
                'message': 'SQL query is required'
            }

        # Get or create connection pool — keyed per subscription (tenant +
        # application instance) and per connection fingerprint (credentials/URL)
        database_type = self.auth_config.get('database_type', 'postgresql')
        base_url = context.get('application_base_url', '')
        pool_prefix = f"{self.subscription_id}_{database_type}_"
        pool_key = pool_prefix + connection_fingerprint(base_url, self.auth_credentials, self.auth_config)
        pool = CONNECTION_POOLS.get(pool_key)

        if not pool:
            # Create new pool
            if not base_url:
                return {
                    'error': True,
                    'message': 'Database connection URL not configured'
                }

            # Connection config changed for this subscription — close the old
            # pool first so we don't leak server-side connection slots
            await evict_stale_pools(CONNECTION_POOLS, pool_prefix, pool_key)

            pool_size = self.auth_config.get('connection_pool_size', 10)

            pool = DatabaseConnectionPool(
                base_url,
                self.auth_credentials,
                self.auth_config,
                pool_size
            )

            try:
                await pool.initialize()
                CONNECTION_POOLS[pool_key] = pool
            except ValueError as e:
                # Handle unsupported database type or missing driver
                logger.error(f"Failed to initialize database pool: {str(e)}")
                return {
                    'error': True,
                    'message': str(e),
                    'error_type': 'configuration_error'
                }
            except ConnectionError as e:
                # Handle specific connection errors (like Oracle DPY-4011)
                logger.error(f"Database connection error: {str(e)}")
                return {
                    'error': True,
                    'message': str(e),
                    'error_type': 'connection_error'
                }
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {str(e)}")
                return {
                    'error': True,
                    'message': f'Failed to connect to database: {str(e)}',
                    'error_type': 'connection_error'
                }
        
        # An explicit commit/rollback step acts on the flow-scoped transaction
        # regardless of the autocommit setting. If none is open (e.g. the app is
        # in autocommit mode), it is a harmless no-op.
        control = self._transaction_control_op(sql_query, config)
        if control is not None:
            from services import db_transaction_manager as txn_mgr
            execution_id = context.get('execution_id')
            if control == 'commit':
                committed = await txn_mgr.commit(execution_id, pool_key)
                return {
                    'success': True,
                    'committed': committed,
                    'message': 'Transaction committed' if committed
                               else 'No open transaction to commit'
                }
            rolled = await txn_mgr.rollback(execution_id, pool_key)
            return {
                'success': True,
                'rolled_back': rolled,
                'message': 'Transaction rolled back' if rolled
                           else 'No open transaction to roll back'
            }

        # Resolve autocommit behaviour. Default True preserves the per-call
        # commit semantics every existing flow relies on. Set autocommit=false
        # on the database application (auth_config) to run a flow-scoped
        # transaction that is committed by an explicit commit step instead.
        autocommit_flag = self._resolve_autocommit_flag(config)
        if not autocommit_flag:
            return await self._execute_transactional(
                pool, pool_key, sql_query, query_params, config, context
            )

        # Execute query
        conn = None
        conn_failed = False
        try:
            conn = await pool.get_connection()

            # Set autocommit for read queries to avoid transaction issues
            if hasattr(conn, 'autocommit'):
                conn.autocommit = True
            
            # Convert named parameters to appropriate format for database
            processed_query, processed_params = self._process_query_parameters(
                sql_query, 
                query_params, 
                pool.database_type
            )
            
            # Execute based on operation type
            operation_type = config.get('operation_type', 'query')

            # Auto-detect operation type if needed
            # If operation_type is 'query' but the SQL is not a SELECT, auto-detect
            detected_type = self._detect_sql_operation_type(processed_query)
            if operation_type == 'query' and detected_type != 'query':
                logger.info(f"Auto-detected operation type '{detected_type}' for SQL: {processed_query[:100]}")
                operation_type = detected_type

            if operation_type == 'query':
                result = await self._execute_query(
                    conn, 
                    processed_query, 
                    processed_params, 
                    pool.database_type,
                    config
                )
            elif operation_type == 'execute':
                result = await self._execute_command(
                    conn, 
                    processed_query, 
                    processed_params, 
                    pool.database_type,
                    config
                )
            elif operation_type == 'batch':
                # For batch operations, expect multiple SQL statements
                batch_queries = parameters.get('batch_queries', [])
                result = await self._execute_batch(
                    conn, 
                    batch_queries, 
                    pool.database_type,
                    config
                )
            else:
                result = {
                    'error': True,
                    'message': f'Unknown operation type: {operation_type}'
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Database query execution failed: {str(e)}", exc_info=True)
            # If the failure looks like a dropped/closed session, mark the
            # connection so we discard it instead of poisoning the pool.
            if conn is not None and _is_connection_lost_error(e, pool.database_type):
                logger.warning(
                    f"Detected lost {pool.database_type} session in query path; "
                    f"connection will be discarded so the next request reconnects"
                )
                conn_failed = True
            # Rollback transaction on error to clean up connection state
            if conn and not conn_failed:
                try:
                    conn.rollback()
                except:
                    pass
            return {
                'error': True,
                'message': str(e),
                'error_type': type(e).__name__
            }
        finally:
            if conn:
                if conn_failed:
                    pool.discard_connection(conn)
                else:
                    await pool.return_connection(conn)

    def _resolve_autocommit_flag(self, config: Dict[str, Any]) -> bool:
        """Whether this database service should commit each statement on its own.

        Precedence: service_config override -> application auth_config -> default
        True (so flows that never opt in behave exactly as before)."""
        raw = config.get('autocommit', self.auth_config.get('autocommit', True))
        if isinstance(raw, str):
            return raw.strip().lower() not in ('false', '0', 'no', 'off')
        return bool(raw)

    def _transaction_control_op(self, sql_query: str, config: Dict[str, Any]) -> Optional[str]:
        """Detect an explicit commit/rollback step.

        Recognised either via ``operation_type`` (dedicated commit_transaction /
        rollback_transaction services) or a bare ``COMMIT`` / ``ROLLBACK`` SQL."""
        op = (config.get('operation_type') or '').strip().lower()
        if op in ('commit', 'rollback'):
            return op
        normalized = (sql_query or '').strip().rstrip(';').strip().upper()
        if normalized == 'COMMIT':
            return 'commit'
        if normalized in ('ROLLBACK', 'ABORT'):
            return 'rollback'
        return None

    async def _execute_transactional(self, pool, pool_key, sql_query, query_params,
                                     config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a statement inside a flow-scoped transaction (autocommit=false).

        The connection is pinned to the execution by db_transaction_manager and
        held across nodes until an explicit commit/rollback step runs. If the
        flow ends without committing, the engine's release hook rolls it back.

        Commit/rollback control steps are handled by execute() before this is
        called, so here sql_query is always a real statement."""
        from services import db_transaction_manager as txn_mgr

        execution_id = context.get('execution_id')

        if not sql_query:
            return {'error': True, 'message': 'SQL query is required'}

        try:
            conn = await txn_mgr.get_sync_connection(execution_id, pool_key, pool)

            processed_query, processed_params = self._process_query_parameters(
                sql_query, query_params, pool.database_type
            )

            operation_type = config.get('operation_type', 'query')
            detected_type = self._detect_sql_operation_type(processed_query)
            if operation_type == 'query' and detected_type != 'query':
                logger.info(f"Auto-detected operation type '{detected_type}' for SQL: {processed_query[:100]}")
                operation_type = detected_type

            # commit=False everywhere: the transaction spans the whole flow and
            # is committed only by an explicit commit step.
            if operation_type == 'query':
                return await self._execute_query(
                    conn, processed_query, processed_params, pool.database_type, config
                )
            elif operation_type == 'execute':
                return await self._execute_command(
                    conn, processed_query, processed_params, pool.database_type, config,
                    commit=False
                )
            elif operation_type == 'batch':
                batch_queries = query_params.get('batch_queries', [])
                return await self._execute_batch(
                    conn, batch_queries, pool.database_type, config, commit=False
                )
            else:
                return {'error': True, 'message': f'Unknown operation type: {operation_type}'}

        except Exception as e:
            logger.error(f"Transactional DB execution failed: {str(e)}", exc_info=True)
            # A failed statement aborts the transaction (PostgreSQL blocks any
            # further work on it), so tear the whole flow transaction down and
            # release the connection. Downstream nodes that write will start a
            # fresh transaction.
            try:
                await txn_mgr.rollback(execution_id, pool_key)
            except Exception:
                pass
            return {
                'error': True,
                'message': str(e),
                'error_type': type(e).__name__
            }

    def _detect_sql_operation_type(self, sql: str) -> str:
        """
        Auto-detect SQL operation type from the SQL statement
        Returns: 'query', 'execute', or 'batch'
        """
        if not sql:
            return 'query'

        # Normalize SQL - strip leading/trailing whitespace and convert to uppercase
        normalized_sql = sql.strip().upper()

        # Remove leading comments
        while normalized_sql.startswith('--') or normalized_sql.startswith('/*'):
            if normalized_sql.startswith('--'):
                # Single line comment
                newline_pos = normalized_sql.find('\n')
                if newline_pos == -1:
                    return 'query'  # Entire string is comment
                normalized_sql = normalized_sql[newline_pos+1:].strip()
            elif normalized_sql.startswith('/*'):
                # Multi-line comment
                end_pos = normalized_sql.find('*/')
                if end_pos == -1:
                    return 'query'  # Unterminated comment
                normalized_sql = normalized_sql[end_pos+2:].strip()

        # Check for SELECT queries (read operations)
        if normalized_sql.startswith('SELECT') or normalized_sql.startswith('WITH'):
            return 'query'

        # Check for write operations (INSERT, UPDATE, DELETE, MERGE)
        if (normalized_sql.startswith('INSERT') or
            normalized_sql.startswith('UPDATE') or
            normalized_sql.startswith('DELETE') or
            normalized_sql.startswith('MERGE')):
            return 'execute'

        # Check for DDL operations (CREATE, ALTER, DROP, TRUNCATE)
        if (normalized_sql.startswith('CREATE') or
            normalized_sql.startswith('ALTER') or
            normalized_sql.startswith('DROP') or
            normalized_sql.startswith('TRUNCATE')):
            return 'execute'

        # Check for transaction control (COMMIT, ROLLBACK)
        if (normalized_sql.startswith('COMMIT') or
            normalized_sql.startswith('ROLLBACK')):
            return 'execute'

        # Default to query for unknown types
        logger.warning(f"Unknown SQL operation type for: {sql[:50]}... - defaulting to 'query'")
        return 'query'

    def _find_bind_variables_outside_strings(self, query: str) -> List[Tuple[int, int, str]]:
        """
        Find all bind variable positions (:param_name) that are NOT inside string literals.
        Returns list of (start_pos, end_pos, param_name) tuples.
        """
        if not query:
            return []

        bind_vars = []
        i = 0
        length = len(query)
        in_string = False

        while i < length:
            char = query[i]

            # Handle string literals (single quotes in SQL)
            if char == "'":
                # Check if this is an escaped quote ('')
                if i + 1 < length and query[i + 1] == "'":
                    # Skip escaped quote
                    i += 2
                    continue
                else:
                    # Toggle in_string state
                    in_string = not in_string
                    i += 1
                    continue

            # Only look for bind variables when NOT in a string
            if not in_string and char == ':':
                # Check if this looks like a bind variable (:word_chars)
                # Make sure it's not already a numbered bind variable (:1, :2, etc.)
                if i + 1 < length:
                    next_char = query[i + 1]
                    # Skip if next char is a digit (already processed bind variable)
                    if next_char.isdigit():
                        i += 1
                        continue

                    # Extract parameter name (word characters only)
                    j = i + 1
                    while j < length and (query[j].isalnum() or query[j] == '_'):
                        j += 1

                    if j > i + 1:  # Found at least one word character
                        param_name = query[i+1:j]
                        bind_vars.append((i, j, param_name))
                        i = j
                        continue

            i += 1

        return bind_vars

    def _process_query_parameters(self, query: str, params: Dict[str, Any],
                                 database_type: str) -> Tuple[str, Any]:
        """Convert named parameters to database-specific format"""

        if query is None:
            return None, params
            
        if database_type == 'postgresql':
            # PostgreSQL uses %(name)s format
            processed_query = query
            processed_params = {}
            
            # Find all :param_name patterns
            param_pattern = r':(\w+)'
            for match in re.finditer(param_pattern, query):
                param_name = match.group(1)
                if param_name in params:
                    # Replace :param with %(param)s
                    processed_query = processed_query.replace(
                        f':{param_name}', 
                        f'%({param_name})s'
                    )
                    processed_params[param_name] = params[param_name]
            
            return processed_query, processed_params
            
        elif database_type == 'mysql':
            # MySQL uses %s format with positional parameters
            processed_query = query
            processed_params = []
            
            # Find and replace parameters in order
            param_pattern = r':(\w+)'
            for match in re.finditer(param_pattern, query):
                param_name = match.group(1)
                if param_name in params:
                    processed_query = processed_query.replace(
                        f':{param_name}', 
                        '%s', 
                        1  # Replace only first occurrence
                    )
                    processed_params.append(params[param_name])
            
            return processed_query, tuple(processed_params)
            
        elif database_type == 'oracle':
            # Oracle uses :1, :2 format
            # Important: Only process bind variables that are OUTSIDE of string literals
            # to avoid treating time values like '21:30' as bind variables

            # Find all bind variables outside of string literals
            bind_vars = self._find_bind_variables_outside_strings(query)

            if not bind_vars:
                # No bind variables found, return query as-is
                return query, []

            # Build parameter mapping and replacement
            processed_query = query
            processed_params = []
            param_mapping = {}
            param_index = 1

            # Sort bind variables by position (descending) to replace from end to start
            # This prevents position shifts during replacement
            bind_vars_sorted = sorted(bind_vars, key=lambda x: x[0], reverse=True)

            # First pass: build unique parameter mapping
            seen_params = set()
            for start_pos, end_pos, param_name in bind_vars:
                if param_name not in seen_params:
                    param_mapping[param_name] = param_index
                    processed_params.append(params.get(param_name))
                    param_index += 1
                    seen_params.add(param_name)

            # Second pass: replace in reverse order (from end to start)
            for start_pos, end_pos, param_name in bind_vars_sorted:
                replacement = f':{param_mapping[param_name]}'
                processed_query = processed_query[:start_pos] + replacement + processed_query[end_pos:]

            return processed_query, processed_params
            
        elif database_type == 'sqlserver':
            # SQL Server uses ? format
            processed_query = query
            processed_params = []
            
            # Find and replace parameters in order
            param_pattern = r':(\w+)'
            for match in re.finditer(param_pattern, query):
                param_name = match.group(1)
                if param_name in params:
                    processed_query = processed_query.replace(
                        f':{param_name}', 
                        '?', 
                        1
                    )
                    processed_params.append(params[param_name])
            
            return processed_query, tuple(processed_params)
            
        elif database_type == 'sqlite':
            # SQLite uses ? format
            processed_query = query
            processed_params = []
            
            # Find and replace parameters in order
            param_pattern = r':(\w+)'
            for match in re.finditer(param_pattern, query):
                param_name = match.group(1)
                if param_name in params:
                    processed_query = processed_query.replace(
                        f':{param_name}', 
                        '?', 
                        1
                    )
                    processed_params.append(params[param_name])
            
            return processed_query, tuple(processed_params)
            
        else:
            # Default: return as-is
            return query, params
    
    async def _execute_query(self, conn, query: str, params: Any,
                           database_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SELECT query and return results"""
        # Run synchronous database operations in thread pool to prevent blocking
        loop = asyncio.get_event_loop()
        # Default to 180 seconds for database queries (3 minutes)
        query_timeout = config.get('query_timeout', self.auth_config.get('query_timeout', 180))

        try:
            # Execute query with timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._execute_query_sync,
                    conn, query, params, database_type, config
                ),
                timeout=query_timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Query execution timed out after {query_timeout} seconds")
            return {
                'error': True,
                'message': f'Query execution timed out after {query_timeout} seconds',
                'error_type': 'timeout'
            }
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise

    def _execute_query_sync(self, conn, query: str, params: Any,
                           database_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SELECT query synchronously (runs in thread pool)"""
        cursor = None
        try:
            # Get configuration
            max_rows = config.get('max_rows', 10000)
            result_format = config.get('result_format', 'json_array')
            
            if database_type == 'postgresql' and HAS_POSTGRES:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query, params)
                rows = cursor.fetchmany(max_rows)
                
            elif database_type == 'mysql' and HAS_MYSQL:
                cursor = conn.cursor(dictionary=True, buffered=True)
                # Execute with timeout protection
                cursor.execute(query, params)
                rows = cursor.fetchmany(max_rows)
                
            elif database_type == 'oracle' and HAS_ORACLE:
                cursor = conn.cursor()
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                rows = []
                for row in cursor.fetchmany(max_rows):
                    rows.append(dict(zip(columns, row)))
                    
            elif database_type == 'sqlserver' and HAS_SQLSERVER:
                cursor = conn.cursor()
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                rows = []
                for row in cursor.fetchmany(max_rows):
                    rows.append(dict(zip(columns, row)))
                    
            elif database_type == 'sqlite':
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = [dict(row) for row in cursor.fetchmany(max_rows)]
            else:
                raise ValueError(f"Unsupported database type: {database_type}")
            
            # Convert results based on format
            if result_format == 'json_array':
                # Convert special types for JSON serialization
                result_data = self._serialize_results(rows)
            elif result_format == 'json_object':
                # Return first row as object
                result_data = self._serialize_results(rows[0] if rows else {})
            elif result_format == 'csv':
                # Convert to CSV format
                import csv
                import io
                output = io.StringIO()
                if rows:
                    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                result_data = output.getvalue()
            else:
                result_data = rows
            
            return {
                'success': True,
                'data': result_data,
                'row_count': len(rows),
                'truncated': len(rows) == max_rows
            }

        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
    
    async def _execute_command(self, conn, query: str, params: Any,
                             database_type: str, config: Dict[str, Any],
                             commit: bool = True) -> Dict[str, Any]:
        """Execute INSERT/UPDATE/DELETE command.

        commit=False leaves the statement in the open transaction (flow-scoped
        transaction mode); the caller commits later via an explicit step."""
        # Run synchronous database operations in thread pool to prevent blocking
        loop = asyncio.get_event_loop()
        # Default to 180 seconds for database queries (3 minutes)
        query_timeout = config.get('query_timeout', self.auth_config.get('query_timeout', 180))

        try:
            # Execute command with timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._execute_command_sync,
                    conn, query, params, database_type, config, commit
                ),
                timeout=query_timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Command execution timed out after {query_timeout} seconds")
            # Try to rollback if possible
            try:
                await loop.run_in_executor(None, conn.rollback)
            except:
                pass
            return {
                'error': True,
                'message': f'Command execution timed out after {query_timeout} seconds',
                'error_type': 'timeout'
            }
        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            raise

    def _execute_command_sync(self, conn, query: str, params: Any,
                             database_type: str, config: Dict[str, Any],
                             commit: bool = True) -> Dict[str, Any]:
        """Execute INSERT/UPDATE/DELETE command synchronously (runs in thread pool)"""
        cursor = None
        try:
            if database_type == 'postgresql' and HAS_POSTGRES:
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_rows = cursor.rowcount
                if commit:
                    conn.commit()
                
            elif database_type == 'mysql' and HAS_MYSQL:
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_rows = cursor.rowcount
                if commit:
                    conn.commit()
                
            elif database_type == 'oracle' and HAS_ORACLE:
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_rows = cursor.rowcount
                if commit:
                    conn.commit()
                
            elif database_type == 'sqlserver' and HAS_SQLSERVER:
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_rows = cursor.rowcount
                if commit:
                    conn.commit()
                
            elif database_type == 'sqlite':
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_rows = cursor.rowcount
                if commit:
                    conn.commit()
            else:
                raise ValueError(f"Unsupported database type: {database_type}")
            
            return {
                'success': True,
                'affected_rows': affected_rows,
                'message': f'Successfully executed command, {affected_rows} rows affected'
            }

        except Exception as e:
            # Rollback on error
            try:
                conn.rollback()
            except:
                pass
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
    
    async def _execute_batch(self, conn, batch_queries: List[Dict[str, Any]],
                           database_type: str, config: Dict[str, Any],
                           commit: bool = True) -> Dict[str, Any]:
        """Execute multiple queries in a transaction.

        commit=False means the batch runs inside a caller-owned, flow-scoped
        transaction: this method must not toggle autocommit or commit/restore
        it — the pinned connection is already in manual-transaction mode and
        stays that way until an explicit commit step."""
        cursor = None
        results = []

        try:
            # Start transaction (own the autocommit toggle only when we also own
            # the commit; in flow-scoped mode the connection is already manual).
            if commit and database_type != 'sqlite':
                conn.autocommit = False
            
            cursor = conn.cursor()
            
            for query_item in batch_queries:
                sql = query_item.get('sql')
                params = query_item.get('parameters', {})
                
                if not sql:
                    continue
                
                # Process parameters
                processed_query, processed_params = self._process_query_parameters(
                    sql, params, database_type
                )
                
                # Execute query
                if database_type == 'postgresql' and HAS_POSTGRES:
                    cursor.execute(processed_query, processed_params)
                elif database_type == 'mysql' and HAS_MYSQL:
                    cursor.execute(processed_query, processed_params)
                elif database_type == 'oracle' and HAS_ORACLE:
                    cursor.execute(processed_query, processed_params)
                elif database_type == 'sqlserver' and HAS_SQLSERVER:
                    cursor.execute(processed_query, processed_params)
                elif database_type == 'sqlite':
                    cursor.execute(processed_query, processed_params)
                    
                results.append({
                    'query': sql,
                    'affected_rows': cursor.rowcount
                })
            
            # Commit transaction (only when this call owns it)
            if commit:
                conn.commit()

            return {
                'success': True,
                'results': results,
                'total_queries': len(batch_queries),
                'message': f'Successfully executed {len(batch_queries)} queries in batch'
            }
            
        except Exception as e:
            # Rollback on error only when this call owns the transaction. In
            # flow-scoped mode the caller (_execute_transactional) tears down the
            # whole flow transaction instead.
            if commit:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if cursor:
                cursor.close()
            # Restore autocommit only when this call owned the toggle. Leaving a
            # pinned flow-scoped connection in manual mode is intentional.
            if commit and database_type != 'sqlite' and hasattr(conn, 'autocommit'):
                conn.autocommit = True
    
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
            # Try to decode as UTF-8, otherwise return base64
            try:
                return data.decode('utf-8')
            except:
                import base64
                return base64.b64encode(data).decode('ascii')
        else:
            return data


# Cleanup function to close all pools
async def cleanup_connection_pools():
    """Close all connection pools"""
    for pool_key, pool in CONNECTION_POOLS.items():
        try:
            await pool.close()
        except Exception as e:
            logger.error(f"Error closing pool {pool_key}: {str(e)}")
    
    CONNECTION_POOLS.clear()