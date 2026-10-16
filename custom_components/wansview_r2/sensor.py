"""Battery sensor, updated only by the cached cloud monitor."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from . import DOMAIN
from .entity import DeviceMixin

async def async_setup_entry(hass,entry,async_add_entities):
    controller,_=hass.data[DOMAIN][entry.entry_id]
    async_add_entities([R2BatterySensor(controller)])

class R2BatterySensor(DeviceMixin,SensorEntity):
    _attr_translation_key='battery'
    _attr_device_class=SensorDeviceClass.BATTERY
    _attr_state_class=SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement=PERCENTAGE
    _attr_suggested_display_precision=0

    def __init__(self,controller):
        self.setup_device(controller,'battery')

    @property
    def available(self):
        return self.controller.battery.available

    @property
    def native_value(self):
        return self.controller.battery.data.get('percentage')

    @property
    def extra_state_attributes(self):
        b=self.controller.battery
        return {'measurement_time':b.data.get('measurement_time'),
                'source':'cloud_cache','last_error':b.last_error}
