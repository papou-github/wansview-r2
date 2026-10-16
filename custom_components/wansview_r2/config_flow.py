"""UI setup: cloud account then one selected camera."""
import hashlib
import socket
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .cloud import Client
from . import DOMAIN

class ConfigFlow(config_entries.ConfigFlow,domain=DOMAIN):
    VERSION=1

    async def async_step_user(self,user_input=None):
        errors={}
        if user_input is not None:
            try:
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(family=socket.AF_INET),
                    timeout=aiohttp.ClientTimeout(total=25,connect=10,sock_read=15)) as session:
                    client=Client(session)
                    await client.login(user_input['email'].strip(),user_input['password'])
                    result=await client.post('/v3/device-list',{},signed=True)
                aliases={d['deviceId']:d.get('aliasName','Caméra') for d in result.get('conDevices',[])}
                self._cameras={d['deviceId']:aliases.get(d['deviceId'],d.get('prodName','Caméra'))
                    for d in result.get('devGenerals',[]) if d.get('prodName') in ('R2','R2 Pro')}
                if not self._cameras:
                    return self.async_abort(reason='no_camera')
                self._credentials={'email':user_input['email'].strip(),'password':user_input['password']}
                return await self.async_step_camera()
            except (aiohttp.ClientError,TimeoutError):
                errors['base']='cannot_connect'
            except RuntimeError:
                errors['base']='invalid_auth'
            except (KeyError,ValueError,TypeError):
                errors['base']='unexpected_response'
        return self.async_show_form(step_id='user',data_schema=vol.Schema({
            vol.Required('email'):str,
            vol.Required('password'):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }),errors=errors)

    async def async_step_camera(self,user_input=None):
        if user_input is not None:
            did=user_input['camera']
            if did not in self._cameras:
                return self.async_abort(reason='no_camera')
            unique=hashlib.sha256((self._credentials['email'].casefold()+':'+did).encode()).hexdigest()
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()
            data={**self._credentials,'device_id':did,'name':self._cameras[did]}
            return self.async_create_entry(title=self._cameras[did],data=data)
        return self.async_show_form(step_id='camera',data_schema=vol.Schema({
            vol.Required('camera'):vol.In(self._cameras),
        }))
