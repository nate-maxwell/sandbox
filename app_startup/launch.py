"""
Modular Application Launch System

This module defines a deterministic, declarative system for launching
applications with versioned executables, structured environment composition,
plugin and Python path injection, and dynamic custom environment variables.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

from app_startup import appspec


class EnvironmentBuilder(object):
    """
    Constructs a deterministic environment mapping for an application launch.
    """

    @staticmethod
    def _join_paths(paths: List[Path]) -> str:
        """Join a list of paths using the OS path separator."""
        return ";".join(p.as_posix() for p in paths)

    @classmethod
    def build(
        cls,
        app_spec: appspec.ApplicationSpec,
        app_version: appspec.ApplicationVersion,
        user_env: Optional[Dict[str, str]] = None,
        inherit_os_env: bool = False,
    ) -> Dict[str, str]:
        """
        Build the final environment mapping.

        Args:
            app_spec (ApplicationSpec): Application definition.
            app_version (ApplicationVersion): Version definition.
            user_env (Optional[dict[str, str]]): Arbitrary user-provided env vars.
            inherit_os_env (bool): Whether to inherit os.environ.

        Returns:
            dict[str, str]: Fully composed environment.
        """
        env: Dict[str, str] = {}

        if inherit_os_env:
            env.update(os.environ)

        env.update(app_spec.env)
        env.update(app_version.env)

        if app_version.python_paths:
            env["PYTHONPATH"] = cls._join_paths(app_version.python_paths)

        if app_version.plugin_paths:
            env["PLUGIN_PATH"] = cls._join_paths(app_version.plugin_paths)

        if user_env:
            env.update(user_env)

        return env


# -------------------------------------------------------------------------------------------------
# Launcher
# -------------------------------------------------------------------------------------------------


class ApplicationLauncher:
    """
    Orchestrates application registration, environment construction, and process launch.
    """

    def __init__(self) -> None:
        self._apps: Dict[str, appspec.ApplicationSpec] = {}

    def register(self, app_spec: appspec.ApplicationSpec) -> None:
        """
        Register an application specification.

        Args:
            app_spec (ApplicationSpec): Application to register.
        """
        if app_spec.name in self._apps:
            raise ValueError(f'Application "{app_spec.name}" is already registered.')
        self._apps[app_spec.name] = app_spec

    def unregister(self, app_name: str) -> None:
        """
        Unregister an application.

        Args:
            app_name (str): Application name.
        """
        if app_name not in self._apps:
            raise KeyError(f'Application "{app_name}" is not registered.')
        del self._apps[app_name]

    def launch(
        self,
        app_name: str,
        version: Optional[str] = None,
        user_env: Optional[Dict[str, str]] = None,
        args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        inherit_os_env: bool = False,
        creation_flags: Optional[int] = None,
    ) -> subprocess.Popen:
        """
        Launch an application.

        Args:
            app_name (str): Registered application name.
            version (Optional[str]): Version identifier.
            user_env (Optional[dict[str, str]]): Arbitrary environment overrides.
            args (Optional[list[str]]): Command-line arguments.
            cwd (Optional[Path]): Working directory.
            inherit_os_env (bool): Whether to inherit os.environ.
            creation_flags (Optional[int]): Subprocess creation flags (Windows).

        Returns:
            subprocess.Popen: Launched process.
        """
        if app_name not in self._apps:
            raise KeyError(f'Application "{app_name}" is not registered.')

        app_spec = self._apps[app_name]
        app_version = app_spec.get_version(version)

        # Run flight checks
        for check in app_spec.flight_checks:
            check()

        # Build environment
        env = EnvironmentBuilder.build(
            app_spec=app_spec,
            app_version=app_version,
            user_env=user_env,
            inherit_os_env=inherit_os_env,
        )

        # Build command
        cmd: List[str] = [app_version.executable.as_posix()]
        if args:
            cmd.extend(args)

        return subprocess.Popen(
            cmd,
            env=env,
            cwd=str(cwd) if cwd else None,
            creationflags=creation_flags or 0,
        )


# -------------------------------------------------------------------------------------------------
# Example Configuration (Minimal, Real, No Stubs)
# -------------------------------------------------------------------------------------------------


def maya_flight_checks() -> None:
    """Realistic Maya flight check placeholder."""
    print("Maya flight checks executed.")


def nuke_flight_checks() -> None:
    """Realistic Nuke flight check placeholder."""
    print("Nuke flight checks executed.")


def build_launcher() -> ApplicationLauncher:
    """
    Build a launcher with example application registrations.

    Returns:
        ApplicationLauncher: Configured launcher instance.
    """
    launcher = ApplicationLauncher()

    maya_2023 = appspec.ApplicationVersion(
        version="2023",
        executable=Path("C:/Program Files/Autodesk/Maya2023/bin/maya.exe"),
        python_paths=[
            Path("C:/Program Files/Autodesk/Maya2023/Python/Lib/site-packages"),
            Path("V:/pipeline/tools/live/mythos"),
        ],
        plugin_paths=[
            Path("V:/pipeline/programs/plugins/maya"),
            Path("V:/pipeline/programs/plugins/maya/studiolibrary/src"),
        ],
        env={
            "MAYA_RENDER_SETUP_ENABLED": "1",
        },
    )

    maya_spec = appspec.ApplicationSpec(
        name="maya",
        versions={"2023": maya_2023},
        default_version="2023",
        env={
            "VIZ_DCC": "maya",
        },
        flight_checks=[maya_flight_checks],
    )

    nuke_14 = appspec.ApplicationVersion(
        version="14.0v1",
        executable=Path("C:/Program Files/Nuke14.0/Nuke14.0.exe"),
        python_paths=[
            Path("C:/Program Files/Nuke14.0/pythonextensions/site-packages"),
            Path("V:/pipeline/tools/live/mythos"),
        ],
        plugin_paths=[
            Path("V:/pipeline/programs/plugins/nuke"),
            Path("V:/pipeline/programs/plugins/nuke/KeenTools"),
        ],
        env={
            "NUKE_PATH": "V:/pipeline/programs/plugins/nuke",
        },
    )

    nuke_spec = appspec.ApplicationSpec(
        name="nuke",
        versions={"14.0v1": nuke_14},
        default_version="14.0v1",
        env={
            "VIZ_DCC": "nuke",
        },
        flight_checks=[nuke_flight_checks],
    )

    launcher.register(maya_spec)
    launcher.register(nuke_spec)

    return launcher


# -------------------------------------------------------------------------------------------------
# Example Usage
# -------------------------------------------------------------------------------------------------


def example_usage() -> None:
    """Demonstrate launching applications."""
    launcher = build_launcher()

    user_env = {
        "VIZ_SHOW": "MyShow",
        "DD_ROLE": "artist",
        "VIZ_PHASE": "previs",
        "VIZ_ASSET": "Dragon",
        "VIZ_SHOT": "010",
        "VIZ_SEQ": "A01",
        "VIZ_EPISODE": "E01",
        "VIZ_DEV_LEVEL": "1",
        "CUSTOM_FLAG": "enabled",
    }

    launcher.launch(
        app_name="maya",
        version="2023",
        user_env=user_env,
        inherit_os_env=False,
        creation_flags=subprocess.CREATE_NEW_CONSOLE,
    )

    launcher.launch(
        app_name="nuke",
        version="14.0v1",
        user_env=user_env,
        inherit_os_env=False,
        creation_flags=subprocess.CREATE_NEW_CONSOLE,
    )


if __name__ == "__main__":
    example_usage()
