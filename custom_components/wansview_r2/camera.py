"""Camera: explicit live lease and cached stills, no polling wakeups."""
from datetime import datetime,timezone
from homeassistant.components.camera import Camera,CameraEntityFeature
from . import DOMAIN
from .entity import DeviceMixin

async def async_setup_entry(hass,entry,async_add_entities):
    controller,_=hass.data[DOMAIN][entry.entry_id]
    async_add_entities([R2Camera(controller)])

class R2Camera(DeviceMixin,Camera):
    _attr_name=None
    _attr_supported_features=CameraEntityFeature.STREAM
    _attr_use_stream_for_stills=False

    def __init__(self,controller):
        super().__init__()
        self.setup_device(controller,'camera')

    @property
    def is_on(self):
        # Software stream leases do not power off the physical camera or its cached image.
        return True

    @property
    def is_streaming(self):
        return self.controller.active and self.controller.status=='streaming'

    async def async_camera_image(self,width=None,height=None):
        return self.controller.jpeg

    async def stream_source(self):
        if self.controller.active and not self.controller._capture_only:
            return self.controller.stream_url
        return None

    async def async_turn_on(self):
        await self.controller.start()

    async def async_turn_off(self):
        await self.controller.stop()

    @property
    def extra_state_attributes(self):
        c=self.controller
        return {'connection_state':c.status,'last_error':c.error,
            'connection_attempts':c.stats.get('attempts',0),'frames_received':c.stats.get('frames',0),
            'received_bytes':c.stats.get('bytes',0), 'codec':c.stats.get('codec'),
            'image_time':datetime.fromtimestamp(c.last_image,timezone.utc).isoformat() if c.last_image else None,
            'cloud_hostname':c.stats.get('cloud_hostname'), 'maximum_live_seconds':60}
