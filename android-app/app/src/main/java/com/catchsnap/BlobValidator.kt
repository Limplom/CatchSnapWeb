package com.catchsnap

import com.catchsnap.models.ValidationResult

/**
 * Validates blob data to ensure files are complete and valid.
 * Ported from Python traffic_recorder.py:143-213
 */
object BlobValidator {

    /**
     * Validates blob data based on content type
     * @param data The blob file data as ByteArray
     * @param contentType The MIME type of the blob
     * @return ValidationResult with isValid flag and message
     */
    fun validate(data: ByteArray, contentType: String): ValidationResult {
        // Minimum size check
        if (data.size < 100) {
            return ValidationResult(false, "Datei zu klein (< 100 bytes)")
        }

        val contentTypeBase = contentType.split(';')[0].trim()

        return when (contentTypeBase) {
            "image/jpeg" -> validateJpeg(data)
            "image/png" -> validatePng(data)
            "image/gif" -> validateGif(data)
            "image/webp" -> validateWebP(data)
            "video/mp4" -> validateMp4(data)
            "video/webm" -> validateWebM(data)
            else -> ValidationResult(true, "OK") // Unknown types pass through
        }
    }

    /**
     * Validate JPEG image
     * Start: FF D8 FF
     * End: FF D9
     */
    private fun validateJpeg(data: ByteArray): ValidationResult {
        // Check start marker: FF D8 FF
        if (data.size < 3 ||
            data[0] != 0xFF.toByte() ||
            data[1] != 0xD8.toByte() ||
            data[2] != 0xFF.toByte()) {
            return ValidationResult(false, "JPEG: Ungültiger Start (FF D8 FF fehlt)")
        }

        // Check end marker: FF D9
        if (data.size < 2 ||
            data[data.size - 2] != 0xFF.toByte() ||
            data[data.size - 1] != 0xD9.toByte()) {
            return ValidationResult(false, "JPEG: Unvollständig (FF D9 End-Marker fehlt)")
        }

        return ValidationResult(true, "OK")
    }

    /**
     * Validate PNG image
     * Start: 89 50 4E 47 0D 0A 1A 0A (PNG signature)
     * End: IEND chunk must be present
     */
    private fun validatePng(data: ByteArray): ValidationResult {
        // Check PNG signature: 89 50 4E 47 0D 0A 1A 0A
        val pngSignature = byteArrayOf(
            0x89.toByte(), 0x50, 0x4E, 0x47,
            0x0D, 0x0A, 0x1A.toByte(), 0x0A
        )

        if (data.size < 8 || !data.startsWith(pngSignature)) {
            return ValidationResult(false, "PNG: Ungültiger Start")
        }

        // Check for IEND chunk in last 12 bytes
        val iendBytes = "IEND".toByteArray()
        val last12 = data.slice(maxOf(0, data.size - 12) until data.size).toByteArray()

        if (!last12.containsSequence(iendBytes)) {
            return ValidationResult(false, "PNG: Unvollständig (IEND chunk fehlt)")
        }

        return ValidationResult(true, "OK")
    }

    /**
     * Validate GIF image
     * Start: GIF87a or GIF89a
     * End: 3B (semicolon trailer)
     */
    private fun validateGif(data: ByteArray): ValidationResult {
        // Check GIF signature
        val gif87a = "GIF87a".toByteArray()
        val gif89a = "GIF89a".toByteArray()

        if (data.size < 6 ||
            !(data.startsWith(gif87a) || data.startsWith(gif89a))) {
            return ValidationResult(false, "GIF: Ungültiger Start")
        }

        // Check trailer: 3B
        if (data.isEmpty() || data[data.size - 1] != 0x3B.toByte()) {
            return ValidationResult(false, "GIF: Unvollständig (Trailer fehlt)")
        }

        return ValidationResult(true, "OK")
    }

    /**
     * Validate WebP image
     * Must contain RIFF header and WEBP signature
     */
    private fun validateWebP(data: ByteArray): ValidationResult {
        // Check RIFF header
        val riff = "RIFF".toByteArray()
        if (data.size < 4 || !data.startsWith(riff)) {
            return ValidationResult(false, "WebP: Ungültiger Start (RIFF fehlt)")
        }

        // Check WEBP signature within first 20 bytes
        val webp = "WEBP".toByteArray()
        val first20 = data.slice(0 until minOf(20, data.size)).toByteArray()

        if (!first20.containsSequence(webp)) {
            return ValidationResult(false, "WebP: Ungültige Struktur")
        }

        return ValidationResult(true, "OK")
    }

    /**
     * Validate MP4 video
     * Must contain ftyp box and moov box
     */
    private fun validateMp4(data: ByteArray): ValidationResult {
        // Check for ftyp box in first 20 bytes
        val ftyp = "ftyp".toByteArray()
        val first20 = data.slice(0 until minOf(20, data.size)).toByteArray()

        if (!first20.containsSequence(ftyp)) {
            return ValidationResult(false, "MP4: Ungültiger Start (ftyp fehlt)")
        }

        // Check for moov box (essential for video playback)
        val moov = "moov".toByteArray()
        if (!data.containsSequence(moov)) {
            return ValidationResult(false, "MP4: Unvollständig (moov box fehlt)")
        }

        // Videos should be reasonably large
        if (data.size < 1000) {
            return ValidationResult(false, "MP4: Datei zu klein für Video")
        }

        return ValidationResult(true, "OK")
    }

    /**
     * Validate WebM video
     * Must start with EBML header: 1A 45 DF A3
     */
    private fun validateWebM(data: ByteArray): ValidationResult {
        // Check EBML header
        val ebmlHeader = byteArrayOf(0x1A, 0x45.toByte(), 0xDF.toByte(), 0xA3.toByte())

        if (data.size < 4 || !data.startsWith(ebmlHeader)) {
            return ValidationResult(false, "WebM: Ungültiger EBML Header")
        }

        // Videos should be reasonably large
        if (data.size < 1000) {
            return ValidationResult(false, "WebM: Datei zu klein für Video")
        }

        return ValidationResult(true, "OK")
    }

    // Helper extensions
    private fun ByteArray.startsWith(prefix: ByteArray): Boolean {
        if (this.size < prefix.size) return false
        for (i in prefix.indices) {
            if (this[i] != prefix[i]) return false
        }
        return true
    }

    private fun ByteArray.containsSequence(sequence: ByteArray): Boolean {
        if (sequence.isEmpty()) return true
        if (this.size < sequence.size) return false

        for (i in 0..(this.size - sequence.size)) {
            var found = true
            for (j in sequence.indices) {
                if (this[i + j] != sequence[j]) {
                    found = false
                    break
                }
            }
            if (found) return true
        }
        return false
    }
}
