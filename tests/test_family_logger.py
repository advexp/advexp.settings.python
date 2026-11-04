"""The logging channels of the family, as the accessors of the library hand
them out.

:meth:`LibraryConfiguration.logger` returns the channel of the family root.
This is the one object through which every record of every distribution
passes. The root class of each distribution hands out its own package
channel in the same way. An application can therefore configure either of
them without knowing a channel name, and the level parameter of the same
class governs the very object that it handed out.
"""

import logging

from advexp.configuration import Configuration
from advexp.configuration.plugin_api import PACKAGE_NAME as CONFIGURATION_NAME
from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import PACKAGE_NAME as SETTINGS_NAME
from advexp.settings_base.library_configuration import FAMILY_LOGGER_NAME


def test_logger_hands_out_the_family_channel():
    # the accessor hides the channel's name: the application configures
    # the object it was handed, the library keeps the spelling its own
    assert LibraryConfiguration.logger() is logging.getLogger(FAMILY_LOGGER_NAME)


def test_set_log_level_governs_the_handed_out_channel():
    logger = LibraryConfiguration.logger()
    try:
        LibraryConfiguration.set_log_level(logging.DEBUG)
        assert logger.level == logging.DEBUG
    finally:
        logger.setLevel(logging.NOTSET)


def test_root_classes_hand_out_their_distribution_channels():
    assert Settings.logger() is logging.getLogger(SETTINGS_NAME)
    assert Configuration.logger() is logging.getLogger(CONFIGURATION_NAME)
    # the family accessors stay distinct: a handler on the family channel
    # receives every record, one on a package channel its package's alone
    assert Settings.logger() is not LibraryConfiguration.logger()
    assert Configuration.logger() is not Settings.logger()


def test_subclasses_inherit_the_distribution_channel():
    class WorkerSettings(Settings):
        pass

    class WorkerConfig(Configuration):
        pass

    # one channel per distribution: the declaration every subclass
    # inherits names the same object
    assert WorkerSettings.logger() is Settings.logger()
    assert WorkerConfig.logger() is Configuration.logger()
