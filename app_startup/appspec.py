from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Callable
from typing import Optional


@dataclass(frozen=True)
class ApplicationVersion(object):
    """
    Represents a specific version of an application.

    Attributes:
        version (str): Human-readable version identifier (e.g. '2023', '14.0v1').
        executable (Path): Full path to the application executable.
        python_paths (list[Path]): Python paths to inject.
        plugin_paths (list[Path]): Plugin paths to inject.
        env (dict[str, str]): Version-specific environment variables.
    """

    version: str
    executable: Path
    python_paths: list[Path] = field(default_factory=list)
    plugin_paths: list[Path] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationSpec(object):
    """
    Declarative specification for an application, with a table for each version.

    Attributes:
        name (str): Logical application name (e.g. 'maya', 'nuke').
        versions (dict[str, ApplicationVersion]): Mapping of version string to
            version definition.
        default_version (str): Default version key.
        env (dict[str, str]): Base environment variables for all versions.
        flight_checks (list[Callable[[], None]]): Optional pre-launch procedures.
    """

    name: str
    versions: dict[str, ApplicationVersion]
    default_version: str
    env: dict[str, str] = field(default_factory=dict)
    flight_checks: list[Callable[[], None]] = field(default_factory=list)

    def get_version(self, version: Optional[str] = None) -> ApplicationVersion:
        """Return the requested or default version definition."""
        if version is None:
            version = self.default_version
        if version not in self.versions:
            raise KeyError(
                f'Unknown version "{version}" for application "{self.name}".'
            )
        return self.versions[version]
