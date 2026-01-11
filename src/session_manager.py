"""
Session management with auto-save and storage monitoring
"""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import aiofiles

from .config import StorageConfig
from .exceptions import StorageError, DiskSpaceError, SessionError
from .logging_config import get_logger

logger = get_logger('session_manager')


class SessionManager:
    """Manages session folders, auto-save and storage monitoring"""

    def __init__(
        self,
        config: StorageConfig,
        browser_name: str = "unknown"
    ):
        self.config = config
        self.browser_name = browser_name
        self.session_start = datetime.now()

        # Create session folder
        self.base_output_dir = Path(config.output_dir)
        self.base_output_dir.mkdir(exist_ok=True)

        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        session_folder = f"{browser_name}_{timestamp}"

        self.output_dir = self.base_output_dir / session_folder
        self.output_dir.mkdir(exist_ok=True)

        self.blobs_dir = self.output_dir / "blobs"
        self.blobs_dir.mkdir(exist_ok=True)

        # Session data
        self.requests: List[Dict[str, Any]] = []
        self.responses: List[Dict[str, Any]] = []

        # Auto-save task
        self.auto_save_task: Optional[asyncio.Task] = None
        self.is_running = False

        logger.info(
            f"Session created",
            extra_data={'output_dir': str(self.output_dir), 'browser': browser_name}
        )

        # Check disk space
        self._check_disk_space()

    def _check_disk_space(self) -> None:
        """Checks available disk space"""
        try:
            stat = shutil.disk_usage(self.output_dir)
            free_mb = stat.free / (1024 * 1024)

            logger.info(
                f"Available disk space: {free_mb:.2f} MB",
                extra_data={'free_mb': free_mb}
            )

            if free_mb < self.config.min_free_space:
                warning = f"Warning: Only {free_mb:.2f} MB disk space available!"
                logger.warning(warning)
                print(f"\n⚠️  {warning}\n")

            if free_mb < 100:  # Critical: < 100 MB
                raise DiskSpaceError(
                    f"Insufficient disk space ({free_mb:.2f} MB available)",
                    {'free_mb': free_mb, 'required_mb': self.config.min_free_space}
                )

        except Exception as e:
            if isinstance(e, DiskSpaceError):
                raise
            logger.error(f"Error checking disk space: {e}")

    async def add_request(self, request_data: Dict[str, Any]) -> None:
        """Adds request to list"""
        self.requests.append(request_data)

    async def add_response(self, response_data: Dict[str, Any]) -> None:
        """Adds response to list"""
        self.responses.append(response_data)

    async def save_requests(self) -> Path:
        """Saves requests asynchronously"""
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        requests_file = self.output_dir / f"requests_{timestamp}.json"

        try:
            async with aiofiles.open(requests_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.requests, indent=2, ensure_ascii=False))

            logger.info(f"Requests saved: {requests_file}")
            return requests_file

        except Exception as e:
            logger.error(f"Error saving requests: {e}")
            raise StorageError(f"Error saving requests: {e}")

    async def save_responses(self) -> Path:
        """Saves responses asynchronously"""
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        responses_file = self.output_dir / f"responses_{timestamp}.json"

        try:
            async with aiofiles.open(responses_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.responses, indent=2, ensure_ascii=False))

            logger.info(f"Responses saved: {responses_file}")
            return responses_file

        except Exception as e:
            logger.error(f"Error saving responses: {e}")
            raise StorageError(f"Error saving responses: {e}")

    async def save_blobs_info(self, blobs_info: List[Dict[str, Any]]) -> Optional[Path]:
        """Saves blob information"""
        if not blobs_info:
            return None

        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        blobs_file = self.output_dir / f"downloaded_blobs_{timestamp}.json"

        try:
            async with aiofiles.open(blobs_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(blobs_info, indent=2, ensure_ascii=False))

            logger.info(f"Blob information saved: {blobs_file}")
            return blobs_file

        except Exception as e:
            logger.error(f"Error saving blob info: {e}")
            raise StorageError(f"Error saving blob info: {e}")

    async def save_summary(
        self,
        blob_stats: Dict[str, Any],
        downloaded_blobs: List[Any]
    ) -> Path:
        """Creates and saves session summary"""
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        summary_file = self.output_dir / f"summary_{timestamp}.json"

        # Calculate statistics
        unique_blobs = [b for b in downloaded_blobs if not b.is_duplicate]
        duplicate_count = len(downloaded_blobs) - len(unique_blobs)

        unique_domains = list(set([
            r["url"].split("/")[2] if len(r["url"].split("/")) > 2 else ""
            for r in self.requests
        ]))

        summary = {
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "browser": self.browser_name,
            "total_requests": len(self.requests),
            "total_responses": len(self.responses),
            "blobs": {
                "total_processed": len(downloaded_blobs),
                "unique_saved": len(unique_blobs),
                "duplicates_skipped": duplicate_count,
                **blob_stats
            },
            "unique_domains": unique_domains,
            "output_directory": str(self.output_dir)
        }

        try:
            async with aiofiles.open(summary_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(summary, indent=2, ensure_ascii=False))

            logger.info(f"Summary saved: {summary_file}")
            return summary_file

        except Exception as e:
            logger.error(f"Error saving summary: {e}")
            raise StorageError(f"Error saving summary: {e}")

    async def save_all(
        self,
        blob_stats: Dict[str, Any],
        blobs_info: List[Dict[str, Any]],
        downloaded_blobs: List[Any]
    ) -> None:
        """Saves all session data"""
        logger.info("Saving session data...")

        try:
            # Save in parallel
            await asyncio.gather(
                self.save_requests(),
                self.save_responses(),
                self.save_blobs_info(blobs_info),
                self.save_summary(blob_stats, downloaded_blobs)
            )

            # Statistics output
            unique_count = len([b for b in downloaded_blobs if not b.is_duplicate])
            duplicate_count = len(downloaded_blobs) - unique_count

            logger.info(
                "Session data saved successfully",
                extra_data={
                    'requests': len(self.requests),
                    'responses': len(self.responses),
                    'unique_blobs': unique_count,
                    'duplicates': duplicate_count
                }
            )

            # Console output for user
            print(f"\n{'='*80}")
            print(f"Session Summary:")
            print(f"  - {len(self.requests)} Requests")
            print(f"  - {len(self.responses)} Responses")
            print(f"  - {unique_count} unique blob(s)")
            if duplicate_count > 0:
                print(f"  - {duplicate_count} duplicate(s)")
            print(f"  - Output directory: {self.output_dir}")
            print(f"{'='*80}\n")

        except Exception as e:
            logger.error(f"Error saving session data: {e}")
            raise

    async def auto_save_loop(
        self,
        blob_stats_func,
        blobs_info_func,
        downloaded_blobs_func
    ) -> None:
        """Periodic auto-save"""
        interval = self.config.auto_save_interval

        logger.info(f"Auto-save enabled (every {interval} seconds)")

        while self.is_running:
            try:
                await asyncio.sleep(interval)

                logger.info("Running auto-save...")

                blob_stats = blob_stats_func()
                blobs_info = blobs_info_func()
                downloaded_blobs = downloaded_blobs_func()

                await self.save_all(blob_stats, blobs_info, downloaded_blobs)

                # Check disk space
                self._check_disk_space()

            except asyncio.CancelledError:
                logger.info("Auto-save stopped")
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")

    def start_auto_save(
        self,
        blob_stats_func,
        blobs_info_func,
        downloaded_blobs_func
    ) -> None:
        """Starts auto-save task"""
        self.is_running = True
        self.auto_save_task = asyncio.create_task(
            self.auto_save_loop(blob_stats_func, blobs_info_func, downloaded_blobs_func)
        )
        logger.info("Auto-save task started")

    async def stop_auto_save(self) -> None:
        """Stops auto-save task"""
        self.is_running = False

        if self.auto_save_task:
            self.auto_save_task.cancel()
            try:
                await self.auto_save_task
            except asyncio.CancelledError:
                pass

        logger.info("Auto-save task stopped")

    def get_session_info(self) -> Dict[str, Any]:
        """Returns session information"""
        return {
            'session_start': self.session_start.isoformat(),
            'browser': self.browser_name,
            'output_dir': str(self.output_dir),
            'requests_count': len(self.requests),
            'responses_count': len(self.responses)
        }
