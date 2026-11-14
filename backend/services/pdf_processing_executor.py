"""
PDF Processing Executor for handling various PDF manipulation and creation operations
"""
import os
import base64
import json
import io
import tempfile
from typing import Dict, Any, Optional, List, Union
import logging
from datetime import datetime

from services.service_executors import ServiceExecutor

logger = logging.getLogger(__name__)


class PDFProcessingExecutor(ServiceExecutor):
    """Universal PDF processing executor - handles PDF manipulation, creation, encryption, and more"""

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute PDF processing operation"""
        try:
            # Get operation from parameters or from schema default
            operation = parameters.get('operation')

            # If operation is not provided, check schema for default
            if not operation:
                schema = self.service_config.get('parameter_schema', {})
                properties = schema.get('properties', {})
                operation_schema = properties.get('operation', {})
                operation = operation_schema.get('default')

                if not operation:
                    # If still no operation, this is an error
                    return {
                        'error': True,
                        'message': "Operation parameter is missing. Please specify the PDF operation type."
                    }

                logger.info(f"Using default operation from schema: {operation}")

            logger.info(f"Executing PDF operation: {operation}")

            # Route to appropriate handler based on operation
            if operation == 'merge_pdfs':
                return await self._handle_merge_pdfs(parameters)
            elif operation == 'split_pdf':
                return await self._handle_split_pdf(parameters)
            elif operation == 'rotate_pages':
                return await self._handle_rotate_pages(parameters)
            elif operation == 'extract_pages':
                return await self._handle_extract_pages(parameters)
            elif operation == 'encrypt_pdf':
                return await self._handle_encrypt_pdf(parameters)
            elif operation == 'decrypt_pdf':
                return await self._handle_decrypt_pdf(parameters)
            elif operation == 'get_pdf_info':
                return await self._handle_get_pdf_info(parameters)
            elif operation == 'extract_text':
                return await self._handle_extract_text(parameters)
            elif operation == 'add_watermark':
                return await self._handle_add_watermark(parameters)
            elif operation == 'compress_pdf':
                return await self._handle_compress_pdf(parameters)
            elif operation == 'create_pdf':
                return await self._handle_create_pdf(parameters)
            elif operation == 'html_to_pdf':
                return await self._handle_html_to_pdf(parameters)
            elif operation == 'text_to_pdf':
                return await self._handle_text_to_pdf(parameters)
            elif operation == 'images_to_pdf':
                return await self._handle_images_to_pdf(parameters)
            elif operation == 'extract_images':
                return await self._handle_extract_images(parameters)
            elif operation == 'extract_tables':
                return await self._handle_extract_tables(parameters)
            elif operation == 'ocr_pdf':
                return await self._handle_ocr_pdf(parameters)
            elif operation == 'sign_pdf':
                return await self._handle_sign_pdf(parameters)
            elif operation == 'fill_form':
                return await self._handle_fill_form(parameters)
            elif operation == 'add_annotations':
                return await self._handle_add_annotations(parameters)
            else:
                return {
                    'error': True,
                    'message': f"Unknown operation: {operation}"
                }

        except Exception as e:
            logger.error(f"PDF operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"PDF operation failed: {str(e)}"
            }

    def _extract_pdf_content(self, pdf_param: Any) -> bytes:
        """Extract PDF content from various input formats"""
        if isinstance(pdf_param, dict):
            # File object from upload
            if 'content' in pdf_param:
                content = pdf_param['content']
            elif 'data' in pdf_param:
                content = pdf_param['data']
            else:
                raise ValueError("PDF object missing 'content' or 'data' field")
        else:
            content = pdf_param

        if isinstance(content, str):
            # Base64 encoded string
            return base64.b64decode(content)
        elif isinstance(content, bytes):
            return content
        else:
            raise ValueError(f"Invalid PDF content type: {type(content).__name__}")

    async def _handle_merge_pdfs(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple PDF files into one"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDFs
            pdfs_param = parameters.get('pdfs', [])
            if not pdfs_param or not isinstance(pdfs_param, list):
                return {
                    'error': True,
                    'message': "PDFs parameter must be a non-empty list"
                }

            writer = PdfWriter()

            # Process each PDF
            for i, pdf_param in enumerate(pdfs_param):
                try:
                    pdf_content = self._extract_pdf_content(pdf_param)
                    reader = PdfReader(io.BytesIO(pdf_content))

                    # Add all pages from this PDF
                    for page in reader.pages:
                        writer.add_page(page)

                    # Merge metadata
                    if i == 0 and reader.metadata:
                        writer.add_metadata(reader.metadata)

                except Exception as e:
                    logger.error(f"Failed to process PDF {i+1}: {str(e)}")
                    return {
                        'error': True,
                        'message': f"Failed to process PDF {i+1}: {str(e)}"
                    }

            # Save merged PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'page_count': len(writer.pages),
                'pdf_count': len(pdfs_param),
                'size': len(output_content)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'PDF merging requires pypdf library. Please install: pip install pypdf'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Merge operation failed: {str(e)}"
            }

    async def _handle_split_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Split a PDF into multiple files"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            split_mode = parameters.get('split_mode', 'pages')  # 'pages', 'range', 'chunks'

            reader = PdfReader(io.BytesIO(pdf_content))
            total_pages = len(reader.pages)

            split_pdfs = []

            if split_mode == 'pages':
                # Split into individual pages
                for i, page in enumerate(reader.pages):
                    writer = PdfWriter()
                    writer.add_page(page)

                    output = io.BytesIO()
                    writer.write(output)
                    split_pdfs.append({
                        'pdf': base64.b64encode(output.getvalue()).decode('utf-8'),
                        'page_number': i + 1,
                        'total_pages': 1
                    })

            elif split_mode == 'range':
                # Split by page ranges
                ranges = parameters.get('ranges', [])
                if not ranges:
                    return {
                        'error': True,
                        'message': "Ranges parameter is required for range split mode"
                    }

                for range_spec in ranges:
                    writer = PdfWriter()
                    start = range_spec.get('start', 1) - 1  # Convert to 0-based
                    end = range_spec.get('end', total_pages)

                    for i in range(max(0, start), min(end, total_pages)):
                        writer.add_page(reader.pages[i])

                    if len(writer.pages) > 0:
                        output = io.BytesIO()
                        writer.write(output)
                        split_pdfs.append({
                            'pdf': base64.b64encode(output.getvalue()).decode('utf-8'),
                            'page_range': f"{start+1}-{min(end, total_pages)}",
                            'total_pages': len(writer.pages)
                        })

            elif split_mode == 'chunks':
                # Split into chunks of specified size
                chunk_size = parameters.get('chunk_size', 1)
                for i in range(0, total_pages, chunk_size):
                    writer = PdfWriter()
                    for j in range(i, min(i + chunk_size, total_pages)):
                        writer.add_page(reader.pages[j])

                    output = io.BytesIO()
                    writer.write(output)
                    split_pdfs.append({
                        'pdf': base64.b64encode(output.getvalue()).decode('utf-8'),
                        'chunk_number': (i // chunk_size) + 1,
                        'page_range': f"{i+1}-{min(i+chunk_size, total_pages)}",
                        'total_pages': len(writer.pages)
                    })

            return {
                'success': True,
                'pdfs': split_pdfs,
                'total_files': len(split_pdfs),
                'original_pages': total_pages,
                'split_mode': split_mode
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Split operation failed: {str(e)}"
            }

    async def _handle_rotate_pages(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Rotate specific pages in a PDF"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            angle = parameters.get('angle', 90)  # Rotation angle (90, 180, 270)
            pages = parameters.get('pages', 'all')  # 'all' or list of page numbers

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Normalize angle
            angle = angle % 360
            if angle not in [90, 180, 270]:
                return {
                    'error': True,
                    'message': "Rotation angle must be 90, 180, or 270 degrees"
                }

            # Process pages
            for i, page in enumerate(reader.pages):
                page_num = i + 1

                # Check if this page should be rotated
                if pages == 'all' or (isinstance(pages, list) and page_num in pages):
                    page.rotate(angle)

                writer.add_page(page)

            # Preserve metadata
            if reader.metadata:
                writer.add_metadata(reader.metadata)

            # Save rotated PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'angle': angle,
                'pages_rotated': pages,
                'total_pages': len(writer.pages),
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Rotate operation failed: {str(e)}"
            }

    async def _handle_extract_pages(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific pages from a PDF"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            pages = parameters.get('pages', [])  # List of page numbers to extract

            if not pages:
                return {
                    'error': True,
                    'message': "Pages parameter is required"
                }

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Extract specified pages
            extracted_pages = []
            for page_num in pages:
                if 1 <= page_num <= len(reader.pages):
                    writer.add_page(reader.pages[page_num - 1])
                    extracted_pages.append(page_num)

            if not extracted_pages:
                return {
                    'error': True,
                    'message': "No valid pages found to extract"
                }

            # Save extracted PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'pages_extracted': extracted_pages,
                'total_pages': len(extracted_pages),
                'original_pages': len(reader.pages),
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Extract pages operation failed: {str(e)}"
            }

    async def _handle_encrypt_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add password protection to a PDF"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            user_password = parameters.get('user_password', '')
            owner_password = parameters.get('owner_password', user_password)
            permissions = parameters.get('permissions', ['print', 'modify', 'copy', 'annotate'])

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Copy all pages
            for page in reader.pages:
                writer.add_page(page)

            # Preserve metadata
            if reader.metadata:
                writer.add_metadata(reader.metadata)

            # Set encryption
            permissions_flags = []
            if 'print' in permissions:
                permissions_flags.append('print')
            if 'modify' in permissions:
                permissions_flags.append('modify')
            if 'copy' in permissions:
                permissions_flags.append('copy')
            if 'annotate' in permissions:
                permissions_flags.append('annotate')

            writer.encrypt(
                user_password=user_password,
                owner_password=owner_password,
                permissions_flag=-1 if len(permissions_flags) == 4 else sum([
                    4 if 'print' in permissions_flags else 0,
                    8 if 'modify' in permissions_flags else 0,
                    16 if 'copy' in permissions_flags else 0,
                    32 if 'annotate' in permissions_flags else 0
                ])
            )

            # Save encrypted PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'encrypted': True,
                'permissions': permissions,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Encrypt operation failed: {str(e)}"
            }

    async def _handle_decrypt_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Remove password protection from a PDF"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            password = parameters.get('password', '')

            reader = PdfReader(io.BytesIO(pdf_content))

            # Check if PDF is encrypted
            if reader.is_encrypted:
                # Try to decrypt
                if not reader.decrypt(password):
                    return {
                        'error': True,
                        'message': "Failed to decrypt PDF. Invalid password."
                    }
            else:
                return {
                    'error': False,
                    'message': "PDF is not encrypted",
                    'pdf': parameters.get('pdf')
                }

            writer = PdfWriter()

            # Copy all pages without encryption
            for page in reader.pages:
                writer.add_page(page)

            # Preserve metadata
            if reader.metadata:
                writer.add_metadata(reader.metadata)

            # Save decrypted PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'decrypted': True,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Decrypt operation failed: {str(e)}"
            }

    async def _handle_get_pdf_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get metadata and information about a PDF"""
        try:
            from pypdf import PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))

            reader = PdfReader(io.BytesIO(pdf_content))

            # Extract metadata
            metadata = {}
            if reader.metadata:
                for key, value in reader.metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        metadata[key] = value
                    else:
                        metadata[key] = str(value)

            # Get page information
            pages_info = []
            for i, page in enumerate(reader.pages):
                page_info = {
                    'page_number': i + 1,
                    'width': float(page.mediabox.width),
                    'height': float(page.mediabox.height),
                    'rotation': page.rotation if hasattr(page, 'rotation') else 0
                }
                pages_info.append(page_info)

            return {
                'success': True,
                'page_count': len(reader.pages),
                'metadata': metadata,
                'encrypted': reader.is_encrypted,
                'pages': pages_info[:10],  # Return first 10 pages info to avoid huge response
                'file_size': len(pdf_content),
                'pdf_version': reader.pdf_header if hasattr(reader, 'pdf_header') else 'Unknown'
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Get info operation failed: {str(e)}"
            }

    async def _handle_extract_text(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from a PDF"""
        try:
            # Try PyMuPDF first for better text extraction
            try:
                import fitz  # PyMuPDF
                HAS_PYMUPDF = True
            except ImportError:
                HAS_PYMUPDF = False

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            pages = parameters.get('pages', 'all')  # 'all' or list of page numbers

            if HAS_PYMUPDF:
                # Use PyMuPDF for better text extraction
                doc = fitz.open(stream=pdf_content, filetype="pdf")

                extracted_text = []
                for i, page in enumerate(doc):
                    page_num = i + 1
                    if pages == 'all' or (isinstance(pages, list) and page_num in pages):
                        text = page.get_text()
                        extracted_text.append({
                            'page': page_num,
                            'text': text
                        })

                doc.close()
            else:
                # Fallback to pypdf
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(pdf_content))
                extracted_text = []

                for i, page in enumerate(reader.pages):
                    page_num = i + 1
                    if pages == 'all' or (isinstance(pages, list) and page_num in pages):
                        text = page.extract_text()
                        extracted_text.append({
                            'page': page_num,
                            'text': text
                        })

            # Combine all text if requested
            combined_text = "\n\n".join([f"Page {item['page']}:\n{item['text']}" for item in extracted_text])

            return {
                'success': True,
                'text': combined_text,
                'pages': extracted_text,
                'page_count': len(extracted_text),
                'extraction_method': 'PyMuPDF' if HAS_PYMUPDF else 'pypdf'
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Extract text operation failed: {str(e)}"
            }

    async def _handle_add_watermark(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add a watermark to a PDF"""
        try:
            from pypdf import PdfWriter, PdfReader
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.colors import HexColor
            import io

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            watermark_text = parameters.get('text', 'WATERMARK')
            position = parameters.get('position', 'center')  # center, diagonal
            opacity = parameters.get('opacity', 0.3)
            font_size = parameters.get('font_size', 50)
            color = parameters.get('color', '#808080')

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Create watermark PDF
            watermark_buffer = io.BytesIO()
            c = canvas.Canvas(watermark_buffer, pagesize=letter)

            # Set transparency
            c.saveState()
            c.setFillColor(HexColor(color), alpha=opacity)
            c.setFont("Helvetica", font_size)

            # Get page dimensions (use first page as reference)
            if len(reader.pages) > 0:
                first_page = reader.pages[0]
                width = float(first_page.mediabox.width)
                height = float(first_page.mediabox.height)
            else:
                width, height = letter

            if position == 'diagonal':
                # Diagonal watermark
                c.translate(width/2, height/2)
                c.rotate(45)
                c.drawCentredString(0, 0, watermark_text)
            else:  # center
                c.drawCentredString(width/2, height/2, watermark_text)

            c.restoreState()
            c.save()

            # Read watermark PDF
            watermark_buffer.seek(0)
            watermark_reader = PdfReader(watermark_buffer)
            watermark_page = watermark_reader.pages[0]

            # Apply watermark to each page
            for page in reader.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)

            # Preserve metadata
            if reader.metadata:
                writer.add_metadata(reader.metadata)

            # Save watermarked PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'watermark_text': watermark_text,
                'position': position,
                'pages_watermarked': len(writer.pages),
                'size': len(output_content)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'Watermarking requires reportlab library. Please install: pip install reportlab'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Watermark operation failed: {str(e)}"
            }

    async def _handle_compress_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Compress a PDF to reduce file size"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            compression_level = parameters.get('compression_level', 'medium')  # low, medium, high

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Copy pages to writer first
            for page in reader.pages:
                writer.add_page(page)

            # Now compress the pages in the writer
            for page in writer.pages:
                page.compress_content_streams()

            # Remove unnecessary elements based on compression level
            if compression_level in ['medium', 'high']:
                writer.compress_identical_objects(remove_use_as_template=True)

            # Preserve essential metadata only
            if reader.metadata and compression_level != 'high':
                writer.add_metadata(reader.metadata)

            # Save compressed PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            original_size = len(pdf_content)
            compressed_size = len(output_content)
            compression_ratio = (1 - compressed_size / original_size) * 100

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': f"{compression_ratio:.1f}%",
                'compression_level': compression_level
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Compress operation failed: {str(e)}"
            }

    async def _handle_create_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new PDF from scratch"""
        try:
            from reportlab.lib.pagesizes import letter, A4, A3, legal
            from reportlab.pdfgen import canvas
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            import io

            # Get parameters
            page_size = parameters.get('page_size', 'letter')
            title = parameters.get('title', '')
            author = parameters.get('author', '')
            subject = parameters.get('subject', '')
            content = parameters.get('content', [])  # List of content items

            # Map page sizes
            page_sizes = {
                'letter': letter,
                'a4': A4,
                'a3': A3,
                'legal': legal
            }
            size = page_sizes.get(page_size.lower(), letter)

            # Create PDF
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=size)

            # Set metadata
            if title:
                c.setTitle(title)
            if author:
                c.setAuthor(author)
            if subject:
                c.setSubject(subject)

            # Process content
            width, height = size
            y_position = height - inch

            for item in content:
                item_type = item.get('type', 'text')

                if item_type == 'text':
                    text = item.get('text', '')
                    font = item.get('font', 'Helvetica')
                    font_size = item.get('font_size', 12)
                    x = item.get('x', inch)
                    y = item.get('y', y_position)

                    c.setFont(font, font_size)
                    c.drawString(x, y, text)
                    y_position -= font_size + 6

                elif item_type == 'paragraph':
                    from reportlab.platypus import SimpleDocTemplate, Paragraph
                    from reportlab.lib.styles import getSampleStyleSheet

                    # For complex paragraphs, we'd need to use Platypus
                    text = item.get('text', '')
                    font_size = item.get('font_size', 12)

                    # Simple paragraph handling
                    lines = text.split('\n')
                    c.setFont('Helvetica', font_size)
                    for line in lines:
                        if y_position < inch:
                            c.showPage()
                            y_position = height - inch
                        c.drawString(inch, y_position, line)
                        y_position -= font_size + 4

                elif item_type == 'page_break':
                    c.showPage()
                    y_position = height - inch

            c.save()

            # Get PDF content
            buffer.seek(0)
            output_content = buffer.read()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'page_size': page_size,
                'content_items': len(content),
                'size': len(output_content)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'PDF creation requires reportlab library. Please install: pip install reportlab'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Create PDF operation failed: {str(e)}"
            }

    async def _handle_html_to_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Convert HTML to PDF"""
        try:
            # Try pdfkit first (requires wkhtmltopdf)
            try:
                import pdfkit
                HAS_PDFKIT = True
            except ImportError:
                HAS_PDFKIT = False

            html_content = parameters.get('html', '')
            if not html_content:
                return {
                    'error': True,
                    'message': "HTML content is required"
                }

            if HAS_PDFKIT:
                try:
                    # Convert HTML to PDF using pdfkit
                    options = {
                        'page-size': parameters.get('page_size', 'A4'),
                        'margin-top': parameters.get('margin_top', '0.75in'),
                        'margin-right': parameters.get('margin_right', '0.75in'),
                        'margin-bottom': parameters.get('margin_bottom', '0.75in'),
                        'margin-left': parameters.get('margin_left', '0.75in'),
                        'encoding': "UTF-8",
                        'no-outline': None
                    }

                    pdf_content = pdfkit.from_string(html_content, False, options=options)

                    return {
                        'success': True,
                        'pdf': base64.b64encode(pdf_content).decode('utf-8'),
                        'method': 'pdfkit',
                        'size': len(pdf_content)
                    }
                except Exception as e:
                    logger.warning(f"pdfkit failed: {e}, falling back to reportlab")
                    HAS_PDFKIT = False

            if not HAS_PDFKIT:
                # Fallback to reportlab with basic HTML support
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.pdfgen import canvas
                from html.parser import HTMLParser
                import io

                # Simple HTML parser for basic conversion
                class SimpleHTMLParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text_content = []
                        self.current_text = ""

                    def handle_data(self, data):
                        self.current_text += data

                    def handle_starttag(self, tag, attrs):
                        if tag in ['p', 'div', 'br', 'h1', 'h2', 'h3']:
                            if self.current_text.strip():
                                self.text_content.append(self.current_text.strip())
                            self.current_text = ""

                    def handle_endtag(self, tag):
                        if tag in ['p', 'div', 'h1', 'h2', 'h3']:
                            if self.current_text.strip():
                                self.text_content.append(self.current_text.strip())
                            self.current_text = ""

                # Parse HTML
                parser = SimpleHTMLParser()
                parser.feed(html_content)
                if parser.current_text.strip():
                    parser.text_content.append(parser.current_text.strip())

                # Create PDF with parsed content
                buffer = io.BytesIO()
                page_size = A4 if parameters.get('page_size', 'A4').upper() == 'A4' else letter
                c = canvas.Canvas(buffer, pagesize=page_size)

                width, height = page_size
                y_position = height - 72  # 1 inch margin

                c.setFont("Helvetica", 12)
                for line in parser.text_content:
                    if y_position < 72:  # New page if near bottom
                        c.showPage()
                        c.setFont("Helvetica", 12)
                        y_position = height - 72

                    # Wrap long lines
                    max_width = width - 144  # 2 inch total margin
                    if len(line) * 7 > max_width:  # Rough estimate
                        words = line.split()
                        current_line = ""
                        for word in words:
                            test_line = current_line + " " + word if current_line else word
                            if len(test_line) * 7 <= max_width:
                                current_line = test_line
                            else:
                                if current_line:
                                    c.drawString(72, y_position, current_line)
                                    y_position -= 18
                                    if y_position < 72:
                                        c.showPage()
                                        c.setFont("Helvetica", 12)
                                        y_position = height - 72
                                current_line = word
                        if current_line:
                            c.drawString(72, y_position, current_line)
                            y_position -= 18
                    else:
                        c.drawString(72, y_position, line)
                        y_position -= 18

                c.save()
                buffer.seek(0)
                pdf_content = buffer.read()

                return {
                    'success': True,
                    'pdf': base64.b64encode(pdf_content).decode('utf-8'),
                    'method': 'reportlab',
                    'size': len(pdf_content)
                }

        except Exception as e:
            return {
                'error': True,
                'message': f"HTML to PDF conversion failed: {str(e)}"
            }

    async def _handle_text_to_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Convert plain text to PDF"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
            import io

            # Get parameters
            text = parameters.get('text', '')
            page_size = parameters.get('page_size', 'letter')
            font = parameters.get('font', 'Helvetica')
            font_size = parameters.get('font_size', 12)
            line_spacing = parameters.get('line_spacing', 1.2)

            if not text:
                return {
                    'error': True,
                    'message': "Text content is required"
                }

            # Map page sizes
            page_sizes = {
                'letter': letter,
                'a4': A4
            }
            size = page_sizes.get(page_size.lower(), letter)

            # Create PDF
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=size)

            width, height = size
            margin = inch
            y_position = height - margin
            line_height = font_size * line_spacing

            # Process text
            lines = text.split('\n')
            c.setFont(font, font_size)

            for line in lines:
                # Check if we need a new page
                if y_position < margin:
                    c.showPage()
                    c.setFont(font, font_size)
                    y_position = height - margin

                # Handle line wrapping
                max_width = width - (2 * margin)
                char_width = font_size * 0.6  # Approximate character width
                max_chars = int(max_width / char_width)

                if len(line) > max_chars:
                    # Wrap long lines
                    words = line.split()
                    current_line = ""

                    for word in words:
                        test_line = current_line + " " + word if current_line else word
                        if len(test_line) <= max_chars:
                            current_line = test_line
                        else:
                            if current_line:
                                c.drawString(margin, y_position, current_line)
                                y_position -= line_height
                                if y_position < margin:
                                    c.showPage()
                                    c.setFont(font, font_size)
                                    y_position = height - margin
                            current_line = word

                    if current_line:
                        c.drawString(margin, y_position, current_line)
                        y_position -= line_height
                else:
                    c.drawString(margin, y_position, line)
                    y_position -= line_height

            c.save()
            buffer.seek(0)
            output_content = buffer.read()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'page_size': page_size,
                'font': font,
                'font_size': font_size,
                'line_count': len(lines),
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Text to PDF conversion failed: {str(e)}"
            }

    async def _handle_images_to_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Convert images to PDF"""
        try:
            from PIL import Image
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.utils import ImageReader
            import io

            # Extract images
            images_param = parameters.get('images', [])
            if not images_param or not isinstance(images_param, list):
                return {
                    'error': True,
                    'message': "Images parameter must be a non-empty list"
                }

            page_size = parameters.get('page_size', 'letter')
            fit_to_page = parameters.get('fit_to_page', True)

            # Map page sizes
            page_sizes = {
                'letter': letter,
                'a4': A4
            }
            size = page_sizes.get(page_size.lower(), letter)
            page_width, page_height = size

            # Create PDF
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=size)

            # Process each image
            for i, image_param in enumerate(images_param):
                try:
                    # Extract image content
                    if isinstance(image_param, dict):
                        if 'content' in image_param:
                            image_content = image_param['content']
                        elif 'data' in image_param:
                            image_content = image_param['data']
                        else:
                            raise ValueError("Image object missing 'content' or 'data' field")
                    else:
                        image_content = image_param

                    if isinstance(image_content, str):
                        image_bytes = base64.b64decode(image_content)
                    else:
                        image_bytes = image_content

                    # Open image with PIL
                    img = Image.open(io.BytesIO(image_bytes))
                    img_width, img_height = img.size

                    # Calculate dimensions to fit on page if requested
                    if fit_to_page:
                        # Leave margins
                        margin = 72  # 1 inch
                        max_width = page_width - (2 * margin)
                        max_height = page_height - (2 * margin)

                        # Calculate scale factor
                        width_scale = max_width / img_width
                        height_scale = max_height / img_height
                        scale = min(width_scale, height_scale, 1.0)  # Don't upscale

                        draw_width = img_width * scale
                        draw_height = img_height * scale

                        # Center on page
                        x = (page_width - draw_width) / 2
                        y = (page_height - draw_height) / 2
                    else:
                        # Use original dimensions
                        draw_width = img_width
                        draw_height = img_height
                        x = 0
                        y = 0

                    # Draw image on canvas
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='PNG')
                    img_buffer.seek(0)

                    c.drawImage(ImageReader(img_buffer), x, y, width=draw_width, height=draw_height)

                    # Add new page for next image (except for last image)
                    if i < len(images_param) - 1:
                        c.showPage()

                except Exception as e:
                    logger.error(f"Failed to process image {i+1}: {str(e)}")
                    return {
                        'error': True,
                        'message': f"Failed to process image {i+1}: {str(e)}"
                    }

            c.save()
            buffer.seek(0)
            output_content = buffer.read()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'image_count': len(images_param),
                'page_size': page_size,
                'fit_to_page': fit_to_page,
                'size': len(output_content)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'Images to PDF requires Pillow and reportlab. Please install: pip install Pillow reportlab'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Images to PDF conversion failed: {str(e)}"
            }

    def _extract_images_with_pypdf(self, pdf_content: bytes, pages: Any):
        """Extract embedded images with pypdf, returned as PNG in the same shape
        the PyMuPDF path produces. Returns (images, skipped) where skipped lists
        'page N image M: reason' for images pypdf/Pillow could not decode."""
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_content))
        images: List[Dict[str, Any]] = []
        skipped: List[str] = []
        for page_num, page in enumerate(reader.pages, 1):
            if not (pages == 'all' or (isinstance(pages, list) and page_num in pages)):
                continue
            try:
                page_images = list(page.images)
            except Exception as e:  # malformed resources on this page
                skipped.append(f"page {page_num}: {e}")
                continue
            for img_index, img_file in enumerate(page_images, 1):
                try:
                    pil_image = img_file.image
                    if pil_image is None:
                        raise ValueError("no decodable image data")
                    if pil_image.mode not in ('RGB', 'RGBA', 'L', 'LA'):
                        pil_image = pil_image.convert('RGBA' if 'A' in pil_image.mode else 'RGB')
                    buf = io.BytesIO()
                    pil_image.save(buf, format='PNG')
                    images.append({
                        'image': base64.b64encode(buf.getvalue()).decode('utf-8'),
                        'page': page_num,
                        'index': img_index,
                        'width': pil_image.width,
                        'height': pil_image.height
                    })
                except Exception as e:
                    skipped.append(f"page {page_num} image {img_index}: {e}")
        return images, skipped

    async def _handle_extract_images(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract images from a PDF"""
        try:
            # Try PyMuPDF for better image extraction
            try:
                import fitz  # PyMuPDF
                HAS_PYMUPDF = True
            except ImportError:
                HAS_PYMUPDF = False

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            pages = parameters.get('pages', 'all')

            extracted_images = []

            if HAS_PYMUPDF:
                # Use PyMuPDF for image extraction
                doc = fitz.open(stream=pdf_content, filetype="pdf")

                for page_num, page in enumerate(doc, 1):
                    if pages == 'all' or (isinstance(pages, list) and page_num in pages):
                        image_list = page.get_images(full=True)

                        for img_index, img in enumerate(image_list):
                            # Extract image
                            xref = img[0]
                            pix = fitz.Pixmap(doc, xref)

                            # Convert to PNG
                            if pix.n - pix.alpha < 4:  # GRAY or RGB
                                img_data = pix.tobytes("png")
                            else:  # CMYK
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                                img_data = pix.tobytes("png")

                            extracted_images.append({
                                'image': base64.b64encode(img_data).decode('utf-8'),
                                'page': page_num,
                                'index': img_index + 1,
                                'width': pix.width,
                                'height': pix.height
                            })
                            pix = None

                doc.close()
            else:
                # PyMuPDF is optional (AGPL-3.0); fall back to pypdf (BSD) + Pillow
                extracted_images, skipped = self._extract_images_with_pypdf(pdf_content, pages)
                if skipped:
                    logger.warning(f"extract_images (pypdf): skipped {len(skipped)} image(s) "
                                   f"that could not be decoded: {skipped[:5]}")

            return {
                'success': True,
                'images': extracted_images,
                'image_count': len(extracted_images),
                'extraction_method': 'PyMuPDF' if HAS_PYMUPDF else 'pypdf'
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Extract images operation failed: {str(e)}"
            }

    async def _handle_extract_tables(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tables from a PDF"""
        try:
            # Try pdfplumber for table extraction
            try:
                import pdfplumber
                HAS_PDFPLUMBER = True
            except ImportError:
                HAS_PDFPLUMBER = False

            if not HAS_PDFPLUMBER:
                return {
                    'error': True,
                    'message': 'Table extraction requires pdfplumber. Please install: pip install pdfplumber'
                }

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            pages = parameters.get('pages', 'all')

            extracted_tables = []

            # Use pdfplumber for table extraction
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if pages == 'all' or (isinstance(pages, list) and page_num in pages):
                        tables = page.extract_tables()

                        for table_index, table in enumerate(tables):
                            if table:
                                extracted_tables.append({
                                    'page': page_num,
                                    'table_index': table_index + 1,
                                    'data': table,
                                    'rows': len(table),
                                    'columns': len(table[0]) if table else 0
                                })

            return {
                'success': True,
                'tables': extracted_tables,
                'table_count': len(extracted_tables)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Extract tables operation failed: {str(e)}"
            }

    async def _handle_ocr_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform OCR on a scanned PDF"""
        try:
            try:
                import pytesseract
                from pdf2image import convert_from_bytes
                HAS_OCR = True
            except ImportError:
                HAS_OCR = False

            if not HAS_OCR:
                return {
                    'error': True,
                    'message': 'OCR requires pytesseract and pdf2image. Please install: pip install pytesseract pdf2image'
                }

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            language = parameters.get('language', 'eng')
            pages = parameters.get('pages', 'all')

            # Convert PDF to images
            images = convert_from_bytes(pdf_content)

            extracted_text = []
            for page_num, image in enumerate(images, 1):
                if pages == 'all' or (isinstance(pages, list) and page_num in pages):
                    # Perform OCR on the image
                    text = pytesseract.image_to_string(image, lang=language)
                    extracted_text.append({
                        'page': page_num,
                        'text': text
                    })

            # Combine all text
            combined_text = "\n\n".join([f"Page {item['page']}:\n{item['text']}" for item in extracted_text])

            return {
                'success': True,
                'text': combined_text,
                'pages': extracted_text,
                'page_count': len(extracted_text),
                'language': language
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"OCR operation failed: {str(e)}"
            }

    async def _handle_sign_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add a digital signature to a PDF (placeholder for future implementation)"""
        return {
            'error': True,
            'message': "Digital signature feature is not yet implemented. This requires cryptographic libraries and certificate management."
        }

    async def _handle_fill_form(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fill PDF form fields"""
        try:
            from pypdf import PdfWriter, PdfReader

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            form_data = parameters.get('form_data', {})

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Copy all pages
            for page in reader.pages:
                writer.add_page(page)

            # Fill form fields if they exist
            if reader.get_form_text_fields():
                writer.update_page_form_field_values(
                    writer.pages[0], form_data
                )
            else:
                return {
                    'error': True,
                    'message': "PDF does not contain fillable form fields"
                }

            # Save filled PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'fields_filled': list(form_data.keys()),
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Fill form operation failed: {str(e)}"
            }

    async def _handle_add_annotations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add annotations to a PDF"""
        try:
            from pypdf import PdfWriter, PdfReader
            from pypdf.annotations import Text, FreeText

            # Extract PDF content
            pdf_content = self._extract_pdf_content(parameters.get('pdf'))
            annotations = parameters.get('annotations', [])

            reader = PdfReader(io.BytesIO(pdf_content))
            writer = PdfWriter()

            # Process each page
            for page_num, page in enumerate(reader.pages, 1):
                # Add annotations for this page
                for annotation in annotations:
                    if annotation.get('page') == page_num:
                        ann_type = annotation.get('type', 'text')

                        if ann_type == 'text':
                            # Add text annotation (note)
                            text_ann = Text(
                                text=annotation.get('text', ''),
                                rect=(
                                    annotation.get('x', 100),
                                    annotation.get('y', 100),
                                    annotation.get('x', 100) + 20,
                                    annotation.get('y', 100) + 20
                                )
                            )
                            writer.add_annotation(page_number=page_num-1, annotation=text_ann)

                writer.add_page(page)

            # Save annotated PDF
            output = io.BytesIO()
            writer.write(output)
            output_content = output.getvalue()

            return {
                'success': True,
                'pdf': base64.b64encode(output_content).decode('utf-8'),
                'annotations_added': len(annotations),
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Add annotations operation failed: {str(e)}"
            }