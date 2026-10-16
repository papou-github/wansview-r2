"""Diagnostics deliberately exclude credentials, camera identity and stream URL."""
from . import DOMAIN

async def async_get_config_entry_diagnostics(hass,entry):
    controller,_=hass.data[DOMAIN][entry.entry_id]
    return {'integration_version':'0.1.3','connection_state':controller.status,
        'battery':controller.battery.diagnostics(),'last_error':controller.error,'statistics':dict(controller.stats),
        'image_available':controller.jpeg is not None,'stream_active':controller.active,
        'maximum_live_seconds':60,'bootstrap_relays':'fixed_from_validated_capture',
        'notes':'No camera ID, email, password, access key, token, video or stream URL included'}
