import argparse
import logging
import sys
from pathlib import Path

from tank_controls.config.errors import ConfigError
from tank_controls.config.loader import load_config
from tank_controls.hid.dry_run import log_action


def main() -> None:
    parser = argparse.ArgumentParser(description="War Thunder multimodal controls")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to keybind config file (default: config.toml)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        config = load_config(args.config)
    except ConfigError as e:
        logging.error(str(e))
        sys.exit(1)

    logging.info("Loaded profile: %s", config.profile_name)

    for action, key in config.press.items():
        log_action(action, "press", key)
    for action, key in config.hold.items():
        log_action(action, "hold", key)
    for action, binding in config.mouse.items():
        log_action(action, "mouse_move", binding)


if __name__ == "__main__":
    main()
