"""Support for Tuya Vacuums."""
from __future__ import annotations
import logging

from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PAUSED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType

_LOGGER = logging.getLogger(__name__)

TUYA_MODE_RETURN_HOME = "chargego"
TUYA_STATUS_TO_HA = {
    "areaing": STATE_CLEANING,
    "charge_done": STATE_DOCKED,
    "chargecompleted": STATE_DOCKED,
    "chargego": STATE_DOCKED,
    "charging": STATE_DOCKED,
    "chargring": STATE_DOCKED,
    "cleaning": STATE_CLEANING,
    "curpointing": STATE_CLEANING,
    "docking": STATE_RETURNING,
    "dormant": STATE_IDLE,
    "dustcenterworking": STATE_CLEANING,
    "fault": STATE_ERROR,
    "fullcharge": STATE_DOCKED,
    "goto_charge": STATE_RETURNING,
    "goto_pos": STATE_CLEANING,
    "idle": STATE_IDLE,
    "left_bow": STATE_CLEANING,
    "left_spiral": STATE_CLEANING,
    "mop": STATE_CLEANING,
    "mop_clean": STATE_CLEANING,
    "part_clean": STATE_CLEANING,
    "partial_bow": STATE_CLEANING,
    "pause": STATE_PAUSED,
    "paused": STATE_PAUSED,
    "pick_zone_clean": STATE_CLEANING,
    "pointing": STATE_CLEANING,
    "pos_arrived": STATE_CLEANING,
    "pos_unarrive": STATE_CLEANING,
    "random": STATE_CLEANING,
    "remotectl": STATE_CLEANING,
    "right_bow": STATE_CLEANING,
    "right_spiral": STATE_CLEANING,
    "selectroom": STATE_CLEANING,
    "sleep": STATE_IDLE,
    "spiral": STATE_CLEANING,
    "smart_clean": STATE_CLEANING,
    "smart": STATE_CLEANING,
    "spot_clean": STATE_CLEANING,
    "sweep": STATE_CLEANING,
    "standby": STATE_IDLE,
    "tocharge": STATE_RETURNING,
    "totaling": STATE_CLEANING,
    "wall_clean": STATE_CLEANING,
    "wall_follow": STATE_CLEANING,
    "zone_clean": STATE_CLEANING,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya vacuum dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya vacuum."""
        entities: list[TuyaVacuumEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if device.category == "sd":
                entities.append(TuyaVacuumEntity(device, hass_data.manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaVacuumEntity(TuyaEntity, StateVacuumEntity):
    """Tuya Vacuum Device."""

    _fan_speed: EnumTypeData | None = None
    _battery_level: IntegerTypeData | None = None
    _attr_name = None

    def __init__(self, device: CustomerDevice, device_manager: Manager) -> None:
        """Init Tuya vacuum."""
        super().__init__(device, device_manager)

        self._attr_fan_speed_list = []
        
        self._attr_supported_features = (
            VacuumEntityFeature.SEND_COMMAND | 
            VacuumEntityFeature.STATE |
            VacuumEntityFeature.STATUS |
            VacuumEntityFeature.BATTERY
        )
        if self.find_dpcode(DPCode.PAUSE, prefer_function=True):
            self._attr_supported_features |= VacuumEntityFeature.PAUSE

        if self.find_dpcode(DPCode.SWITCH_CHARGE, prefer_function=True):
            self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME
        elif (
            enum_type := self.find_dpcode(
                DPCode.MODE, dptype=DPType.ENUM, prefer_function=True
            )
        ) and TUYA_MODE_RETURN_HOME in enum_type.range:
            self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME

        if self.find_dpcode(DPCode.SEEK, prefer_function=True):
            self._attr_supported_features |= VacuumEntityFeature.LOCATE

        if self.find_dpcode(DPCode.POWER_GO, prefer_function=True):
            self._attr_supported_features |= (
                VacuumEntityFeature.STOP | VacuumEntityFeature.START
            )

        if enum_type := self.find_dpcode(
            DPCode.SUCTION, dptype=DPType.ENUM, prefer_function=True
        ):
            self._fan_speed = enum_type
            self._attr_fan_speed_list = enum_type.range
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED

        _LOGGER.debug(f"[Tuya] Status {self.device.status.get(DPCode.STATUS)}")
        _LOGGER.debug(f"[Tuya] Robot State {self.device.status.get(DPCode.ROBOT_STATE)}")
        _LOGGER.debug(f"[Tuya] Battery {self.device.status.get(DPCode.BATTERY)}")
        _LOGGER.debug(f"[Tuya] Battery 2 {self.device.status.get(DPCode.ELECTRICITY_LEFT)}")
        _LOGGER.debug(f"[Tuya] Battery % {self.device.status.get(DPCode.BATTERY_PERCENTAGE)}")

        # if int_type := self.find_dpcode(DPCode.BATTERY, dptype=DPType.INTEGER):
        #     self._attr_supported_features |= VacuumEntityFeature.BATTERY
        #     self._attr_battery_level = int_type

    @property
    def battery_level(self) -> int | None:
        """Return Tuya device state."""
        return self.device.status.get(DPCode.ELECTRICITY_LEFT)
    
    # @property
    # def battery_level(self) -> int | None:
    #     """Return Tuya device state."""
    #     # if self._attr_battery_level is None or not (
    #     #     status := self.device.status.get(DPCode.ELECTRICITY_LEFT)
    #     # ):
    #     #     return None
    #     #return round(self._battery_level.scale_value(status))
    #     return self.device.status.get(DPCode.BATTERY)

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.device.status.get(DPCode.SUCTION)
    
    @property
    def state_attributes(self):
        """Return the optional state attributes with device specific additions."""
        attr = {}
        if self.device.status.get(DPCode.MODE):
          attr[DPCode.MODE] = self.device.status.get(DPCode.MODE)
        if self.device.status.get(DPCode.ROBOT_STATE):
          attr[DPCode.ROBOT_STATE] = self.device.status.get(DPCode.ROBOT_STATE)
        if self.device.status.get(DPCode.CLEAN_AREA):
          attr[DPCode.CLEAN_AREA] = self.device.status.get(DPCode.CLEAN_AREA)
        if self.device.status.get(DPCode.CLEAN_TIME):
          attr[DPCode.CLEAN_TIME] = self.device.status.get(DPCode.CLEAN_TIME)
        return attr
    
    @property
    def state(self):
        """Return Tuya device state."""
        if (
            DPCode.PAUSE in self.device.status
            and self.device.status[DPCode.PAUSE]
        ):
            return STATE_PAUSED

        status = self.device.status.get(DPCode.ROBOT_STATE)

        if status == "standby":
            return STATE_IDLE
        if status == "goto_charge" or status == "docking" or status == "tocharge":
            return STATE_RETURNING
        if status == "charging" or status == "charge_done" or status == "chargecompleted" or status == "fullcharge":
            return STATE_DOCKED
        if status == "pause":
            return STATE_PAUSED
        return STATE_CLEANING

    def start(self, **kwargs: Any) -> None:
        """Start the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": True}])

    def stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": False}])

    def pause(self, **kwargs: Any) -> None:
        """Pause the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": False}])

    def return_to_base(self, **kwargs: Any) -> None:
        """Return device to dock."""
        self._send_command(
            [
                {"code": DPCode.SWITCH_CHARGE, "value": True},
                {"code": DPCode.MODE, "value": TUYA_MODE_RETURN_HOME},
            ]
        )

    def locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        self._send_command([{"code": DPCode.SEEK, "value": True}])

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._send_command([{"code": DPCode.SUCTION, "value": fan_speed}])

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send raw command."""
        if not params:
            raise ValueError("Params cannot be omitted for Tuya vacuum commands")
        if not isinstance(params, list):
            raise TypeError("Params must be a list for Tuya vacuum commands")
        self._send_command([{"code": command, "value": params[0]}])
