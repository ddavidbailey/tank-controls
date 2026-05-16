class ConfigError(Exception):
    pass


class EmptyKeybindError(ConfigError):
    pass


class InvalidKeybindError(ConfigError):
    pass


class DoubleBoundKeyError(ConfigError):
    pass
