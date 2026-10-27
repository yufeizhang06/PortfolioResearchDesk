"""Expected, user-actionable application errors."""


class ProjectError(Exception):
    """Base error handled at the CLI boundary without a traceback."""


class ConfigError(ProjectError):
    """Invalid or unreadable Phase 0 configuration."""


class SampleError(ProjectError):
    """Packaged synthetic sample is missing or invalid."""


class DataError(ProjectError):
    """Invalid, incomplete or unavailable research inputs."""


class ExecutionError(ProjectError):
    """An execution or accounting invariant cannot be satisfied."""


class ReportError(ProjectError):
    """An immutable run report cannot be written."""
