"""Module for multi-socket devices (HS300, HS107).

.. todo:: describe how this interfaces with single plugs.
"""
import datetime
import logging
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List

from pyHS100.protocol import TPLinkSmartHomeProtocol
from pyHS100.smartdevice import DeviceType
from pyHS100.smartplug import SmartPlug

_LOGGER = logging.getLogger(__name__)


class SmartStrip(SmartPlug):
    """Representation of a TP-Link Smart Power Strip.

    Usage example when used as library:
    ```python
    p = SmartStrip("192.168.1.105")

    # query the state of the strip
    print(p.sync.is_on())

    # change state of all outlets
    p.sync.turn_on()
    p.sync.turn_off()

    # individual outlets are accessible through plugs variable
    for plug in p.plugs:
        print(f"{p}: {p.sync.is_on()}")

    # change state of a single outlet
    p.plugs[0].sync.turn_on()
    ```

    Omit the `sync` attribute to get coroutines.

    Errors reported by the device are raised as SmartDeviceExceptions,
    and should be handled by the user of the library.
    """

    def __init__(
        self,
        host: str,
        protocol: TPLinkSmartHomeProtocol = None,
        cache_ttl: int = 3,
        ioloop=None,
    ) -> None:
        SmartPlug.__init__(self, host=host, protocol=protocol, cache_ttl=cache_ttl)
        self.emeter_type = "emeter"
        self._device_type = DeviceType.Strip
        self.plugs: List[SmartPlug] = []
        children = self.sync.get_sys_info()["children"]
        self.num_children = len(children)
        for plug in range(self.num_children):
            self.plugs.append(
                SmartPlug(
                    host,
                    protocol,
                    context=children[plug]["id"],
                    cache_ttl=cache_ttl,
                    ioloop=ioloop,
                )
            )

    async def is_on(self) -> bool:
        """Return if any of the outlets are on."""
        for plug in self.plugs:
            is_on = await plug.is_on()
            if is_on:
                return True
        return False

    async def turn_on(self):
        """Turn the strip on.

        :raises SmartDeviceException: on error
        """
        await self._query_helper("system", "set_relay_state", {"state": 1})

    async def turn_off(self):
        """Turn the strip off.

        :raises SmartDeviceException: on error
        """
        await self._query_helper("system", "set_relay_state", {"state": 0})

    async def get_on_since(self) -> datetime.datetime:
        """Return the maximum on-time of all outlets."""
        return max([await plug.get_on_since() for plug in self.plugs])

    async def state_information(self) -> Dict[str, Any]:
        """Return strip-specific state information.

        :return: Strip information dict, keys in user-presentable form.
        :rtype: dict
        """
        state: Dict[str, Any] = {"LED state": self.led}
        for plug in self.plugs:
            if await plug.is_on():
                state["Plug %s on since" % str(plug)] = await plug.get_on_since()

        return state

    async def current_consumption(self) -> float:
        """Get the current power consumption in watts.

        :return: the current power consumption in watts.
        :rtype: float
        :raises SmartDeviceException: on error
        """
        consumption = sum([await plug.current_consumption() for plug in self.plugs])

        return consumption

    async def icon(self) -> Dict:
        """Icon for the device.

        Overriden to keep the API, as the SmartStrip and children do not
        have icons, we just return dummy strings.
        """
        return {"icon": "SMARTSTRIP-DUMMY", "hash": "SMARTSTRIP-DUMMY"}

    async def set_alias(self, alias: str) -> None:
        """Set the alias for the strip.

        :param alias: new alias
        :raises SmartDeviceException: on error
        """
        return await super().set_alias(alias)

    async def get_emeter_daily(
        self, year: int = None, month: int = None, kwh: bool = True
    ) -> Dict:
        """Retrieve daily statistics for a given month.

        :param year: year for which to retrieve statistics (default: this year)
        :param month: month for which to retrieve statistics (default: this
                      month)
        :param kwh: return usage in kWh (default: True)
        :return: mapping of day of month to value
        :rtype: dict
        :raises SmartDeviceException: on error
        """
        emeter_daily: DefaultDict[int, float] = defaultdict(lambda: 0.0)
        for plug in self.plugs:
            plug_emeter_daily = await plug.get_emeter_daily(
                year=year, month=month, kwh=kwh
            )
            for day, value in plug_emeter_daily.items():
                emeter_daily[day] += value
        return emeter_daily

    async def get_emeter_monthly(self, year: int = None, kwh: bool = True) -> Dict:
        """Retrieve monthly statistics for a given year.

        :param year: year for which to retrieve statistics (default: this year)
        :param kwh: return usage in kWh (default: True)
        :return: dict: mapping of month to value
        :rtype: dict
        :raises SmartDeviceException: on error
        """
        emeter_monthly: DefaultDict[int, float] = defaultdict(lambda: 0.0)
        for plug in self.plugs:
            plug_emeter_monthly = await plug.get_emeter_monthly(year=year, kwh=kwh)
            for month, value in plug_emeter_monthly:
                emeter_monthly[month] += value
        return emeter_monthly

    async def erase_emeter_stats(self):
        """Erase energy meter statistics for all plugs.

        :raises SmartDeviceException: on error
        """
        for plug in self.plugs:
            await plug.erase_emeter_stats()
