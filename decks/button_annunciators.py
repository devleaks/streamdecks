# ###########################
# Special Airbus Button Rendering
#
import logging
import threading
import time
import colorsys
import traceback

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
from mergedeep import merge

from .constant import ANNUNCIATOR_DEFAULTS, ANNUNCIATOR_STYLE, LIGHT_OFF_BRIGHTNESS, convert_color, print_stack
from .button_core import Button
from .rpc import RPC

logger = logging.getLogger("AnnunciatorButton")
# logger.setLevel(logging.DEBUG)

DATAREF_RPN = "dataref-rpn"

def convert_color_string(instr) -> tuple:  # tuple of int 0-255
    # process either a color name or a color tuple as a string "(1, 2, 3)"
    # and returns a tuple of 3 or 4 intergers in range [0,255].
    # If case of failure to convert, returns middle grey values.
    if type(instr) == tuple or type(instr) == list:
        return tuple(instr)
    if type(instr) != str:
        logger.debug(f"convert_color_string: color {instr} ({type(instr)}) not found, using grey")
        return (128, 128, 128)
    # it's a string...
    instr = instr.strip()
    if "," in instr and instr.startswith("("):  # "(255, 7, 2)"
        a = instr.replace("(", "").replace(")", "").split(",")
        return tuple([int(e) for e in a])
    else:  # it may be a color name...
        try:
            color = ImageColor.getrgb(instr)
        except ValueError:
            logger.debug(f"convert_color_string: fail to convert color {instr} ({type(instr)}), using grey")
            color = (128, 128, 128)
        return color
    logger.debug(f"convert_color_string: not a string {instr} ({type(instr)}), using grey")
    return (128, 128, 128)


class AnnunciatorButton(Button):

    def __init__(self, config: dict, page: "Page"):

        self.lit = {}  # parts of annunciator that are lit

        self.multi_icons = config.get("multi-icons")
        self.icon = config.get("icon")

        self.annunciator = None                   # working def
        self.annunciator_datarefs = None          # cache
        self._annunciator = config.get("annunciator")  # keep raw
        if self._annunciator is not None:
            self.annunciator = merge({}, ANNUNCIATOR_DEFAULTS, self._annunciator)
        else:
            logger.error(f"__init__: button {self.name}: has no annunciator property")

        Button.__init__(self, config=config, page=page)

        if self.annunciator is not None and (config.get("icon") is not None or config.get("multi-icons") is not None):
            logger.warning(f"__init__: button {self.name}: has annunciator property with icon/multi-icons, ignoring icons")

        if self.annunciator is not None:
            self.icon = None
            self.multi_icons = None

            # Normalize annunciator in case of A type (single part)
            atyp = self.annunciator.get("type", "A")
            parts = self.annunciator.get("parts")
            if atyp == "A" and parts is None:  # if only one annunciator, no need for "parts" (special case)
                self.annunciator["parts"] = { "A0": self.annunciator }
                logger.debug(f"__init__: button {self.name}: annunciator part normalized")

    def part_iterator(self):
        """
        Build annunciator part index list
        """
        atyp = self.annunciator.get("type", "A")
        acnt = 1
        if atyp in "BC":
            acnt = 2
        elif atyp in "DE":
            acnt = 3
        elif atyp == "F":
            acnt = 4
        return [atyp + str(partnum) for partnum in range(acnt)]

    def get_annunciator_datarefs(self, base:dict = None):
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        # print_stack(logger)
        if self.annunciator_datarefs is not None:
            # logger.debug(f"get_annunciator_datarefs: button {self.name}: returned from cache")
            return self.annunciator_datarefs
        r = []
        parts = self.annunciator.get("parts")
        for key in self.part_iterator():
            if key in parts.keys():
                datarefs = super().get_datarefs(base=parts[key])
                if len(datarefs) > 0:
                    r = r + datarefs
                    logger.debug(f"get_annunciator_datarefs: button {self.name}: added {key} datarefs {datarefs}")
        self.annunciator_datarefs = list(set(r))
        return self.annunciator_datarefs

    def get_datarefs(self, base:dict = None):
        """
        Complement button datarefs with annunciator special lit datarefs
        """
        if self.all_datarefs is not None:  # cached
            logger.debug(f"get_datarefs: button {self.name}: returned from cache")
            return self.all_datarefs

        r = super().get_datarefs()
        a = self.get_annunciator_datarefs()
        if len(a) > 0:
            r = r + a
        if DATAREF_RPN in r:  # label: ${dataref-rpn}, DATAREF_RPN is not a dataref.
            r.remove(DATAREF_RPN)
        return list(set(r))

    def button_level_driven(self) -> bool:
        """
        Determine if we need to consider either the global button-level value or
        individula part-level values
        """
        button_level = True
        # Is there material to decide at part level?
        parts = self.annunciator["parts"]
        for key in self.part_iterator():
            if key in parts:
                c = parts[key]
                if DATAREF_RPN in c or "dataref" in c:
                    button_level = False
                # else remains button-level True
        if not button_level:
            logger.debug(f"button_level_driven: button {self.name}: driven at part level")
            datarefs = self.get_annunciator_datarefs()
            if len(datarefs) < 1:
                logger.warning(f"button_level_driven: button {self.name}: no part dataref")
            return False
        # Is there material to decide at button level?
        logger.debug(f"button_level_driven: button {self.name}: driven at button level")
        if self.dataref is None and self.datarefs is None and self.dataref_rpn is None:  # Airbus button is driven by button-level dataref
            logger.warning(f"button_level_driven: button {self.name}: no button dataref")
        return True

    def button_value(self):
        """
        Same as button value, but exclusively for Annunciator-type buttons with distinct values for each part.
        If button is driven by single dataref, we forward to button class.
        Else, we check with the supplied dataref/dataref-rpn that the button is lit or not for each button part.
        """
        if self.button_level_driven():
            logger.debug(f"button_value: button {self.name}: driven by button-level dataref")
            return super().button_value()

        r = {}
        parts = self.annunciator.get("parts")
        for key in self.part_iterator():
            if key in parts.keys():
                c = parts[key]
                if DATAREF_RPN in c:
                    calc = c[DATAREF_RPN]
                    expr = self.substitute_dataref_values(calc)
                    rpc = RPC(expr)
                    res = rpc.calculate()
                    logger.debug(f"button_value: button {self.name}: {key}: {expr}={res}")
                    r[key] = 1 if (res is not None and res > 0) else 0
                elif "dataref" in c:
                    dataref = c["dataref"]
                    res = self.get_dataref_value(dataref)
                    logger.debug(f"button_value: button {self.name}: {key}: {dataref}={res}")
                    r[key] = 1 if (res is not None and res > 0) else 0
                else:
                    logger.debug(f"button_value: button {self.name}: {key}: no formula, set to 0")
                    r[key] = 0
            else:
                r[key] = 0
                logger.debug(f"button_value: button {self.name}: {key}: key not found, set to 0")
        # logger.debug(f"annunciator_button_value: button {self.name} returning: {r}")
        return r

    def set_key_icon(self):
        logger.debug(f"set_key_icon: button {self.name} has current value {self.current_value}")
        if self.current_value is not None and type(self.current_value) in [dict] and len(self.current_value) > 1:
            logger.debug(f"set_key_icon: button {self.name}: driven by part dataref")
            self.lit = {}
            for key in self.part_iterator():
                self.lit[key] = self.current_value[key] != 0
        elif self.current_value is not None and type(self.current_value) in [int, float]:
            logger.debug(f"set_key_icon: button {self.name}: driven by button-level dataref")
            self.lit = {}
            for key in self.part_iterator():
                self.lit[key] = self.current_value != 0
        # else: leave untouched

    def get_image(self):
        """
        """
        self.set_key_icon()
        return self.mk_annunciator()

    def mk_annunciator(self):
        # If the part is not lit, a darker version is printed unless dark option is added to button
        # in which case nothing gets added to the button.
        AC = {
            "A0": [0.50, 0.50],
            "B0": [0.50, 0.25],
            "B1": [0.50, 0.75],
            "C0": [0.25, 0.50],
            "C1": [0.75, 0.50],
            "D0": [0.50, 0.25],
            "D1": [0.25, 0.75],
            "D2": [0.75, 0.75],
            "E0": [0.25, 0.25],
            "E1": [0.25, 0.75],
            "E2": [0.50, 0.75],
            "F0": [0.25, 0.25],
            "F1": [0.75, 0.25],
            "F2": [0.25, 0.75],
            "F3": [0.75, 0.75]
        }

        def light_off(color, lightness: float = LIGHT_OFF_BRIGHTNESS / 100):
            # Darkens (or lighten) a color
            if color.startswith("("):
                color = convert_color(color)
            if type(color) == str:
                color = ImageColor.getrgb(color)
            a = list(colorsys.rgb_to_hls(*[c / 255 for c in color]))
            a[1] = lightness
            return tuple([int(c * 256) for c in colorsys.hls_to_rgb(*a)])

        def get_color(disp:dict, lit: bool):
            color = disp.get("color")
            if type(color) == tuple or type(color) == list:  # we transfort it back to a string, read on...
                color = "(" + ",".join([str(i) for i in color]) + ")"

            if not lit:
                try:
                    color = disp.get("off-color", light_off(color))
                except ValueError:
                    logger.debug(f"mk_annunciator: button {self.name}: color {color} ({type(color)}) not found, using grey")
                    color = (128, 128, 128)
            elif color.startswith("("):
                color = convert_color(color)
            else:
                try:
                    color = ImageColor.getrgb(color)
                except ValueError:
                    logger.debug(f"mk_annunciator: color {color} not found, using grey")
                    color = (128, 128, 128)
            return color

        def has_frame(part: dict):
            framed = part.get("framed")
            if framed is None:
                return False
            if type(framed) == bool:
                return framed
            elif type(framed) == int:
                return framed == 1
            elif type(framed) == str:
                return framed.lower() in ["true", "on", "yes", "1"]
            return False

        def get_text(base: dict, text_format: str = None):
            """
            Returns text, if any, with substitution of datarefs if any.
            Same as Button.get_label().
            """
            label = base.get("text")
            DATAREF_RPN_STR = f"${{DATAREF_RPN}}"

            # logger.debug(f"get_text: button {self.name}: raw: {label}")
            # If text contains ${dataref-rpn}, it is replaced by the value of the dataref-rpn calculation.
            # So we do it.
            if label is not None:
                if DATAREF_RPN_STR in label:
                    dataref_rpn = base.get(DATAREF_RPN)
                    if dataref_rpn is not None:
                        expr = self.substitute_dataref_values(dataref_rpn)
                        rpc = RPC(expr)
                        res = rpc.calculate()  # to be formatted
                        if text_format is None:
                            text_format = base.get("text-format")
                        if text_format is not None:
                            res = text_format.format(res)
                        else:
                            res = str(res)
                        label = label.replace(DATAREF_RPN_STR, res)
                    else:
                        logger.warning(f"get_text: button {self.name}: text contains {DATAREF_RPN_STR} not no attribute found")
                else:
                    label = self.substitute_dataref_values(label, formatting=text_format, default="---")
                # logger.debug(f"get_text: button {self.name}: returned: {label}")
            return label


        ICON_SIZE = 256  # px
        inside = ICON_SIZE / 32 # 8px

        # Button overall size: full, large, medium, small.
        size = self.annunciator.get("size", "large")
        if size == "small":  # about 1/2, starts at 128
            button_height = int(ICON_SIZE / 2)
            box = (0, int(ICON_SIZE/4))
        elif size == "medium":  # about 5/8, starts at 96
            button_height = int(10 * ICON_SIZE / 16)
            box = (0, int(3 * ICON_SIZE / 16))
        elif size == "full":  # starts at 0
            button_height = ICON_SIZE
            box = (0, 0)
        else:  # "large", full size, default, starts at 48
            button_height = int(13 * ICON_SIZE / 16)
            box = (0, int(3 * ICON_SIZE / 16))

        led_offset = inside
        text_size = int(ICON_SIZE / 4)

        # PART 1:
        # Texts that will glow if Korry style
        glow = Image.new(mode="RGBA", size=(ICON_SIZE, button_height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        back = Image.new(mode="RGBA", size=(ICON_SIZE, button_height), color=(0, 0, 0, 0))
        bg   = ImageDraw.Draw(back)

        parts = self.annunciator.get("parts")
        for partname in self.part_iterator():
            part = parts.get(partname)
            if part is not None:
                txt = get_text(part)
                if txt is not None:  # we need to display text...
                    display_pos = "mm"  # part.get("position", "mm")  # always centered
                    text = get_text(part)  # part.get("text")
                    if text is not None:
                        fontname = self.get_font(part.get("font"))
                        font = ImageFont.truetype(fontname, part.get("size", text_size))
                        w = glow.width / 2
                        p = "m"
                        a = "center"
                        if display_pos[0] == "l":
                            w = inside
                            p = "l"
                            a = "left"
                        elif display_pos[0] == "r":
                            w = glow.width - inside
                            p = "r"
                            a = "right"
                        w, h = AC[partname]
                        w = w * 256
                        h = h * 256
                        # logger.debug(f"mk_annunciator: position {display_pos}: {(w, h)}, {part}")
                        color = get_color(part, self.lit[partname])

                        if self.lit[partname] or not ANNUNCIATOR_STYLE == "v":
                            invert = part.get("invert")
                            if self.lit[partname] and invert is not None:
                                if w == 128:
                                    w0 = 0
                                    w1 = 2 * w
                                else:
                                    w0 = w - 64
                                    w1 = w + 64
                                if h == 128:
                                    h0 = 0
                                    h1 = 2 * w
                                else:
                                    h0 = h - 64
                                    h1 = h + 64
                                frame = ((w0, h0), (w1, h1))
                                invert_color = convert_color_string(invert)
                                bg.rectangle(frame, fill=invert_color)

                            draw.multiline_text((w, h),  # (glow.width / 2, 15)
                                      text=text,
                                      font=font,
                                      anchor=p+"m",
                                      align=a,
                                      fill=color)

                            if has_frame(part):
                                txtbb = draw.multiline_textbbox((w, h),  # min frame, just around the text
                                          text=text,
                                          font=font,
                                          anchor=p+"m",
                                          align=a)
                                margin = 3 * inside
                                framebb = ((txtbb[0]-margin, txtbb[1]-margin), (txtbb[2]+margin, txtbb[3]+margin))

                                thick = int(button_height / 16)

                                he = 128 if h == 128 else 64
                                hstart = (h - he) + inside
                                height = 2 * (he - inside)
                                we = 128 if w == 128 else 64
                                wstart = (w - we) + inside
                                width = 2 * (we - inside)
                                framemax = ((wstart, hstart), (wstart + width, hstart + height))
                                # logger.debug(f"mk_annunciator: {partname}: {w} x {h} (inside={inside},thick={thick})")
                                # logger.debug(f"mk_annunciator:  framebb: {framebb}")
                                # logger.debug(f"mk_annunciator: framemax: {framemax}")
                                # optimal frame, largest possible in button and that surround text
                                frame = ((min(framebb[0][0], framemax[0][0]),min(framebb[0][1], framemax[0][1])), (max(framebb[1][0], framemax[1][0]), max(framebb[1][1], framemax[1][1])))
                                draw.rectangle(frame, outline=color, width=thick)
                else:  # no text, try led:
                    led = part.get("led")
                    w, h = AC[partname]
                    w = w * 256
                    h = h * 256
                    color = get_color(part, self.lit[partname])
                    if led is not None:
                        if led in ["block", "led"]:
                            thick = 30
                            if size == "large":
                                thick = 40
                            frame = ((w - 64 + 2 * inside, h - thick / 2), (w + 64 - 2 * inside, h + thick / 2))
                            draw.rectangle(frame, fill=color)
                        elif led in ["bar", "bars"]:
                            nbar = 3
                            thick = 10
                            if size == "large":
                                thick = 12
                            spacer = 3
                            hstart = h - (nbar * thick + (nbar - 1) * spacer) / 2
                            for i in range(3):
                                frame = ((w - 64 + 2 * inside, hstart), (w + 64 - 2 * inside, hstart + thick))
                                draw.rectangle(frame, fill=color)
                                hstart = hstart + thick + spacer
                        elif led == "dot":
                            # Plot a series of circular dot on a line
                            radius = ICON_SIZE / 16  # LED diameter
                            frame = ((w - radius, h - radius), (w + radius, h + radius))
                            draw.ellipse(frame, fill=color)
                        elif led == "lgear":
                            nins = 8
                            w2 = w
                            if w == 128:
                                w0 = (nins / 4) * inside
                                w1 = 2 * w - (nins / 4) * inside
                            else:
                                w0 = w - 64 + (nins / 4) * inside
                                w1 = w + 64 - (nins / 4) * inside
                            if h == 128:
                                h0 = nins * inside
                                h1 = 2 * w - nins * inside
                            else:
                                h0 = h - 64 + (nins / 2) * inside
                                h1 = h + 64 - (nins / 2) * inside
                            triangle = [(w0, h0), (w1, h0), (w2, h1), (w0, h0)]
                            draw.polygon(triangle, outline=color, width=int(96/nins))
                        else:
                            logger.warning(f"mk_annunciator: button {self.name}: part {partname}: invalid led {led}")
                    else:
                        logger.warning(f"mk_annunciator: button {self.name}: part {partname}: no text, no led")
            else:
                logger.warning(f"mk_annunciator: button {self.name}: part {partname}: nothing to display")


        # PART 1.2: Glowing texts, later because not nicely perfect.
        if ANNUNCIATOR_STYLE == "k":
            # blurred_image = glow.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=10))
            blurred_image1 = glow.filter(ImageFilter.GaussianBlur(16)) # self.annunciator.get("blurr", 10)
            blurred_image2 = glow.filter(ImageFilter.GaussianBlur(6)) # self.annunciator.get("blurr", 10)
            # blurred_image = glow.filter(ImageFilter.BLUR)
            glow.alpha_composite(blurred_image1)
            glow.alpha_composite(blurred_image2)
            # glow = blurred_image
            # logger.debug("mk_annunciator: blurred")

        # We paste the transparent glow into a button:
        color = get_color(self.annunciator, True)
        button = Image.new(mode="RGB", size=(ICON_SIZE, button_height), color=color)
        button.paste(back, box=box)
        button.paste(glow, mask=glow)

        # PART 2: Background
        image = Image.new(mode="RGB", size=(ICON_SIZE, ICON_SIZE), color=self.annunciator.get("background", "lightsteelblue"))
        draw = ImageDraw.Draw(image)

        # Button
        image.paste(button, box=box)

        # PART 3: Title
        if self.label is not None:
            title_pos = self.label_position
            fontname = self.get_font()
            size = 2 * self.label_size
            font = ImageFont.truetype(fontname, size)
            w = image.width / 2
            p = "m"
            a = "center"
            if title_pos[0] == "l":
                w = inside
                p = "l"
                a = "left"
            elif title_pos[0] == "r":
                w = image.width - inside
                p = "r"
                a = "right"
            h = (box[1] + self.label_size ) / 2  # middle of "title" box
            # logger.debug(f"mk_annunciator: position {title_pos}: {(w, h)}")
            draw.multiline_text((w, h),  # (image.width / 2, 15)
                      text=self.label,
                      font=font,
                      anchor=p+"m",
                      align=a,
                      fill=self.label_color)

        # Button
        # image.paste(button, box=box)

        # logger.debug(f"mk_annunciator: button {self.name}: ..done")

        return image


class AnnunciatorButtonPush(AnnunciatorButton):
    """
    Execute command once when key pressed. Nothing is done when button is released.
    """
    def __init__(self, config: dict, page: "Page"):
        AnnunciatorButton.__init__(self, config=config, page=page)

    def is_valid(self):
        if self.command is None:
            logger.warning(f"is_valid: button {self.name} has no command")
            if not self.has_option("counter"):
                logger.warning(f"is_valid: button {self.name} has no command or counter option")
                return False
        return super().is_valid()

    def activate(self, state: bool):
        # logger.debug(f"ButtonPush::activate: button {self.name}: {state}")
        super().activate(state)
        if state:
            if self.is_valid():
                if self.command is not None:
                    self.xp.commandOnce(self.command)
                self.render()
            else:
                logger.warning(f"activate: button {self.name} is invalid")


class AnnunciatorButtonAnimate(AnnunciatorButton):
    """
    """
    def __init__(self, config: dict, page: "Page"):
        self.running = None  # state unknown
        self.thread = None
        self.finished = None
        self.counter = 0
        AnnunciatorButton.__init__(self, config=config, page=page)
        self.speed = float(self.option_value("animation_speed", 0.5))

        self.render()

    def should_run(self):
        """
        Check conditions to animate the icon.
        """
        logger.debug(f"should_run: button {self.name}: current value {self.current_value}, ({type(self.current_value)})")
        # If computed value:
        if self.has_option("counter"):
            self.current_value = self.pressed_count % 2 if self.pressed_count is not None else 0
            logger.debug(f"should_run: button {self.name}: current counter value {self.current_value}")
            return self.current_value == 0

        if self.current_value is None:
            logger.debug(f"should_run: button {self.name}: current value is None, returning False")
            return False

        # If scalar value:
        if type(self.current_value) in [int, float]:
            logger.debug(f"should_run: button {self.name}: current value is integer")
            if self.has_option("inverted_logic"):
                logger.debug(f"should_run: button {self.name}: inverted logic")
                return self.current_value == 0
            return self.current_value != 0

        # If array or tuple value
        for i in self.current_value:
            if i is not None:
                if type(i) == bool and i != False:
                    logger.debug(f"should_run: button {self.name}: complex current bool value {i}, returning True")
                    return True
                elif type(i) == int and i != 0:
                    logger.debug(f"should_run: button {self.name}: complex current int value {i}, returning True")
                    return True
                # else, do nothing, False assumed ("no clear sign to set it True")
            # else, do nothing, None assumed False
        logger.debug(f"should_run: button {self.name}: complex current value {self.current_value}, returning False")
        return False  # all individual scalar in array or tuple are None, or 0, or False

    def loop(self):
        self.finished = threading.Event()
        while self.running:
            self.render()
            self.counter = self.counter + 1
            time.sleep(self.speed)
        self.finished.set()

    def anim_start(self):
        if not self.running:
            logger.debug(f"anim_start: button {self.name}: starting..")
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.name = f"AnnunciatorButtonAnimate::loop({self.name})"
            self.thread.start()
            logger.debug(f"anim_start: button {self.name}: ..started")
        else:
            logger.warning(f"anim_start: button {self.name}: already started")

    def anim_stop(self):
        if self.running:
            logger.debug(f"anim_stop: button {self.name}: stopping..")
            self.running = False
            if not self.finished.wait(timeout=2*self.speed):
                logger.warning(f"anim_stop: button {self.name}: did not get finished signal")
            logger.debug(f"anim_start: button {self.name}: ..stopped")
            self.render()
        else:
            logger.debug(f"anim_stop: button {self.name}: already stopped")

    def set_key_icon(self):
        """
        If button has more icons, select one from button current value
        """
        if self.running:
            if k in self.lit.keys():
                self.lit[k] = not self.lit[k]
#            logger.debug(f"set_key_icon: button {self.name}: running")
        else:
#            logger.debug(f"set_key_icon: button {self.name}: NOT running")
            if k in self.lit.keys():
                self.lit[k] = False
            super().set_key_icon()  # set off icon

    # Works with activation on/off
    def activate(self, state: bool):
        super().activate(state)
        if state:
            if self.is_valid():
                # self.label = f"pressed {self.current_value}"
                self.xp.commandOnce(self.command)
                if self.should_run():
                    self.anim_start()
                else:
                    self.anim_stop()
                    self.render()  # renders default "off" icon
        logger.debug(f"activate: button {self.name}: {self.pressed_count}")

    # Works if underlying dataref changed
    def dataref_changed(self, dataref: "Dataref"):
        """
        One of its dataref has changed, records its value and provoke an update of its representation.
        """
        self.set_current_value(self.button_value())
        logger.debug(f"{self.name}: {self.previous_value} -> {self.current_value}")
        if self.should_run():
            self.anim_start()
        else:
            self.anim_stop()
            self.render()  # renders default "off" icon

    def render(self):
        if self.running is None:  # state unknown?
            logger.debug(f"render: button {self.name}: unknown state")
            if self.should_run():
                self.anim_start()
            else:
                logger.debug(f"render: button {self.name}: stopping..")
                self.anim_stop()
                super().render() # renders default "off" icon
            logger.debug(f"render: button {self.name}: ..done")
        else:
            super().render()

    def clean(self):
        logger.debug(f"clean: button {self.name}: asking to stop..")
        self.anim_stop()
        self.running = None  # unknown state
        logger.debug(f"clean: button {self.name}: ..stopped")
