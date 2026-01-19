"""
Environment builder.

Constructs environment variables before launching DCC applications.
Handles PYTHONPATH construction, plugin paths, project context variables,
and custom environment modifiers.

The built environment is passed to the dcc launcher.
"""

import os
from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from enum import IntEnum
from typing import Optional


class DCCType(Enum):
    """Supported DCC applications."""

    MAYA = "maya"
    NUKE = "nuke"
    AFTER_EFFECTS = "after_effects"
    BLENDER = "blender"
    UNREAL = "unreal"


class DeveloperLevel(IntEnum):
    """Developer access levels."""

    USER = 1
    LEAD = 2
    SUPERVISOR = 3
    PIPELINE = 4


@dataclass
class EnvironmentConfig(object):
    """Configuration for building DCC environment."""

    pipeline_root: Path
    project_root: Path
    dcc_type: DCCType

    dcc_version: str = None
    developer_level: DeveloperLevel = DeveloperLevel.USER

    context: dict[str, str] = field(default_factory=dict)
    """Flexible context dict - gets converted to environment variables."""

    custom_vars: dict[str, str] = field(default_factory=dict)
    """Additional environment variables to set."""


class EnvironmentBuilder(object):
    """Builds environment variables for DCC launch."""

    def __init__(self, config: EnvironmentConfig) -> None:
        self.config = config
        self._env: dict[str, str] = {}
        self._python_paths: list[Path] = []
        self._plugin_paths: dict[str, list[Path]] = {}
        self._modifiers: list[Callable[[dict[str, str]], None]] = []

    def add_python_path(self, path: Path) -> None:
        """Add a path to PYTHONPATH."""
        if path.exists():
            self._python_paths.append(path)

    def add_plugin_path(self, env_var: str, path: Path) -> None:
        """Add a plugin path to a specific environment variable."""
        if env_var not in self._plugin_paths:
            self._plugin_paths[env_var] = []
        if path.exists():
            self._plugin_paths[env_var].append(path)

    def set_variable(self, key: str, value: str) -> None:
        """Set an environment variable."""
        self._env[key] = value

    def register_modifier(self, modifier: Callable[[dict[str, str]], None]) -> None:
        """Register a function to modify the environment before finalization."""
        self._modifiers.append(modifier)

    def _build_core_environment(self) -> None:
        """Build core pipeline environment variables."""
        self._env["PIPELINE_ROOT"] = str(self.config.pipeline_root)
        self._env["PROJECT_ROOT"] = str(self.config.project_root)
        self._env["DCC_TYPE"] = self.config.dcc_type.value

        if self.config.dcc_version:
            self._env["DCC_VERSION"] = self.config.dcc_version

        self._env["VIZ_DEV_LEVEL"] = str(self.config.developer_level.value)

        self._env.update(self.config.context)
        self._env.update(self.config.custom_vars)

    def _get_dcc_site_packages(self) -> Optional[str]:
        """Get the site packages path for the DCC (must be first in PYTHONPATH)."""
        # This needs to be constructed based on DCC type/version/platform
        # Override this method or pass in via config if needed
        return None

    def _build_dcc_paths(self) -> None:
        """Build DCC-specific plugin and script paths."""
        # Override this method to add DCC-specific paths
        # Example: self.add_plugin_path('MAYA_SCRIPT_PATH', Path('/path'))
        pass

    def _finalize_paths(self) -> None:
        """Convert path lists to environment variable strings."""
        separator = ";" if os.name == "nt" else ":"

        if self._python_paths:
            existing_pythonpath = os.environ.get("PYTHONPATH", "")

            # Order: DCC site packages → Pipeline paths → Existing PYTHONPATH
            # Paths in the environment variable PYTHONPATH will be added to the
            # front of the list of sys.paths set by the DCC, meaning that these
            # paths will be searched before Maya's own. We want Maya to use its
            # own libraries first, so we explicitly add the
            # DCC_SITE_PACKAGES_PATH (or equivalent var) to the top of the list.
            # Omitting this will sometimes, at minimum, cause shiboken to crash
            # on startup due to mismatched memory addresses.
            all_paths = []

            dcc_site_packages = self._get_dcc_site_packages()
            if dcc_site_packages:
                all_paths.append(dcc_site_packages)

            all_paths.extend([p.as_posix() for p in self._python_paths])

            if existing_pythonpath:
                all_paths.append(existing_pythonpath)

            self._env["PYTHONPATH"] = separator.join(all_paths)

        # Build plugin path variables
        for env_var, paths in self._plugin_paths.items():
            if not paths:
                continue

            existing = os.environ.get(env_var, "")
            all_paths = [p.as_posix() for p in paths]
            if existing:
                all_paths.append(existing)
            self._env[env_var] = separator.join(all_paths)

    def build(self) -> dict[str, str]:
        """Build the complete environment dictionary."""
        self._build_core_environment()
        self._build_dcc_paths()
        self._finalize_paths()

        for modifier in self._modifiers:
            modifier(self._env)

        final_env = os.environ.copy()
        final_env.update(self._env)
        return final_env
