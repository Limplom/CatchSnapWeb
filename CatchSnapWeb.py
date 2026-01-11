"""
CatchSnapWeb v2.0 - Browser Traffic Recorder for Snapchat Web
Main entry point with modular architecture
"""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src import (
    Config,
    setup_logging,
    get_logger,
    FileValidator,
    BlobDownloader,
    SessionManager,
    NetworkRecorder,
    RecorderUI,
    print_banner
)
from src.exceptions import BrowserLaunchError, CatchSnapException


# Global variable for graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler(sig, frame):
    """Signal handler for graceful shutdown"""
    print("\n\nCtrl+C detected - stopping session...")
    shutdown_event.set()


class TrafficRecorderApp:
    """Main application for traffic recording"""

    def __init__(self, config: Config, browser_type: str, start_url: str):
        self.config = config
        self.browser_type = browser_type
        self.start_url = start_url

        # Setup Logging
        log_dir = Path(config.storage.output_dir) / "logs"
        self.logger = setup_logging(
            log_level=config.logging.level,
            log_format=config.logging.format,
            console_output=config.logging.console_output,
            file_output=config.logging.file_output,
            log_dir=log_dir
        )

        self.logger = get_logger('app')

        # Components
        self.session_manager: Optional[SessionManager] = None
        self.file_validator: Optional[FileValidator] = None
        self.blob_downloader: Optional[BlobDownloader] = None
        self.network_recorder: Optional[NetworkRecorder] = None
        self.ui: Optional[RecorderUI] = None

        # Browser components
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Cookie save task
        self.cookie_save_task: Optional[asyncio.Task] = None

        # Worker tasks
        self.download_workers: list = []

    async def initialize_components(self) -> None:
        """Initializes all components"""
        self.logger.info("Initializing components...")

        # Session Manager
        self.session_manager = SessionManager(
            self.config.storage,
            browser_name=self.browser_type
        )

        # File Validator
        self.file_validator = FileValidator(self.config.validation)

        # Blob Downloader (if enabled)
        if self.config.downloads.blob_download_enabled:
            # Download folder from config (relative or absolute)
            download_dir = Path(self.config.downloads.download_dir)

            # If relative path, relative to project directory
            if not download_dir.is_absolute():
                download_dir = Path.cwd() / download_dir

            download_dir.mkdir(exist_ok=True)

            self.blob_downloader = BlobDownloader(
                self.config.downloads,
                self.file_validator,
                download_dir
            )

        # Network Recorder
        self.network_recorder = NetworkRecorder(
            self.session_manager,
            self.blob_downloader,
            self.config.filters
        )

        # UI
        if self.config.features.progress_bar:
            self.ui = RecorderUI(self.browser_type, self.start_url)

        self.logger.info("Components successfully initialized")

    async def launch_browser(self) -> None:
        """Launches the browser"""
        self.logger.info(f"Starting browser: {self.browser_type}")

        async with async_playwright() as p:
            try:
                browser_launcher, launch_options = self._get_browser_config(p)

                # Launch browser
                self.browser = await browser_launcher.launch(**launch_options)

                # Context options
                context_options = {
                    "user_agent": self.config.browser.user_agent
                }

                # Viewport configuration
                if self.config.browser.viewport_responsive:
                    # no_viewport = True makes page adapt to window size
                    context_options["no_viewport"] = True
                else:
                    # Fixed viewport size
                    context_options["viewport"] = {
                        "width": self.config.browser.viewport_width,
                        "height": self.config.browser.viewport_height
                    }

                # Cookie persistence: Load saved cookies
                cookie_file = Path("browser_cookies.json")
                if cookie_file.exists():
                    try:
                        context_options["storage_state"] = str(cookie_file)
                        self.logger.info("Browser state loaded (Cookies & LocalStorage)")
                    except Exception as e:
                        self.logger.warning(f"Error loading browser state: {e}")

                # HAR recording (if enabled)
                if self.config.features.har_recording:
                    har_path = self.session_manager.output_dir / "session.har"
                    context_options["record_har_path"] = str(har_path)
                    self.logger.info(f"HAR recording enabled: {har_path}")

                # Create browser context
                self.context = await self.browser.new_context(**context_options)
                self.page = await self.context.new_page()

                # Set page reference (for blob downloads and user attribution)
                if self.blob_downloader:
                    self.blob_downloader.set_page(self.page)
                if self.network_recorder:
                    self.network_recorder.set_page(self.page)

                # Register event listeners
                self.page.on("request", self.network_recorder.on_request)
                self.page.on("response", self.network_recorder.on_response)

                self.logger.info("Browser started successfully")

                # Start session
                await self.run_session()

            except Exception as e:
                self.logger.error(f"Error starting browser: {e}")
                raise BrowserLaunchError(f"Could not start browser: {e}")

            finally:
                await self.cleanup()

    def _get_browser_config(self, playwright):
        """Returns browser launcher and launch options"""
        launch_options = {"headless": self.config.browser.headless}

        if self.browser_type == "firefox":
            return playwright.firefox, launch_options

        elif self.browser_type == "webkit":
            return playwright.webkit, launch_options

        elif self.browser_type == "brave":
            # Brave browser paths
            brave_paths = [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe")
            ]
            for path in brave_paths:
                if os.path.exists(path):
                    launch_options["executable_path"] = path
                    break
            return playwright.chromium, launch_options

        elif self.browser_type == "chrome":
            launch_options["channel"] = "chrome"
            return playwright.chromium, launch_options

        elif self.browser_type == "msedge":
            launch_options["channel"] = "msedge"
            return playwright.chromium, launch_options

        else:  # chromium (default)
            return playwright.chromium, launch_options

    async def _periodic_cookie_save(self) -> None:
        """Saves browser state periodically (every 60 seconds)"""
        try:
            while True:
                await asyncio.sleep(60)  # Every 60 seconds
                if self.context:
                    try:
                        cookie_file = Path("browser_cookies.json")
                        await self.context.storage_state(path=str(cookie_file))
                        self.logger.debug("Browser state automatically saved")
                    except Exception as e:
                        self.logger.debug(f"Error auto-saving cookies: {e}")
        except asyncio.CancelledError:
            self.logger.debug("Periodic cookie saving stopped")

    async def run_session(self) -> None:
        """Runs browser session"""
        try:
            # Show UI header
            if self.ui:
                self.ui.print_ready_message()

            # Start download workers
            if self.blob_downloader:
                self.download_workers = await self.blob_downloader.start_workers()
                self.logger.info(f"{len(self.download_workers)} download workers started")

            # Start auto-save
            self.session_manager.start_auto_save(
                lambda: self.blob_downloader.get_statistics() if self.blob_downloader else {},
                lambda: [b.to_dict() for b in self.blob_downloader.downloaded_blobs] if self.blob_downloader else [],
                lambda: self.blob_downloader.downloaded_blobs if self.blob_downloader else []
            )

            # Start periodic cookie saving (every 60 seconds)
            self.cookie_save_task = asyncio.create_task(self._periodic_cookie_save())

            # Navigate to start URL
            self.logger.info(f"Navigating to {self.start_url}")
            # Snapchat loads continuously - use "domcontentloaded" instead of "networkidle"
            await self.page.goto(self.start_url, wait_until="domcontentloaded", timeout=60000)

            print(f"\n{'='*80}")
            print("✓ Browser is ready. You can now manually navigate.")
            print("Press Ctrl+C to stop and save logs...")
            if self.config.session.timeout > 0:
                timeout_mins = self.config.session.timeout / 60
                print(f"⏱️  Session timeout: {timeout_mins:.0f} minutes")
            else:
                print("⏱️  Session timeout: Disabled (runs until Ctrl+C)")
            print(f"{'='*80}\n")

            # Wait for shutdown signal or timeout
            timeout_seconds = self.config.session.timeout
            try:
                if timeout_seconds > 0:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=timeout_seconds
                    )
                else:
                    # No timeout - wait indefinitely for signal
                    await shutdown_event.wait()
            except asyncio.TimeoutError:
                self.logger.info("Session timeout reached")

        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt - stopping session")

        except Exception as e:
            self.logger.error(f"Error during session: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleans up all resources"""
        self.logger.info("Starting cleanup...")

        try:
            # CRITICAL: Cancel pending settle tasks FIRST (before browser closes!)
            if self.network_recorder:
                await self.network_recorder.cancel_pending_settle_tasks()

            # Stop periodic cookie saving
            if self.cookie_save_task:
                self.cookie_save_task.cancel()
                try:
                    await self.cookie_save_task
                except asyncio.CancelledError:
                    pass

            # Save browser state one last time (Cookies + LocalStorage)
            if self.context:
                try:
                    cookie_file = Path("browser_cookies.json")
                    await self.context.storage_state(path=str(cookie_file))
                    self.logger.info(f"Browser state finally saved to {cookie_file}")
                except Exception as e:
                    self.logger.warning(f"Error saving browser state finally: {e}")
                    # If this fails, the periodic task version should still exist

            # Stop auto-save
            if self.session_manager:
                await self.session_manager.stop_auto_save()

            # Stop download workers
            if self.blob_downloader and self.download_workers:
                await self.blob_downloader.stop_workers(self.download_workers)

            # Save final data
            if self.ui:
                self.ui.print_save_message()

            if self.session_manager and self.blob_downloader:
                blob_stats = self.blob_downloader.get_statistics()
                blobs_info = [b.to_dict() for b in self.blob_downloader.downloaded_blobs]
                downloaded_blobs = self.blob_downloader.downloaded_blobs

                await self.session_manager.save_all(
                    blob_stats,
                    blobs_info,
                    downloaded_blobs
                )

            # Show statistics
            if self.ui and self.network_recorder:
                stats = self.network_recorder.get_statistics()
                self.ui.print_statistics(stats)
                self.ui.print_completion_message(str(self.session_manager.output_dir))

            # Close browser
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()

            self.logger.info("Cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


async def main(browser_type: str = "chrome", start_url: str = "https://www.snapchat.com/web"):
    """
    Main function

    Args:
        browser_type: Browser type (chrome, firefox, etc.)
        start_url: Start URL
    """
    # Load configuration
    config = Config.load()

    # Show banner
    if config.features.progress_bar:
        print_banner()

    print("="*80)
    print(f"Browser: {browser_type.upper()}")
    print(f"Start URL: {start_url}")
    print("="*80)
    if config.downloads.blob_download_enabled:
        print("🔥 BLOB DOWNLOAD ENABLED (Snapchat blobs only)")
        print("="*80)

    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Create and start app
    app = TrafficRecorderApp(config, browser_type, start_url)

    try:
        await app.initialize_components()
        await app.launch_browser()

    except CatchSnapException as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Parse command-line arguments
    BROWSER = sys.argv[1].lower() if len(sys.argv) > 1 else "chrome"
    START_URL = sys.argv[2] if len(sys.argv) > 2 else "https://www.snapchat.com/web"

    # Start application
    asyncio.run(main(BROWSER, START_URL))
