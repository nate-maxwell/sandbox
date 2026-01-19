"""
Stage 3: DCC application launcher.

Provides the executable registry and launcher for DCC applications, i.e.
wrapper objects that represent a registered operable DCC within the pipeline.

This module handles the actual subprocess launching with the environment
built by Stage 1 (environment_builder). The DCC will then execute Stage 4
(dcc_startup) which triggers Stage 2 (startup_registry) tasks.
"""

import subprocess
from pathlib import Path
from dataclasses import dataclass

from environment_builder import EnvironmentBuilder
from environment_builder import EnvironmentConfig
from environment_builder import DCCType


@dataclass
class DCCExecutable(object):
    """Defines a DCC executable location."""

    path: Path
    """Path to the executable."""

    version: str
    """Version string."""

    args: list[str] = None
    """Default arguments to pass when launching."""

    def __post_init__(self):
        if self.args is None:
            self.args = []


class DCCRegistry(object):
    """Registry of DCC executable locations."""

    def __init__(self) -> None:
        self._executables: dict[DCCType, dict[str, DCCExecutable]] = {
            dcc_type: {} for dcc_type in DCCType
        }

    def register(
        self,
        dcc_type: DCCType,
        version: str,
        path: Path,
        args: list[str] = None,
    ) -> None:
        """Register a DCC executable."""
        executable = DCCExecutable(path=path, version=version, args=args or [])
        self._executables[dcc_type][version] = executable

    def get(
        self, dcc_type: DCCType, version: str | None = None
    ) -> DCCExecutable | None:
        """Get a DCC executable (latest if version not specified)."""
        versions = self._executables.get(dcc_type, {})
        if not versions:
            return None
        if version:
            return versions.get(version)
        latest_version = sorted(versions.keys())[-1]
        return versions[latest_version]

    def list_versions(self, dcc_type: DCCType) -> list[str]:
        """List available versions for a DCC."""
        return sorted(self._executables.get(dcc_type, {}).keys())


class DCCLauncher(object):
    """Launches DCC applications with configured environments."""

    def __init__(self, dcc_registry: DCCRegistry) -> None:
        self.registry = dcc_registry

    def launch(
        self,
        config: EnvironmentConfig,
        executable: DCCExecutable | None = None,
        extra_args: list[str] | None = None,
        wait: bool = False,
    ) -> subprocess.Popen | None:
        """Launch a DCC with the configured environment."""
        if executable is None:
            executable = self.registry.get(config.dcc_type, config.dcc_version)
            if executable is None:
                return None

        if not executable.path.exists():
            return None

        builder = EnvironmentBuilder(config)
        env = builder.build()

        cmd = [str(executable.path)]
        cmd.extend(executable.args)
        if extra_args:
            cmd.extend(extra_args)

        process = subprocess.Popen(
            cmd, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE
        )

        if wait:
            process.wait()
            return None

        return process
