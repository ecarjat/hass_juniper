from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from jnpr.junos import Device
from jnpr.junos.utils.config import Config


# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (PLATFORM_SCHEMA,SwitchEntity)

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string,
})

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Juniper platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    # Add devices
    add_entities([JuniperPort(name, host, port)])


class JuniperPort(SwitchEntity):
    
    def __init__(self, name,  host, port):
        self._is_on = False
        self._name = name
        self._host = host
        self._port = port
        self.dev = Device(host=self._host,ssh_private_key_file='/config/ssh_id', user='emmanuel').open()
        
    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        cu = Config(self.dev)
        cu.load('set interfaces ' + self._port + ' enable', format='set')
        cu.commit()
        self._is_on = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        cu = Config(self.dev)
        cu.load('set interfaces '+ self._port + ' disable', format='set')
        cu.commit()
        self._is_on = False
    
    @property
    def name(self) -> str:
        """Return the name of this port."""
        return self._name