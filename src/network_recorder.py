"""
Network recording for HTTP requests and responses
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, Any, Optional
from playwright.async_api import Request, Response, Page

from .config import FilterConfig
from .session_manager import SessionManager
from .blob_downloader import BlobDownloader
from .logging_config import get_logger

logger = get_logger('network_recorder')


class NetworkRecorder:
    """Captures and saves HTTP requests and responses"""

    def __init__(
        self,
        session_manager: SessionManager,
        blob_downloader: Optional[BlobDownloader] = None,
        filter_config: Optional[FilterConfig] = None,
        page: Optional[Page] = None
    ):
        self.session_manager = session_manager
        self.blob_downloader = blob_downloader
        self.filter_config = filter_config or FilterConfig()
        self.page = page  # Page reference for URL tracking and DOM access
        self._pending_settle_tasks = []  # Track delayed blob tasks
        self._blob_last_seen = {}  # Track when blob was last seen (for deduplication)
        self._blob_pending_tasks = {}  # Track pending download tasks per blob URL

    def _format_headers(self, headers: dict) -> Dict[str, str]:
        """Formats header dictionary"""
        return dict(headers)

    def _should_record_request(self, request: Request) -> bool:
        """Checks if request should be recorded (filter)"""
        if not self.filter_config.enabled:
            return True

        url = request.url

        # Domain whitelist (if set, only these domains)
        if self.filter_config.domain_whitelist:
            domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
            if not any(allowed in domain for allowed in self.filter_config.domain_whitelist):
                return False

        # Domain blacklist
        if self.filter_config.domain_blacklist:
            domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
            if any(blocked in domain for blocked in self.filter_config.domain_blacklist):
                return False

        return True

    def _should_record_response(self, response: Response) -> bool:
        """Checks if response should be recorded (filter)"""
        if not self.filter_config.enabled:
            return True

        # Content-Type filter
        if self.filter_config.content_types:
            content_type = response.headers.get("content-type", "")
            if not any(ct in content_type for ct in self.filter_config.content_types):
                return False

        return True

    async def on_request(self, request: Request) -> None:
        """Callback for outgoing requests"""
        try:
            # Check filter
            if not self._should_record_request(request):
                return

            # Safely extract POST data
            post_data = None
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    post_data = request.post_data
                except (UnicodeDecodeError, Exception):
                    post_data = "<binary data>"

            # Collect request data
            request_data = {
                "timestamp": datetime.now().isoformat(),
                "method": request.method,
                "url": request.url,
                "headers": self._format_headers(request.headers),
                "post_data": post_data,
                "resource_type": request.resource_type
            }

            # Add asynchronously
            await self.session_manager.add_request(request_data)

            # Live output (optionally reduced for performance)
            logger.debug(
                f"Request: {request.method} {request.url}",
                extra_data={'method': request.method, 'type': request.resource_type}
            )

        except Exception as e:
            logger.error(f"Error processing request: {e}")

    async def on_response(self, response: Response) -> None:
        """Callback for incoming responses"""
        try:
            # Check filter
            if not self._should_record_response(response):
                return

            # Collect response data
            response_data: Dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "url": response.url,
                "status": response.status,
                "status_text": response.status_text,
                "headers": self._format_headers(response.headers),
                "content_type": response.headers.get("content-type", "")
            }

            # Capture body for certain Content-Types
            try:
                content_type = response_data["content_type"]

                if "application/json" in content_type:
                    response_data["body"] = await response.text()
                elif "text/" in content_type:
                    # Limit text body size
                    text = await response.text()
                    if len(text) < 100000:  # Max 100KB
                        response_data["body"] = text
                    else:
                        response_data["body"] = "<text too large>"

            except Exception as e:
                response_data["body_error"] = str(e)

            # Add asynchronously
            await self.session_manager.add_response(response_data)

            # Live output
            status_indicator = "✓" if 200 <= response.status < 300 else "✗"
            logger.debug(
                f"Response: {status_indicator} {response.status} {response.url}",
                extra_data={'status': response.status}
            )

            # Detect blob URL and add to download queue
            # Only Snapchat blobs (blob:https://www.snapchat.com/...)
            if self.blob_downloader and response.url.startswith('blob:https://www.snapchat.com/'):
                content_type = response_data["content_type"]

                # Filter: Only media blobs (no JavaScript, HTML, CSS, etc.)
                if content_type.startswith(('image/', 'video/', 'audio/')):
                    # EXPERIMENTAL: Log Content-Length to analyze multi-response
                    content_length = response.headers.get("content-length", "unknown")

                    # User attribution: Extract User ID and Username
                    page_url = self.page.url if self.page else None
                    user_id = self._extract_user_id(page_url) if page_url else None
                    username = await self._extract_username(user_id) if self.page else None

                    logger.info(
                        f"Snapchat media blob detected: {response.url[-12:]}",
                        extra_data={
                            'content_type': content_type,
                            'content_length': content_length,
                            'full_url': response.url,
                            'user_id': user_id,
                            'username': username,
                            'page_url': page_url
                        }
                    )

                    # Opportunistic download: Try immediately!
                    # Retries handle progressive JPEGs automatically
                    await self.blob_downloader.queue_blob_download(
                        response.url,
                        content_type,
                        page_url=page_url,
                        user_id=user_id,
                        username=username
                    )
                else:
                    logger.debug(
                        f"Snapchat blob ignored (no media content): {response.url}",
                        extra_data={'content_type': content_type}
                    )

        except Exception as e:
            logger.error(f"Error processing response: {e}")

    async def _delayed_queue_blob(self, blob_url: str, content_type: str, delay: float) -> None:
        """Waits a certain time and then adds blob to download queue"""
        try:
            await asyncio.sleep(delay)
            logger.info(
                f"No further response - downloading final blob: {blob_url}",
                extra_data={'content_type': content_type, 'delay': delay}
            )
            await self.blob_downloader.queue_blob_download(blob_url, content_type)
            # Remove from pending tasks
            if blob_url in self._blob_pending_tasks:
                del self._blob_pending_tasks[blob_url]
        except asyncio.CancelledError:
            logger.debug(f"Download task cancelled (newer response received): {blob_url}")
            # Remove from pending tasks
            if blob_url in self._blob_pending_tasks:
                del self._blob_pending_tasks[blob_url]
            raise

    async def cancel_pending_settle_tasks(self) -> None:
        """Cancels all pending settle tasks (during shutdown)"""
        if self._pending_settle_tasks:
            logger.info(f"Cancelling {len(self._pending_settle_tasks)} pending settle tasks...")
            for task in self._pending_settle_tasks:
                task.cancel()
            # Wait until all are cancelled
            await asyncio.gather(*self._pending_settle_tasks, return_exceptions=True)
            self._pending_settle_tasks.clear()
            logger.info("All pending settle tasks cancelled")

    def set_page(self, page: Page) -> None:
        """Sets the page reference for URL tracking and DOM access"""
        self.page = page
        logger.info("Page reference set for user attribution")

    def _extract_user_id(self, url: str) -> Optional[str]:
        """Extracts UUID from Snapchat Web URL

        Args:
            url: Browser URL (e.g., https://www.snapchat.com/web/UUID)

        Returns:
            UUID string or None if not found

        Example:
            Input: https://www.snapchat.com/web/bd26aad2-b709-5a65-975b-805b24bdfdfd
            Output: bd26aad2-b709-5a65-975b-805b24bdfdfd
        """
        if not url:
            return None

        # UUID pattern: 8-4-4-4-12 hexadecimal characters
        uuid_pattern = r'/web/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        match = re.search(uuid_pattern, url, re.IGNORECASE)

        if match:
            user_id = match.group(1)
            logger.debug(f"User ID extracted: {user_id}")
            return user_id

        return None

    async def _extract_username(self, user_id: Optional[str] = None) -> Optional[str]:
        """Attempts to extract username from Snapchat DOM

        Args:
            user_id: User UUID for constructing ID selector

        Returns:
            Username string or None if not found

        Strategy:
            1. UUID-based selector: #title-{UUID} .nonIntl (most reliable method)
            2. Fallback to generic selectors

        HTML structure:
            <span id="title-{UUID}">
                <span class="nonIntl">Username</span>
            </span>
        """
        if not self.page:
            return None

        try:
            # Strategy 1: UUID-based selector (most reliable!)
            if user_id:
                try:
                    # Construct ID selector: title-{UUID}
                    title_id = f"title-{user_id}"
                    # Search within title span for .nonIntl
                    title_element = await self.page.locator(f'#{title_id}').locator('.nonIntl').first.text_content(timeout=1000)

                    if title_element and title_element.strip():
                        username_clean = title_element.strip()
                        logger.debug(f"Username extracted via UUID selector: {username_clean}")
                        return username_clean
                except Exception as e:
                    logger.debug(f"UUID-based selector failed: {e}")

            # Strategy 2: Fallback to generic selectors
            selectors = [
                '.nonIntl',  # Direct class name
                '[data-testid="chat-header-name"]',
                '.chat-header__name',
                '[aria-label*="conversation"]',
                'header [class*="name"]',
                '[class*="ChatHeader"] [class*="Name"]',
            ]

            for selector in selectors:
                try:
                    username = await self.page.locator(selector).first.text_content(timeout=1000)
                    if username and username.strip():
                        username_clean = username.strip()
                        logger.debug(f"Username extracted from DOM: {username_clean} (selector: {selector})")
                        return username_clean
                except Exception:
                    # This selector didn't work, try next
                    continue

            logger.debug("No username selector found (DOM may have changed)")
            return None

        except Exception as e:
            logger.debug(f"Error extracting username: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Returns recording statistics"""
        session_info = self.session_manager.get_session_info()

        stats = {
            'requests_recorded': session_info['requests_count'],
            'responses_recorded': session_info['responses_count'],
            'session_duration': (
                datetime.now() - datetime.fromisoformat(session_info['session_start'])
            ).total_seconds()
        }

        if self.blob_downloader:
            stats['blob_stats'] = self.blob_downloader.get_statistics()

        return stats
