"""On-demand image capture."""
from homeassistant.components.button import ButtonEntity
from . import DOMAIN
from .entity import DeviceMixin

async def async_setup_entry(hass,entry,async_add_entities):
    controller,_=hass.data[DOMAIN][entry.entry_id]
    async_add_entities([R2CaptureButton(controller)])

class R2CaptureButton(DeviceMixin,ButtonEntity):
    _attr_name='Actualiser l’image'
    _attr_icon='mdi:camera-refresh'

    def __init__(self,controller):
        self.setup_device(controller,'capture')

    async def async_press(self):
        await self.controller.start(capture_only=True)
