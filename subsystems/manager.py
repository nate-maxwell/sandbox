from typing import Optional, Any, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import time


# ============================================================================
# SERVICE REGISTRY - Single source of truth for what's available
# ============================================================================


class ServiceStatus(Enum):
    """Service health states"""

    AVAILABLE = 0x1
    DEGRADED = 0x2
    UNAVAILABLE = 0x4


@dataclass
class ServiceRegistration(object):
    """Registration info for a subsystem"""

    subsystem_type: type
    capabilities: set[str]
    status: ServiceStatus
    last_heartbeat: float


class ServiceRegistry(object):
    """
    Central registry of available subsystems and capabilities.

    This is the source of truth - subsystems query it, not events.
    """

    def __init__(self) -> None:
        self._services: dict[type, ServiceRegistration] = {}
        self._capability_to_service: dict[str, type] = {}

    def register_service(
        self,
        subsystem_type: type,
        capabilities: list[str],
        status: ServiceStatus = ServiceStatus.AVAILABLE,
    ) -> None:
        """Register a subsystem and its capabilities"""
        registration = ServiceRegistration(
            subsystem_type=subsystem_type,
            capabilities=set(capabilities),
            status=status,
            last_heartbeat=time.time(),
        )

        self._services[subsystem_type] = registration

        # Index by capability for fast lookup
        for capability in capabilities:
            self._capability_to_service[capability] = subsystem_type

        print(
            f"[Registry] Registered {subsystem_type.__name__} with capabilities: {capabilities}"
        )

    def unregister_service(self, subsystem_type: type) -> None:
        """Remove a subsystem from registry"""
        if subsystem_type in self._services:
            registration = self._services[subsystem_type]

            # Remove capability mappings
            for capability in registration.capabilities:
                if capability in self._capability_to_service:
                    del self._capability_to_service[capability]

            del self._services[subsystem_type]
            print(f"[Registry] Unregistered {subsystem_type.__name__}")

    def has_capability(self, capability: str) -> bool:
        """Check if a capability is currently available"""
        if capability not in self._capability_to_service:
            return False

        service_type = self._capability_to_service[capability]
        registration = self._services.get(service_type)

        return (
            registration is not None and registration.status == ServiceStatus.AVAILABLE
        )

    def get_service_for_capability(self, capability: str) -> Optional[type]:
        """Get the subsystem type that provides a capability"""
        return self._capability_to_service.get(capability)

    def get_all_capabilities(self) -> set[str]:
        """Get all currently available capabilities"""
        return set(
            cap
            for cap, service_type in self._capability_to_service.items()
            if self._services[service_type].status == ServiceStatus.AVAILABLE
        )

    def heartbeat(self, subsystem_type: type) -> None:
        """Update heartbeat for a service"""
        if subsystem_type in self._services:
            self._services[subsystem_type].last_heartbeat = time.time()

    def check_health(self, timeout: float = 5.0) -> dict[type, ServiceStatus]:
        """Check health of all services based on heartbeats"""
        now = time.time()
        health = {}

        for service_type, registration in self._services.items():
            age = now - registration.last_heartbeat
            if age > timeout:
                registration.status = ServiceStatus.UNAVAILABLE
                health[service_type] = ServiceStatus.UNAVAILABLE
            else:
                health[service_type] = registration.status

        return health


# ============================================================================
# BASE SUBSYSTEM - Pull-based capability discovery
# ============================================================================


class Subsystem(ABC):
    """Base subsystem with service registry integration"""

    _instances: dict[type["Subsystem"], "Subsystem"] = {}

    def __new__(cls) -> "Subsystem":
        if cls not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[cls] = instance
        return cls._instances[cls]

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._initialized: bool = False
        self._broker: Optional["EventBroker"] = None
        self._registry: Optional[ServiceRegistry] = None
        self._subscriptions: list[tuple[str, Callable[..., None]]] = []

    def set_broker(self, broker: "EventBroker") -> None:
        """Inject event broker"""
        self._broker = broker

    def set_registry(self, registry: ServiceRegistry) -> None:
        """Inject service registry"""
        self._registry = registry

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return capabilities this subsystem provides"""
        return []

    def initialize(self) -> None:
        """Initialize subsystem"""
        if self._initialized:
            return

        # Register ourselves in the registry
        if self._registry:
            self._registry.register_service(type(self), self.get_capabilities())

        # Setup event handlers
        self._setup_event_handlers()

        self._initialized = True

    def shutdown(self) -> None:
        """Shutdown subsystem"""
        # Unregister from registry
        if self._registry:
            self._registry.unregister_service(type(self))

        # Cleanup subscriptions
        if self._broker:
            for namespace, callback in self._subscriptions:
                self._broker.unsubscribe(namespace, callback)
        self._subscriptions.clear()

    @abstractmethod
    def _setup_event_handlers(self) -> None:
        """Setup event subscriptions"""
        pass

    # Capability checking - queries registry directly
    def requires_capability(self, capability: str) -> bool:
        """
        Check if a required capability is available.

        Returns True if available, False otherwise.
        Call this when you need something critical.
        """
        if not self._registry:
            return False

        available = self._registry.has_capability(capability)

        if not available:
            print(
                f"[{type(self).__name__}] Required capability '{capability}' not available"
            )

        return available

    def has_optional_capability(self, capability: str) -> bool:
        """
        Check if an optional capability is available.

        Use this for enhanced features that aren't critical.
        """
        if not self._registry:
            return False

        return self._registry.has_capability(capability)

    # Event helpers
    def subscribe(self, namespace: str, callback: Callable[..., None]) -> None:
        if self._broker:
            self._broker.subscribe(namespace, callback)
            self._subscriptions.append((namespace, callback))

    def publish(self, namespace: str, *args: Any, **kwargs: Any) -> None:
        if self._broker:
            self._broker.publish(namespace, *args, **kwargs)


# ============================================================================
# CONCRETE SUBSYSTEMS - Using registry for discovery
# ============================================================================


class CacheSubsystem(Subsystem):
    """Cache with optional filesystem integration"""

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, Any] = {}
        self._auto_invalidation: bool = False

    def get_capabilities(self) -> list[str]:
        return ["cache.get", "cache.set", "cache.invalidate"]

    def _setup_event_handlers(self) -> None:
        """
        Check registry for optional filesystem capability.
        Can be called at any time - will work whenever filesystem appears.
        """
        # Check if filesystem is available NOW
        if self.has_optional_capability("filesystem.watch"):
            self._enable_filesystem_integration()

    def _enable_filesystem_integration(self) -> None:
        """Enable filesystem integration if available"""
        if not self._auto_invalidation:
            self.subscribe("filesystem.file.changed", self._on_file_changed)
            self._auto_invalidation = True
            print("[Cache] Filesystem detected - enabling auto-invalidation")

    def _on_file_changed(self, path: str) -> None:
        """Invalidate on file changes"""
        self.invalidate(path)

    # Core API - always works
    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def invalidate(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]

    # Public method to check for new capabilities
    def refresh_capabilities(self) -> None:
        """
        Manually check for new capabilities.

        Can be called at any time to discover newly available services.
        """
        if not self._auto_invalidation and self.has_optional_capability(
            "filesystem.watch"
        ):
            self._enable_filesystem_integration()


class FileSystemSubsystem(Subsystem):
    """Filesystem subsystem"""

    def __init__(self) -> None:
        super().__init__()
        self._watched_paths: list[str] = []

    def get_capabilities(self) -> list[str]:
        return ["filesystem.read", "filesystem.write", "filesystem.watch"]

    def _setup_event_handlers(self) -> None:
        pass

    def read_file(self, path: str) -> str:
        content = f"<content of {path}>"
        self.publish("filesystem.file.read", path=path)
        return content

    def watch_path(self, path: str) -> None:
        self._watched_paths.append(path)
        # Simulate file change
        self.publish("filesystem.file.changed", path=path)


class RenderSubsystem(Subsystem):
    """Render subsystem with required scene dependency"""

    def __init__(self) -> None:
        super().__init__()

    def get_capabilities(self) -> list[str]:
        # Only provide capabilities if dependencies are met
        if self.requires_capability("scene.get"):
            return ["render.submit"]
        return []

    def _setup_event_handlers(self) -> None:
        pass

    def submit_render(self, shot_name: str) -> bool:
        """Submit render - fails gracefully if scene unavailable"""

        # Check capability at call time (registry might have changed)
        if not self.requires_capability("scene.get"):
            print(f"[Render] Cannot submit - scene subsystem unavailable")
            return False

        print(f"[Render] Submitting render for {shot_name}")
        self.publish("render.submitted", shot=shot_name)
        return True


class SceneSubsystem(Subsystem):
    """Scene subsystem"""

    def __init__(self) -> None:
        super().__init__()
        self.shots: dict[str, Any] = {}

    def get_capabilities(self) -> list[str]:
        return ["scene.get", "scene.set"]

    def _setup_event_handlers(self) -> None:
        pass

    def add_shot(self, shot_name: str) -> None:
        self.shots[shot_name] = {"name": shot_name}
        self.publish("scene.shot.added", shot=shot_name)


# ============================================================================
# MANAGER - Integrates registry
# ============================================================================


class EventBroker:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, namespace: str, callback: Callable[..., None]) -> None:
        if namespace not in self._handlers:
            self._handlers[namespace] = []
        self._handlers[namespace].append(callback)

    def publish(self, namespace: str, *args: Any, **kwargs: Any) -> None:
        for ns, handlers in self._handlers.items():
            if ns == namespace or ns == "*":
                for handler in handlers:
                    handler(*args, **kwargs)

    def unsubscribe(self, namespace: str, callback: Callable[..., None]) -> None:
        if namespace in self._handlers:
            self._handlers[namespace].remove(callback)


class SubsystemManager(object):
    """Manager with service registry"""

    _instance: Optional["SubsystemManager"] = None

    def __new__(cls) -> "SubsystemManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized_manager"):
            return

        self._subsystems: dict[type[Subsystem], Subsystem] = {}
        self._broker: EventBroker = EventBroker()
        self._registry: ServiceRegistry = ServiceRegistry()
        self._initialized_manager: bool = True

    def register(self, subsystem_class: type[Subsystem]) -> None:
        """Register and initialize a subsystem"""
        subsystem = subsystem_class()
        subsystem.set_broker(self._broker)
        subsystem.set_registry(self._registry)
        self._subsystems[subsystem_class] = subsystem

    def initialize(self) -> None:
        """Initialize all registered subsystems"""
        for subsystem in self._subsystems.values():
            subsystem.initialize()

        # After initialization, let subsystems discover new capabilities
        self._refresh_all_capabilities()

    def _refresh_all_capabilities(self) -> None:
        """Notify all subsystems to check for new capabilities"""
        for subsystem in self._subsystems.values():
            if hasattr(subsystem, "refresh_capabilities"):
                subsystem.refresh_capabilities()

    def add_subsystem(self, subsystem_class: type[Subsystem]) -> None:
        """
        Hot-add a subsystem to a running system.

        This is the key method for dynamic systems.
        """
        self.register(subsystem_class)

        # Initialize the new subsystem
        subsystem = self._subsystems[subsystem_class]
        subsystem.initialize()

        # Let existing subsystems discover the new capabilities
        self._refresh_all_capabilities()

    def remove_subsystem(self, subsystem_class: type[Subsystem]) -> None:
        """
        Hot-remove a subsystem from running system.
        """
        if subsystem_class in self._subsystems:
            subsystem = self._subsystems[subsystem_class]
            subsystem.shutdown()
            del self._subsystems[subsystem_class]

            print(f"[Manager] Removed {subsystem_class.__name__}")

    @property
    def registry(self) -> ServiceRegistry:
        """Access to service registry for advanced queries"""
        return self._registry

    @property
    def cache(self) -> CacheSubsystem:
        return self._subsystems.get(CacheSubsystem)  # type: ignore

    @property
    def filesystem(self) -> FileSystemSubsystem:
        return self._subsystems.get(FileSystemSubsystem)  # type: ignore

    @property
    def scene(self) -> SceneSubsystem:
        return self._subsystems.get(SceneSubsystem)  # type: ignore

    @property
    def render(self) -> RenderSubsystem:
        return self._subsystems.get(RenderSubsystem)  # type: ignore


# ============================================================================
# DEMONSTRATION - Hot-swapping subsystems
# ============================================================================


def demonstrate_dynamic_system() -> None:
    """Show subsystems being added/removed dynamically"""

    print("=== Starting with minimal system ===")
    manager = SubsystemManager()

    # Start with just cache and render
    manager.register(CacheSubsystem)
    manager.register(RenderSubsystem)
    manager.initialize()

    print("\n=== Cache works, but no filesystem integration ===")
    manager.cache.set("key1", "value1")
    print(f"Cached: {manager.cache.get('key1')}")

    print("\n=== Render can't work without scene ===")
    manager.render.submit_render("shot_010")

    print("\n=== HOT-ADD Scene subsystem ===")
    manager.add_subsystem(SceneSubsystem)

    print("\n=== Now render works! ===")
    manager.scene.add_shot("shot_010")
    manager.render.submit_render("shot_010")

    print("\n=== HOT-ADD Filesystem subsystem ===")
    manager.add_subsystem(FileSystemSubsystem)

    print("\n=== Cache automatically discovers filesystem ===")
    manager.cache.refresh_capabilities()

    print("\n=== Filesystem triggers cache invalidation ===")
    manager.cache.set("/path/file.txt", "content")
    manager.filesystem.watch_path("/path/file.txt")  # Triggers invalidation
    print(f"After invalidation: {manager.cache.get('/path/file.txt')}")

    print("\n=== HOT-REMOVE Filesystem ===")
    manager.remove_subsystem(FileSystemSubsystem)

    print("\n=== Cache still works, just without auto-invalidation ===")
    manager.cache.set("key2", "value2")
    print(f"Cached: {manager.cache.get('key2')}")

    print("\n=== Available capabilities ===")
    print(f"All capabilities: {manager.registry.get_all_capabilities()}")


if __name__ == "__main__":
    demonstrate_dynamic_system()
