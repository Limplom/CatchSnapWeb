package com.catchsnap.models

data class BlobData(
    val blobUrl: String,
    val filename: String,
    val filepath: String,
    val contentType: String,
    val size: Int,
    val hash: String,
    val duplicate: Boolean,
    val timestamp: String
)

data class ValidationResult(
    val isValid: Boolean,
    val message: String
)
