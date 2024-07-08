from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
import logging

from cockpitdecks.constant import CONFIG_KW
from .resources.rpc import RPC
from .resources.iconfonts import ICON_FONTS

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

DECK_BUTTON_DEFINITION = "_deck_def"


# Dataref and local variable scanning
# Note:
# Local datarefs (data:...) are managed like regular datarefs.

INTERNAL_STATE_PREFIX = "state:"
BUTTON_VARIABLE_PREFIX = "button:"

# ${ ... }: dollar + anything between curly braces, but not start with state: or button: prefix
PATTERN_DOLCB = f"\\${{(?!({INTERNAL_STATE_PREFIX}|{BUTTON_VARIABLE_PREFIX}))([^\\}}]+?)}}"


class Value:
    """Value class.

    Defines a value used by Cockpitdecks which is based on datarefs and button state variables.
    """

    def __init__(self, name: str, config: dict, button: "Button"):
        self._config = config
        self._button = button
        self.name = name  # for debeging and information purpose

        # Used in "value"
        self._datarefs = []
        self._statevars = {}

    def init(self):
        pass

    def get_dataref_value(self, dataref):
        return self._button.get_dataref_value(dataref)

    def get_state_value(self, state):
        return self._button.get_state_value(state)

    @property
    def formula(self) -> str:
        # Formula
        return self._config.get(CONFIG_KW.FORMULA.value, "")

    @property
    def string_datarefs(self) -> list:
        # List of string datarefs
        return self._config.get(CONFIG_KW.STRING_DATAREFS.value, [])

    @property
    def dataref(self) -> list:
        # Single datatef
        return self._config.get(CONFIG_KW.DATAREF.value, [])

    @property
    def datarefs(self) -> list:
        # List of datarefs
        return self._config.get(CONFIG_KW.DATAREFS.value, [])

    def get_datarefs(self, base: dict | None = None) -> list:
        """
        Returns all datarefs used by this button from label, texts, computed datarefs, and explicitely
        listed dataref and datarefs attributes.
        This can be applied to the entire button or to a subset (for annunciator parts)
        """
        if base is None:  # local, button-level ones
            if self._datarefs is not None:  # cached if globals (base is None)
                return self._datarefs
            base = self._config

        r = self.scan_datarefs(base)
        r = list(set(r))  # removes duplicates
        logger.debug(f"value {self.name}: found datarefs {r}")
        return r

    def scan_datarefs(self, base: dict, extra_keys: list = [CONFIG_KW.FORMULA.value]) -> list:
        """
        scan all datarefs in texts, computed datarefs, or explicitely listed.
        This is applied to the entire button or to a subset (for annunciator parts for example).
        """

        def is_dref(r):
            # ${state:button-value} is not a dataref, BUT ${data:path} is a "local" dataref
            PREFIX = list(ICON_FONTS.keys()) + [INTERNAL_STATE_PREFIX[:-1], BUTTON_VARIABLE_PREFIX[:-1]]
            SEP = ":"
            for s in PREFIX:
                if r.startswith(s + SEP):
                    return False
            return r != CONFIG_KW.FORMULA.value

        r = []

        # Direct use of datarefs:
        #
        # 1.1 Single
        dataref = base.get(CONFIG_KW.DATAREF.value)
        if dataref is not None and is_dref(dataref):
            r.append(dataref)
            logger.debug(f"value {self.name}: added single dataref {dataref}")
        #
        # Note:
        #
        #    If button, we need to add managed and guarded datarefs
        #

        # 1.2 Multiple
        datarefs = base.get(CONFIG_KW.MULTI_DATAREFS.value)
        if datarefs is not None:
            a = []
            for d in datarefs:
                if is_dref(d):
                    r.append(d)
                    a.append(d)
            logger.debug(f"value {self.name}: added multiple datarefs {a}")

        # 2. In string datarefs:
        if CONFIG_KW.FORMULA.value not in extra_keys:
            extra_keys.append(CONFIG_KW.FORMULA.value)

        for key in extra_keys:
            text = base.get(key)
            if text is not None and type(text) == str:
                datarefs = re.findall(PATTERN_DOLCB, text)
                datarefs = list(filter(lambda x: is_dref(x), datarefs))
                if len(datarefs) > 0:
                    r = r + datarefs
                    logger.debug(f"value {self.name}: added datarefs found in {key}: {datarefs}")

        # Clean up
        if CONFIG_KW.FORMULA.value in r:  # label or text may contain like ${{CONFIG_KW.FORMULA.value}}, but {CONFIG_KW.FORMULA.value} is not a dataref.
            r.remove(CONFIG_KW.FORMULA.value)
        if None in r:
            r.remove(None)

        return list(set(r))  # removes duplicates

    # ##################################
    # Formula value substitution
    #
    def substitute_dataref_values(self, message: str | int | float, default: str = "0.0", formatting=None):
        """
        Replaces ${dataref} with value of dataref in labels and execution formula.
        @todo: should take into account dataref value type (Dataref.xp_data_type or Dataref.data_type).
        """
        if type(message) is int or type(message) is float:  # probably formula is a constant value
            value_str = message
            if formatting is not None:
                if formatting is not None:
                    value_str = formatting.format(message)
                    logger.debug(f"value {self.name}:received int or float, returning as is.")
                else:
                    value_str = str(message)
                    logger.debug(f"value {self.name}:received int or float, returning formatted {formatting}.")
            return value_str

        dataref_names = re.findall(PATTERN_DOLCB, message)

        if len(dataref_names) == 0:
            return message

        if formatting is not None:
            if type(formatting) == list:
                if len(dataref_names) != len(formatting):
                    logger.warning(
                        f"value {self.name}:number of datarefs {len(dataref_names)} not equal to the number of format {len(formatting)}, cannot proceed."
                    )
                    return message
            elif type(formatting) != str:
                logger.warning(f"value {self.name}:single format is not a string, cannot proceed.")
                return message

        retmsg = message
        cnt = 0
        for dataref_name in dataref_names:
            value = self.get_dataref_value(dataref_name)
            value_str = ""
            if formatting is not None and value is not None:
                if type(formatting) == list:
                    value_str = formatting[cnt].format(value)
                elif formatting is not None and type(formatting) == str:
                    value_str = formatting.format(value)
            else:
                value_str = str(value) if value is not None else str(default)  # default gets converted in float sometimes!
            retmsg = retmsg.replace(f"${{{dataref_name}}}", value_str)
            cnt = cnt + 1

        more = re.findall(PATTERN_DOLCB, retmsg)  # XXXHERE
        if len(more) > 0:
            logger.warning(f"value {self.name}:unsubstituted dataref values {more}")

        return retmsg

    def substitute_state_values(self, text, default: str = "0.0", formatting=None):
        status = self.get_state_variables()
        txtcpy = text
        more = re.findall(f"\\${{{INTERNAL_STATE_PREFIX}([^\\}}]+?)}}", txtcpy)
        for name in more:
            state_string = f"${{{INTERNAL_STATE_PREFIX}{name}}}"  # @todo: !!possible injection!!
            value = self.button.get_state_value(name)
            if value is not None:
                txtcpy = txtcpy.replace(state_string, default)
            else:
                txtcpy = txtcpy.replace(state_string, value)
        more = re.findall(f"\\${{{INTERNAL_STATE_PREFIX}([^\\}}]+?)}}", txtcpy)
        if len(more) > 0:
            logger.warning(f"value {self.name}:unsubstituted status values {more}")
        return txtcpy

    # def substitute_button_values(self, text, default: str = "0.0", formatting=None):
    #     # Experimental, do not use
    #     txtcpy = text
    #     more = re.findall("\\${button:([^\\}]+?)}", txtcpy)
    #     if len(more) > 0:
    #         for m in more:
    #             v = self.deck.cockpit.get_button_value(m)  # starts at the top
    #             if v is None:
    #                 logger.warning(f"value {self.name}:{m} has no value")
    #                 v = str(default)
    #             else:
    #                 v = str(v)  # @todo: later: use formatting
    #             m_str = f"${{button:{m}}}"  # "${formula}"
    #             txtcpy = txtcpy.replace(m_str, v)
    #             logger.debug(f"value {self.name}:replaced {m_str} by {str(v)}. ({m})")
    #     more = re.findall("\\${button:([^\\}]+?)}", txtcpy)
    #     if len(more) > 0:
    #         logger.warning(f"value {self.name}:unsubstituted button values {more}")
    #     return txtcpy

    def substitute_values(self, text, default: str = "0.0", formatting=None):
        if type(text) != str or "$" not in text:  # no ${..} to stubstitute
            return text
        step1 = self.substitute_state_values(text, default=default, formatting=formatting)
        if text != step1:
            logger.log(SPAM_LEVEL, f"substitute_values: value {self.name}:{text} => {step1}")
        # step2 = self.substitute_button_values(step1, default=default, formatting=formatting)
        # logger.log(SPAM_LEVEL, f"substitute_values: value {self.name}:{step1} => {step2}")
        step2 = step1
        step3 = self.substitute_dataref_values(step2, default=default, formatting=formatting)
        if step3 != step2:
            logger.log(SPAM_LEVEL, f"substitute_values: value {self.name}:{step2} => {step3}")
        return step3

    # ##################################
    # Formula Execution
    #
    def execute_formula(self, formula, default: float = 0.0):
        """
        replace datarefs variables with their (numeric) value and execute formula.
        Returns formula result.
        """
        expr = self.substitute_values(text=formula, default=str(default))
        # logger.debug(f"value {self.name}:{formula} => {expr}")
        r = RPC(expr)
        value = r.calculate()
        # print("FORMULA", formula, "=>", expr, "=", value)
        logger.logger(
            f"execute_formula: value {self.name}:{formula} => {expr}:  => {value}",
        )
        return value

    # ##################################
    # Value computation
    #
    def use_internal_state(self) -> bool:
        return self.formula is not None and INTERNAL_STATE_PREFIX in self.formula

    def get_value(self):
        """ """
        # 1. If there is a formula, value comes from it
        if self.formula is not None:
            logger.debug(f"value {self.name}:formula without dataref")
            return self.execute_formula(formula=self.formula)

        # 3. One dataref
        if len(self._datarefs) == 1:
            # if self._datarefs[0] in self.page.datarefs.keys():  # unnecessary check
            logger.debug(f"value {self.name}:single dataref {self._datarefs[0]}")
            return self.get_dataref_value(self._datarefs[0])

        # 4. Multiple datarefs
        if len(self._datarefs) > 1:
            r = {}
            for d in self._datarefs:
                v = self.get_dataref_value(d)
                r[d] = v
            logger.debug(f"value {self.name}:getting dict of datarefs")
            return r

        return None
