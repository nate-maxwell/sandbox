"""
Example startup tasks for a VFX pipeline application.

This demonstrates how to use the startup_task decorator to register
initialization tasks with different priorities.
"""

import logging

from startup_registry import startup_task
from startup_registry import Priority


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# CRITICAL priority - Core systems that everything depends on
@startup_task(
    priority=Priority.CRITICAL,
    name="initialize_event_broker",
    description="Initialize the event broker system",
)
def initialize_event_broker():
    """Initialize the core event broker"""
    logger.info("Event broker initialized")
    # Your actual broker initialization here
    # broker = EventBroker()
    # broker.start()


@startup_task(
    priority=Priority.CRITICAL,
    name="setup_logging",
    description="Configure application logging",
)
def setup_logging():
    """Set up pipeline logging configuration"""
    logger.info("Logging configuration loaded")
    # Configure your logging handlers, formatters, etc.


# HIGH priority - Configuration and path setup
@startup_task(
    priority=Priority.HIGH,
    name="load_pipeline_config",
    description="Load pipeline configuration from YAML",
)
def load_pipeline_config():
    """Load pipeline configuration"""
    logger.info("Pipeline configuration loaded from config.yaml")
    # config = PipelineConfig.load("config.yaml")


@startup_task(
    priority=Priority.HIGH,
    name="initialize_template_system",
    description="Initialize SGTK-style path templates",
)
def initialize_template_system():
    """Initialize the template/path resolution system"""
    logger.info("Template system initialized with templates.yaml")
    # template_registry = TemplateRegistry()
    # template_registry.load("templates.yaml")


@startup_task(
    priority=Priority.HIGH,
    name="setup_environment",
    description="Set up environment variables and paths",
)
def setup_environment():
    """Configure environment variables"""
    logger.info("Environment variables configured")

    # os.environ['PIPELINE_ROOT'] = '/mnt/pipeline'
    # os.environ['PROJECT_ROOT'] = '/mnt/projects/current'


# NORMAL priority - Standard tools and plugins
@startup_task(
    priority=Priority.NORMAL,
    name="register_custom_nodes",
    description="Register custom DCC nodes/tools",
)
def register_custom_nodes():
    """Register custom nodes or plugins"""
    logger.info("Custom nodes registered")
    # register_node_type("CustomDeformer")
    # register_node_type("CustomShader")


@startup_task(
    priority=Priority.NORMAL,
    name="load_asset_library",
    description="Initialize asset library connection",
)
def load_asset_library():
    """Connect to asset library"""
    logger.info("Asset library connection established")
    # asset_lib = AssetLibrary.connect()


@startup_task(
    priority=Priority.NORMAL,
    name="setup_shotgrid_connection",
    description="Initialize ShotGrid API connection",
)
def setup_shotgrid_connection():
    """Set up ShotGrid/production tracking connection"""
    logger.info("ShotGrid connection initialized")
    # sg = shotgun_api3.Shotgun(url, script, key)


# LOW priority - UI and optional features
@startup_task(
    priority=Priority.LOW,
    name="create_custom_menus",
    description="Add custom menu items to DCC",
)
def create_custom_menus():
    """Create custom UI menus"""
    logger.info("Custom menus created")
    # create_menu("Pipeline Tools")
    # add_menu_item("Publish", publish_callback)


@startup_task(
    priority=Priority.LOW,
    name="load_user_preferences",
    description="Load user-specific preferences",
)
def load_user_preferences():
    """Load user preferences from settings file"""
    logger.info("User preferences loaded")
    # prefs = UserPreferences.load()


# DEFERRED priority - Background tasks
@startup_task(
    priority=Priority.DEFERRED,
    name="check_for_updates",
    description="Check for pipeline tool updates",
)
def check_for_updates():
    """Check for available updates in background"""
    logger.info("Checking for updates...")
    # update_checker.check_async()


@startup_task(
    priority=Priority.DEFERRED,
    name="sync_user_data",
    description="Sync user data to cloud",
)
def sync_user_data():
    """Sync user preferences/history to cloud storage"""
    logger.info("User data sync initiated")
    # cloud_sync.sync_async()


# Example of a disabled task
@startup_task(
    priority=Priority.NORMAL,
    name="experimental_feature",
    description="Experimental feature (currently disabled)",
    enabled=False,
)
def experimental_feature():
    """This won't run because enabled=False"""
    logger.info("This shouldn't appear!")


if __name__ == "__main__":
    # This demonstrates running the tasks directly
    # In production, you'd use dcc_runner.auto_run() instead
    from startup_registry import get_registry

    logger.info("=" * 60)
    logger.info("Starting pipeline initialization")
    logger.info("=" * 60)

    registry = get_registry()
    registry.execute_all()

    logger.info("=" * 60)
    logger.info("Pipeline initialization complete")
    logger.info("=" * 60)
