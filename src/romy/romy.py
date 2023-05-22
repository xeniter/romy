"""Control your Wi-Fi enabled ROMY vacuum cleaner robot. 

Based on the robot interface protocol
https://www.romyrobot.com/en-AT/romy-robot-interface-protocol
"""

import json
import logging
import aiohttp
import asyncio
import requests

from .utils import async_query, async_query_with_http_status

from collections.abc import Mapping
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

async def create_romy(host: str, password:str):
    romy = RomyRobot(host, password)
    return await romy._init()

class RomyRobot():
    """Representation of a ROMY vacuum cleaner robot."""

    def __init__(self, host: str, password: str) -> None:
        """Initialize the ROMY Robot."""
        self._host = host
        self._password = password
        self._ports : list[int] = [8080, 10009, 80]
        self._port :int = 8080
        
        self._local_http_interface_is_locked : bool = False
        self._initialized : bool = False

        self._name : str = ""
        self._unique_id : str = ""
        self._model : str = ""
        self._firmware : str = ""


        self._battery_level : Optional[int] = None
        self._fan_speed : Optional[int] = None
        self._status : Optional[str] = None

    async def _init(self):

        self._initialized = False
        # check all ports and if local http interface is locked
        for port in self._ports:            
            _, _, http_status = await async_query_with_http_status(self._host, port, "ishttpinterfacelocked")
            if http_status == 400:
                self._local_http_interface_is_locked = False
                self._initialized = True
                self._port = port
                break
            if http_status == 403:
                _LOGGER.info("ROMYs local http interface is locked!")
                self._initialized = True
                self._port = port
                self._local_http_interface_is_locked = True
                break

        # in case http inerface is locked unlock it
        if self._local_http_interface_is_locked:
            if len(self._password) != 8:
                _LOGGER.error("Can not unlock ROMY's http interface, wrong password provided, password must contain exact 8 chars!")
            else:
                ret, response = await self.romy_async_query(f"set/unlock_http?pass={self._password}")
                if ret:
                    self._local_http_interface_is_locked = False
                    _LOGGER.info("ROMY's http interface is unlocked now!")
                else:
                    _LOGGER.error("Couldn't unlock ROMY's http interface!")


        # get robot name
        ret, response = await self.romy_async_query("get/robot_name")
        if ret:
            json_response = json.loads(response)
            self._name = json_response["name"]
        else:
            _LOGGER.error("Couldn't fetch your ROMY's name!")

        # get robot infos
        ret, response = await self.romy_async_query("get/robot_id")
        if ret:
            json_response = json.loads(response)
            self._unique_id = json_response["unique_id"]
            self._model = json_response["model"]
            self._firmware = json_response["firmware"]
        else:
            _LOGGER.error("Error fetching get/robot_id: %s", response)


        if self._initialized:
            _LOGGER.info("ROMY is reachable under %s", self._host)
        else:
            _LOGGER.error("ROMY is not reachable under %s", self._host)
        
        return self

    async def romy_async_query(self, command: str) -> tuple[bool, str]:
        """Send a http query."""
        # TODO: unlock robot again if you get here forbidden
        return await async_query(self._host, self._port, command)

    @property
    def is_initialized(self) -> Optional[bool]:
        """Return true if ROMY is initialized."""
        return self._initialized
    @property
    def is_unlocked(self) -> Optional[bool]:
        """Return true if ROMY's http interface is unlocked."""
        return not self._local_http_interface_is_locked        


    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    async def set_name(self, new_name) -> None:
        ret, response = await self.romy_async_query(f"set/robot_name?name={new_name}")
        if ret:
            self._name = new_name
        else:
            _LOGGER.error("Error setting ROMY's name, response: %s", response)

    @property
    def port(self) -> int:
        """Return the port of the device."""
        return self._port

    @property
    def unique_id(self) -> str:
        """Return the name of the device."""
        return self._unique_id

    @property
    def model(self) -> str:
        """Return the model of the device."""
        return self._model

    @property
    def firmware(self) -> str:
        """Return the firmware of the device."""
        return self._firmware


    @property
    def fan_speed(self) -> int:
        """Return the current fan speed of the vacuum cleaner."""
        return self._fan_speed

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self._status

    async def async_clean_start_or_continue(self, **kwargs: Any) -> bool:
        """Start or countinue cleaning."""
        _LOGGER.debug("async_clean_start_or_continue")
        ret, _ = await self.romy_async_query(f"set/clean_start_or_continue?cleaning_parameter_set={self._fan_speed}")

    async def async_clean_all(self, **kwargs: Any) -> bool:
        """Start clean all."""
        _LOGGER.debug("async_clean_all")
        ret, _ = await self.romy_async_query(f"set/clean_all?cleaning_parameter_set={self._fan_speed}")

    async def async_stop(self, **kwargs: Any) -> bool:
        """Stop the vacuum cleaner."""
        _LOGGER.debug("async_stop")
        ret, _ = await self.romy_async_query("set/stop")
        return ret

    async def async_return_to_base(self, **kwargs: Any) -> bool:
        """Set the vacuum cleaner to return to the dock."""
        _LOGGER.debug("async_return_to_base")
        ret, _ = await self.romy_async_query("set/go_home")
        return ret

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        _LOGGER.debug("async_set_fan_speed to %s", fan_speed)
        if fan_speed in FAN_SPEEDS:
            self._fan_speed_update = True
            self._fan_speed = FAN_SPEEDS.index(fan_speed)
            ret, response = await self.romy_async_query(f"set/switch_cleaning_parameter_set?cleaning_parameter_set={self._fan_speed}")
            self._fan_speed_update = False
            if not ret:
                _LOGGER.error(" async_set_fan_speed -> async_query response: %s", response)
        else:
            _LOGGER.error("No such fan speed available: %d", fan_speed)

    async def async_update(self) -> None:
        """Fetch state from the device."""
        _LOGGER.debug("async_update")

        ret, response = await self.romy_async_query("get/status")
        if ret:
            status = json.loads(response)
            self._status = status["mode"]
            self._battery_level = status["battery_level"]
        else:
            _LOGGER.error("ROMY function async_update -> async_query response: %s", response)

        ret, response = await self.romy_async_query("get/cleaning_parameter_set")
        if ret:
            status = json.loads(response)
            self._fan_speed = status["cleaning_parameter_set"]
        else:
            _LOGGER.error("FOMY function async_update -> async_query response: %s", response)



