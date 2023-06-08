# ###########################
# Buttons that are drawn on render()
#
# Buttons were isolated here bevcause they use quite larger packages (avwx-engine),
# call and rely on external services.
#
import logging
import random
import re
from functools import reduce
from datetime import datetime, timezone

from avwx import Metar, Station
from suntime import Sun
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from PIL import Image, ImageDraw

from cockpitdecks import ICON_SIZE
from cockpitdecks.resources.iconfonts import WEATHER_ICONS, WEATHER_ICON_FONT
from cockpitdecks.resources.color import convert_color, light_off
from cockpitdecks.xplane import Dataref

from .draw import DrawBase, DrawAnimation
from .annunciator import TRANSPARENT_PNG_COLOR


logger = logging.getLogger(__name__)
# logger.setLevel(SPAM_LEVEL)
logger.setLevel(logging.DEBUG)

# #############
# Local constant
#
KW_NAME   = "iconName"      # "cloud",
KW_DAY    = "day"           # 2,  0=night, 1=day, 2=day or night
KW_NIGHT  = "night"         # 1,
KW_TAGS   = "descriptor"    # [],
KW_PRECIP = "precip"        # "RA",
KW_VIS    = "visibility"    # [""],
KW_CLOUD  = "cloud"         # ["BKN"],
KW_WIND   = "wind"          # [0, 21]

WI_PREFIX = "wi-"
DAY       = "day-"
NIGHT     = "night-"
NIGHT_ALT = "night-alt-"

KW_CAVOK  = "clear"         # Special keyword for CAVOK day or night
CAVOK_DAY = "wi-day-sunny"
CAVOK_NIGHT  = "wi-night-clear"
DEFAULT_ICON = "wi-day-cloudy-high"


class WI:
    """
    Simplified weather icon
    """
    I_S = [
        "_sunny",
        "_cloudy",
        "_cloudy_gusts",
        "_cloudy_windy",
        "_fog",
        "_hail",
        "_haze",
        "_lightning",
        "_rain",
        "_rain_mix",
        "_rain_wind",
        "_showers",
        "_sleet",
        "_sleet_storm",
        "_snow",
        "_snow_thunderstorm",
        "_snow_wind",
        "_sprinkle",
        "_storm_showers",
        "_sunny_overcast",
        "_thunderstorm",
        "_windy",
        "_cloudy_high",
        "_light_wind"
    ]

    DB = [
        {
            KW_NAME: KW_CAVOK,
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["CAVOK", "NCD"],
            KW_CLOUD: [""],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "cloud",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["BKN"],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "cloudy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["OVC"],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "cloudy-gusts",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["SCT", "BKN", "OVC"],
            KW_WIND: [22, 63]
        },
        {
            KW_NAME: "rain",
            KW_TAGS: [],
            KW_PRECIP: "RA",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "rain-wind",
            KW_TAGS: [],
            KW_PRECIP: "RA",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [22, 63]
        },
        {
            KW_NAME: "showers",
            KW_TAGS: ["SH"],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 63]
        },
        {
            KW_NAME: "fog",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["BR", "FG"],
            KW_CLOUD: [""],
            KW_WIND: [0, 63]
        },
        {
            KW_NAME: "storm-showers",
            KW_TAGS: ["TS", "SH"],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 63]
        },
        {
            KW_NAME: "thunderstorm",
            KW_TAGS: ["TS"],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 63]
        },
        {
            KW_NAME: "windy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["CAVOK", "NCD"],
            KW_CLOUD: [""],
            KW_WIND: [22, 33]
        },
        {
            KW_NAME: "strong-wind",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: ["CAVOK", "NCD"],
            KW_CLOUD: [""],
            KW_WIND: [34, 63]
        },
        {
            KW_NAME: "cloudy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "cloudy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "cloudy-gusts",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["SCT", "BKN", "OVC"],
            KW_WIND: [22, 63]
        },
        {
            KW_NAME: "cloudy-gusts",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["SCT", "BKN", "OVC"],
            KW_WIND: [22, 63]
        },
        {
            KW_NAME: "cloudy-windy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [22, 63]
        },
        {
            KW_NAME: "cloudy-windy",
            KW_TAGS: [],
            KW_PRECIP: "",
            KW_VIS: [""],
            KW_CLOUD: ["FEW", "SCT"],
            KW_WIND: [22, 63]
        },
        {
            KW_NAME: "snow",
            KW_TAGS: [],
            KW_PRECIP: "SN",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [0, 21]
        },
        {
            KW_NAME: "snow-wind",
            KW_TAGS: [],
            KW_PRECIP: "SN",
            KW_VIS: [""],
            KW_CLOUD: [""],
            KW_WIND: [22, 63]
        },
    ]



    def __init__(self, day: bool, cover=float, wind=float, precip=float, special=float):
        self.day = day          # night=False, time at location (local time)
        self.cover = cover      # 0=clear, 1=overcast
        self.wind = wind        # 0=no wind, 1=storm
        self.precip = precip    # 0=none, 1=rain1, 2=rain2, 3=snow, 4=hail
        self.special = special  # 0=none, 1=fog, 2=sandstorm

    def icon(self):
        return f"wi_{'day' if self.day else 'night'}" + random.choice(WI.I_S)

    # @staticmethod
    # def check():
    #     err = 0
    #     for i in WI.DB:
    #         if i["iconName"] not in WEATHER_ICONS.keys():
    #             logger.error(f"check: invalid icon {i['iconName']}")
    #             err = err + 1
    #     if err > 0:
    #         logger.error(f"check: {err} invalid icons")

class WeatherIcon(DrawAnimation):
    """
    Depends on avwx-engine
    """
    MIN_UPDATE = 600  # seconds between two station updates
    DEFAULT_STATION = "EBBR"  # LFBO for Airbus?

    def __init__(self, config: dict, button: "Button"):
        self._inited = False
        self._moved = False    # True if we get Metar for location at (lat, lon), False if Metar for default station
        self.weather = config.get("weather")
        if self.weather is not None and isinstance(self.weather, dict):
            config["animation"] = config.get("weather")
        else:
            config["animation"] = {}
            self.weather = {}

        DrawAnimation.__init__(self, config=config, button=button)

        self._last_updated = None
        self._cache = None

        # "Animation" (refresh)
        speed = self.weather.get("refresh", 30)     # minutes, should be ~30 minutes
        self.speed = int(speed) * 60                # minutes

        updated = self.weather.get("refresh-location", 10) # minutes
        WeatherIcon.MIN_UPDATE = int(updated) * 60

        # Working variables
        self.station = None
        self.metar = None
        self.weather_icon = None

        # Init
        self.update()
        self.anim_start()

    def init(self):
        if not self._inited:
            icao = self.weather.get("station", WeatherIcon.DEFAULT_STATION)
            self.station = Station.from_icao(icao)
            self.metar = Metar(self.station.icao)
            self.sun = Sun(self.station.latitude, self.station.longitude)
            self.button._config["label"] = icao
            self._last_updated = datetime.now()
            self._inited = True
            logger.debug(f"init: default station installed {icao}")

    def at_default_station(self):
        if self.weather is not None and self.station is not None:
            logger.debug(f"at_default_station: default station installed {self.station.icao}, {self.weather.get('station', WeatherIcon.DEFAULT_STATION)}, {self._moved}")
            return not self._moved and self.station.icao == self.weather.get("station", WeatherIcon.DEFAULT_STATION)
        logger.debug(f"at_default_station: True")
        return True

    def get_datarefs(self):
        return [
            "sim/flightmodel/position/latitude",
            "sim/flightmodel/position/longitude",
            "sim/cockpit2/clock_timer/local_time_hours",
            Dataref.mk_internal_dataref("weather:pressure"),
            Dataref.mk_internal_dataref("weather:wind_speed"),
            Dataref.mk_internal_dataref("weather:temperature"),
            Dataref.mk_internal_dataref("weather:dew_point")
        ]

    def should_run(self) -> bool:
        """
        Check conditions to animate the icon.
        In this case, always runs
        """
        return True

    def animate(self):
        self.update()
        return super().animate()

    def get_station(self):
        if self._last_updated is not None and not self.at_default_station():
            now = datetime.now()
            diff = now.timestamp() - self._last_updated.timestamp()
            if diff < WeatherIcon.MIN_UPDATE:
                logger.debug(f"get_station: updated less than {WeatherIcon.MIN_UPDATE} secs. ago ({diff}), skipping..")
                return None
            logger.debug(f"get_station: updated  {diff} secs. ago")

        # If we are at the default station, we check where we are to see if we moved.
        lat = self.button.get_dataref_value("sim/flightmodel/position/latitude")
        lon = self.button.get_dataref_value("sim/flightmodel/position/longitude")

        if lat is None or lon is None:
            logger.warning(f"get_station: no coordinates")
            if self.station is None:  # If no station, attempt to suggest the default one if we find it
                icao = self.weather.get("station", WeatherIcon.DEFAULT_STATION)
                logger.warning(f"get_station: no station, getting default {icao}")
                return Station.from_icao(icao)
            return None

        logger.debug(f"get_station: closest station to lat={lat},lon={lon}")
        (nearest, coords) = Station.nearest(lat=lat, lon=lon, max_coord_distance=150000)
        self._moved = True
        logger.debug(f"get_station: nearest={nearest}")
        return nearest

    def update(self, force: bool = False) -> bool:
        """
        Creates or updates Metar. Call to avwx may fail, so it is wrapped into try/except block

        :param      force:  The force
        :type       force:  bool

        :returns:   { description_of_the_return_value }
        :rtype:     bool
        """
        updated = False
        if force:
            self._last_updated = None
        new = self.get_station()

        if new is None:
            if self.station is None:
                return updated   # no new station, no existing station, we leave it as it is

        if self.station is None:
            try:
                self.station = new
                self.metar = Metar(self.station.icao)
                self.metar.update()
                self.sun = Sun(self.station.latitude, self.station.longitude)
                self.button._config["label"] = new.icao
                self._last_updated = datetime.now()
                updated = True
                logger.info(f"update: new station {self.station.icao}")
            except:
                self.metar = None
                logger.warning(f"update: new station {new.icao}: Metar not created", exc_info=True)
        elif new is not None and new.icao != self.station.icao:
            try:
                self.station = new
                self.metar = Metar(self.station.icao)
                self.metar.update()
                self.sun = Sun(self.station.latitude, self.station.longitude)
                self.button._config["label"] = new.icao
                self._last_updated = datetime.now()
                updated = True
                logger.info(f"update: station changed to {self.station.icao}")
            except:
                self.metar = None
                logger.warning(f"update: change station to {new.icao}: Metar not created", exc_info=True)
        elif self.metar is None:
            try:
                self.metar = Metar(self.station.icao)
                self.metar.update()
                self._last_updated = datetime.now()
                updated = True
                logger.info(f"update: station {self.station.icao}, first Metar")
            except:
                self.metar = None
                logger.warning(f"update: station {self.station.icao}, first Metar not created", exc_info=True)
        else:
            try:
                now = datetime.now()
                diff = now.timestamp() - self._last_updated.timestamp()
                if self._last_updated is None or diff > WeatherIcon.MIN_UPDATE:
                    self.metar.update()
                    self._last_updated = datetime.now()
                    updated = True
                    logger.info(f"update: station {self.station.icao}, Metar updated")
                else:
                    logger.debug(f"update: station {self.station.icao}, Metar does not need updating")
            except:
                self.metar = None
                logger.warning(f"update: station {self.station.icao}: Metar not updated", exc_info=True)

        # if new is None, we leave it as it is
        if updated:
            # AVWX's Metar is not as comprehensive as python-metar's Metar...
            if self.metar is not None and self.metar.data is not None:
                self.button.xp.write_dataref(dataref=Dataref.mk_internal_dataref("weather:pressure"), value=self.metar.data.altimeter.value, vtype='float')
                self.button.xp.write_dataref(dataref=Dataref.mk_internal_dataref("weather:wind_speed"), value=self.metar.data.wind_speed.value, vtype='float')
                self.button.xp.write_dataref(dataref=Dataref.mk_internal_dataref("weather:temperature"), value=self.metar.data.temperature.value, vtype='float')
                self.button.xp.write_dataref(dataref=Dataref.mk_internal_dataref("weather:dew_point"), value=self.metar.data.dewpoint.value, vtype='float')
            else:
                logger.debug(f"update: no metar for {self.station.icao}")
            self.weather_icon = self.select_weather_icon()
            logger.debug(f"update: Metar updated for {self.station.icao}")

        return updated

    def get_image_for_icon(self):
        """
        Helper function to get button image and overlay label on top of it.
        Label may be updated at each activation since it can contain datarefs.
        Also add a little marker on placeholder/invalid buttons that will do nothing.
        """

        if not self.update():
            self._cache

        image = Image.new(mode="RGBA", size=(ICON_SIZE, ICON_SIZE), color=TRANSPARENT_PNG_COLOR)                     # annunciator text and leds , color=(0, 0, 0, 0)
        draw = ImageDraw.Draw(image)
        inside = round(0.04 * image.width + 0.5)

        # Weather Icon
        icon_font = self._config.get("icon-font", WEATHER_ICON_FONT)
        icon_size = int(image.width / 2)
        icon_color = "white"
        font = self.get_font(icon_font, icon_size)
        inside = round(0.04 * image.width + 0.5)
        w = image.width / 2
        h = image.height / 2
        draw.text((w, h),  # (image.width / 2, 15)
                  text=self.weather_icon if self.weather_icon is not None else "\uf00d",
                  font=font,
                  anchor="mm",
                  align="center",
                  fill=light_off(icon_color, 0.6))

        # Weather Data
        lines = None
        try:
            if self.metar is not None and self.metar.summary:
                lines = self.metar.summary.split(",")  # ~ 6-7 short lines
        except:
            lines = None
            logger.warning(f"get_image_for_icon: Metar has no summary")
            # logger.warning(f"get_image_for_icon: Metar has no summary", exc_info=True)

        if lines is not None:
            text_font = self._config.get("weather-font", self.label_font)
            text_size = int(image.width / 10)
            font = self.get_font(text_font, text_size)
            w = inside
            p = "l"
            a = "left"
            h = image.height / 3
            il = text_size
            for line in lines:
                draw.text((w, h),  # (image.width / 2, 15)
                          text=line.strip(),
                          font=font,
                          anchor=p+"m",
                          align=a,
                          fill=self.label_color)
                h = h + il
        else:
            icao = self.station.icao if self.station is not None else "no station"
            logger.warning(f"get_image_for_icon: no metar summary ({icao})")

        # Paste image on cockpit background and return it.
        bg = self.button.deck.get_icon_background(name=self.button_name(), width=ICON_SIZE, height=ICON_SIZE, texture_in=self.icon_texture, color_in=self.icon_color, use_texture=True, who="Weather")
        bg.alpha_composite(image)
        self._cache = bg.convert("RGB")
        return self._cache

    def is_metar_day(self, sunrise: int = 5, sunset: int = 19) -> bool:
        time = self.metar.raw[7:12]
        logger.debug(f"is_metar_day: zulu {time}")
        if time[-1] != "Z":
            logger.warning(f"is_metar_day: no zulu? {time}")
            return True
        tz = self.get_timezone()
        logger.debug(f"is_metar_day: timezone {'UTC' if tz == timezone.utc else tz.key}")
        utc = datetime.now(timezone.utc)
        utc = utc.replace(hour=int(time[0:2]), minute=int(time[2:4]))
        local = utc.astimezone(tz=tz)
        sun = self.get_sun(local)
        day = local.hour > sun[0] and local.hour < sun[1]
        logger.debug(f"is_metar_day: local {local}, day={str(day)} ({sun})")
        return day

    def is_day(self, sunrise: int = 5, sunset: int = 19) -> bool:
        # Uses the simulator local time
        hours = self.button.get_dataref_value("sim/cockpit2/clock_timer/local_time_hours", default=12)
        if self.sun is not None:
            sr = self.sun.get_sunrise_time()
            ss = self.sun.get_sunset_time()
        else:
            sr = sunrise
            ss = sunset
        return hours >= sr and hours <= ss

    def get_timezone(self):
        # pip install timezonefinder
        # from zoneinfo import ZoneInfo
        # from timezonefinder import TimezoneFinder
        #
        tf = TimezoneFinder()
        tzname = tf.timezone_at(lng=self.station.longitude, lat=self.station.latitude)
        if tzname is not None:
            return ZoneInfo(tzname)
        return timezone.utc

    def get_sun(self, moment: datetime = None):
        # Returns sunrise and sunset rounded hours (24h)
        if moment is None:
            today_sr = self.sun.get_sunrise_time()
            today_ss = self.sun.get_sunset_time()
            return (today_sr.hour, today_ss.hour)
        today_sr = self.sun.get_sunrise_time(moment)
        today_ss = self.sun.get_sunset_time(moment)
        return (today_sr.hour, today_ss.hour)


    def day_night(self, icon, day: bool = True):
        # Selects day or night variant of icon
        logger.debug(f"day_night: search {icon}, {day}")

        # Special case cavok
        if icon == KW_CAVOK:
            logger.debug(f"day_night: {KW_CAVOK}, {day}")
            return CAVOK_DAY if day else CAVOK_NIGHT

        # Do we have a variant?
        try_icon = None
        dft_name = None
        for prefix in [WI_PREFIX, WI_PREFIX + DAY, WI_PREFIX + NIGHT, WI_PREFIX + NIGHT_ALT]:
            if try_icon is None:
                dft_name = prefix + icon
                try_icon = WEATHER_ICONS.get(dft_name)
        if try_icon is None:
            logger.debug(f"day_night: no such icon or variant {icon}")
            return DEFAULT_ICON
        else:
            logger.debug(f"day_night: exists {dft_name}")

        # From now on, we are sure we can find an icon
        # day
        if not day:
            icon_name = WI + NIGHT + icon
            try_icon = WEATHER_ICONS.get(icon_name)
            if try_icon is not None:
                logger.debug(f"day_night: exists night {icon_name}")
                return icon_name

            icon_name = WI + NIGHT_ALT + icon
            try_icon = WEATHER_ICONS.get(icon_name)
            if try_icon is not None:
                logger.debug(f"day_night: exists night-alt {try_icon}")
                return icon_name

        icon_name = WI + DAY + icon
        try_icon = WEATHER_ICONS.get(icon_name)
        if try_icon is not None:
            logger.debug(f"day_night: exists day {icon_name}")
            return icon_name

        logger.debug(f"day_night: found {dft_name}")
        return dft_name


    def select_weather_icon(self):
        # Needs improvement
        # Stolen from https://github.com/flybywiresim/efb
        icon = "wi_cloud"
        if self.metar is not None and self.metar.raw is not None:
            rawtext = self.metar.raw[13:]  # strip ICAO DDHHMMZ
            logger.debug(f"select_weather_icon: METAR {rawtext}")
            # Precipitations
            precip = re.match("RA|SN|DZ|SG|PE|GR|GS", rawtext)
            if precip is None:
                precip = []
            logger.debug(f"select_weather_icon: PRECIP {precip}")
            # Wind
            wind = self.metar.data.wind_speed.value if hasattr(self.metar.data, "wind_speed") else 0
            logger.debug(f"select_weather_icon: WIND {wind}")

            findIcon = []
            for item in WI.DB:
                t1 = reduce(lambda x, y: x + y, [rawtext.find(desc) for desc in item[KW_TAGS]], 0) == len(item[KW_TAGS])
                t_precip = ((len(item[KW_PRECIP]) == 0) or rawtext.find(item[KW_PRECIP]))
                t_clouds = ((len(item[KW_CLOUD]) == 0) or (len(item[KW_CLOUD]) == 1 and item[KW_CLOUD][0] == "") or (reduce(lambda x, y: x + y, [rawtext.find(cld) for cld in item[KW_CLOUD]], 0) > 0))
                t_wind = (wind > item[KW_WIND][0] and wind < item[KW_WIND][1])
                t_vis = ((len(item[KW_VIS]) == 0) or (reduce(lambda x, y: x + y, [rawtext.find(vis) for vis in item[KW_VIS]], 0) > 0))
                ok = t1 and t_precip and t_clouds and t_wind and t_vis
                if ok:
                    findIcon.append(item)
                logger.debug(f"select_weather_icon: findIcon: {item[KW_NAME]}, list={t1}, precip={t_precip}, clouds={t_clouds}, wind={t_wind}, vis={t_vis} {('<'*10) if ok else ''}")
            logger.debug(f"select_weather_icon: STEP 1 {findIcon}")

            # findIcon = list(filter(lambda item: reduce(lambda x, y: x + y, [rawtext.find(desc) for desc in item[KW_TAGS]], 0) == len(item[KW_TAGS])
            #                             and ((len(item[KW_PRECIP]) == 0) or rawtext.find(item[KW_PRECIP]))
            #                             and ((len(item[KW_CLOUD]) == 0) or (len(item[KW_CLOUD]) == 1 and item[KW_CLOUD][0] == "") or (reduce(lambda x, y: x + y, [rawtext.find(cld) for cld in item[KW_CLOUD]], 0) > 0))
            #                             and (wind > item[KW_WIND][0] and wind < item[KW_WIND][1])
            #                             and ((len(item[KW_VIS]) == 0) or (reduce(lambda x, y: x + y, [rawtext.find(vis) for vis in item[KW_VIS]], 0) > 0)),
            #                   WI.DB))
            # logger.debug(f"select_weather_icon: STEP 1 {findIcon}")

            l = len(findIcon)
            if l == 1:
                icon = findIcon[0]["iconName"]
            else:
                if l > 1:
                    findIcon2 = []
                    if len(precip) > 0:
                        findIcon2 = list(filter(lambda x: re("RA|SN|DZ|SG|PE|GR|GS").match(x["precip"]), findIcon))
                    else:
                        findIcon2 = list(filter(lambda x: x["day"] == day, findIcon))
                    logger.debug(f"select_weather_icon: STEP 2 {findIcon2}")
                    if len(findIcon2) > 0:
                        icon = findIcon2[0]["iconName"]
        else:
            logger.debug(f"select_weather_icon: no metar ({self.metar})")

        logger.debug(f"select_weather_icon: weather icon {icon}")
        day = self.is_metar_day()
        daynight_icon = self.day_night(icon, day)
        logger.debug(f"select_weather_icon: day/night version: {day}: {daynight_icon}")
        return WEATHER_ICONS.get(daynight_icon)

    def select_random_weather_icon(self):
        # day or night
        # cloud cover
        # precipitation: type, quantity
        # wind: speed
        # currently random anyway...
        return random.choice(list(WEATHER_ICONS.values()))

