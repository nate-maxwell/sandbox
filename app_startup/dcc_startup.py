"""
Stage 4: Startup task executor.

DCC-specific initialization hooks that execute registered startup tasks.

These functions are called from within the DCC (e.g., Maya's userSetup.py)
after the application has launched with the environment from Stage 1.
Executes all tasks registered in Stage 2 (startup_registry) in priority order.
"""

import logging

from startup_registry import get_registry


logger = logging.getLogger(__name__)


def maya_startup() -> None:
    """Execute startup tasks via Maya's evalDeferred"""
    try:
        from maya import cmds

        def execute_tasks():
            registry = get_registry()
            registry.execute_all()

        cmds.evalDeferred(execute_tasks, lowestPriority=True)
        logger.info("Maya startup tasks scheduled")

    except ImportError:
        logger.error("Maya not available")


def nuke_startup() -> None:
    """Execute startup tasks via Nuke callbacks"""
    try:
        import nuke

        def execute_tasks():
            registry = get_registry()
            registry.execute_all()

        nuke.addOnScriptLoad(execute_tasks)
        logger.info("Nuke startup tasks registered")

    except ImportError:
        logger.error("Nuke not available")


def unreal_startup() -> None:
    """Execute startup tasks immediately"""
    try:
        import unreal

        registry = get_registry()
        registry.execute_all()
        logger.info("Unreal startup tasks executed")

    except ImportError:
        logger.error("Unreal not available")


def blender_startup() -> None:
    """Execute startup tasks via Blender's app handlers"""
    try:
        import bpy
        from bpy.app import handlers

        def execute_tasks():
            registry = get_registry()
            registry.execute_all()

        handlers.load_post.append(execute_tasks)
        logger.info("Blender startup tasks registered")

    except ImportError:
        logger.error("Blender not available")


def auto_run() -> None:
    """Detect DCC and run appropriate startup"""
    try:
        import maya.cmds

        maya_startup()
        return
    except ImportError:
        pass

    try:
        import nuke

        nuke_startup()
        return
    except ImportError:
        pass

    try:
        import unreal

        unreal_startup()
        return
    except ImportError:
        pass

    try:
        import bpy

        blender_startup()
        return
    except ImportError:
        pass


if __name__ == "__main__":
    logger.warning("No DCC detected, running tasks immediately")
    get_registry().execute_all()
