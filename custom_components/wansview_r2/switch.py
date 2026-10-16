"""Single play/stop control reflecting the bounded live session."""
from homeassistant.components.switch import SwitchEntity
from . import DOMAIN
from .entity import DeviceMixin

async def async_setup_entry(hass,entry,async_add_entities):
    controller,_=hass.data[DOMAIN][entry.entry_id]
    async_add_entities([R2LiveSwitch(controller)])

class R2LiveSwitch(DeviceMixin,SwitchEntity):
    _attr_name='Direct'

    def __init__(self,controller):
        self.setup_device(controller,'live')

    @property
    def is_on(self):
        c=self.controller
        return c.active and not c._capture_only and c.status in ('connecting','streaming')

    @property
    def icon(self):
        return 'mdi:stop' if self.is_on else 'mdi:play'

    async def async_turn_on(self,**kwargs):
        await self.controller.start()

    async def async_turn_off(self,**kwargs):
        await self.controller.stop()
