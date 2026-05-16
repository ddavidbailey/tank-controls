import logging

logger = logging.getLogger(__name__)


def log_action(action_name: str, action_type: str, binding: str) -> None:
    logger.info("[DRY-RUN] %s: %s (%s)", action_type, binding, action_name)
