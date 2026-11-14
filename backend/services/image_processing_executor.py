"""
Image Processing Executor for handling various image manipulation and analysis operations
"""
import os
import base64
import json
import io
from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime

from services.service_executors import ServiceExecutor

logger = logging.getLogger(__name__)


class ImageProcessingExecutor(ServiceExecutor):
    """Universal image processing executor - handles image manipulation, OCR, QR/barcode reading, and more"""

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute image processing operation"""
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
                        'message': "Operation parameter is missing. Please specify the image operation type."
                    }

                logger.info(f"Using default operation from schema: {operation}")

            logger.info(f"Executing image operation: {operation}")

            # Route to appropriate handler based on operation
            if operation == 'resize':
                return await self._handle_resize(parameters)
            elif operation == 'crop':
                return await self._handle_crop(parameters)
            elif operation == 'rotate':
                return await self._handle_rotate(parameters)
            elif operation == 'convert_format':
                return await self._handle_convert(parameters)
            elif operation == 'reduce_resolution':
                return await self._handle_reduce_resolution(parameters)
            elif operation == 'append_images':
                return await self._handle_append_images(parameters)
            elif operation == 'overlay':
                return await self._handle_overlay(parameters)
            elif operation == 'read_qr_code':
                return await self._handle_read_qr_code(parameters)
            elif operation == 'read_barcode':
                return await self._handle_read_barcode(parameters)
            elif operation == 'ocr':
                return await self._handle_ocr(parameters)
            elif operation == 'get_info':
                return await self._handle_get_info(parameters)
            elif operation == 'thumbnail':
                return await self._handle_thumbnail(parameters)
            elif operation == 'flip':
                return await self._handle_flip(parameters)
            elif operation == 'adjust_brightness':
                return await self._handle_adjust_brightness(parameters)
            elif operation == 'adjust_contrast':
                return await self._handle_adjust_contrast(parameters)
            elif operation == 'grayscale':
                return await self._handle_grayscale(parameters)
            elif operation == 'blur':
                return await self._handle_blur(parameters)
            elif operation == 'sharpen':
                return await self._handle_sharpen(parameters)
            elif operation == 'watermark':
                return await self._handle_watermark(parameters)
            else:
                return {
                    'error': True,
                    'message': f"Unknown operation: {operation}"
                }

        except Exception as e:
            logger.error(f"Image operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"Image operation failed: {str(e)}"
            }

    def _extract_image_content(self, image_param: Any) -> bytes:
        """Extract image content from various input formats"""
        if isinstance(image_param, dict):
            # File object from upload
            if 'content' in image_param:
                content = image_param['content']
            elif 'data' in image_param:
                content = image_param['data']
            else:
                raise ValueError("Image object missing 'content' or 'data' field")
        else:
            content = image_param

        if isinstance(content, str):
            # Base64 encoded string
            return base64.b64decode(content)
        elif isinstance(content, bytes):
            return content
        else:
            raise ValueError(f"Invalid image content type: {type(content).__name__}")

    async def _handle_resize(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Resize an image to specified dimensions"""
        try:
            from PIL import Image

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            width = parameters.get('width')
            height = parameters.get('height')
            maintain_aspect = parameters.get('maintain_aspect_ratio', True)

            # Open image
            img = Image.open(io.BytesIO(image_content))
            original_width, original_height = img.size

            # Calculate new dimensions
            if maintain_aspect:
                if width and not height:
                    # Calculate height maintaining aspect ratio
                    aspect_ratio = original_height / original_width
                    height = int(width * aspect_ratio)
                elif height and not width:
                    # Calculate width maintaining aspect ratio
                    aspect_ratio = original_width / original_height
                    width = int(height * aspect_ratio)
                elif width and height:
                    # Use the dimension that results in the smaller image
                    width_ratio = width / original_width
                    height_ratio = height / original_height
                    if width_ratio < height_ratio:
                        height = int(original_height * width_ratio)
                    else:
                        width = int(original_width * height_ratio)

            if not width or not height:
                return {
                    'error': True,
                    'message': "Width and/or height must be specified"
                }

            # Resize image
            resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
            resized = img.resize((width, height), resample_filter)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            resized.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': width,
                'height': height,
                'original_width': original_width,
                'original_height': original_height,
                'size': len(output_content)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'Image processing requires Pillow library. Please install: pip install Pillow'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Resize operation failed: {str(e)}"
            }

    async def _handle_crop(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Crop an image to specified region"""
        try:
            from PIL import Image

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            left = parameters.get('left', 0)
            top = parameters.get('top', 0)
            right = parameters.get('right')
            bottom = parameters.get('bottom')

            # Open image
            img = Image.open(io.BytesIO(image_content))
            width, height = img.size

            # Handle alternative parameters (width/height instead of right/bottom)
            crop_width = parameters.get('width')
            crop_height = parameters.get('height')

            if crop_width and not right:
                right = left + crop_width
            if crop_height and not bottom:
                bottom = top + crop_height

            # Default to full image if bounds not specified
            if right is None:
                right = width
            if bottom is None:
                bottom = height

            # Validate bounds
            if right <= left or bottom <= top:
                return {
                    'error': True,
                    'message': "Invalid crop dimensions"
                }

            # Crop image
            cropped = img.crop((left, top, right, bottom))

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            cropped.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': right - left,
                'height': bottom - top,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Crop operation failed: {str(e)}"
            }

    async def _handle_rotate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Rotate an image by specified angle"""
        try:
            from PIL import Image

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            angle = parameters.get('angle', 0)
            expand = parameters.get('expand', True)
            fill_color = parameters.get('fill_color', 'white')

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Convert RGBA to RGB if needed for JPEG output
            if img.mode == 'RGBA' and parameters.get('output_format', '').upper() == 'JPEG':
                # Create a white background
                background = Image.new('RGB', img.size, fill_color)
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = background

            # Rotate image
            rotated = img.rotate(-angle, expand=expand, fillcolor=fill_color)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            rotated.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'angle': angle,
                'width': rotated.size[0],
                'height': rotated.size[1],
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Rotate operation failed: {str(e)}"
            }

    async def _handle_convert(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Convert image format"""
        try:
            from PIL import Image

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            output_format = parameters.get('output_format', 'PNG')
            quality = parameters.get('quality', 85)

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Convert RGBA to RGB if converting to JPEG
            if output_format.upper() in ['JPEG', 'JPG'] and img.mode == 'RGBA':
                rgb_img = Image.new('RGB', img.size, 'white')
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img

            # Save to bytes with new format
            output = io.BytesIO()
            save_kwargs = {'format': output_format}

            if output_format.upper() in ['JPEG', 'JPG']:
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True

            img.save(output, **save_kwargs)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': img.size[0],
                'height': img.size[1],
                'size': len(output_content),
                'original_format': img.format
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Format conversion failed: {str(e)}"
            }

    async def _handle_reduce_resolution(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce image resolution while maintaining aspect ratio"""
        try:
            from PIL import Image

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            max_width = parameters.get('max_width')
            max_height = parameters.get('max_height')
            quality = parameters.get('quality', 85)

            # Open image
            img = Image.open(io.BytesIO(image_content))
            original_width, original_height = img.size

            # Calculate new dimensions
            width, height = original_width, original_height

            if max_width and original_width > max_width:
                width = max_width
                height = int(original_height * (max_width / original_width))

            if max_height and height > max_height:
                height = max_height
                width = int(original_width * (max_height / original_height))

            # Only resize if dimensions changed
            if (width, height) != (original_width, original_height):
                resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                img = img.resize((width, height), resample_filter)

            # Save to bytes with compression
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'JPEG')

            save_kwargs = {'format': output_format}
            if output_format.upper() in ['JPEG', 'JPG']:
                # Convert RGBA to RGB for JPEG
                if img.mode == 'RGBA':
                    rgb_img = Image.new('RGB', img.size, 'white')
                    rgb_img.paste(img, mask=img.split()[3])
                    img = rgb_img
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True

            img.save(output, **save_kwargs)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': width,
                'height': height,
                'original_width': original_width,
                'original_height': original_height,
                'size': len(output_content),
                'original_size': len(image_content),
                'compression_ratio': f"{(1 - len(output_content) / len(image_content)) * 100:.1f}%"
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Resolution reduction failed: {str(e)}"
            }

    async def _handle_append_images(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Append multiple images horizontally or vertically"""
        try:
            from PIL import Image

            # Extract images
            images_param = parameters.get('images', [])
            if not images_param or not isinstance(images_param, list):
                return {
                    'error': True,
                    'message': "Images parameter must be a non-empty list"
                }

            direction = parameters.get('direction', 'horizontal')
            spacing = parameters.get('spacing', 0)
            background_color = parameters.get('background_color', 'white')
            resize_to_fit = parameters.get('resize_to_fit', False)

            # Open all images
            images = []
            for img_param in images_param:
                img_content = self._extract_image_content(img_param)
                images.append(Image.open(io.BytesIO(img_content)))

            if len(images) < 2:
                return {
                    'error': True,
                    'message': "At least 2 images are required for append operation"
                }

            # Calculate dimensions for the combined image
            if direction == 'horizontal':
                if resize_to_fit:
                    # Resize all images to the height of the smallest
                    min_height = min(img.height for img in images)
                    resized_images = []
                    for img in images:
                        if img.height != min_height:
                            new_width = int(img.width * (min_height / img.height))
                            resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                            resized_images.append(img.resize((new_width, min_height), resample_filter))
                        else:
                            resized_images.append(img)
                    images = resized_images

                total_width = sum(img.width for img in images) + spacing * (len(images) - 1)
                max_height = max(img.height for img in images)
                combined = Image.new('RGB', (total_width, max_height), background_color)

                # Paste images
                x_offset = 0
                for img in images:
                    y_offset = (max_height - img.height) // 2  # Center vertically
                    if img.mode == 'RGBA':
                        combined.paste(img, (x_offset, y_offset), img)
                    else:
                        combined.paste(img, (x_offset, y_offset))
                    x_offset += img.width + spacing

            else:  # vertical
                if resize_to_fit:
                    # Resize all images to the width of the smallest
                    min_width = min(img.width for img in images)
                    resized_images = []
                    for img in images:
                        if img.width != min_width:
                            new_height = int(img.height * (min_width / img.width))
                            resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                            resized_images.append(img.resize((min_width, new_height), resample_filter))
                        else:
                            resized_images.append(img)
                    images = resized_images

                max_width = max(img.width for img in images)
                total_height = sum(img.height for img in images) + spacing * (len(images) - 1)
                combined = Image.new('RGB', (max_width, total_height), background_color)

                # Paste images
                y_offset = 0
                for img in images:
                    x_offset = (max_width - img.width) // 2  # Center horizontally
                    if img.mode == 'RGBA':
                        combined.paste(img, (x_offset, y_offset), img)
                    else:
                        combined.paste(img, (x_offset, y_offset))
                    y_offset += img.height + spacing

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', 'PNG')
            combined.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': combined.width,
                'height': combined.height,
                'images_count': len(images),
                'direction': direction,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Image append operation failed: {str(e)}"
            }

    async def _handle_overlay(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Overlay one image on top of another"""
        try:
            from PIL import Image

            # Extract base and overlay images
            base_content = self._extract_image_content(parameters.get('base_image'))
            overlay_content = self._extract_image_content(parameters.get('overlay_image'))

            position_x = parameters.get('position_x', '0')
            position_y = parameters.get('position_y', '0')

            # Convert string numbers to integers if needed
            if isinstance(position_x, str) and position_x.isdigit():
                position_x = int(position_x)
            if isinstance(position_y, str) and position_y.isdigit():
                position_y = int(position_y)
            opacity = parameters.get('opacity', 1.0)
            resize_overlay = parameters.get('resize_overlay', False)
            overlay_width = parameters.get('overlay_width')
            overlay_height = parameters.get('overlay_height')

            # Open images
            base = Image.open(io.BytesIO(base_content))
            overlay = Image.open(io.BytesIO(overlay_content))

            # Convert to RGBA for transparency support
            if base.mode != 'RGBA':
                base = base.convert('RGBA')
            if overlay.mode != 'RGBA':
                overlay = overlay.convert('RGBA')

            # Resize overlay if requested
            if resize_overlay and (overlay_width or overlay_height):
                if overlay_width and not overlay_height:
                    # Calculate height maintaining aspect ratio
                    overlay_height = int(overlay.height * (overlay_width / overlay.width))
                elif overlay_height and not overlay_width:
                    # Calculate width maintaining aspect ratio
                    overlay_width = int(overlay.width * (overlay_height / overlay.height))

                if overlay_width and overlay_height:
                    resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                    overlay = overlay.resize((overlay_width, overlay_height), resample_filter)

            # Apply opacity to overlay
            if opacity < 1.0:
                overlay_with_alpha = overlay.copy()
                alpha = overlay_with_alpha.split()[3]
                alpha = alpha.point(lambda p: p * opacity)
                overlay_with_alpha.putalpha(alpha)
                overlay = overlay_with_alpha

            # Handle position keywords
            if isinstance(position_x, str):
                if position_x == 'center':
                    position_x = (base.width - overlay.width) // 2
                elif position_x == 'right':
                    position_x = base.width - overlay.width
                else:
                    position_x = 0

            if isinstance(position_y, str):
                if position_y == 'center':
                    position_y = (base.height - overlay.height) // 2
                elif position_y == 'bottom':
                    position_y = base.height - overlay.height
                else:
                    position_y = 0

            # Paste overlay onto base
            base.paste(overlay, (position_x, position_y), overlay)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', 'PNG')

            if output_format.upper() in ['JPEG', 'JPG']:
                # Convert RGBA to RGB for JPEG
                rgb_img = Image.new('RGB', base.size, 'white')
                rgb_img.paste(base, mask=base.split()[3])
                base = rgb_img

            base.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': base.width,
                'height': base.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Overlay operation failed: {str(e)}"
            }

    async def _handle_read_qr_code(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Read QR codes from an image using multiple detection methods"""
        try:
            from pyzbar import pyzbar
            from PIL import Image, ImageEnhance, ImageFilter
            import cv2
            import numpy as np
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))

            # Open with PIL for better format support
            pil_image = Image.open(io.BytesIO(image_content))

            # Convert to RGB if needed (handles RGBA, CMYK, etc.)
            if pil_image.mode not in ['RGB', 'L']:
                if pil_image.mode == 'RGBA':
                    # Handle transparency
                    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                    background.paste(pil_image, mask=pil_image.split()[3] if len(pil_image.split()) > 3 else None)
                    pil_image = background
                else:
                    pil_image = pil_image.convert('RGB')

            all_qr_codes = []
            found_data = set()  # To avoid duplicates

            # Method 1: Direct pyzbar detection (works for most cases)
            try:
                decoded = pyzbar.decode(pil_image, symbols=[pyzbar.ZBarSymbol.QRCODE, pyzbar.ZBarSymbol.CODE128,
                                                             pyzbar.ZBarSymbol.CODE39, pyzbar.ZBarSymbol.EAN13,
                                                             pyzbar.ZBarSymbol.EAN8, pyzbar.ZBarSymbol.UPCA])
                for obj in decoded:
                    data = obj.data.decode('utf-8')
                    if data not in found_data:
                        found_data.add(data)
                        all_qr_codes.append({
                            'data': data,
                            'type': str(obj.type),
                            'position': {
                                'left': obj.rect.left,
                                'top': obj.rect.top,
                                'width': obj.rect.width,
                                'height': obj.rect.height
                            },
                            'method': 'direct'
                        })
            except Exception as e:
                logger.debug(f"Direct pyzbar detection failed: {e}")

            # Method 1.5: Try with inverted image (white on black QR codes)
            if not all_qr_codes:
                try:
                    from PIL import ImageOps
                    # Invert the image colors
                    inverted = ImageOps.invert(pil_image.convert('RGB'))
                    decoded = pyzbar.decode(inverted)
                    for obj in decoded:
                        data = obj.data.decode('utf-8')
                        if data not in found_data:
                            found_data.add(data)
                            all_qr_codes.append({
                                'data': data,
                                'type': str(obj.type),
                                'position': {
                                    'left': obj.rect.left,
                                    'top': obj.rect.top,
                                    'width': obj.rect.width,
                                    'height': obj.rect.height
                                },
                                'method': 'inverted'
                            })
                except Exception as e:
                    logger.debug(f"Inverted image detection failed: {e}")

            # Method 2: Try with enhanced contrast
            if not all_qr_codes:
                try:
                    enhancer = ImageEnhance.Contrast(pil_image)
                    for factor in [1.5, 2.0, 2.5]:
                        enhanced = enhancer.enhance(factor)
                        decoded = pyzbar.decode(enhanced)
                        for obj in decoded:
                            data = obj.data.decode('utf-8')
                            if data not in found_data:
                                found_data.add(data)
                                all_qr_codes.append({
                                    'data': data,
                                    'type': str(obj.type),
                                    'position': {
                                        'left': obj.rect.left,
                                        'top': obj.rect.top,
                                        'width': obj.rect.width,
                                        'height': obj.rect.height
                                    },
                                    'method': f'contrast_{factor}'
                                })
                        if all_qr_codes:
                            break
                except Exception as e:
                    logger.debug(f"Contrast enhancement failed: {e}")

            # Method 3: Try with grayscale and resizing for better detection
            if not all_qr_codes:
                try:
                    gray_image = pil_image.convert('L')
                    decoded = pyzbar.decode(gray_image)
                    for obj in decoded:
                        data = obj.data.decode('utf-8')
                        if data not in found_data:
                            found_data.add(data)
                            all_qr_codes.append({
                                'data': data,
                                'type': str(obj.type),
                                'position': {
                                    'left': obj.rect.left,
                                    'top': obj.rect.top,
                                    'width': obj.rect.width,
                                    'height': obj.rect.height
                                },
                                'method': 'grayscale'
                            })

                    # If still no codes, try resizing the image (sometimes helps with small/large QR codes)
                    if not all_qr_codes:
                        # Try upscaling for small QR codes
                        width, height = pil_image.size
                        if width < 2000:  # If image is relatively small
                            upscaled = pil_image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
                            decoded = pyzbar.decode(upscaled)
                            for obj in decoded:
                                data = obj.data.decode('utf-8')
                                if data not in found_data:
                                    found_data.add(data)
                                    all_qr_codes.append({
                                        'data': data,
                                        'type': str(obj.type),
                                        'position': {
                                            'left': obj.rect.left // 2,
                                            'top': obj.rect.top // 2,
                                            'width': obj.rect.width // 2,
                                            'height': obj.rect.height // 2
                                        },
                                        'method': 'upscaled_2x'
                                    })

                        # Try downscaling for very large images
                        if not all_qr_codes and width > 3000:
                            downscaled = pil_image.resize((width // 2, height // 2), Image.Resampling.LANCZOS)
                            decoded = pyzbar.decode(downscaled)
                            for obj in decoded:
                                data = obj.data.decode('utf-8')
                                if data not in found_data:
                                    found_data.add(data)
                                    all_qr_codes.append({
                                        'data': data,
                                        'type': str(obj.type),
                                        'position': {
                                            'left': obj.rect.left * 2,
                                            'top': obj.rect.top * 2,
                                            'width': obj.rect.width * 2,
                                            'height': obj.rect.height * 2
                                        },
                                        'method': 'downscaled_2x'
                                    })
                except Exception as e:
                    logger.debug(f"Grayscale/resize detection failed: {e}")


            # Method 4: Try pyzxing (ZXing-based decoder, very robust)
            # Note: pyzxing requires Java and only works with certain image formats
            if not all_qr_codes:
                try:
                    from pyzxing import BarCodeReader
                    reader = BarCodeReader()

                    # Save image as PNG (pyzxing doesn't support all formats)
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                        # Convert to RGB if needed to ensure compatibility
                        save_img = pil_image.convert('RGB') if pil_image.mode != 'RGB' else pil_image
                        save_img.save(tmp_file.name, 'PNG')
                        tmp_path = tmp_file.name

                    try:
                        results = reader.decode(tmp_path)

                        if results:
                            # Handle both single result and list of results
                            results_list = results if isinstance(results, list) else [results]
                            for result in results_list:
                                if result and hasattr(result, 'parsed'):
                                    data = result.parsed
                                    if data and data not in found_data:
                                        found_data.add(data)
                                        all_qr_codes.append({
                                            'data': data,
                                            'type': getattr(result, 'format', 'QRCODE'),
                                            'position': {},
                                            'method': 'pyzxing'
                                        })
                    finally:
                        # Clean up temp file
                        import os
                        try:
                            os.unlink(tmp_path)
                        except:
                            pass
                except Exception as e:
                    # pyzxing may not be installed or Java may not be available
                    logger.debug(f"pyzxing detection skipped: {e}")

            # Method 5: Try specific regions of the image (common QR locations)
            if not all_qr_codes:
                try:
                    width, height = pil_image.size

                    # Define regions to check (common QR code locations on business cards)
                    regions = [
                        ('right_third', (width * 2 // 3, 0, width, height)),
                        ('right_half', (width // 2, 0, width, height)),
                        ('left_third', (0, 0, width // 3, height)),
                        ('bottom_right', (width // 2, height // 2, width, height)),
                        ('bottom_left', (0, height // 2, width // 2, height)),
                        ('top_right', (width // 2, 0, width, height // 2)),
                        ('top_left', (0, 0, width // 2, height // 2))
                    ]

                    for region_name, (x1, y1, x2, y2) in regions:
                        if x2 > x1 and y2 > y1:  # Valid region
                            region_img = pil_image.crop((x1, y1, x2, y2))

                            # Try direct detection on region
                            decoded = pyzbar.decode(region_img)
                            for obj in decoded:
                                data = obj.data.decode('utf-8')
                                if data not in found_data:
                                    found_data.add(data)
                                    all_qr_codes.append({
                                        'data': data,
                                        'type': str(obj.type),
                                        'position': {
                                            'left': obj.rect.left + x1,
                                            'top': obj.rect.top + y1,
                                            'width': obj.rect.width,
                                            'height': obj.rect.height
                                        },
                                        'method': f'region_{region_name}'
                                    })

                            # If found, no need to check other regions
                            if all_qr_codes:
                                break

                            # Try with enhancement on region
                            enhancer = ImageEnhance.Contrast(region_img)
                            enhanced_region = enhancer.enhance(2.0)
                            decoded = pyzbar.decode(enhanced_region)
                            for obj in decoded:
                                data = obj.data.decode('utf-8')
                                if data not in found_data:
                                    found_data.add(data)
                                    all_qr_codes.append({
                                        'data': data,
                                        'type': str(obj.type),
                                        'position': {
                                            'left': obj.rect.left + x1,
                                            'top': obj.rect.top + y1,
                                            'width': obj.rect.width,
                                            'height': obj.rect.height
                                        },
                                        'method': f'region_{region_name}_enhanced'
                                    })

                            if all_qr_codes:
                                break

                except Exception as e:
                    logger.debug(f"Region detection failed: {e}")

            # Method 6: Try CLAHE (Contrast Limited Adaptive Histogram Equalization)
            if not all_qr_codes:
                try:
                    img_array = np.array(pil_image.convert('L'))

                    # Apply CLAHE for better contrast
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                    enhanced = clahe.apply(img_array)

                    # Try detection on CLAHE enhanced image
                    decoded = pyzbar.decode(enhanced)
                    for obj in decoded:
                        data = obj.data.decode('utf-8')
                        if data not in found_data:
                            found_data.add(data)
                            all_qr_codes.append({
                                'data': data,
                                'type': str(obj.type),
                                'position': {
                                    'left': obj.rect.left,
                                    'top': obj.rect.top,
                                    'width': obj.rect.width,
                                    'height': obj.rect.height
                                },
                                'method': 'clahe_enhanced'
                            })

                    # Also try with dilated image to connect broken QR elements
                    if not all_qr_codes:
                        kernel = np.ones((3,3), np.uint8)
                        dilated = cv2.dilate(enhanced, kernel, iterations=1)
                        eroded = cv2.erode(dilated, kernel, iterations=1)

                        decoded = pyzbar.decode(eroded)
                        for obj in decoded:
                            data = obj.data.decode('utf-8')
                            if data not in found_data:
                                found_data.add(data)
                                all_qr_codes.append({
                                    'data': data,
                                    'type': str(obj.type),
                                    'position': {
                                        'left': obj.rect.left,
                                        'top': obj.rect.top,
                                        'width': obj.rect.width,
                                        'height': obj.rect.height
                                    },
                                    'method': 'morphological'
                                })
                except Exception as e:
                    logger.debug(f"CLAHE enhancement failed: {e}")

            # Method 7: Try rotation detection (QR might be at an angle)
            if not all_qr_codes:
                try:
                    # Try common rotation angles
                    for angle in [90, 180, 270]:
                        rotated = pil_image.rotate(angle, expand=True)
                        decoded = pyzbar.decode(rotated)
                        for obj in decoded:
                            data = obj.data.decode('utf-8')
                            if data not in found_data:
                                found_data.add(data)
                                all_qr_codes.append({
                                    'data': data,
                                    'type': str(obj.type),
                                    'position': {},  # Position would need adjustment for rotation
                                    'method': f'rotated_{angle}'
                                })
                        if all_qr_codes:
                            break
                except Exception as e:
                    logger.debug(f"Rotation detection failed: {e}")

            # Method 8: OpenCV QR detector (sometimes works when pyzbar doesn't)
            if not all_qr_codes:
                try:
                    # Convert to OpenCV format
                    img_array = np.array(pil_image)
                    if len(img_array.shape) == 3:
                        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    else:
                        img_cv = img_array

                    # Try OpenCV's QR detector
                    detector = cv2.QRCodeDetector()
                    data, bbox, _ = detector.detectAndDecode(img_cv)
                    if data:
                        if data not in found_data:
                            found_data.add(data)
                            position = {}
                            if bbox is not None:
                                bbox = bbox[0].tolist()
                                position = {
                                    'top_left': {'x': bbox[0][0], 'y': bbox[0][1]},
                                    'top_right': {'x': bbox[1][0], 'y': bbox[1][1]},
                                    'bottom_right': {'x': bbox[2][0], 'y': bbox[2][1]},
                                    'bottom_left': {'x': bbox[3][0], 'y': bbox[3][1]}
                                }
                            all_qr_codes.append({
                                'data': data,
                                'type': 'QRCODE',
                                'position': position,
                                'method': 'opencv'
                            })

                    # Also try with multiple QR detector (for multiple codes)
                    detector_multi = cv2.QRCodeDetectorAruco()
                    retval, decoded_info, points, _ = detector_multi.detectAndDecodeMulti(img_cv)
                    if retval and decoded_info:
                        for i, data in enumerate(decoded_info):
                            if data and data not in found_data:
                                found_data.add(data)
                                position = {}
                                if points is not None and i < len(points):
                                    pts = points[i][0].tolist()
                                    position = {
                                        'top_left': {'x': pts[0][0], 'y': pts[0][1]},
                                        'top_right': {'x': pts[1][0], 'y': pts[1][1]},
                                        'bottom_right': {'x': pts[2][0], 'y': pts[2][1]},
                                        'bottom_left': {'x': pts[3][0], 'y': pts[3][1]}
                                    }
                                all_qr_codes.append({
                                    'data': data,
                                    'type': 'QRCODE',
                                    'position': position,
                                    'method': 'opencv_multi'
                                })
                except Exception as e:
                    logger.debug(f"OpenCV detection failed: {e}")

            # Method 5: Try with image preprocessing if still no codes found
            if not all_qr_codes:
                try:
                    img_array = np.array(pil_image.convert('L'))

                    # List of preprocessing methods to try
                    preprocessed_images = [
                        ('binary_threshold', cv2.threshold(img_array, 127, 255, cv2.THRESH_BINARY)[1]),
                        ('otsu', cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
                        ('adaptive', cv2.adaptiveThreshold(img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2))
                    ]

                    for method_name, processed_img in preprocessed_images:
                        decoded = pyzbar.decode(processed_img)
                        for obj in decoded:
                            data = obj.data.decode('utf-8')
                            if data not in found_data:
                                found_data.add(data)
                                all_qr_codes.append({
                                    'data': data,
                                    'type': str(obj.type),
                                    'position': {
                                        'left': obj.rect.left,
                                        'top': obj.rect.top,
                                        'width': obj.rect.width,
                                        'height': obj.rect.height
                                    },
                                    'method': method_name
                                })
                        if all_qr_codes:
                            break
                except Exception as e:
                    logger.debug(f"Preprocessing detection failed: {e}")

            # Return results
            if all_qr_codes:
                return {
                    'success': True,
                    'qr_codes': all_qr_codes,
                    'message': f"Found {len(all_qr_codes)} QR/barcode(s)",
                    'count': len(all_qr_codes)
                }
            else:
                # Debug mode: Save the image for inspection when no QR found
                try:
                    import tempfile
                    import os
                    debug_path = '/tmp/qr_debug_' + str(os.getpid()) + '.png'
                    pil_image.save(debug_path)
                    logger.info(f"No QR found. Debug image saved to: {debug_path}")
                except:
                    pass

                return {
                    'success': True,
                    'qr_codes': [],
                    'message': 'No QR codes or barcodes found in the image',
                    'count': 0,
                    'debug_info': 'Image saved for debugging. Check backend logs.'
                }

        except ImportError as e:
            return {
                'error': True,
                'message': 'QR code reading requires opencv-python. Please install: pip install opencv-python pyzbar'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"QR code reading failed: {str(e)}"
            }

    async def _handle_read_barcode(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Read barcodes from an image"""
        try:
            from pyzbar import pyzbar
            from PIL import Image
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))

            # Open with PIL
            img = Image.open(io.BytesIO(image_content))

            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Decode barcodes
            decoded = pyzbar.decode(img)

            barcodes = []
            for obj in decoded:
                barcode_data = {
                    'data': obj.data.decode('utf-8'),
                    'type': obj.type,
                    'position': {
                        'left': obj.rect.left,
                        'top': obj.rect.top,
                        'width': obj.rect.width,
                        'height': obj.rect.height
                    }
                }

                # Add polygon points if available
                if obj.polygon:
                    barcode_data['polygon'] = [{'x': point.x, 'y': point.y} for point in obj.polygon]

                barcodes.append(barcode_data)

            return {
                'success': True,
                'barcodes': barcodes,
                'count': len(barcodes),
                'message': f"Found {len(barcodes)} barcode(s)" if barcodes else "No barcodes found"
            }

        except ImportError:
            return {
                'error': True,
                'message': 'Barcode reading requires pyzbar library. Please install: pip install pyzbar'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Barcode reading failed: {str(e)}"
            }

    async def _handle_ocr(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform OCR (Optical Character Recognition) on an image"""
        try:
            import pytesseract
            from PIL import Image
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            language = parameters.get('language', 'eng')

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Perform OCR
            text = pytesseract.image_to_string(img, lang=language)

            # Get detailed data if requested
            if parameters.get('detailed', False):
                data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)

                words = []
                n_boxes = len(data['text'])
                for i in range(n_boxes):
                    if data['text'][i].strip():
                        words.append({
                            'text': data['text'][i],
                            'confidence': data['conf'][i],
                            'position': {
                                'left': data['left'][i],
                                'top': data['top'][i],
                                'width': data['width'][i],
                                'height': data['height'][i]
                            }
                        })

                return {
                    'success': True,
                    'text': text.strip(),
                    'words': words,
                    'language': language
                }
            else:
                return {
                    'success': True,
                    'text': text.strip(),
                    'language': language
                }

        except ImportError:
            return {
                'error': True,
                'message': 'OCR requires pytesseract and tesseract-ocr. Please install: pip install pytesseract and install tesseract-ocr system package'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"OCR operation failed: {str(e)}"
            }

    async def _handle_get_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about an image"""
        try:
            from PIL import Image
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Get basic info
            info = {
                'success': True,
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': len(image_content),
                'has_transparency': img.mode in ('RGBA', 'LA', 'PA')
            }

            # Add image metadata if available
            if hasattr(img, 'info'):
                metadata = {}
                for key, value in img.info.items():
                    if isinstance(value, (str, int, float, bool)):
                        metadata[key] = value
                if metadata:
                    info['metadata'] = metadata

            # Get EXIF data for JPEG images
            if img.format == 'JPEG':
                try:
                    from PIL.ExifTags import TAGS
                    exifdata = img.getexif()
                    if exifdata:
                        exif = {}
                        for tag_id, value in exifdata.items():
                            tag = TAGS.get(tag_id, tag_id)
                            if isinstance(value, (str, int, float, bool)):
                                exif[tag] = value
                        if exif:
                            info['exif'] = exif
                except:
                    pass

            return info

        except Exception as e:
            return {
                'error': True,
                'message': f"Get info operation failed: {str(e)}"
            }

    async def _handle_thumbnail(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a thumbnail of an image"""
        try:
            from PIL import Image
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            max_size = parameters.get('max_size', 128)

            # Handle max_size as either single value or tuple
            if isinstance(max_size, int):
                max_size = (max_size, max_size)
            elif isinstance(max_size, list) and len(max_size) == 2:
                max_size = tuple(max_size)

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Create thumbnail
            img.thumbnail(max_size)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            img.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': img.width,
                'height': img.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Thumbnail operation failed: {str(e)}"
            }

    async def _handle_flip(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Flip an image horizontally or vertically"""
        try:
            from PIL import Image
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            direction = parameters.get('direction', 'horizontal')

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Flip image
            if direction == 'horizontal':
                flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif direction == 'vertical':
                flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
            else:
                return {
                    'error': True,
                    'message': "Direction must be 'horizontal' or 'vertical'"
                }

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            flipped.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'direction': direction,
                'width': flipped.width,
                'height': flipped.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Flip operation failed: {str(e)}"
            }

    async def _handle_adjust_brightness(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust image brightness"""
        try:
            from PIL import Image, ImageEnhance
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            factor = parameters.get('factor', 1.0)

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Adjust brightness
            enhancer = ImageEnhance.Brightness(img)
            enhanced = enhancer.enhance(factor)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            enhanced.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'brightness_factor': factor,
                'width': enhanced.width,
                'height': enhanced.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Brightness adjustment failed: {str(e)}"
            }

    async def _handle_adjust_contrast(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust image contrast"""
        try:
            from PIL import Image, ImageEnhance
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            factor = parameters.get('factor', 1.0)

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Adjust contrast
            enhancer = ImageEnhance.Contrast(img)
            enhanced = enhancer.enhance(factor)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            enhanced.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'contrast_factor': factor,
                'width': enhanced.width,
                'height': enhanced.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Contrast adjustment failed: {str(e)}"
            }

    async def _handle_grayscale(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Convert image to grayscale"""
        try:
            from PIL import Image
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Convert to grayscale
            grayscale = img.convert('L')

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            grayscale.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'width': grayscale.width,
                'height': grayscale.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Grayscale conversion failed: {str(e)}"
            }

    async def _handle_blur(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply blur effect to image"""
        try:
            from PIL import Image, ImageFilter
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            radius = parameters.get('radius', 2)
            blur_type = parameters.get('blur_type', 'gaussian')

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Apply blur
            if blur_type == 'gaussian':
                blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
            elif blur_type == 'box':
                blurred = img.filter(ImageFilter.BoxBlur(radius=radius))
            elif blur_type == 'simple':
                blurred = img.filter(ImageFilter.BLUR)
            else:
                return {
                    'error': True,
                    'message': "Blur type must be 'gaussian', 'box', or 'simple'"
                }

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            blurred.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'blur_type': blur_type,
                'radius': radius,
                'width': blurred.width,
                'height': blurred.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Blur operation failed: {str(e)}"
            }

    async def _handle_sharpen(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply sharpen effect to image"""
        try:
            from PIL import Image, ImageFilter
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Apply sharpen
            sharpened = img.filter(ImageFilter.SHARPEN)

            # Apply multiple times for stronger effect
            iterations = parameters.get('iterations', 1)
            for _ in range(iterations - 1):
                sharpened = sharpened.filter(ImageFilter.SHARPEN)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', img.format or 'PNG')
            sharpened.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'iterations': iterations,
                'width': sharpened.width,
                'height': sharpened.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Sharpen operation failed: {str(e)}"
            }

    async def _handle_watermark(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add text watermark to image"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io

            # Extract image content
            image_content = self._extract_image_content(parameters.get('image'))
            text = parameters.get('text', 'WATERMARK')
            position = parameters.get('position', 'bottom-right')
            opacity = parameters.get('opacity', 0.5)
            font_size = parameters.get('font_size', 30)
            color = parameters.get('color', 'white')

            # Open image
            img = Image.open(io.BytesIO(image_content))

            # Convert to RGBA for transparency
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Create a transparent overlay
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)

            # Try to use a better font, fallback to default if not available
            try:
                font = ImageFont.truetype("Arial.ttf", font_size)
            except:
                font = ImageFont.load_default()

            # Get text dimensions
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Calculate position
            margin = 10
            if position == 'top-left':
                x, y = margin, margin
            elif position == 'top-right':
                x, y = img.width - text_width - margin, margin
            elif position == 'bottom-left':
                x, y = margin, img.height - text_height - margin
            elif position == 'bottom-right':
                x, y = img.width - text_width - margin, img.height - text_height - margin
            elif position == 'center':
                x, y = (img.width - text_width) // 2, (img.height - text_height) // 2
            else:
                x, y = margin, img.height - text_height - margin

            # Draw text with transparency
            if isinstance(color, str):
                if color == 'white':
                    color = (255, 255, 255, int(255 * opacity))
                elif color == 'black':
                    color = (0, 0, 0, int(255 * opacity))
                else:
                    color = (255, 255, 255, int(255 * opacity))

            draw.text((x, y), text, font=font, fill=color)

            # Composite the watermark with the image
            watermarked = Image.alpha_composite(img, overlay)

            # Save to bytes
            output = io.BytesIO()
            output_format = parameters.get('output_format', 'PNG')

            if output_format.upper() in ['JPEG', 'JPG']:
                # Convert RGBA to RGB for JPEG
                rgb_img = Image.new('RGB', watermarked.size, 'white')
                rgb_img.paste(watermarked, mask=watermarked.split()[3])
                watermarked = rgb_img

            watermarked.save(output, format=output_format)
            output_content = output.getvalue()

            return {
                'success': True,
                'image': base64.b64encode(output_content).decode('utf-8'),
                'format': output_format,
                'watermark_text': text,
                'position': position,
                'width': watermarked.width,
                'height': watermarked.height,
                'size': len(output_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Watermark operation failed: {str(e)}"
            }