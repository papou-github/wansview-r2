"""Shared cached-only entity metadata."""
from . import DOMAIN

class DeviceMixin:
    _attr_should_poll=False
    _attr_has_entity_name=True

    def setup_device(self,controller,suffix):
        self.controller=controller
        self._attr_unique_id=controller.did+'_'+suffix
        self._attr_device_info={'identifiers':{(DOMAIN,controller.did)},
            'manufacturer':'Wansview / Galayou','model':'R2 Pro', 'name':controller.alias}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.listen(self.async_write_ha_state))
