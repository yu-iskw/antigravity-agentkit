"""Re-export deployment loading from the shared loader module."""

from antigravity_agentkit.loader import DEPLOYMENT_FILENAME, load_deployment

__all__ = ["DEPLOYMENT_FILENAME", "load_deployment"]
