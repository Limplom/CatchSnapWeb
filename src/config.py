"""
Configuration system for CatchSnapWeb Traffic Recorder
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import yaml


@dataclass
class BrowserConfig:
    """Browser-specific settings"""
    default: str = "chrome"
    headless: bool = False
    viewport_width: int = 1080
    viewport_height: int = 720
    viewport_responsive: bool = True  # true = passt sich an Fenstergröße an
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


@dataclass
class DownloadDelays:
    """Delays for different Content-Types"""
    video: float = 0.0
    image: float = 0.0
    other: float = 0.0


@dataclass
class DownloadConfig:
    """Download-specific settings"""
    blob_download_enabled: bool = True
    download_dir: str = "Downloads"  # Zentraler Download-Ordner
    max_retries: int = 8
    retry_backoff_max: int = 15  # Sekunden
    retry_backoff_base: float = 2.0  # Basis-Delay zwischen Retries
    chunk_size: int = 65536  # 64KB
    parallel_downloads: int = 3
    settle_time: float = 8.0  # Wartezeit VOR Queue-Hinzufügung
    delays: DownloadDelays = field(default_factory=DownloadDelays)


@dataclass
class ValidationConfig:
    """Validation settings"""
    min_file_size: int = 100  # Bytes
    validate_formats: bool = True


@dataclass
class StorageConfig:
    """Storage settings"""
    output_dir: str = "traffic_logs"
    auto_save_interval: int = 60  # Sekunden
    log_rotation_size: int = 50  # MB
    min_free_space: int = 1024  # MB


@dataclass
class FilterConfig:
    """Filter settings"""
    enabled: bool = False
    domain_whitelist: List[str] = field(default_factory=list)
    domain_blacklist: List[str] = field(default_factory=list)
    content_types: List[str] = field(default_factory=list)


@dataclass
class LoggingConfig:
    """Logging settings"""
    level: str = "INFO"
    format: str = "json"
    console_output: bool = True
    file_output: bool = True


@dataclass
class SessionConfig:
    """Session settings"""
    timeout: int = 3600  # Sekunden (0 = kein Timeout)


@dataclass
class FeaturesConfig:
    """Feature-Flags"""
    har_recording: bool = True
    metadata_extraction: bool = False
    progress_bar: bool = True
    csv_export: bool = False


@dataclass
class Config:
    """Main configuration class"""
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    downloads: DownloadConfig = field(default_factory=DownloadConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'Config':
        """Loads configuration from YAML file"""
        if not yaml_path.exists():
            return cls()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # Erstelle Sub-Configs
        browser_data = data.get('browser', {}).copy()
        # Extrahiere viewport-Daten
        viewport = browser_data.pop('viewport', {})
        browser_config = BrowserConfig(
            default=browser_data.get('default', 'chrome'),
            headless=browser_data.get('headless', False),
            viewport_width=viewport.get('width', 1080),
            viewport_height=viewport.get('height', 720),
            viewport_responsive=viewport.get('responsive', True),
            user_agent=browser_data.get('user_agent', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        )

        download_delays = DownloadDelays(
            **data.get('downloads', {}).get('delays', {})
        )
        download_data = data.get('downloads', {}).copy()
        download_data.pop('delays', None)
        download_config = DownloadConfig(
            **download_data,
            delays=download_delays
        )

        validation_config = ValidationConfig(
            **data.get('validation', {})
        )

        storage_config = StorageConfig(
            **data.get('storage', {})
        )

        filter_config = FilterConfig(
            **data.get('filters', {})
        )

        logging_config = LoggingConfig(
            **data.get('logging', {})
        )

        session_config = SessionConfig(
            **data.get('session', {})
        )

        features_config = FeaturesConfig(
            **data.get('features', {})
        )

        return cls(
            browser=browser_config,
            downloads=download_config,
            validation=validation_config,
            storage=storage_config,
            filters=filter_config,
            logging=logging_config,
            session=session_config,
            features=features_config
        )

    @classmethod
    def from_env(cls, base_config: Optional['Config'] = None) -> 'Config':
        """Overrides configuration with environment variables"""
        config = base_config or cls()

        # Browser-Einstellungen
        if env_browser := os.getenv('CATCHSNAP_BROWSER'):
            config.browser.default = env_browser
        if env_headless := os.getenv('CATCHSNAP_HEADLESS'):
            config.browser.headless = env_headless.lower() == 'true'

        # Download-Einstellungen
        if env_max_retries := os.getenv('CATCHSNAP_MAX_RETRIES'):
            config.downloads.max_retries = int(env_max_retries)
        if env_parallel := os.getenv('CATCHSNAP_PARALLEL_DOWNLOADS'):
            config.downloads.parallel_downloads = int(env_parallel)

        # Storage
        if env_output := os.getenv('CATCHSNAP_OUTPUT_DIR'):
            config.storage.output_dir = env_output

        # Logging
        if env_log_level := os.getenv('CATCHSNAP_LOG_LEVEL'):
            config.logging.level = env_log_level.upper()

        return config

    @classmethod
    def load(cls, yaml_path: Optional[Path] = None) -> 'Config':
        """
        Loads configuration with the following priority:
        1. Environment variables (highest priority)
        2. YAML file
        3. Default values (lowest priority)
        """
        # Default path for config file
        if yaml_path is None:
            yaml_path = Path(__file__).parent.parent / "config" / "default_config.yaml"

        # Load YAML (or use defaults)
        config = cls.from_yaml(yaml_path)

        # Override with environment variables
        config = cls.from_env(config)

        return config

    def to_yaml(self, yaml_path: Path) -> None:
        """Saves configuration as YAML file"""
        data = {
            'browser': {
                'default': self.browser.default,
                'headless': self.browser.headless,
                'viewport': {
                    'width': self.browser.viewport_width,
                    'height': self.browser.viewport_height
                }
            },
            'downloads': {
                'blob_download_enabled': self.downloads.blob_download_enabled,
                'max_retries': self.downloads.max_retries,
                'retry_backoff_max': self.downloads.retry_backoff_max,
                'chunk_size': self.downloads.chunk_size,
                'parallel_downloads': self.downloads.parallel_downloads,
                'delays': {
                    'video': self.downloads.delays.video,
                    'image': self.downloads.delays.image,
                    'other': self.downloads.delays.other
                }
            },
            'validation': {
                'min_file_size': self.validation.min_file_size,
                'validate_formats': self.validation.validate_formats
            },
            'storage': {
                'output_dir': self.storage.output_dir,
                'auto_save_interval': self.storage.auto_save_interval,
                'log_rotation_size': self.storage.log_rotation_size,
                'min_free_space': self.storage.min_free_space
            },
            'filters': {
                'enabled': self.filters.enabled,
                'domain_whitelist': self.filters.domain_whitelist,
                'domain_blacklist': self.filters.domain_blacklist,
                'content_types': self.filters.content_types
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'console_output': self.logging.console_output,
                'file_output': self.logging.file_output
            },
            'features': {
                'har_recording': self.features.har_recording,
                'metadata_extraction': self.features.metadata_extraction,
                'progress_bar': self.features.progress_bar,
                'csv_export': self.features.csv_export
            }
        }

        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
