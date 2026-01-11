"""
File validation for various media formats
"""

from typing import Tuple, Optional
from .config import ValidationConfig
from .exceptions import BlobValidationError
from .logging_config import get_logger

logger = get_logger('file_validator')


class FileValidator:
    """Validates downloaded blob files for completeness"""

    def __init__(self, config: ValidationConfig):
        self.config = config

    def validate(self, file_data: bytes, content_type: str) -> Tuple[bool, str]:
        """
        Validates file data based on Content-Type

        Args:
            file_data: Raw file bytes
            content_type: MIME type of the file

        Returns:
            Tuple (is_valid, message)
        """
        if not self.config.validate_formats:
            return True, "Validation disabled"

        # Minimum size check
        if len(file_data) < self.config.min_file_size:
            msg = f"File too small (< {self.config.min_file_size} bytes)"
            logger.warning(msg, extra_data={'size': len(file_data)})
            return False, msg

        # Content-Type without parameters
        content_type_base = content_type.split(';')[0].strip()

        # Format-specific validation
        validators = {
            'image/jpeg': self._validate_jpeg,
            'image/jpg': self._validate_jpeg,
            'image/png': self._validate_png,
            'image/gif': self._validate_gif,
            'image/webp': self._validate_webp,
            'video/mp4': self._validate_mp4,
            'video/webm': self._validate_webm,
        }

        validator = validators.get(content_type_base)
        if validator:
            try:
                return validator(file_data)
            except Exception as e:
                logger.error(f"Validation error for {content_type_base}: {e}")
                return False, f"Validation error: {e}"

        # No specific validator - accept file
        return True, "No specific validator (accepted)"

    def validate_and_repair(self, file_data: bytes, content_type: str) -> Tuple[bytes, bool, str]:
        """
        Validates and repairs file data automatically

        Args:
            file_data: Raw file bytes
            content_type: MIME type of the file

        Returns:
            Tuple (repaired_data, was_repaired, message)
            - repaired_data: Repaired data (or original)
            - was_repaired: True if repair was performed
            - message: Description (e.g., "JPEG: Repaired (added EOI marker)")
        """
        if not self.config.validate_formats:
            return file_data, False, "Validation disabled"

        # Minimum size check (without repair)
        if len(file_data) < self.config.min_file_size:
            msg = f"File too small (< {self.config.min_file_size} bytes)"
            logger.warning(msg, extra_data={'size': len(file_data)})
            return file_data, False, msg

        content_type_base = content_type.split(';')[0].strip()

        # Format-specific validation + repair
        repair_validators = {
            'image/jpeg': self._validate_and_repair_jpeg,
            'image/jpg': self._validate_and_repair_jpeg,
            'image/png': self._validate_and_repair_png,
            'image/gif': self._validate_and_repair_gif,
            'image/webp': self._validate_and_repair_webp,
            'video/mp4': self._validate_and_repair_mp4,
            'video/webm': self._validate_and_repair_webm,
        }

        validator = repair_validators.get(content_type_base)
        if validator:
            try:
                return validator(file_data)
            except Exception as e:
                logger.error(f"Repair error for {content_type_base}: {e}")
                return file_data, False, f"Repair error: {e}"

        # No specific validator
        return file_data, False, "No specific validator"

    def _validate_jpeg(self, data: bytes) -> Tuple[bool, str]:
        """
        Validates JPEG files

        JPEG structure:
        - Start: FF D8 FF (SOI + APP0/APP1)
        - End: FF D9 (EOI)
        """
        if not data.startswith(b'\xFF\xD8\xFF'):
            return False, "JPEG: Invalid start (FF D8 FF missing)"

        if not data.endswith(b'\xFF\xD9'):
            return False, "JPEG: Incomplete (FF D9 end marker missing)"

        return True, "JPEG: OK"

    def _validate_png(self, data: bytes) -> Tuple[bool, str]:
        """
        Validates PNG files

        PNG structure:
        - Start: 89 50 4E 47 0D 0A 1A 0A (PNG signature)
        - End: IEND chunk
        """
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return False, "PNG: Invalid start"

        # IEND chunk should be at the end
        if b'IEND' not in data[-12:]:
            return False, "PNG: Incomplete (IEND chunk missing)"

        return True, "PNG: OK"

    def _validate_gif(self, data: bytes) -> Tuple[bool, str]:
        """
        Validates GIF files

        GIF structure:
        - Start: GIF87a or GIF89a
        - End: 3B (Trailer)
        """
        if not (data.startswith(b'GIF87a') or data.startswith(b'GIF89a')):
            return False, "GIF: Invalid start"

        if not data.endswith(b'\x3B'):
            return False, "GIF: Incomplete (trailer missing)"

        return True, "GIF: OK"

    def _validate_webp(self, data: bytes) -> Tuple[bool, str]:
        """
        Validates WebP files

        WebP structure:
        - Start: RIFF....WEBP
        """
        if not data.startswith(b'RIFF'):
            return False, "WebP: Invalid start (RIFF missing)"

        if b'WEBP' not in data[:20]:
            return False, "WebP: Invalid structure (WEBP header missing)"

        return True, "WebP: OK"

    def _validate_mp4(self, data: bytes) -> Tuple[bool, str]:
        """
        Validates MP4 files

        MP4 structure:
        - Start: ftyp box (within first 20 bytes)
        - Must contain moov box (Movie Header)
        """
        # Videos should have a minimum size
        if len(data) < 1000:
            return False, "MP4: File too small for video"

        if b'ftyp' not in data[:20]:
            return False, "MP4: Invalid start (ftyp missing)"

        # Check for essential boxes
        if b'moov' not in data:
            return False, "MP4: Incomplete (moov box missing)"

        return True, "MP4: OK"

    def _validate_webm(self, data: bytes) -> Tuple[bool, str]:
        """
        Validates WebM files

        WebM structure:
        - Start: EBML Header (1A 45 DF A3)
        """
        # Videos should have a minimum size
        if len(data) < 1000:
            return False, "WebM: File too small for video"

        if not data.startswith(b'\x1a\x45\xdf\xa3'):
            return False, "WebM: Invalid EBML header"

        return True, "WebM: OK"

    def _validate_and_repair_jpeg(self, data: bytes) -> Tuple[bytes, bool, str]:
        """Validates and repairs JPEG files"""
        # Check start marker (not repairable)
        if not data.startswith(b'\xFF\xD8\xFF'):
            return data, False, "JPEG: Invalid start (FF D8 FF missing) - NOT REPAIRABLE"

        # Check end marker and add if necessary
        if not data.endswith(b'\xFF\xD9'):
            repaired_data = data + b'\xFF\xD9'
            logger.info("JPEG: End marker (FF D9) added", extra_data={'size_before': len(data), 'size_after': len(repaired_data)})
            return repaired_data, True, "JPEG: Repaired (added EOI marker FF D9)"

        return data, False, "JPEG: OK"

    def _validate_and_repair_png(self, data: bytes) -> Tuple[bytes, bool, str]:
        """Validates and repairs PNG files"""
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return data, False, "PNG: Invalid start - NOT REPAIRABLE"

        # Check IEND chunk and add if necessary
        if b'IEND' not in data[-12:]:
            # IEND chunk: length(4) + 'IEND'(4) + CRC(4)
            iend_chunk = b'\x00\x00\x00\x00' + b'IEND' + b'\xAE\x42\x60\x82'
            repaired_data = data + iend_chunk
            logger.info("PNG: IEND chunk added", extra_data={'size_before': len(data), 'size_after': len(repaired_data)})
            return repaired_data, True, "PNG: Repaired (added IEND chunk)"

        return data, False, "PNG: OK"

    def _validate_and_repair_gif(self, data: bytes) -> Tuple[bytes, bool, str]:
        """Validates and repairs GIF files"""
        if not (data.startswith(b'GIF87a') or data.startswith(b'GIF89a')):
            return data, False, "GIF: Invalid start - NOT REPAIRABLE"

        # Check trailer and add if necessary
        if not data.endswith(b'\x3B'):
            repaired_data = data + b'\x3B'
            logger.info("GIF: Trailer (3B) added", extra_data={'size_before': len(data), 'size_after': len(repaired_data)})
            return repaired_data, True, "GIF: Repaired (added trailer 3B)"

        return data, False, "GIF: OK"

    def _validate_and_repair_webp(self, data: bytes) -> Tuple[bytes, bool, str]:
        """Validates WebP files (no repair possible)"""
        if not data.startswith(b'RIFF'):
            return data, False, "WebP: Invalid start (RIFF missing)"

        if b'WEBP' not in data[:20]:
            logger.warning("WebP: Incomplete but saved", extra_data={'size': len(data)})
            return data, False, "WebP: Incomplete but saved"

        return data, False, "WebP: OK"

    def _validate_and_repair_mp4(self, data: bytes) -> Tuple[bytes, bool, str]:
        """Validates MP4 files (no repair possible)"""
        if len(data) < 1000:
            return data, False, "MP4: File too small"

        if b'ftyp' not in data[:20]:
            return data, False, "MP4: Invalid start (ftyp missing)"

        # moov box missing - too complex to repair
        if b'moov' not in data:
            logger.warning("MP4: Incomplete (moov box missing) but saved", extra_data={'size': len(data)})
            return data, False, "MP4: Incomplete (missing moov) but saved"

        return data, False, "MP4: OK"

    def _validate_and_repair_webm(self, data: bytes) -> Tuple[bytes, bool, str]:
        """Validates WebM files (no repair possible)"""
        if len(data) < 1000:
            return data, False, "WebM: File too small"

        if not data.startswith(b'\x1a\x45\xdf\xa3'):
            logger.warning("WebM: Invalid EBML header but saved")
            return data, False, "WebM: Invalid EBML but saved"

        return data, False, "WebM: OK"


def get_file_extension(content_type: str) -> str:
    """
    Determines file extension based on Content-Type

    Args:
        content_type: MIME type

    Returns:
        File extension with dot (e.g., ".jpg")
    """
    extensions = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/svg+xml': '.svg',
        'video/mp4': '.mp4',
        'video/webm': '.webm',
        'video/ogg': '.ogg',
        'audio/mpeg': '.mp3',
        'audio/ogg': '.ogg',
        'audio/wav': '.wav',
        'application/javascript': '.js',
        'application/json': '.json',
        'text/html': '.html',
        'text/css': '.css',
        'text/plain': '.txt'
    }
    return extensions.get(content_type.split(';')[0].strip(), '.bin')
