"""
Blob download manager with async I/O and intelligent retry logic
"""

import asyncio
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Set
import aiofiles
from playwright.async_api import Page

from .config import DownloadConfig
from .file_validator import FileValidator, get_file_extension
from .exceptions import BlobDownloadError, BlobValidationError
from .logging_config import get_logger

logger = get_logger('blob_downloader')


class BlobInfo:
    """Information about a downloaded blob"""

    def __init__(
        self,
        blob_url: str,
        filename: str,
        filepath: Path,
        content_type: str,
        size: int,
        file_hash: str,
        is_duplicate: bool,
        timestamp: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        page_url: Optional[str] = None,
        was_repaired: bool = False,
        repair_message: Optional[str] = None
    ):
        self.blob_url = blob_url
        self.filename = filename
        self.filepath = filepath
        self.content_type = content_type
        self.size = size
        self.hash = file_hash
        self.is_duplicate = is_duplicate
        self.timestamp = timestamp
        # User-Attribution
        self.user_id = user_id
        self.username = username
        self.page_url = page_url
        # Repair-Status
        self.was_repaired = was_repaired
        self.repair_message = repair_message

    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary for JSON export"""
        return {
            'blob_url': self.blob_url,
            'filename': self.filename,
            'filepath': str(self.filepath),
            'content_type': self.content_type,
            'size': self.size,
            'hash': self.hash,
            'duplicate': self.is_duplicate,
            'timestamp': self.timestamp,
            # User-Attribution
            'user_id': self.user_id,
            'username': self.username,
            'page_url': self.page_url,
            # Repair-Status
            'was_repaired': self.was_repaired,
            'repair_message': self.repair_message
        }


class BlobDownloader:
    """Manages downloads from blob URLs with validation and deduplication"""

    def __init__(
        self,
        config: DownloadConfig,
        validator: FileValidator,
        blobs_dir: Path,
        page: Optional[Page] = None
    ):
        self.config = config
        self.validator = validator
        self.blobs_dir = blobs_dir
        self.page = page

        self.blob_urls: Set[str] = set()
        self.downloaded_blobs: list[BlobInfo] = []
        self.download_queue: asyncio.Queue = asyncio.Queue()
        self.active_downloads = 0
        self.max_parallel = config.parallel_downloads

        # Statistics
        self.stats = {
            'total_attempts': 0,
            'successful': 0,
            'failed': 0,
            'duplicates': 0,
            'validation_errors': 0
        }

    def set_page(self, page: Page) -> None:
        """Sets the page reference for downloads"""
        self.page = page

    async def download_blob(
        self,
        blob_url: str,
        content_type: str = "",
        page_url: Optional[str] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None
    ) -> Optional[BlobInfo]:
        """
        Downloads a blob URL with retry logic

        Args:
            blob_url: Blob URL
            content_type: MIME type of the blob
            page_url: Browser URL at time of download
            user_id: Snapchat User ID (UUID)
            username: Snapchat Username

        Returns:
            BlobInfo on success, None on error
        """
        if not self.page:
            logger.error("No page reference available")
            raise BlobDownloadError("No page reference available")

        attempt = 0
        last_error = None

        while attempt < self.config.max_retries:
            try:
                self.stats['total_attempts'] += 1

                # JavaScript to fetch blob data
                blob_data = await self.page.evaluate("""
                    async (blobUrl) => {
                        try {
                            const response = await fetch(blobUrl);
                            const blob = await response.blob();
                            const arrayBuffer = await blob.arrayBuffer();

                            // Process in chunks for large files
                            const uint8Array = new Uint8Array(arrayBuffer);
                            const chunkSize = 65536; // 64KB
                            let base64 = '';

                            for (let i = 0; i < uint8Array.length; i += chunkSize) {
                                const chunk = uint8Array.subarray(
                                    i,
                                    Math.min(i + chunkSize, uint8Array.length)
                                );
                                base64 += btoa(String.fromCharCode.apply(null, chunk));
                            }

                            return {
                                success: true,
                                data: base64,
                                type: blob.type,
                                size: blob.size
                            };
                        } catch (e) {
                            return {
                                success: false,
                                error: e.message
                            };
                        }
                    }
                """, blob_url)

                if not blob_data.get('success'):
                    error_msg = blob_data.get('error', 'Unknown error')
                    logger.warning(
                        f"Blob fetch failed: {error_msg}",
                        extra_data={'blob_url': blob_url, 'attempt': attempt + 1}
                    )
                    last_error = error_msg
                    attempt += 1
                    await asyncio.sleep(min(2 ** attempt, self.config.retry_backoff_max))
                    continue

                # Decode Base64 data
                file_data = base64.b64decode(blob_data['data'])
                content_type = blob_data.get('type', content_type)

                # Strategy: Only activate auto-repair after 5 retries
                # First try to get complete file (best quality)
                if attempt < 5:
                    # Normal validation (without repair)
                    is_valid, validation_msg = self.validator.validate(file_data, content_type)

                    if not is_valid:
                        logger.warning(
                            f"Validation failed (attempt {attempt + 1}/5): {validation_msg}",
                            extra_data={'blob_url': blob_url, 'attempt': attempt + 1}
                        )
                        self.stats['validation_errors'] += 1
                        last_error = validation_msg
                        attempt += 1
                        await asyncio.sleep(min(2 ** attempt, self.config.retry_backoff_max))
                        continue

                    # Validation successful - use original data
                    repaired_data = file_data
                    was_repaired = False
                    repair_msg = validation_msg
                else:
                    # From attempt 6: activate auto-repair
                    repaired_data, was_repaired, repair_msg = self.validator.validate_and_repair(file_data, content_type)

                    # Log repair info
                    if was_repaired:
                        logger.warning(
                            f"Blob repaired after {attempt + 1} attempts: {repair_msg}",
                            extra_data={
                                'blob_url': blob_url,
                                'size_before': len(file_data),
                                'size_after': len(repaired_data),
                                'repair_message': repair_msg,
                                'attempt': attempt + 1
                            }
                        )

                # Calculate hash AFTER repair/validation
                file_hash = hashlib.sha256(repaired_data).hexdigest()

                # Determine filename
                ext = get_file_extension(content_type)
                filename = f"{file_hash}{ext}"

                # User-specific subfolder
                if user_id:
                    # Format: "Username_UUID" or just "UUID" if no username
                    if username:
                        # Sanitize username for filenames (remove invalid characters)
                        safe_username = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in username)
                        folder_name = f"{safe_username}_{user_id}"
                    else:
                        folder_name = user_id

                    user_dir = self.blobs_dir / folder_name
                    user_dir.mkdir(exist_ok=True)
                else:
                    # No user context - "unknown" folder
                    user_dir = self.blobs_dir / "unknown"
                    user_dir.mkdir(exist_ok=True)

                filepath = user_dir / filename

                # Check for duplicate
                is_duplicate = filepath.exists()

                # Save repaired file asynchronously
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(repaired_data)

                # Create BlobInfo (with user attribution + repair status)
                blob_info = BlobInfo(
                    blob_url=blob_url,
                    filename=filename,
                    filepath=filepath,
                    content_type=content_type,
                    size=len(repaired_data),  # Size AFTER repair
                    file_hash=file_hash,
                    is_duplicate=is_duplicate,
                    timestamp=datetime.now().isoformat(),
                    user_id=user_id,
                    username=username,
                    page_url=page_url,
                    was_repaired=was_repaired,
                    repair_message=repair_msg
                )

                self.downloaded_blobs.append(blob_info)
                self.stats['successful'] += 1

                if is_duplicate:
                    self.stats['duplicates'] += 1
                    logger.info(
                        f"Blob updated (duplicate): {filename}",
                        extra_data={'size': blob_data['size'], 'type': content_type}
                    )
                else:
                    logger.info(
                        f"Blob downloaded: {filename}",
                        extra_data={'size': blob_data['size'], 'type': content_type}
                    )

                return blob_info

            except Exception as e:
                logger.error(
                    f"Download error: {e}",
                    extra_data={'blob_url': blob_url, 'attempt': attempt + 1}
                )
                last_error = str(e)
                attempt += 1

                if attempt < self.config.max_retries:
                    # Exponential backoff with configurable base
                    wait_time = min(
                        self.config.retry_backoff_base ** attempt,
                        self.config.retry_backoff_max
                    )
                    logger.info(
                        f"Retry #{attempt + 1} in {wait_time:.1f}s",
                        extra_data={'blob_url': blob_url}
                    )
                    await asyncio.sleep(wait_time)

        # Max retries reached
        self.stats['failed'] += 1
        logger.error(
            f"Blob download failed after {self.config.max_retries} attempts",
            extra_data={'blob_url': blob_url, 'last_error': last_error}
        )
        return None

    async def queue_blob_download(
        self,
        blob_url: str,
        content_type: str = "",
        page_url: Optional[str] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None
    ) -> None:
        """
        Adds blob to download queue with content-type-based delay

        Args:
            blob_url: Blob URL
            content_type: MIME type
            page_url: Browser URL at time of download
            user_id: Snapchat User ID (UUID from URL)
            username: Snapchat Username (from DOM)
        """
        if blob_url in self.blob_urls:
            return  # Already in queue or downloaded

        self.blob_urls.add(blob_url)

        # Determine delay based on Content-Type
        if 'video' in content_type.lower():
            delay = self.config.delays.video
        elif 'image' in content_type.lower():
            delay = self.config.delays.image
        else:
            delay = self.config.delays.other

        # Wait before download
        await asyncio.sleep(delay)

        # Add to queue (with user attribution)
        await self.download_queue.put({
            'blob_url': blob_url,
            'content_type': content_type,
            'page_url': page_url,
            'user_id': user_id,
            'username': username,
            'timestamp': datetime.now().isoformat()
        })

    async def download_worker(self) -> None:
        """Worker for parallel blob downloads"""
        while True:
            try:
                # Get next download from queue
                blob_data = await self.download_queue.get()

                # Extract data from dictionary
                blob_url = blob_data['blob_url']
                content_type = blob_data['content_type']
                page_url = blob_data.get('page_url')
                user_id = blob_data.get('user_id')
                username = blob_data.get('username')

                self.active_downloads += 1
                logger.debug(
                    f"Starting download",
                    extra_data={
                        'blob_url': blob_url,
                        'active': self.active_downloads,
                        'user_id': user_id
                    }
                )

                # Perform download (with user attribution)
                await self.download_blob(
                    blob_url,
                    content_type,
                    page_url=page_url,
                    user_id=user_id,
                    username=username
                )

            except asyncio.CancelledError:
                logger.info("Download worker stopped")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
            finally:
                self.active_downloads -= 1
                self.download_queue.task_done()

    async def start_workers(self) -> list[asyncio.Task]:
        """Starts download workers"""
        workers = []
        for i in range(self.max_parallel):
            worker = asyncio.create_task(self.download_worker())
            workers.append(worker)
            logger.info(f"Download worker #{i + 1} started")
        return workers

    async def stop_workers(self, workers: list[asyncio.Task]) -> None:
        """Stops download workers gracefully"""
        logger.info("Waiting for active downloads...")

        # Wait until queue is empty
        await self.download_queue.join()

        # Cancel all workers
        for worker in workers:
            worker.cancel()

        # Wait for termination
        await asyncio.gather(*workers, return_exceptions=True)

        logger.info("All download workers stopped")

    def get_statistics(self) -> Dict[str, Any]:
        """Returns download statistics"""
        unique_count = len([b for b in self.downloaded_blobs if not b.is_duplicate])

        return {
            **self.stats,
            'unique_downloads': unique_count,
            'total_blobs': len(self.downloaded_blobs),
            'queue_size': self.download_queue.qsize(),
            'active_downloads': self.active_downloads
        }

