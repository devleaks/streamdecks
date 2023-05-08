"""
Application constants
Also contains default defaults :-D
This file should NEVER be altered, it is part of the code.
Adjust default values in file resources/config.yaml instead.
"""
import os
from inspect import stack
from enum import Enum

EXCLUDE_DECKS = []  # list serial numbers of deck not usable by Streadecks

# Files
CONFIG_FOLDER = "deckconfig"
CONFIG_FILE = "config.yaml"
SECRET_FILE = "secret.yaml"

DEFAULT_AIRCRAFT = "AIRCRAFT"

RESOURCES_FOLDER = "resources"

DEFAULT_WALLPAPER = "wallpaper.png"
DEFAULT_LOGO = "logo.png"

DEFAULT_LAYOUT = "default"
HOME_PAGE = "index"
DEFAULT_PAGE_NAME = "X-Plane"

# Fonts
FONTS_FOLDER = "fonts"
DEFAULT_SYSTEM_FONT = "Monaco.ttf"  # on MacOS, if above not found

DEFAULT_LABEL_FONT = "DIN.ttf"
DEFAULT_LABEL_SIZE = 10
DEFAULT_LABEL_COLOR = "white"
DEFAULT_LABEL_POSITION = "ct"

# Icons
ICONS_FOLDER = "icons"
ICON_SIZE = 256 # px
DEFAULT_ICON_NAME = "_default_icon.png"
DEFAULT_ICON_COLOR = (0, 0, 100)
DEFAULT_ICON_TEXTURE = None
DEFAULT_ANNUNCIATOR_COLOR = (0, 0, 0)

# Decor, colors
COCKPIT_COLOR = (94, 111, 130)  # tuple (r, g, b) or string of PILLOW color name
COCKPIT_TEXTURE = None

DEFAULT_LIGHT_OFF_INTENSITY = 10  # %

# Attribute keybords
KW_FORMULA = "formula"

# Debug, internals
SPAM_LEVEL = 15
SPAM = "SPAM"
ID_SEP = "/"

ROOT_DEBUG = "cockpitdecks.xplaneudp,cockpitdecks.xplane,cockpitdecks.button"

class ANNUNCIATOR_STYLES(Enum):
    KORRY = "k"           # k(orry): backlit, glowing
    VIVISUN = "v"         # v(ivisun): bright, sharp.

DEFAULT_ANNUNCIATOR_STYLE = ANNUNCIATOR_STYLES.KORRY
