"""Experimental Wansview R2 integration."""
import asyncio
import socket
import aiohttp
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.components.ffmpeg import DATA_FFMPEG
from .cloud import Client
from .controller import Controller

DOMAIN='wansview_r2'
PLATFORMS=[Platform.CAMERA,Platform.BUTTON,Platform.SWITCH]

async def async_setup_entry(hass,entry):
    connector=aiohttp.TCPConnector(family=socket.AF_INET)
    session=aiohttp.ClientSession(connector=connector,
        timeout=aiohttp.ClientTimeout(total=25,connect=10,sock_connect=10,sock_read=15))
    client=Client(session)
    async def prepare():
        await client.login(entry.data['email'],entry.data['password'])
        result=await client.post('/v3/device-list',{},signed=True)
        device=next((d for d in result.get('devGenerals',[]) if d['deviceId']==entry.data['device_id']),None)
        if device is None: raise RuntimeError('CameraNotFound')
        device=dict(device)
        device['display_name']=entry.data['name']
        return device
    try:
        device=await prepare()
        manager=Controller(client,device,hass.data[DATA_FFMPEG].binary)
        async def refresh_account():
            manager.device=await prepare()
        manager.prepare_account=refresh_account
        await manager.setup()
    except Exception as error:
        await session.close()
        if isinstance(error,RuntimeError) and str(error).startswith('AJCloud refuse'):
            raise ConfigEntryAuthFailed('Authentification cloud refusée') from None
        raise ConfigEntryNotReady('Connexion cloud impossible : '+type(error).__name__) from None
    hass.data.setdefault(DOMAIN,{})[entry.entry_id]=(manager,session)
    async def shutdown(event):
        await manager.close()
        await session.close()
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,shutdown))
    # Retire only this entry's two superseded command entities.
    from homeassistant.helpers import entity_registry as er
    registry=er.async_get(hass)
    for suffix in ('start','stop'):
        entity_id=registry.async_get_entity_id('button',DOMAIN,manager.did+'_'+suffix)
        if entity_id and registry.entities[entity_id].config_entry_id==entry.entry_id:
            registry.async_remove(entity_id)
    try:
        await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS)
    except BaseException:
        await manager.close()
        await session.close()
        hass.data[DOMAIN].pop(entry.entry_id,None)
        raise
    return True

async def async_unload_entry(hass,entry):
    if not await hass.config_entries.async_unload_platforms(entry,PLATFORMS):
        return False
    manager,session=hass.data[DOMAIN].pop(entry.entry_id)
    await manager.close()
    await session.close()
    return True
