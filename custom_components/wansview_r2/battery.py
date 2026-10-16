"""Cached cloud battery polling, isolated from video authentication and wakeups."""
import asyncio
from datetime import datetime, timezone
import math

INTERVAL=1800

def parse_battery(base):
    raw=base.get('batteryCapacity')
    if isinstance(raw,bool) or not isinstance(raw,(str,int,float)):
        raise ValueError('InvalidBattery')
    value=float(raw)
    if not math.isfinite(value) or not 0<=value<=100:
        raise ValueError('InvalidBattery')
    measurement=None
    try:
        raw_ts=base.get('batteryCapacityTs')
        if not isinstance(raw_ts,bool):
            ts=float(raw_ts)/1000
            if math.isfinite(ts) and ts>0:
                measurement=datetime.fromtimestamp(ts,timezone.utc).isoformat()
    except (TypeError,ValueError,OverflowError,OSError):
        pass
    return {'percentage':value,'measurement_time':measurement}

class BatteryMonitor:
    def __init__(self,client,config,did,email,password,notify):
        self.client=client
        self.config=config
        self.did=did
        self.email=email
        self.password=password
        self.notify=notify
        self.data={}
        self.available=False
        self.last_error=None
        self.task=None

    def start(self):
        if self.task is None:
            self.task=asyncio.create_task(self._loop())

    async def refresh(self):
        try:
            await self.client.login(self.email,self.password)
            gateway=self.config()['appGatewayUrl'].rstrip('/')
            if not gateway.endswith('/api'): gateway+='/api'
            result=await self.client.post('/v1/fetch-infos',{'devices':[
                {'did':self.did,'scopes':[],'isShare':False}]},signed=True,base=gateway)
            infos=result.get('infos',[])
            if len(infos)!=1: raise ValueError('UnexpectedCameraInfo')
            self.data=parse_battery(infos[0].get('info',{}).get('base',{}))
            self.available=True
            self.last_error=None
        except Exception as error:
            self.available=False
            self.last_error=type(error).__name__
        self.notify()

    async def _loop(self):
        while True:
            await self.refresh()
            await asyncio.sleep(INTERVAL)

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
            self.task=None

    def diagnostics(self):
        return {**self.data,'available':self.available,'last_error':self.last_error,
                'cloud_poll_seconds':INTERVAL}
