import logging
import os

from .constant import CONFIG_DIR, ICONS_FOLDER, FONTS_FOLDER

logger = logging.getLogger("Button")


class Display:

    DISPLAY_FIELDS = [
        "name",
        "text-center",
        "font-path",
        "font-size",
        "zero-pad",
        "min",
        "max",
        "step",
        "keep-decimal",
        "background"
    ]

    def __init__(self, config: dict):
        self.name = config.get("name")
        self.text_center = config.get("text-center")
        self.font_path = config.get("font-path")
        self.font_size = config.get("font-size")
        self.zero_pad = config.get("zero-pad")
        self.min = config.get("min")
        self.max = config.get("max")
        self.step = config.get("step")
        self.keep_decimal = config.get("keep-decimal")
        self.background = config.get("background")


class Button:

    def __init__(self, config: dict, deck: "Streamdeck"):

        self.deck = deck
        self.name = config.get("name", f"bnt-{config['index']}")
        self.index = config.get("index")

        self.pressed_count = 0
        self.label = config.get("label")
        self.icon = config.get("icon")
        self.icons = config.get("file_names")

        self.command = None
        self.dataref = None

        self.previous_value = None
        self.current_value = None

        if self.icon is not None and not self.icon.endswith(".png"):  # @todo check for .PNG ok too.
            self.icon = self.icon + ".png"
            if self.icon not in self.deck.icons.keys():
                logger.warning(f"__init__: button {self.name}: icon not found {self.icon}")
        self.display = None
        if "display" in config:
            self.display = Display(config.get("display"))

        self.init()

    @classmethod
    def new(cls, config: dict, deck: "Streamdeck"):
        return cls(config=config, deck=deck)

    def init(self):
        """
        Install button
        """
        pass

    def changed(self) -> bool:
        """
        Determine if button's underlying value has changed
        """
        newval = None

        return self.previous_value == self.current_value

    def update(self, force: bool = False):
        """
        Renders button if it has changed
        """
        if force or self.changed():
            self.previous_value == self.current_value
            self.render()

    def render(self):
        if self.deck is not None:
            self.deck.set_key_image(self)
        logger.info(f"render: button {self.name} rendered")

    def activate(self):
        self.pressed_count = self.pressed_count + 1
        logger.info(f"activate: button {self.name} activated")


class ButtonSingle(Button):

    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)


class ButtonDual(Button):

    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)


class ButtonPage(Button):

    def __init__(self, config: dict, deck: "Streamdeck"):
        Button.__init__(self, config=config, deck=deck)

    def activate(self):
        super().activate()
        self.deck.change_page(self.name)


BUTTON_TYPES = {
    "none": Button,
    "single": ButtonSingle,
    "dual": ButtonDual,
    "page": ButtonPage,
    "dir": ButtonPage
}