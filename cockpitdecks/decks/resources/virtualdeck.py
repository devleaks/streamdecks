"""
Virtual deck cockpitdeck interface class
Does not perform any action. Just a wrapper for Cockpitdecks.
Behaves like a "device driver".
"""

import logging
import struct
import socket

from cockpitdecks.constant import CONFIG_KW

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class VirtualDeck:
    DECK_NAME = "virtualdeck"

    def __init__(self, name: str, definition: "DeckType", config: dict):
        self.name: str = name
        self.virtual_deck_definition: dict = definition  # DeckType
        self.virtual_deck_config: dict = config  # Deck entry in deckconfig/config.yaml
        self.serial_number = None

    def deck_type(self):
        return VirtualDeck.DECK_NAME

    def set_serial_number(self, serial):
        self.serial_number = serial

    def get_serial_number(self):
        return self.serial_number

    def is_visual(self):
        return True

    def key_image_format(self):
        # dummy
        return {
            "size": (0, 0),
            "format": "",
            "flip": (False, False),
            "rotation": 0,
        }

    # #########################################
    #
    def open(self):
        pass

    def close(self):
        pass

    def reset(self):
        pass
