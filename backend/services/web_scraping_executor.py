"""
Web Scraping Executor for handling various web scraping and data extraction operations
"""
import os
import re
import base64
import json
import asyncio
import random
import time
from typing import Dict, Any, Optional, List, Union
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from services.service_executors import ServiceExecutor

logger = logging.getLogger(__name__)


class WebScrapingExecutor(ServiceExecutor):
    """Universal web scraping executor - handles static and dynamic web scraping operations"""

    def __init__(self, service_config: Dict[str, Any], auth_credentials: Dict[str, Any] = None,
                 subscription_id: str = None, auth_config: Dict[str, Any] = None):
        super().__init__(service_config, auth_credentials, subscription_id, auth_config)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web scraping operation"""
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
                    return {
                        'error': True,
                        'message': "Operation parameter is missing. Please specify the web scraping operation type."
                    }

                logger.info(f"Using default operation from schema: {operation}")

            logger.info(f"Executing web scraping operation: {operation}")

            # Route to appropriate handler based on operation
            # Static content operations
            if operation == 'scrape_page':
                return await self._handle_scrape_page(parameters)
            elif operation == 'extract_text':
                return await self._handle_extract_text(parameters)
            elif operation == 'extract_links':
                return await self._handle_extract_links(parameters)
            elif operation == 'extract_images':
                return await self._handle_extract_images(parameters)
            elif operation == 'extract_metadata':
                return await self._handle_extract_metadata(parameters)
            elif operation == 'extract_tables':
                return await self._handle_extract_tables(parameters)
            elif operation == 'extract_by_selector':
                return await self._handle_extract_by_selector(parameters)
            elif operation == 'extract_by_xpath':
                return await self._handle_extract_by_xpath(parameters)
            elif operation == 'extract_structured_data':
                return await self._handle_extract_structured_data(parameters)
            # Dynamic content operations
            elif operation == 'scrape_dynamic':
                return await self._handle_scrape_dynamic(parameters)
            elif operation == 'screenshot_page':
                return await self._handle_screenshot_page(parameters)
            elif operation == 'fill_form':
                return await self._handle_fill_form(parameters)
            elif operation == 'click_and_extract':
                return await self._handle_click_and_extract(parameters)
            elif operation == 'scroll_and_load':
                return await self._handle_scroll_and_load(parameters)
            elif operation == 'wait_and_extract':
                return await self._handle_wait_and_extract(parameters)
            elif operation == 'multi_page_scrape':
                return await self._handle_multi_page_scrape(parameters)
            # Advanced features
            elif operation == 'scrape_with_auth':
                return await self._handle_scrape_with_auth(parameters)
            elif operation == 'download_files':
                return await self._handle_download_files(parameters)
            elif operation == 'monitor_changes':
                return await self._handle_monitor_changes(parameters)
            elif operation == 'sitemap_scrape':
                return await self._handle_sitemap_scrape(parameters)
            elif operation == 'api_discover':
                return await self._handle_api_discover(parameters)
            else:
                return {
                    'error': True,
                    'message': f"Unknown operation: {operation}"
                }

        except Exception as e:
            logger.error(f"Web scraping operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"Web scraping operation failed: {str(e)}"
            }

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        return random.choice(self.user_agents)

    async def _fetch_page(self, url: str, headers: Dict[str, str] = None,
                         cookies: Dict[str, str] = None, timeout: int = 30) -> tuple:
        """Fetch a webpage using httpx"""
        import httpx

        # Prepare headers
        default_headers = {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        if headers:
            default_headers.update(headers)

        # Add random delay to avoid rate limiting
        await asyncio.sleep(random.uniform(0.5, 2.0))

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=default_headers, cookies=cookies)
            response.raise_for_status()
            return response.text, response.status_code, dict(response.headers)

    async def _handle_scrape_page(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape a webpage and return its HTML content"""
        try:
            url = parameters.get('url')
            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            headers = parameters.get('headers', {})
            cookies = parameters.get('cookies', {})
            timeout = parameters.get('timeout', 30)

            # Fetch the page
            html_content, status_code, response_headers = await self._fetch_page(
                url, headers, cookies, timeout
            )

            return {
                'success': True,
                'url': url,
                'html': html_content,
                'status_code': status_code,
                'headers': response_headers,
                'content_length': len(html_content)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Failed to scrape page: {str(e)}"
            }

    async def _handle_extract_text(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all text content from a webpage"""
        try:
            from bs4 import BeautifulSoup

            url = parameters.get('url')
            html_content = parameters.get('html')

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            # Extract specific elements if requested
            include_headers = parameters.get('include_headers', True)
            include_paragraphs = parameters.get('include_paragraphs', True)
            include_lists = parameters.get('include_lists', True)

            structured_text = {}

            if include_headers:
                headers = {}
                for i in range(1, 7):
                    headers[f'h{i}'] = [tag.get_text().strip() for tag in soup.find_all(f'h{i}')]
                structured_text['headers'] = headers

            if include_paragraphs:
                structured_text['paragraphs'] = [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()]

            if include_lists:
                structured_text['lists'] = []
                for ul in soup.find_all(['ul', 'ol']):
                    list_items = [li.get_text().strip() for li in ul.find_all('li')]
                    structured_text['lists'].append(list_items)

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'text': text,
                'structured_text': structured_text,
                'word_count': len(text.split()),
                'character_count': len(text)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'Text extraction requires BeautifulSoup. Please install: pip install beautifulsoup4'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Text extraction failed: {str(e)}"
            }

    async def _handle_extract_links(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all links from a webpage"""
        try:
            from bs4 import BeautifulSoup

            url = parameters.get('url')
            html_content = parameters.get('html')
            include_external = parameters.get('include_external', True)
            include_internal = parameters.get('include_internal', True)

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract links
            all_links = []
            internal_links = []
            external_links = []

            base_domain = urlparse(url).netloc if url else None

            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().strip()

                # Resolve relative URLs
                if url:
                    href = urljoin(url, href)

                link_info = {
                    'url': href,
                    'text': text,
                    'title': link.get('title', ''),
                    'target': link.get('target', ''),
                    'rel': link.get('rel', [])
                }

                all_links.append(link_info)

                # Classify as internal or external
                if base_domain:
                    link_domain = urlparse(href).netloc
                    if link_domain == base_domain:
                        internal_links.append(link_info)
                    else:
                        external_links.append(link_info)

            # Filter based on parameters
            result_links = []
            if include_internal:
                result_links.extend(internal_links)
            if include_external:
                result_links.extend(external_links)

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'links': result_links if (include_internal or include_external) else all_links,
                'total_links': len(all_links),
                'internal_count': len(internal_links),
                'external_count': len(external_links)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Link extraction failed: {str(e)}"
            }

    async def _handle_extract_images(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all image URLs from a webpage"""
        try:
            from bs4 import BeautifulSoup

            url = parameters.get('url')
            html_content = parameters.get('html')
            include_data_urls = parameters.get('include_data_urls', False)

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract images
            images = []
            for img in soup.find_all('img'):
                src = img.get('src', '')

                # Skip data URLs if not requested
                if src.startswith('data:') and not include_data_urls:
                    continue

                # Resolve relative URLs
                if url and src and not src.startswith(('data:', 'http://', 'https://')):
                    src = urljoin(url, src)

                if src:
                    image_info = {
                        'url': src,
                        'alt': img.get('alt', ''),
                        'title': img.get('title', ''),
                        'width': img.get('width', ''),
                        'height': img.get('height', ''),
                        'class': img.get('class', []),
                        'id': img.get('id', ''),
                        'loading': img.get('loading', '')
                    }
                    images.append(image_info)

            # Also check for images in CSS backgrounds (basic extraction)
            style_images = []
            for element in soup.find_all(style=True):
                style = element['style']
                # Simple regex to find background-image URLs
                urls = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style)
                for img_url in urls:
                    if url and not img_url.startswith(('data:', 'http://', 'https://')):
                        img_url = urljoin(url, img_url)
                    if img_url and (include_data_urls or not img_url.startswith('data:')):
                        style_images.append({
                            'url': img_url,
                            'source': 'css_background',
                            'element': element.name
                        })

            # Extract images from picture elements
            picture_images = []
            for picture in soup.find_all('picture'):
                sources = []
                for source in picture.find_all('source'):
                    srcset = source.get('srcset', '')
                    if srcset:
                        if url and not srcset.startswith(('data:', 'http://', 'https://')):
                            srcset = urljoin(url, srcset)
                        sources.append({
                            'srcset': srcset,
                            'media': source.get('media', ''),
                            'type': source.get('type', '')
                        })

                img = picture.find('img')
                if img:
                    src = img.get('src', '')
                    if url and src and not src.startswith(('data:', 'http://', 'https://')):
                        src = urljoin(url, src)

                    picture_images.append({
                        'fallback': src,
                        'sources': sources,
                        'alt': img.get('alt', '')
                    })

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'images': images,
                'style_images': style_images,
                'picture_images': picture_images,
                'total_images': len(images) + len(style_images) + len(picture_images)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Image extraction failed: {str(e)}"
            }

    async def _handle_extract_metadata(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from a webpage"""
        try:
            from bs4 import BeautifulSoup

            url = parameters.get('url')
            html_content = parameters.get('html')

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract basic metadata
            metadata = {
                'title': soup.title.string if soup.title else '',
                'description': '',
                'keywords': '',
                'author': '',
                'viewport': '',
                'charset': '',
                'language': soup.html.get('lang', '') if soup.html else ''
            }

            # Extract meta tags
            meta_tags = {}
            for meta in soup.find_all('meta'):
                if meta.get('name'):
                    meta_tags[meta['name']] = meta.get('content', '')
                    # Update specific metadata fields
                    if meta['name'] == 'description':
                        metadata['description'] = meta.get('content', '')
                    elif meta['name'] == 'keywords':
                        metadata['keywords'] = meta.get('content', '')
                    elif meta['name'] == 'author':
                        metadata['author'] = meta.get('content', '')
                    elif meta['name'] == 'viewport':
                        metadata['viewport'] = meta.get('content', '')
                elif meta.get('property'):
                    meta_tags[meta['property']] = meta.get('content', '')
                elif meta.get('charset'):
                    metadata['charset'] = meta['charset']
                elif meta.get('http-equiv'):
                    meta_tags[meta['http-equiv']] = meta.get('content', '')

            # Extract Open Graph metadata
            og_data = {}
            for meta in soup.find_all('meta', property=re.compile('^og:')):
                property_name = meta['property'].replace('og:', '')
                og_data[property_name] = meta.get('content', '')

            # Extract Twitter Card metadata
            twitter_data = {}
            for meta in soup.find_all('meta', attrs={'name': re.compile('^twitter:')}):
                property_name = meta['name'].replace('twitter:', '')
                twitter_data[property_name] = meta.get('content', '')

            # Extract canonical URL
            canonical = soup.find('link', rel='canonical')
            canonical_url = canonical['href'] if canonical else ''
            if canonical_url and url and not canonical_url.startswith(('http://', 'https://')):
                canonical_url = urljoin(url, canonical_url)

            # Extract favicon
            favicon = ''
            icon_link = soup.find('link', rel=re.compile('icon'))
            if icon_link:
                favicon = icon_link.get('href', '')
                if favicon and url and not favicon.startswith(('http://', 'https://', 'data:')):
                    favicon = urljoin(url, favicon)

            # Extract RSS/Atom feeds
            feeds = []
            for feed in soup.find_all('link', type=re.compile('application/(rss|atom)')):
                feed_url = feed.get('href', '')
                if feed_url and url and not feed_url.startswith(('http://', 'https://')):
                    feed_url = urljoin(url, feed_url)
                feeds.append({
                    'url': feed_url,
                    'type': feed.get('type', ''),
                    'title': feed.get('title', '')
                })

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'metadata': metadata,
                'meta_tags': meta_tags,
                'open_graph': og_data,
                'twitter_card': twitter_data,
                'canonical_url': canonical_url,
                'favicon': favicon,
                'feeds': feeds
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Metadata extraction failed: {str(e)}"
            }

    async def _handle_extract_tables(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tables from a webpage"""
        try:
            from bs4 import BeautifulSoup
            import pandas as pd

            url = parameters.get('url')
            html_content = parameters.get('html')
            as_dataframe = parameters.get('as_dataframe', False)

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract tables
            tables = []
            for table_idx, table in enumerate(soup.find_all('table')):
                table_data = []
                headers = []

                # Extract headers
                thead = table.find('thead')
                if thead:
                    header_row = thead.find('tr')
                    if header_row:
                        headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]
                else:
                    # Check if first row contains headers
                    first_row = table.find('tr')
                    if first_row:
                        first_cells = first_row.find_all(['th', 'td'])
                        if first_cells and first_cells[0].name == 'th':
                            headers = [cell.get_text().strip() for cell in first_cells]

                # Extract rows
                tbody = table.find('tbody') or table
                for row in tbody.find_all('tr'):
                    # Skip header row if already processed
                    if headers and row.find('th'):
                        continue

                    cells = row.find_all(['td', 'th'])
                    if cells:
                        row_data = [cell.get_text().strip() for cell in cells]
                        table_data.append(row_data)

                # Create table info
                table_info = {
                    'index': table_idx,
                    'id': table.get('id', ''),
                    'class': table.get('class', []),
                    'headers': headers,
                    'data': table_data,
                    'rows': len(table_data),
                    'columns': len(headers) if headers else (len(table_data[0]) if table_data else 0)
                }

                # Convert to DataFrame if requested
                if as_dataframe and table_data:
                    try:
                        if headers:
                            df = pd.DataFrame(table_data, columns=headers)
                        else:
                            df = pd.DataFrame(table_data)
                        table_info['dataframe'] = df.to_dict('records')
                    except:
                        pass

                tables.append(table_info)

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'tables': tables,
                'table_count': len(tables)
            }

        except ImportError as e:
            missing_lib = 'pandas' if 'pandas' in str(e) else 'beautifulsoup4'
            return {
                'error': True,
                'message': f'Table extraction requires {missing_lib}. Please install: pip install {missing_lib}'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Table extraction failed: {str(e)}"
            }

    async def _handle_extract_by_selector(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content using CSS selectors"""
        try:
            from bs4 import BeautifulSoup

            url = parameters.get('url')
            html_content = parameters.get('html')
            selector = parameters.get('selector')
            extract_type = parameters.get('extract_type', 'text')  # text, html, attributes
            multiple = parameters.get('multiple', True)

            if not selector:
                return {
                    'error': True,
                    'message': "CSS selector is required"
                }

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find elements
            if multiple:
                elements = soup.select(selector)
            else:
                element = soup.select_one(selector)
                elements = [element] if element else []

            # Extract data based on type
            results = []
            for elem in elements:
                if extract_type == 'text':
                    results.append(elem.get_text().strip())
                elif extract_type == 'html':
                    results.append(str(elem))
                elif extract_type == 'attributes':
                    attrs = dict(elem.attrs)
                    attrs['text'] = elem.get_text().strip()
                    results.append(attrs)
                else:
                    results.append(elem.get_text().strip())

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'selector': selector,
                'results': results if multiple else (results[0] if results else None),
                'count': len(results)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"CSS selector extraction failed: {str(e)}"
            }

    async def _handle_extract_by_xpath(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content using XPath expressions"""
        try:
            from lxml import html

            url = parameters.get('url')
            html_content = parameters.get('html')
            xpath = parameters.get('xpath')
            extract_type = parameters.get('extract_type', 'text')  # text, html, attributes

            if not xpath:
                return {
                    'error': True,
                    'message': "XPath expression is required"
                }

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML with lxml
            tree = html.fromstring(html_content)

            # Extract using XPath
            elements = tree.xpath(xpath)

            # Process results based on type
            results = []
            for elem in elements:
                if isinstance(elem, str):
                    # Direct text result from XPath
                    results.append(elem)
                else:
                    if extract_type == 'text':
                        text = elem.text_content() if hasattr(elem, 'text_content') else str(elem)
                        results.append(text.strip())
                    elif extract_type == 'html':
                        html_str = html.tostring(elem, encoding='unicode') if hasattr(elem, 'tag') else str(elem)
                        results.append(html_str)
                    elif extract_type == 'attributes':
                        if hasattr(elem, 'attrib'):
                            attrs = dict(elem.attrib)
                            attrs['text'] = elem.text_content().strip() if hasattr(elem, 'text_content') else ''
                            results.append(attrs)
                        else:
                            results.append(str(elem))

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'xpath': xpath,
                'results': results,
                'count': len(results)
            }

        except ImportError:
            return {
                'error': True,
                'message': 'XPath extraction requires lxml. Please install: pip install lxml'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"XPath extraction failed: {str(e)}"
            }

    async def _handle_extract_structured_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data (JSON-LD, microdata, etc.) from a webpage"""
        try:
            from bs4 import BeautifulSoup
            import json

            url = parameters.get('url')
            html_content = parameters.get('html')

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract JSON-LD
            json_ld_data = []
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    json_ld_data.append(data)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse JSON-LD data")

            # Extract microdata (basic extraction)
            microdata = []
            for item in soup.find_all(attrs={'itemscope': True}):
                item_data = {
                    'type': item.get('itemtype', ''),
                    'properties': {}
                }

                for prop in item.find_all(attrs={'itemprop': True}):
                    prop_name = prop['itemprop']
                    if prop.get('content'):
                        prop_value = prop['content']
                    elif prop.get('href'):
                        prop_value = prop['href']
                    elif prop.get('src'):
                        prop_value = prop['src']
                    else:
                        prop_value = prop.get_text().strip()

                    if prop_name in item_data['properties']:
                        # Handle multiple values
                        if not isinstance(item_data['properties'][prop_name], list):
                            item_data['properties'][prop_name] = [item_data['properties'][prop_name]]
                        item_data['properties'][prop_name].append(prop_value)
                    else:
                        item_data['properties'][prop_name] = prop_value

                if item_data['properties']:
                    microdata.append(item_data)

            # Extract RDFa (basic extraction)
            rdfa_data = []
            for elem in soup.find_all(attrs={'typeof': True}):
                rdfa_item = {
                    'type': elem.get('typeof', ''),
                    'properties': {}
                }

                for prop in elem.find_all(attrs={'property': True}):
                    prop_name = prop['property']
                    prop_value = prop.get('content', prop.get_text().strip())
                    rdfa_item['properties'][prop_name] = prop_value

                if rdfa_item['properties']:
                    rdfa_data.append(rdfa_item)

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'json_ld': json_ld_data,
                'microdata': microdata,
                'rdfa': rdfa_data,
                'total_items': len(json_ld_data) + len(microdata) + len(rdfa_data)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Structured data extraction failed: {str(e)}"
            }

    async def _handle_scrape_dynamic(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape JavaScript-rendered content using Playwright"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            wait_for = parameters.get('wait_for', 'load')  # load, domcontentloaded, networkidle
            wait_selector = parameters.get('wait_selector')  # Wait for specific element
            timeout = parameters.get('timeout', 30000)
            viewport = parameters.get('viewport', {'width': 1920, 'height': 1080})

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport=viewport,
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until=wait_for, timeout=timeout)

                    # Wait for specific selector if provided
                    if wait_selector:
                        await page.wait_for_selector(wait_selector, timeout=timeout)

                    # Get the HTML content
                    html_content = await page.content()

                    # Get page title
                    title = await page.title()

                    # Get current URL (may differ due to redirects)
                    current_url = page.url

                    # Extract any console messages
                    console_messages = []
                    page.on('console', lambda msg: console_messages.append({
                        'type': msg.type,
                        'text': msg.text
                    }))

                    return {
                        'success': True,
                        'url': current_url,
                        'original_url': url,
                        'html': html_content,
                        'title': title,
                        'content_length': len(html_content),
                        'console_messages': console_messages
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Dynamic scraping requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Dynamic scraping failed: {str(e)}"
            }

    async def _handle_screenshot_page(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Take a screenshot of a webpage"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            full_page = parameters.get('full_page', False)
            viewport = parameters.get('viewport', {'width': 1920, 'height': 1080})
            wait_for = parameters.get('wait_for', 'networkidle')
            timeout = parameters.get('timeout', 30000)
            format = parameters.get('format', 'png')  # png or jpeg

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport=viewport,
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until=wait_for, timeout=timeout)

                    # Take screenshot
                    screenshot_bytes = await page.screenshot(
                        full_page=full_page,
                        type=format
                    )

                    # Get page title and URL
                    title = await page.title()
                    current_url = page.url

                    return {
                        'success': True,
                        'url': current_url,
                        'original_url': url,
                        'screenshot': base64.b64encode(screenshot_bytes).decode('utf-8'),
                        'format': format,
                        'title': title,
                        'full_page': full_page,
                        'size': len(screenshot_bytes)
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Screenshot requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Screenshot failed: {str(e)}"
            }

    async def _handle_fill_form(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fill and submit a web form"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            form_data = parameters.get('form_data', {})
            submit_button_selector = parameters.get('submit_button_selector')
            form_selector = parameters.get('form_selector')
            wait_after_submit = parameters.get('wait_after_submit', 'networkidle')
            timeout = parameters.get('timeout', 30000)

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            if not form_data:
                return {
                    'error': True,
                    'message': "Form data is required"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until='networkidle', timeout=timeout)

                    # Fill form fields
                    for field_selector, value in form_data.items():
                        element = await page.query_selector(field_selector)
                        if element:
                            tag_name = await element.evaluate('el => el.tagName')
                            input_type = await element.evaluate('el => el.type')

                            if tag_name.upper() == 'SELECT':
                                await page.select_option(field_selector, value)
                            elif input_type in ['checkbox', 'radio']:
                                if value:
                                    await page.check(field_selector)
                            else:
                                await page.fill(field_selector, str(value))

                    # Submit form
                    if submit_button_selector:
                        await page.click(submit_button_selector)
                    elif form_selector:
                        await page.evaluate(f'document.querySelector("{form_selector}").submit()')
                    else:
                        # Try to find and click a submit button
                        await page.click('button[type="submit"], input[type="submit"]')

                    # Wait for navigation or specified condition
                    await page.wait_for_load_state(wait_after_submit)

                    # Get result page content
                    result_html = await page.content()
                    result_url = page.url
                    result_title = await page.title()

                    return {
                        'success': True,
                        'original_url': url,
                        'result_url': result_url,
                        'result_html': result_html,
                        'result_title': result_title,
                        'form_submitted': True
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Form filling requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Form filling failed: {str(e)}"
            }

    async def _handle_click_and_extract(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Click elements and extract resulting content"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            click_selectors = parameters.get('click_selectors', [])
            extract_selector = parameters.get('extract_selector')
            wait_after_click = parameters.get('wait_after_click', 2000)
            timeout = parameters.get('timeout', 30000)

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            if not click_selectors:
                return {
                    'error': True,
                    'message': "Click selectors are required"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until='networkidle', timeout=timeout)

                    results = []

                    # Click each selector and extract content
                    for selector in click_selectors:
                        try:
                            # Click the element
                            await page.click(selector)

                            # Wait for content to load
                            await page.wait_for_timeout(wait_after_click)

                            # Extract content
                            if extract_selector:
                                elements = await page.query_selector_all(extract_selector)
                                extracted = []
                                for elem in elements:
                                    text = await elem.text_content()
                                    extracted.append(text.strip() if text else '')
                            else:
                                # Get entire page content
                                extracted = await page.content()

                            results.append({
                                'clicked': selector,
                                'extracted': extracted
                            })

                        except Exception as e:
                            results.append({
                                'clicked': selector,
                                'error': str(e)
                            })

                    return {
                        'success': True,
                        'url': url,
                        'results': results,
                        'total_clicks': len(click_selectors)
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Click and extract requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Click and extract failed: {str(e)}"
            }

    async def _handle_scroll_and_load(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scroll page to load infinite scroll content"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            max_scrolls = parameters.get('max_scrolls', 10)
            scroll_delay = parameters.get('scroll_delay', 2000)
            extract_selector = parameters.get('extract_selector')
            timeout = parameters.get('timeout', 60000)

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, wait_until='networkidle', timeout=timeout)

                    all_content = []
                    previous_height = 0
                    scroll_count = 0

                    for _ in range(max_scrolls):
                        # Get current scroll height
                        current_height = await page.evaluate('document.body.scrollHeight')

                        # Break if no new content loaded
                        if current_height == previous_height:
                            break

                        # Extract content before scrolling
                        if extract_selector:
                            elements = await page.query_selector_all(extract_selector)
                            for elem in elements:
                                text = await elem.text_content()
                                if text and text.strip() not in all_content:
                                    all_content.append(text.strip())

                        # Scroll to bottom
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

                        # Wait for new content to load
                        await page.wait_for_timeout(scroll_delay)

                        previous_height = current_height
                        scroll_count += 1

                    # Final extraction
                    if extract_selector:
                        elements = await page.query_selector_all(extract_selector)
                        for elem in elements:
                            text = await elem.text_content()
                            if text and text.strip() not in all_content:
                                all_content.append(text.strip())
                    else:
                        # Get entire page content
                        all_content = await page.content()

                    return {
                        'success': True,
                        'url': url,
                        'content': all_content,
                        'scroll_count': scroll_count,
                        'items_found': len(all_content) if isinstance(all_content, list) else 1
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Scroll and load requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Scroll and load failed: {str(e)}"
            }

    async def _handle_wait_and_extract(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for specific elements to load then extract content"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            wait_selector = parameters.get('wait_selector')
            extract_selectors = parameters.get('extract_selectors', [])
            timeout = parameters.get('timeout', 30000)

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            if not wait_selector:
                return {
                    'error': True,
                    'message': "Wait selector is required"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to page
                    await page.goto(url, timeout=timeout)

                    # Wait for specific element
                    await page.wait_for_selector(wait_selector, timeout=timeout)

                    # Extract content
                    results = {}

                    if extract_selectors:
                        for selector_info in extract_selectors:
                            if isinstance(selector_info, dict):
                                selector = selector_info.get('selector')
                                name = selector_info.get('name', selector)
                            else:
                                selector = selector_info
                                name = selector

                            elements = await page.query_selector_all(selector)
                            extracted = []
                            for elem in elements:
                                text = await elem.text_content()
                                extracted.append(text.strip() if text else '')

                            results[name] = extracted if len(extracted) > 1 else (extracted[0] if extracted else None)
                    else:
                        # Get entire page content
                        results['html'] = await page.content()

                    return {
                        'success': True,
                        'url': url,
                        'waited_for': wait_selector,
                        'results': results
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Wait and extract requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Wait and extract failed: {str(e)}"
            }

    async def _handle_multi_page_scrape(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate through pagination and scrape multiple pages"""
        try:
            from playwright.async_api import async_playwright

            start_url = parameters.get('url')
            next_button_selector = parameters.get('next_button_selector')
            max_pages = parameters.get('max_pages', 10)
            extract_selector = parameters.get('extract_selector')
            page_delay = parameters.get('page_delay', 2000)
            timeout = parameters.get('timeout', 30000)

            if not start_url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            if not next_button_selector:
                return {
                    'error': True,
                    'message': "Next button selector is required for pagination"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Navigate to start page
                    await page.goto(start_url, wait_until='networkidle', timeout=timeout)

                    all_results = []
                    pages_scraped = 0

                    for page_num in range(max_pages):
                        # Extract content from current page
                        if extract_selector:
                            elements = await page.query_selector_all(extract_selector)
                            page_content = []
                            for elem in elements:
                                text = await elem.text_content()
                                if text:
                                    page_content.append(text.strip())
                        else:
                            page_content = await page.content()

                        all_results.append({
                            'page': page_num + 1,
                            'url': page.url,
                            'content': page_content,
                            'items': len(page_content) if isinstance(page_content, list) else 1
                        })

                        pages_scraped += 1

                        # Try to find and click next button
                        next_button = await page.query_selector(next_button_selector)
                        if not next_button:
                            break

                        # Check if button is disabled
                        is_disabled = await next_button.evaluate('el => el.disabled || el.classList.contains("disabled")')
                        if is_disabled:
                            break

                        # Click next button
                        await next_button.click()

                        # Wait for new page to load
                        await page.wait_for_load_state('networkidle')
                        await page.wait_for_timeout(page_delay)

                    return {
                        'success': True,
                        'start_url': start_url,
                        'pages_scraped': pages_scraped,
                        'results': all_results,
                        'total_items': sum(r['items'] for r in all_results)
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Multi-page scrape requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Multi-page scrape failed: {str(e)}"
            }

    async def _handle_scrape_with_auth(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape pages requiring authentication"""
        try:
            from playwright.async_api import async_playwright

            url = parameters.get('url')
            login_url = parameters.get('login_url')
            username_selector = parameters.get('username_selector')
            password_selector = parameters.get('password_selector')
            username = parameters.get('username')
            password = parameters.get('password')
            submit_selector = parameters.get('submit_selector')
            extract_selector = parameters.get('extract_selector')
            timeout = parameters.get('timeout', 30000)

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            if login_url and not all([username_selector, password_selector, username, password]):
                return {
                    'error': True,
                    'message': "Login credentials and selectors are required for authentication"
                }

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self._get_random_user_agent()
                )

                page = await context.new_page()

                try:
                    # Perform login if required
                    if login_url:
                        await page.goto(login_url, wait_until='networkidle', timeout=timeout)

                        # Fill login form
                        await page.fill(username_selector, username)
                        await page.fill(password_selector, password)

                        # Submit form
                        if submit_selector:
                            await page.click(submit_selector)
                        else:
                            await page.press(password_selector, 'Enter')

                        # Wait for login to complete
                        await page.wait_for_load_state('networkidle')

                    # Navigate to target URL
                    await page.goto(url, wait_until='networkidle', timeout=timeout)

                    # Extract content
                    if extract_selector:
                        elements = await page.query_selector_all(extract_selector)
                        results = []
                        for elem in elements:
                            text = await elem.text_content()
                            results.append(text.strip() if text else '')
                    else:
                        results = await page.content()

                    return {
                        'success': True,
                        'url': url,
                        'authenticated': bool(login_url),
                        'content': results
                    }

                finally:
                    await browser.close()

        except ImportError:
            return {
                'error': True,
                'message': 'Authenticated scraping requires Playwright. Please install: pip install playwright && playwright install'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Authenticated scraping failed: {str(e)}"
            }

    #: Upper bound on files one download_files call may fetch (the payload
    #: carries every file base64-encoded through the flow).
    MAX_DOWNLOAD_FILES = 200

    @staticmethod
    def _file_link_extension(file_url: str, file_extensions: List[str]) -> Optional[str]:
        """The listed extension a link points at, judged on the URL PATH (so
        ``/x/portfolio.xlsx?v=3`` matches) or, for script-served downloads
        (``download.php?file=portfolio.xls``), on a query value."""
        parsed = urlparse(file_url)
        candidates = [parsed.path.lower()]
        for values in parse_qs(parsed.query).values():
            candidates.extend(v.lower() for v in values)
        for candidate in candidates:
            for ext in file_extensions:
                if candidate.endswith(ext.lower()):
                    return ext.lower()
        return None

    async def _handle_download_files(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Download files linked from a webpage.

        Links are matched on their URL path or a query value, so versioned and
        script-served downloads are found; ``url_contains`` narrows them by URL
        or link text; ``skip_urls`` leaves out files a previous run already
        took (a flow keeps no state between runs, so the caller supplies it);
        ``render_js`` reads a page whose links are drawn by JavaScript;
        ``include_content: false`` lists the links without downloading."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            url = parameters.get('url')
            file_extensions = parameters.get('file_extensions') or ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip']
            if isinstance(file_extensions, str):
                file_extensions = [e.strip() for e in file_extensions.split(',') if e.strip()]
            try:
                max_files = int(parameters.get('max_files') or 10)
            except (TypeError, ValueError):
                return {'error': True, 'message': "max_files must be an integer"}
            max_files = max(1, min(max_files, self.MAX_DOWNLOAD_FILES))
            url_contains = parameters.get('url_contains') or []
            if isinstance(url_contains, str):
                url_contains = [url_contains]
            url_contains = [str(t).lower() for t in url_contains if str(t).strip()]
            skip_urls = {str(u).strip() for u in (parameters.get('skip_urls') or []) if str(u).strip()}
            include_content = parameters.get('include_content', True) not in (False, 'false', 'False', 0)

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            # Fetch page (static, or rendered when the links are drawn by script)
            if parameters.get('render_js'):
                rendered = await self._handle_scrape_dynamic({
                    'url': url,
                    'wait_for': parameters.get('wait_for', 'networkidle'),
                    'wait_selector': parameters.get('wait_selector'),
                    'timeout': parameters.get('timeout', 30000),
                })
                if rendered.get('error'):
                    return rendered
                html_content = rendered.get('html') or ''
                url = rendered.get('url') or url
            else:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find all links
            file_links = []
            seen = set()
            skipped = 0
            for link in soup.find_all('a', href=True):
                file_url = urljoin(url, link['href'].strip())
                if file_url in seen:
                    continue
                ext = self._file_link_extension(file_url, file_extensions)
                if not ext:
                    continue
                text = link.get_text().strip()
                if url_contains and not any(t in file_url.lower() or t in text.lower()
                                            for t in url_contains):
                    continue
                seen.add(file_url)
                if file_url in skip_urls:
                    skipped += 1
                    continue
                file_links.append({
                    'url': file_url,
                    'text': text,
                    'extension': ext
                })
                if len(file_links) >= max_files:
                    break

            if not include_content:
                return {
                    'success': True,
                    'url': url,
                    'files_found': len(file_links),
                    'files_skipped': skipped,
                    'files_downloaded': 0,
                    'files': file_links
                }

            # Download files
            downloaded_files = []
            failed_files = []
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                for file_info in file_links:
                    try:
                        response = await client.get(
                            file_info['url'],
                            headers={'User-Agent': self._get_random_user_agent(), 'Referer': url})
                        response.raise_for_status()

                        filename = os.path.basename(urlparse(file_info['url']).path) or 'download'
                        disposition = response.headers.get('content-disposition') or ''
                        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
                        if match:
                            filename = os.path.basename(match.group(1).strip())
                        downloaded_files.append({
                            'url': file_info['url'],
                            'text': file_info['text'],
                            'filename': filename,
                            'extension': file_info['extension'],
                            'content_type': response.headers.get('content-type'),
                            'content': base64.b64encode(response.content).decode('utf-8'),
                            'size': len(response.content)
                        })

                    except Exception as e:
                        logger.warning(f"Failed to download {file_info['url']}: {e}")
                        failed_files.append({'url': file_info['url'], 'error': str(e)})

            return {
                'success': True,
                'url': url,
                'files_found': len(file_links),
                'files_skipped': skipped,
                'files_downloaded': len(downloaded_files),
                'files_failed': failed_files,
                'files': downloaded_files
            }

        except Exception as e:
            logger.error(f"File download failed for {parameters.get('url')}: {e}", exc_info=True)
            return {
                'error': True,
                'message': f"File download failed: {str(e)}"
            }

    async def _handle_monitor_changes(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor a webpage for changes (single check, not continuous)"""
        try:
            from bs4 import BeautifulSoup
            import hashlib

            url = parameters.get('url')
            selector = parameters.get('selector')  # Monitor specific element
            previous_hash = parameters.get('previous_hash')  # Hash from previous check

            if not url:
                return {
                    'error': True,
                    'message': "URL parameter is required"
                }

            # Fetch current page
            html_content, _, _ = await self._fetch_page(url)

            # Extract content to monitor
            if selector:
                soup = BeautifulSoup(html_content, 'html.parser')
                element = soup.select_one(selector)
                content_to_monitor = str(element) if element else ''
            else:
                content_to_monitor = html_content

            # Calculate hash
            current_hash = hashlib.sha256(content_to_monitor.encode()).hexdigest()

            # Check for changes
            has_changed = False
            if previous_hash:
                has_changed = current_hash != previous_hash

            return {
                'success': True,
                'url': url,
                'selector': selector,
                'current_hash': current_hash,
                'previous_hash': previous_hash,
                'has_changed': has_changed,
                'content': content_to_monitor if has_changed else None,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Change monitoring failed: {str(e)}"
            }

    async def _handle_sitemap_scrape(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape URLs from sitemap"""
        try:
            from bs4 import BeautifulSoup
            import httpx

            sitemap_url = parameters.get('sitemap_url')
            base_url = parameters.get('base_url')
            max_urls = parameters.get('max_urls', 100)
            filter_pattern = parameters.get('filter_pattern')  # Regex to filter URLs

            if not sitemap_url and not base_url:
                return {
                    'error': True,
                    'message': "Either sitemap_url or base_url is required"
                }

            # If only base_url provided, try common sitemap locations
            if not sitemap_url:
                sitemap_url = urljoin(base_url, '/sitemap.xml')

            # Fetch sitemap
            try:
                sitemap_content, _, _ = await self._fetch_page(sitemap_url)
            except:
                # Try alternative sitemap location
                sitemap_url = urljoin(base_url, '/sitemap_index.xml')
                try:
                    sitemap_content, _, _ = await self._fetch_page(sitemap_url)
                except:
                    return {
                        'error': True,
                        'message': "Could not find sitemap at standard locations"
                    }

            # Parse sitemap
            soup = BeautifulSoup(sitemap_content, 'xml')

            urls = []
            url_elements = soup.find_all('url')

            for url_elem in url_elements[:max_urls]:
                loc = url_elem.find('loc')
                if loc:
                    url = loc.text.strip()

                    # Apply filter if provided
                    if filter_pattern:
                        if not re.search(filter_pattern, url):
                            continue

                    url_info = {
                        'url': url
                    }

                    # Extract optional sitemap elements
                    lastmod = url_elem.find('lastmod')
                    if lastmod:
                        url_info['lastmod'] = lastmod.text.strip()

                    changefreq = url_elem.find('changefreq')
                    if changefreq:
                        url_info['changefreq'] = changefreq.text.strip()

                    priority = url_elem.find('priority')
                    if priority:
                        url_info['priority'] = priority.text.strip()

                    urls.append(url_info)

            # Check for sitemap index
            sitemap_elements = soup.find_all('sitemap')
            sitemaps = []
            for sitemap_elem in sitemap_elements:
                loc = sitemap_elem.find('loc')
                if loc:
                    sitemaps.append(loc.text.strip())

            return {
                'success': True,
                'sitemap_url': sitemap_url,
                'urls': urls,
                'url_count': len(urls),
                'child_sitemaps': sitemaps,
                'is_index': len(sitemaps) > 0
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"Sitemap scraping failed: {str(e)}"
            }

    async def _handle_api_discover(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Discover API endpoints from a webpage"""
        try:
            from bs4 import BeautifulSoup
            import re

            url = parameters.get('url')
            html_content = parameters.get('html')

            if not url and not html_content:
                return {
                    'error': True,
                    'message': "Either URL or HTML content is required"
                }

            # Fetch HTML if not provided
            if not html_content:
                html_content, _, _ = await self._fetch_page(url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Look for API endpoints in various places
            api_endpoints = set()

            # Check script tags for API calls
            for script in soup.find_all('script'):
                if script.string:
                    # Common API patterns
                    patterns = [
                        r'["\']/(api|v\d+|graphql|rest)/[^"\']*["\']',
                        r'https?://[^/]+/(api|v\d+|graphql|rest)/[^"\']*',
                        r'fetch\(["\']([^"\']+)["\']',
                        r'axios\.[get|post|put|delete|patch]\(["\']([^"\']+)["\']',
                        r'XMLHttpRequest.*open\(["\'][^"\']+["\'],\s*["\']([^"\']+)["\']'
                    ]

                    for pattern in patterns:
                        matches = re.findall(pattern, script.string)
                        for match in matches:
                            if isinstance(match, tuple):
                                match = match[0]
                            # Resolve relative URLs
                            if url and not match.startswith(('http://', 'https://')):
                                match = urljoin(url, match)
                            api_endpoints.add(match)

            # Check data attributes
            for elem in soup.find_all(attrs={'data-api-url': True}):
                api_url = elem['data-api-url']
                if url and not api_url.startswith(('http://', 'https://')):
                    api_url = urljoin(url, api_url)
                api_endpoints.add(api_url)

            # Check for API documentation links
            api_docs = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().lower()
                if any(term in text for term in ['api', 'documentation', 'developer', 'docs']):
                    if url and not href.startswith(('http://', 'https://')):
                        href = urljoin(url, href)
                    api_docs.append({
                        'url': href,
                        'text': link.get_text().strip()
                    })

            # Check meta tags for API information
            api_meta = {}
            for meta in soup.find_all('meta'):
                name = meta.get('name', '').lower()
                if 'api' in name:
                    api_meta[meta.get('name')] = meta.get('content', '')

            return {
                'success': True,
                'url': url if url else 'provided_html',
                'api_endpoints': list(api_endpoints),
                'api_documentation': api_docs,
                'api_metadata': api_meta,
                'total_endpoints': len(api_endpoints)
            }

        except Exception as e:
            return {
                'error': True,
                'message': f"API discovery failed: {str(e)}"
            }