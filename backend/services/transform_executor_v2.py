"""
Transform Executor V2 - Alternative execution strategy for transform scripts
This version uses exec with custom namespace instead of RestrictedPython for better compatibility
"""

import os
import sys
import time
import json
import base64
import hashlib
import traceback
import calendar
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)

class AttrDict(dict):
    """Dictionary that allows attribute-style access to its keys"""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None  # Return None for missing attributes instead of raising AttributeError

    def __setattr__(self, name, value):
        self[name] = value

    def __iter__(self):
        # Ensure proper iteration for dict() constructor and update operations
        return super().__iter__()

    def items(self):
        # Ensure proper items() method for dict operations
        return super().items()

    def keys(self):
        # Ensure proper keys() method
        return super().keys()

    def values(self):
        # Ensure proper values() method
        return super().values()


class TransformExecutorV2:
    """
    Alternative transform executor that uses standard Python exec with security controls
    instead of RestrictedPython to avoid compatibility issues with complex libraries
    """

    # Security limits
    MAX_EXECUTION_TIME = 30.0
    MAX_ITERATIONS = 100000
    MAX_OUTPUT_SIZE = 50 * 1024 * 1024  # 50MB

    def __init__(self):
        self._iteration_count = 0
        self._start_time = None

        # Blocked modules for security
        self.blocked_modules = {
            'os', 'subprocess', 'sys', 'eval', 'exec', 'compile',
            'open', 'file', 'input', 'raw_input', '__import__',
            'importlib', 'imp', 'reload', 'execfile',
            'socket', 'urllib2', 'httplib', 'ftplib',
            'telnetlib', 'ssl', 'select', 'pty', 'fcntl',
            'resource', 'signal', 'grp', 'pwd', 'spwd',
            'multiprocessing', 'threading', 'thread', 'Queue',
            'ctypes', 'cffi', 'pdb', 'bdb', 'cmd'
        }

        # Allowed modules (whitelist)
        self.allowed_modules = {
            # Basic modules
            'json', 'base64', 'hashlib', 'uuid', 'datetime', 'time',
            'calendar', 're', 'html', 'string', 'textwrap', 'csv',
            'collections', 'itertools', 'functools', 'operator',
            'decimal', 'fractions', 'math', 'statistics', 'random',
            'heapq', 'bisect', 'difflib', 'unicodedata', 'binascii',
            'urllib', 'urllib.parse', 'urllib.request', 'urllib.error', 'urllib.response',

            # IO modules (safe subset)
            'io', 'StringIO', 'BytesIO',

            # Email modules
            'email', 'email.utils', 'email.mime', 'email.mime.text',
            'email.mime.multipart', 'email.mime.base', 'email.message',
            'email.encoders',

            # ReportLab modules
            'reportlab', 'reportlab.lib', 'reportlab.lib.pagesizes',
            'reportlab.lib.styles', 'reportlab.lib.units',
            'reportlab.platypus', 'reportlab.pdfgen', 'reportlab.pdfgen.canvas',
            'reportlab.lib.colors', 'reportlab.lib.enums',
            'reportlab.platypus.tables', 'reportlab.platypus.paragraph',
            'reportlab.platypus.flowables', 'reportlab.lib.utils',

            # Data processing modules
            'pandas', 'numpy', 'openpyxl', 'xlrd', 'xlwt',
            'docx', 'docx2txt', 'pypdf', 'pptx',
            'olefile', 'striprtf', 'Pillow', 'PIL'
        }

        # Initialize helper operations
        self._init_helper_operations()

    def _init_helper_operations(self):
        """Initialize helper operations dictionaries"""

        # String operations
        self.string_ops = {
            'upper': lambda s: str(s).upper(),
            'lower': lambda s: str(s).lower(),
            'capitalize': lambda s: str(s).capitalize(),
            'title': lambda s: str(s).title(),
            'strip': lambda s, chars=None: str(s).strip(chars),
            'lstrip': lambda s, chars=None: str(s).lstrip(chars),
            'rstrip': lambda s, chars=None: str(s).rstrip(chars),
            'split': lambda s, sep=' ', maxsplit=-1: str(s).split(sep, maxsplit),
            'join': lambda sep, items: str(sep).join(str(i) for i in items),
            'replace': lambda s, old, new, count=-1: str(s).replace(str(old), str(new), count),
            'startswith': lambda s, prefix: str(s).startswith(str(prefix)),
            'endswith': lambda s, suffix: str(s).endswith(str(suffix)),
            'find': lambda s, sub: str(s).find(str(sub)),
            'count': lambda s, sub: str(s).count(str(sub)),
            'format': lambda s, *args, **kwargs: str(s).format(*args, **kwargs),
        }

        # Math operations
        self.math_ops = {
            'add': lambda a, b: a + b,
            'subtract': lambda a, b: a - b,
            'multiply': lambda a, b: a * b,
            'divide': lambda a, b: a / b if b != 0 else None,
            'floor_divide': lambda a, b: a // b if b != 0 else None,
            'modulo': lambda a, b: a % b if b != 0 else None,
            'power': lambda a, b: a ** b,
            'sqrt': lambda x: x ** 0.5 if x >= 0 else None,
        }

        # Base64 operations
        self.base64_ops = {
            'b64encode': lambda data: base64.b64encode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
            'b64decode': lambda data: base64.b64decode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
            'urlsafe_b64encode': lambda data: base64.urlsafe_b64encode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
            'urlsafe_b64decode': lambda data: base64.urlsafe_b64decode(data.encode('utf-8') if isinstance(data, str) else data).decode('utf-8'),
        }

        # Enhanced datetime operations
        import datetime as dt
        import calendar as cal
        self.datetime_ops = {
            # Basic date/time functions
            'now': lambda: dt.datetime.now().isoformat(),
            'utcnow': lambda: dt.datetime.utcnow().isoformat(),
            'today': lambda: dt.date.today().isoformat(),
            'timestamp': lambda: int(dt.datetime.now().timestamp()),
            'format_date': lambda date_str, fmt='%Y-%m-%d': dt.datetime.fromisoformat(date_str).strftime(fmt),
            'parse_date': lambda date_str, fmt='%Y-%m-%d': dt.datetime.strptime(date_str, fmt).isoformat(),

            # Enhanced time operations
            'add_days': lambda date_str, days: (dt.datetime.fromisoformat(date_str) + dt.timedelta(days=days)).isoformat(),
            'add_hours': lambda date_str, hours: (dt.datetime.fromisoformat(date_str) + dt.timedelta(hours=hours)).isoformat(),
            'add_minutes': lambda date_str, minutes: (dt.datetime.fromisoformat(date_str) + dt.timedelta(minutes=minutes)).isoformat(),
            'subtract_days': lambda date_str, days: (dt.datetime.fromisoformat(date_str) - dt.timedelta(days=days)).isoformat(),
            'days_between': lambda date1, date2: (dt.datetime.fromisoformat(date2) - dt.datetime.fromisoformat(date1)).days,

            # Timezone operations (basic UTC support)
            'to_utc': lambda date_str: dt.datetime.fromisoformat(date_str).replace(tzinfo=dt.timezone.utc).isoformat(),
            'from_timestamp': lambda ts: dt.datetime.fromtimestamp(ts).isoformat(),
            'to_timestamp': lambda date_str: int(dt.datetime.fromisoformat(date_str).timestamp()),

            # Calendar operations
            'weekday': lambda date_str: dt.datetime.fromisoformat(date_str).weekday(),  # 0=Monday, 6=Sunday
            'weekday_name': lambda date_str: cal.day_name[dt.datetime.fromisoformat(date_str).weekday()],
            'month_name': lambda date_str: cal.month_name[dt.datetime.fromisoformat(date_str).month],
            'is_weekend': lambda date_str: dt.datetime.fromisoformat(date_str).weekday() >= 5,
            'first_day_of_month': lambda date_str: dt.datetime.fromisoformat(date_str).replace(day=1).date().isoformat(),
            'last_day_of_month': lambda date_str: (dt.datetime.fromisoformat(date_str).replace(day=cal.monthrange(dt.datetime.fromisoformat(date_str).year, dt.datetime.fromisoformat(date_str).month)[1])).date().isoformat(),

            # Business logic helpers
            'age_in_years': lambda birth_date: (dt.date.today() - dt.date.fromisoformat(birth_date)).days // 365,
            'quarter': lambda date_str: (dt.datetime.fromisoformat(date_str).month - 1) // 3 + 1,
            'days_until': lambda target_date: (dt.date.fromisoformat(target_date) - dt.date.today()).days,
        }

        # JSON operations
        self.json_ops = {
            'loads': lambda data: json.loads(data),
            'dumps': lambda data: json.dumps(data, ensure_ascii=False, default=str),
            'dumps_pretty': lambda data: json.dumps(data, ensure_ascii=False, default=str, indent=2),
        }

        # Document processing helper functions
        self.doc_helpers = {
            'extract_text_from_word': self._extract_text_from_word,
            'extract_text_from_doc': self._extract_text_from_doc_file,
            'process_word_document': self._process_word_document
        }

    def _extract_text_from_word(self, file_data, file_type=None):
        """Extract text from Word documents (.doc or .docx)"""
        import io
        import base64

        # Decode base64 if needed
        if isinstance(file_data, str):
            file_data = base64.b64decode(file_data)

        # Try .docx first (most common)
        if file_type is None or 'docx' in file_type or 'wordprocessingml' in file_type:
            try:
                import docx
                doc = docx.Document(io.BytesIO(file_data))
                text = '\n'.join([para.text for para in doc.paragraphs])
                return text
            except Exception as e:
                if file_type and ('docx' in file_type or 'wordprocessingml' in file_type):
                    logger.warning(f"Failed to extract text from .docx: {e}")
                pass

        # Try alternative docx2txt method
        try:
            import docx2txt
            text = docx2txt.process(io.BytesIO(file_data))
            if text:
                return text
        except Exception:
            pass

        # Try .doc format (legacy)
        if file_type is None or 'msword' in file_type or file_type == 'application/msword':
            return self._extract_text_from_doc_file(file_data)

        return ''

    def _extract_text_from_doc_file(self, file_data):
        """Extract text from legacy .doc files"""
        import io
        import base64

        # Decode base64 if needed
        if isinstance(file_data, str):
            file_data = base64.b64decode(file_data)

        # Try using olefile to extract text
        try:
            import olefile
            ole = olefile.OleFileIO(io.BytesIO(file_data))

            # Try to find Word document stream
            if ole.exists('WordDocument'):
                # Extract text from Word document streams
                text_parts = []

                # Try to get the main text stream
                for stream in ole.listdir():
                    if stream[0].startswith('Word'):
                        try:
                            data = ole.openstream(stream).read()
                            # Simple text extraction - look for readable text
                            text = data.decode('utf-8', errors='ignore')
                            # Clean up the text
                            import re
                            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', ' ', text)
                            text = ' '.join(text.split())
                            if len(text) > 50:  # Only add if meaningful text
                                text_parts.append(text)
                        except Exception:
                            pass

                ole.close()
                return '\n'.join(text_parts)
        except Exception as e:
            logger.debug(f"Olefile processing failed: {e}")

        # Try striprtf as fallback (some .doc files are actually RTF)
        try:
            from striprtf import striprtf
            # Try to decode as RTF
            try:
                rtf_text = file_data.decode('utf-8', errors='ignore')
                if '{\\rtf' in rtf_text:
                    text = striprtf.rtf_to_text(rtf_text)
                    if text:
                        return text
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Striprtf processing failed: {e}")

        # Last resort - try to extract any readable text
        try:
            text = file_data.decode('utf-8', errors='ignore')
            # Clean up non-printable characters
            import re
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', ' ', text)
            text = ' '.join(text.split())
            if len(text) > 100:  # Only return if we got meaningful text
                return text
        except Exception:
            pass

        return ''

    def _process_word_document(self, file_data, file_type):
        """Process any Word document format and return text"""
        if file_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                         'application/msword',
                         'application/rtf',
                         'text/rtf']:
            return self._extract_text_from_word(file_data, file_type)
        return ''

    def _wrap_in_attrdict(self, obj):
        """Recursively wrap nested dicts in AttrDict for dot notation access"""
        if isinstance(obj, dict) and not isinstance(obj, AttrDict):
            return AttrDict({k: self._wrap_in_attrdict(v) for k, v in obj.items()})
        elif isinstance(obj, list):
            return [self._wrap_in_attrdict(item) for item in obj]
        else:
            return obj

    def _create_safe_namespace(self, context: Dict[str, Any], variable_manager: Any) -> Dict[str, Any]:
        """Create a safe execution namespace"""

        # Import allowed modules - but don't pre-import them
        # Let the script import them as needed for better compatibility
        safe_modules = {}

        # Custom import function that checks whitelist
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Check if module is allowed
            base_module = name.split('.')[0]
            if base_module in self.blocked_modules:
                raise ImportError(f"Import of module '{name}' is not allowed for security reasons")

            # Check against whitelist
            if base_module not in self.allowed_modules:
                # Check if it's a submodule of an allowed module
                allowed = False
                for allowed_mod in self.allowed_modules:
                    if name == allowed_mod or name.startswith(allowed_mod + '.'):
                        allowed = True
                        break
                if not allowed:
                    logger.warning(f"Import of module '{name}' is not in whitelist, allowing with warning")

            return __import__(name, globals, locals, fromlist, level)

        # Pre-import commonly used modules
        import urllib
        import urllib.parse
        import urllib.request
        import urllib.error
        import re
        import html
        import string as string_module
        import textwrap
        import csv
        import binascii
        import io
        import collections
        import itertools
        import functools
        import operator
        import difflib
        import unicodedata
        import decimal
        import fractions
        import email
        import email.utils
        import math
        import statistics
        import random
        import heapq
        import bisect
        import uuid

        # Build namespace
        namespace = {
            '__builtins__': {
                # Safe built-in functions
                'abs': abs, 'all': all, 'any': any, 'bool': bool,
                'bytes': bytes, 'callable': callable, 'chr': chr,
                'dict': dict, 'dir': dir, 'enumerate': enumerate,
                'filter': filter, 'float': float, 'format': format,
                'getattr': getattr, 'hasattr': hasattr, 'hash': hash,
                'hex': hex, 'id': id, 'int': int, 'isinstance': isinstance,
                'issubclass': issubclass, 'iter': iter, 'len': len,
                'list': list, 'map': map, 'max': max, 'min': min,
                'next': next, 'object': object, 'ord': ord, 'pow': pow,
                'print': print, 'range': range, 'repr': repr,
                'reversed': reversed, 'round': round, 'set': set,
                'slice': slice, 'sorted': sorted, 'str': str,
                'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip,

                # Limited I/O
                'open': self._restricted_open,

                # Custom import
                '__import__': safe_import,

                # Constants
                'None': None, 'True': True, 'False': False,
                'NotImplemented': NotImplemented, 'Ellipsis': Ellipsis,

                # Exception classes
                'Exception': Exception,
                'ValueError': ValueError,
                'TypeError': TypeError,
                'KeyError': KeyError,
                'IndexError': IndexError,
                'AttributeError': AttributeError,
                'RuntimeError': RuntimeError,
                'StopIteration': StopIteration,
                'ImportError': ImportError,
                'NameError': NameError,
                'IOError': IOError,
                'OSError': OSError,
                'ZeroDivisionError': ZeroDivisionError,
                'SyntaxError': SyntaxError,
                'AssertionError': AssertionError,
                'NotImplementedError': NotImplementedError,
                'LookupError': LookupError,
                'UnicodeError': UnicodeError,
                'UnicodeDecodeError': UnicodeDecodeError,
                'UnicodeEncodeError': UnicodeEncodeError,
                'MemoryError': MemoryError,
                'OverflowError': OverflowError,
                'RecursionError': RecursionError,
                'SystemError': SystemError,
                'Warning': Warning,
                'DeprecationWarning': DeprecationWarning,
                'UserWarning': UserWarning,
                'FutureWarning': FutureWarning,
            },

            # Context variables - wrap in AttrDict for dot notation access
            'input': self._wrap_in_attrdict(context.get('input', {})),
            'input_data': self._wrap_in_attrdict(context.get('input', {})),  # Alias
            'node_outputs': self._wrap_in_attrdict(context.get('node_outputs', {})),
            'global_vars': self._wrap_in_attrdict(context.get('global_vars', {})),
            'loop': context.get('loop', {}),
            'loop_data': context.get('loop', {}),  # Alias
            # Most recent handled node failure (set on error branches), else None
            'error': self._wrap_in_attrdict(context['error']) if context.get('error') is not None else None,
            'output': {},  # Output dictionary
            'local': {},  # Local variables

            # Helper operations dictionaries
            'string': self.string_ops,
            'math': self.math_ops,
            'base64': self.base64_ops,
            'datetime': self.datetime_ops,
            'json': self.json_ops,
            'doc_helpers': self.doc_helpers,

            # Pre-import commonly used modules
            'json_module': json,
            'base64_module': base64,
            'hashlib': hashlib,
            'datetime_module': datetime,
            'timedelta': timedelta,
            'date': date,
            'time': time,
            'calendar': calendar,
            'uuid': uuid,
            'urllib': urllib,
            're': re,
            'html': html,
            'string_module': string_module,
            'textwrap': textwrap,
            'csv': csv,
            'binascii': binascii,
            'io': io,
            'collections': collections,
            'itertools': itertools,
            'functools': functools,
            'operator': operator,
            'difflib': difflib,
            'unicodedata': unicodedata,
            'decimal': decimal,
            'fractions': fractions,
            'email': email,
            'math_module': math,
            'statistics': statistics,
            'random': random,
            'heapq': heapq,
            'bisect': bisect,

            # Variable manager functions
            'set_global': lambda name, value: variable_manager.set_global(name, value) if variable_manager else None,
        }

        # Try to import and add optional modules
        try:
            from reportlab.pdfgen import canvas as reportlab_canvas
            from reportlab.lib import pagesizes as reportlab_pagesizes
            from reportlab.lib import styles as reportlab_styles
            from reportlab.lib import units as reportlab_units
            from reportlab.lib import colors as reportlab_colors
            from reportlab.lib import utils as reportlab_utils
            from reportlab.lib.utils import ImageReader
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

            namespace['reportlab'] = {
                'canvas': reportlab_canvas,
                'pagesizes': reportlab_pagesizes,
                'styles': reportlab_styles,
                'units': reportlab_units,
                'colors': reportlab_colors,
                'utils': reportlab_utils,
                'ImageReader': ImageReader,
                'SimpleDocTemplate': SimpleDocTemplate,
                'Paragraph': Paragraph,
                'Spacer': Spacer,
                'Table': Table,
                'TableStyle': TableStyle,
                'Image': Image,
                'PageBreak': PageBreak,
                'getSampleStyleSheet': getSampleStyleSheet,
                'ParagraphStyle': ParagraphStyle,
                'TA_CENTER': TA_CENTER,
                'TA_LEFT': TA_LEFT,
                'TA_RIGHT': TA_RIGHT,
                'TA_JUSTIFY': TA_JUSTIFY,
            }
        except ImportError:
            logger.debug("ReportLab not available")

        # Try to import pandas
        try:
            import pandas as pd
            import openpyxl
            namespace['pandas'] = pd
            namespace['pd'] = pd
            namespace['openpyxl'] = openpyxl
        except ImportError:
            logger.debug("Pandas/Openpyxl not available")

        # Try to import document processing modules
        try:
            import docx
            namespace['docx'] = docx
        except ImportError:
            logger.debug("python-docx not available")

        try:
            import docx2txt
            namespace['docx2txt'] = docx2txt
        except ImportError:
            logger.debug("docx2txt not available")

        try:
            import olefile
            namespace['olefile'] = olefile
        except ImportError:
            logger.debug("olefile not available")

        try:
            from striprtf import striprtf
            namespace['striprtf'] = striprtf
        except ImportError:
            logger.debug("striprtf not available")

        try:
            import pypdf
            namespace['pypdf'] = pypdf
        except ImportError:
            logger.debug("pypdf not available")

        try:
            import pptx
            namespace['pptx'] = pptx
        except ImportError:
            logger.debug("python-pptx not available")

        return namespace

    def _restricted_open(self, *args, **kwargs):
        """Restricted open function - only allow reading from /tmp"""
        raise IOError("File operations are not allowed in transform scripts")

    def execute(self, script: str, context: Dict[str, Any], variable_manager: Any) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Execute a transform script in a controlled environment

        Args:
            script: Python script to execute
            context: Execution context
            variable_manager: Variable manager instance

        Returns:
            Tuple of (output dict, print output)
        """
        self._start_time = time.time()
        self._iteration_count = 0

        try:
            # Replace 'global.' with 'global_vars.' since 'global' is a Python reserved keyword
            import re as _re
            script = _re.sub(r'\bglobal\.', 'global_vars.', script)

            # Create safe namespace
            namespace = self._create_safe_namespace(context, variable_manager)

            # Capture print output
            import io
            from contextlib import redirect_stdout
            print_buffer = io.StringIO()

            # Execute the script
            with redirect_stdout(print_buffer):
                # Use a timeout mechanism
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Script execution exceeded {self.MAX_EXECUTION_TIME} seconds")

                # Set timeout (Unix-like systems only)
                if hasattr(signal, 'SIGALRM'):
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(int(self.MAX_EXECUTION_TIME))

                try:
                    # Execute the script
                    exec(script, namespace, namespace)
                finally:
                    # Cancel timeout
                    if hasattr(signal, 'SIGALRM'):
                        signal.alarm(0)

            # Get output - check 'output' first, fall back to 'data' for convenience
            result = namespace.get('output', {})
            if not result and 'data' in namespace and isinstance(namespace['data'], dict):
                result = namespace['data']

            # Check output size
            output_str = str(result)
            if len(output_str) > self.MAX_OUTPUT_SIZE:
                raise ValueError(f"Output too large: {len(output_str)} bytes exceeds maximum of {self.MAX_OUTPUT_SIZE}")

            # Get print output
            print_output = print_buffer.getvalue()

            return result, print_output

        except TimeoutError as e:
            raise ValueError(f"Transform script execution timed out after {self.MAX_EXECUTION_TIME}s")
        except Exception as e:
            # Log the full traceback for debugging
            logger.error(f"Transform execution failed: {traceback.format_exc()}")

            # Return a user-friendly error
            error_msg = str(e)
            if "ImportError" in str(type(e).__name__):
                raise ValueError(f"Import error in transform script: {error_msg}")
            else:
                raise ValueError(f"Transform script execution failed: {error_msg}")


# Compatibility wrapper to use V2 in place of V1
class TransformExecutor(TransformExecutorV2):
    """Alias for compatibility"""
    pass