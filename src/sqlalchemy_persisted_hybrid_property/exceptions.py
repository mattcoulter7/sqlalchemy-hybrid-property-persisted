from __future__ import annotations


class PersistedHybridError(Exception):
    """Base exception for persisted hybrid configuration/runtime errors."""


class PersistedHybridConfigurationError(PersistedHybridError):
    """Raised when a persisted hybrid cannot be configured."""


class PersistedColumnConflictError(PersistedHybridConfigurationError):
    """Raised when the requested persisted column already exists."""


class DependencyConfigurationError(PersistedHybridConfigurationError):
    """Raised when dependency configuration is invalid."""


class DependencyAmbiguityError(DependencyConfigurationError):
    """Raised when automatic dependency resolution has multiple valid paths."""


class TypeInferenceError(PersistedHybridConfigurationError):
    """Raised when a column type cannot be inferred."""


class BulkMutationUnsupportedError(PersistedHybridError):
    """Raised for ORM bulk DML that could stale persisted hybrid values."""
