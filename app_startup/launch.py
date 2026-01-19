"""
DCC launcher with pre-flight checks.

Flight checks run before DCC launch, startup tasks run after.
"""

import configparser
import platform
import subprocess
from pathlib import Path
from typing import Optional

import mythos.constants
import mythos.io_utils
from dcc_launcher import DCCRegistry
from environment_builder import EnvironmentBuilder
from environment_builder import EnvironmentConfig
from environment_builder import DCCType
from environment_builder import DeveloperLevel


class MayaEnvironmentBuilder(EnvironmentBuilder):
    """Environment builder for Maya."""

    def _get_dcc_site_packages(self) -> Optional[str]:
        """Get Maya site packages path."""
        return str(mythos.constants.MAYA_SITE_PACKAGES_PATH)

    def _build_dcc_paths(self) -> None:
        """Build Maya-specific paths."""
        self.add_python_path(mythos.constants.MYTHOS_PATH)
        self.add_python_path(Path(mythos.constants.MYTHOS_PATH, "mythos/maya"))
        self.add_plugin_path("MAYA_SCRIPT_PATH", mythos.constants.MAYA_MEL_SCRIPT_PATH)
        self.add_plugin_path("MAYA_PLUG_IN_PATH", mythos.constants.MAYA_PLUGINS_PATH)
        self.add_plugin_path("MAYA_PLUG_IN_PATH", mythos.constants.STUDIO_LIBRARY_PATH)


class NukeEnvironmentBuilder(EnvironmentBuilder):
    """Environment builder for Nuke."""

    def _get_dcc_site_packages(self) -> Optional[str]:
        """Get Nuke site packages path."""
        return str(mythos.constants.NUKE_SITE_PACKAGES_PATH)

    def _build_dcc_paths(self) -> None:
        """Build Nuke-specific paths."""
        self.add_python_path(mythos.constants.MYTHOS_PATH)
        for path in mythos.constants.NUKE_PATHS:
            self.add_plugin_path("NUKE_PATH", path)


class BlenderEnvironmentBuilder(EnvironmentBuilder):
    """Environment builder for Blender."""

    def _build_dcc_paths(self) -> None:
        """Build Blender-specific paths."""
        self.add_python_path(mythos.constants.MYTHOS_PATH)
        self.add_python_path(mythos.constants.BLENDER_MYTHOS_PATH)


class UnrealEnvironmentBuilder(EnvironmentBuilder):
    """Environment builder for Unreal."""

    def _build_dcc_paths(self) -> None:
        """Build Unreal-specific paths."""
        self.add_python_path(mythos.constants.MYTHOS_PATH)
        self.add_python_path(mythos.constants.UNREAL_MYTHOS_PATH)


def maya_flight_checks() -> None:
    """Pre-launch procedures for Maya."""
    if platform.system() == "Linux":
        return

    user_prefs_path = Path(mythos.constants.USER_MAYA_PREFS_DIR, "userPrefs.mel")
    if not user_prefs_path.exists():
        return

    with open(user_prefs_path, "r") as f:
        lines = f.readlines()

    # Find and collect render options block
    start_line = 'optionVar -cat "Rendering"'
    render_setup_line = ' -iv "renderSetupEnable" 0'

    modified = False
    result = []
    in_block = False

    for line in lines:
        if start_line in line:
            in_block = True

        if in_block and render_setup_line in line:
            modified = True
            continue

        result.append(line)

        if in_block and ";" in line:
            in_block = False

    if modified:
        with open(user_prefs_path, "w") as f:
            f.writelines(result)
        print("RenderSetup enabled")


def nuke_flight_checks() -> None:
    """Pre-launch procedures for Nuke."""
    workspace_src = mythos.constants.NUKE_GLOBAL_DEFAULT_WORKSPACE
    workspace_dst = mythos.constants.NUKE_WORKSPACE_PATH

    # Copy workspace if needed
    if not workspace_dst.exists():
        print(f"Copying workspace from {workspace_src.as_posix()}")
        mythos.io_utils.copy_file(workspace_src, workspace_dst.parent)

    # Set as default in uistate.ini
    config = configparser.ConfigParser()
    config.read(mythos.constants.NUKE_UISTATE_INI_PATH)

    section = "Nuke"
    if section not in config:
        config[section] = {}

    config[section]["startupWorkspace"] = workspace_src.stem

    with open(mythos.constants.NUKE_UISTATE_INI_PATH, "w") as f:
        config.write(f)


def setup_registry() -> DCCRegistry:
    """Register all available DCC executables."""
    registry = DCCRegistry()

    # Maya
    registry.register(
        DCCType.MAYA,
        mythos.constants.MAYA_VERSION,
        mythos.constants.MAYA_EXEC,
    )

    # Nuke
    registry.register(
        DCCType.NUKE,
        mythos.constants.NUKE_VERSION,
        mythos.constants.NUKE_EXEC,
    )

    # Unreal
    registry.register(
        DCCType.UNREAL,
        mythos.constants.UNREAL_VERSION,
        mythos.constants.UNREAL_EXEC,
    )

    # Blender
    registry.register(
        DCCType.BLENDER,
        mythos.constants.BLENDER_VERSION,
        mythos.constants.BLENDER_EXEC,
    )

    # After Effects
    registry.register(
        DCCType.AFTER_EFFECTS,
        mythos.constants.AE_VERSION,
        mythos.constants.AFTER_EFFECT_EXEC,
    )

    return registry


def launch_dcc(
    dcc_type: DCCType,
    context: dict[str, str] = None,
    developer_level: int = 1,
) -> None:
    """Launch a DCC with full pipeline environment.

    Args:
        dcc_type: Which DCC to launch.
        context: Flexible context dict for environment variables.
                 Example: {'VIZ_SHOW': 'MyShow', 'VIZ_SHOT': 'sh010', 'VIZ_PHASE': 'previs'}
        developer_level: User's developer level.
    """
    if context is None:
        context = {}

    # Run pre-flight checks
    if dcc_type == DCCType.MAYA:
        maya_flight_checks()
    elif dcc_type == DCCType.NUKE:
        nuke_flight_checks()

    # Get executable
    registry = setup_registry()
    executable = registry.get(dcc_type)
    if not executable or not executable.path.exists():
        print(f"Failed to find {dcc_type.value} executable")
        return

    # Build configuration
    config = EnvironmentConfig(
        pipeline_root=mythos.constants.MYTHOS_PATH,
        project_root=mythos.constants.SHOWS_PATH,
        dcc_type=dcc_type,
        developer_level=DeveloperLevel(developer_level),
        context=context,
    )

    # Pick builder based on DCC type
    builder_map = {
        DCCType.MAYA: MayaEnvironmentBuilder,
        DCCType.NUKE: NukeEnvironmentBuilder,
        DCCType.BLENDER: BlenderEnvironmentBuilder,
        DCCType.UNREAL: UnrealEnvironmentBuilder,
    }

    builder_class = builder_map.get(dcc_type, EnvironmentBuilder)
    builder = builder_class(config)
    env = builder.build()

    # Launch
    cmd = [str(executable.path)] + executable.args
    process = subprocess.Popen(cmd, env=env)

    print(f"Launched {dcc_type.value} (PID: {process.pid})")
