import logging
from typing import Callable
from typing import Optional
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum


logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Startup task priorities - lower values run first"""

    CRITICAL = 0x1
    """Core systems (event broker, logging, ...)."""

    HIGH = 0x2
    """Config, templates, paths..."""

    NORMAL = 0x3
    """Most tools/plugins."""

    LOW = 0x4
    """UI, optional features."""

    DEFERRED = 0x5
    """Background tasks."""


@dataclass(order=True)
class StartupTask(object):
    """A startup task with priority and execution details"""

    priority: int = field(compare=True)
    name: str = field(compare=False)
    callback: Callable = field(compare=False)
    enabled: bool = field(default=True, compare=False)
    description: str = field(default="", compare=False)


class StartupRegistry(object):
    """Registry for application startup tasks"""

    def __init__(self) -> None:
        self._tasks: list[StartupTask] = []

    def register(
        self,
        callback: Callable,
        priority: int = Priority.NORMAL,
        name: Optional[str] = None,
        description: str = "",
        enabled: bool = True,
    ) -> StartupTask:
        """Register a startup task"""
        task_name = name or f"{callback.__module__}.{callback.__name__}"
        task = StartupTask(
            priority=priority,
            name=task_name,
            callback=callback,
            enabled=enabled,
            description=description,
        )
        self._tasks.append(task)
        logger.debug(f"Registered startup task: {task_name} (priority={priority})")
        return task

    def get_tasks(self, enabled_only: bool = True) -> list[StartupTask]:
        """Get all tasks, sorted by priority"""
        tasks = [t for t in self._tasks if not enabled_only or t.enabled]
        return sorted(tasks)

    def execute_all(self) -> None:
        """Execute all enabled tasks in priority order"""
        tasks = self.get_tasks()
        logger.info(f"Executing {len(tasks)} startup tasks...")

        for task in tasks:
            try:
                logger.info(f"Running: {task.name}")
                task.callback()
            except Exception as e:
                logger.error(f"Startup task failed: {task.name}: {e}", exc_info=True)
                # Optionally: decide if you want to continue or halt on errors

    def clear(self) -> None:
        """Clear all registered tasks (useful for testing)"""
        self._tasks.clear()


# Global registry instance
_registry = StartupRegistry()


def startup_task(
    priority: int = Priority.NORMAL,
    name: Optional[str] = None,
    description: str = "",
    enabled: bool = True,
) -> Callable:
    """Decorator to register a function as a startup task"""

    def decorator(func: Callable) -> Callable:
        _registry.register(
            callback=func,
            priority=priority,
            name=name,
            description=description,
            enabled=enabled,
        )
        return func

    return decorator


def get_registry() -> StartupRegistry:
    """Get the global startup registry"""
    return _registry
