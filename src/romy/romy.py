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
from typing import Any

_LOGGER = logging.getLogger(__name__)

supported_binary_sensors = ["dustbin", "dock", "water_tank", "water_tank_empty"]
supported_adc_sensors = ["dustbin_sensor"]

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

        self._battery_level : None | int = None
        self._fan_speed : int = 0
        self._status : None | str = None

        self._sensors : dict[str, bool] = {}
        self._binary_sensors : dict[str, bool] = {}
        self._adc_sensors : dict[str, bool] = {}


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
            self._initialized = False

        # get robot infos
        ret, response = await self.romy_async_query("get/robot_id")
        if ret:
            json_response = json.loads(response)
            self._unique_id = json_response["unique_id"]
            self._model = json_response["model"]
            self._firmware = json_response["firmware"]
        else:
            _LOGGER.error("Error fetching get/robot_id: %s", response)
            self._initialized = False


        if self._initialized:
            _LOGGER.info("ROMY is reachable under %s", self._host)
        else:
            _LOGGER.error("ROMY is not reachable under %s", self._host)

        
        # fetch information which binary sensors are present and add it in case
        ret, response = await self.romy_async_query("get/sensor_status")
        if ret:
            status = json.loads(response)
            hal_status = status["hal_status"]
            for sensor in hal_status["sensor_list"]:
                if sensor["is_registered"] == 1:
                    if sensor["device_descriptor"] in supported_binary_sensors:
                        self._binary_sensors[sensor["device_descriptor"]] = False
        else:
            _LOGGER.error("Error fetching sensor status resp: %s", response)
            self._initialized = False
                
        await self.async_update()

        _LOGGER.info("Your ROMY offers following sensors: %s", self._sensors)
        _LOGGER.info("Your ROMY offers following binary sensors: %s", self._binary_sensors)        
        _LOGGER.info("Your ROMY offers following adc sensors: %s", self._adc_sensors)

        return self

    async def romy_async_query(self, command: str) -> tuple[bool, str]:
        """Send a http query."""
        # TODO: unlock robot again if you get here forbidden
        return await async_query(self._host, self._port, command)

    @property
    def is_initialized(self) -> None | bool:
        """Return true if ROMY is initialized."""
        return self._initialized
    @property
    def is_unlocked(self) -> None | bool:
        """Return true if ROMY's http interface is unlocked."""
        return not self._local_http_interface_is_locked        


    @property
    def name(self) -> str:
        """Return the name of your ROMY."""
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
        """Return the name of your ROMY."""
        return self._unique_id

    @property
    def model(self) -> str:
        """Return the model of your ROMY."""
        return self._model

    @property
    def firmware(self) -> str:
        """Return the firmware of your ROMY."""
        return self._firmware


    @property
    def fan_speed(self) -> int:
        """Return the current fan speed of your ROMY."""
        return self._fan_speed

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of your ROMY."""
        return self._battery_level

    @property
    def status(self) -> str | None:
        """Return the status of your ROMY."""
        return self._status


    @property
    def sensors(self) -> dict[str, bool]:
        """Return the available sensors of your ROMY."""
        return self._sensors

    @property
    def binary_sensors(self) -> dict[str, bool]:
        """Return the available sensors of your ROMY."""
        return self._binary_sensors

    @property
    def adc_sensors(self) -> dict[str, bool]:
        """Return the available sensors of your ROMY."""
        return self._adc_sensors


    async def get_protocol_version(self, **kwargs: Any) -> str:
        """Get http api version."""
        ret, json_resp = await self.romy_async_query(f"get/protocol_version")
        version = json.loads(json_resp)
        return f"{version['version_major']}.{version['version_minor']}.{version['patch_level']}"


    async def async_clean_start_or_continue(self, **kwargs: Any) -> bool:
        """Start or countinue cleaning."""
        _LOGGER.debug("async_clean_start_or_continue")
        ret, _ = await self.romy_async_query(f"set/clean_start_or_continue?cleaning_parameter_set={self._fan_speed}")
        return ret

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

    async def async_set_fan_speed(self, fan_speed: int, **kwargs: Any) -> None:
        """Set fan speed."""            
        ret, response = await self.romy_async_query(f"set/switch_cleaning_parameter_set?cleaning_parameter_set={fan_speed}")
        if ret:
            self._fan_speed = fan_speed
        else:
            _LOGGER.error(" async_set_fan_speed -> async_query response: %s", response)

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

        # update sensor values
        self._sensors["battery_level"] = self._battery_level

        ret, response = await self.romy_async_query("get/wifi_status")
        if ret:
            wifi_status = json.loads(response)
            self._sensors["rssi"] = wifi_status["rssi"]
            
        else:
            _LOGGER.error("ROMY function async_update -> async_query response: %s", response)

        # update sensor values
        ret, response = await self.romy_async_query("get/sensor_values")
        if ret:
            sensor_values = json.loads(response)
            for sensor in sensor_values["sensor_data"]:

                # binary sensors
                if sensor["device_type"] == "gpio":
                    gpio_sensors = sensor["sensor_data"]
                    for gpio_sensor in gpio_sensors:
                        for supported_binary_sensor in supported_binary_sensors:
                            if gpio_sensor["device_descriptor"] == supported_binary_sensor:
                                if gpio_sensor["payload"]["data"]["value"] == "active":                                   
                                    self._binary_sensors[supported_binary_sensor] = True
                                else:
                                    self._binary_sensors[supported_binary_sensor] = False
                
                # adc sensors
                if sensor["device_type"] == "adc":
                    adc_sensors = sensor["sensor_data"]
                    for adc_sensor in adc_sensors:
                        for supported_adc_sensor in supported_adc_sensors:
                            if adc_sensor["device_descriptor"] == supported_adc_sensor:
                                self._adc_sensors[supported_adc_sensor] = adc_sensor["payload"]["data"]["values"][0]

        else:
            _LOGGER.error("ROMY function async_update -> async_query response: %s", response)

