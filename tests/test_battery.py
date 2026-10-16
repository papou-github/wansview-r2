"""Offline battery parsing, failure and cancellation tests. No HA required."""
import asyncio
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'custom_components/wansview_r2/battery.py'
spec=importlib.util.spec_from_file_location('battery',path)
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class Client:
    def __init__(self): self.calls=[]; self.fail=False
    async def login(self,*args): self.calls.append('login')
    async def post(self,route,*args,**kwargs):
        self.calls.append(route)
        if self.fail: raise TimeoutError('secret must not be saved')
        return {'infos':[{'info':{'base':{'batteryCapacity':'100',
            'batteryCapacityTs':'1792136459274','accessKey':'secret'}}}]}

class Tests(unittest.IsolatedAsyncioTestCase):
    def test_values(self):
        for raw,value in [('48',48),('100',100),('42',42),('70',70),('0',0)]:
            self.assertEqual(b.parse_battery({'batteryCapacity':raw})['percentage'],value)
        for raw in [True,None,'NaN','inf',-1,101,{},'invalid']:
            with self.assertRaises((ValueError,TypeError)):
                b.parse_battery({'batteryCapacity':raw})
        value=b.parse_battery({'batteryCapacity':'100','batteryCapacityTs':'1792136459274'})
        self.assertTrue(value['measurement_time'].startswith('2026-10-16T'))

    async def test_poll_and_failure(self):
        c=Client(); updates=[]
        m=b.BatteryMonitor(c,lambda:{'appGatewayUrl':'https://cam-gw-eu02.ajcloud.net'},
            'fake-camera','fake-email','fake-password',lambda:updates.append(True))
        await m.refresh()
        self.assertTrue(m.available)
        self.assertEqual(m.data['percentage'],100)
        self.assertEqual(c.calls,['login','/v1/fetch-infos'])
        c.fail=True
        await m.refresh()
        self.assertFalse(m.available)
        self.assertEqual(m.data['percentage'],100)
        self.assertEqual(m.last_error,'TimeoutError')
        self.assertNotIn('secret',str(m.diagnostics()))
        self.assertNotIn('fake-',str(m.diagnostics()))
        c.fail=False
        m.start()
        await asyncio.sleep(.01)
        self.assertTrue(m.available)
        await m.close()
        count=len(c.calls)
        await asyncio.sleep(.01)
        self.assertEqual(len(c.calls),count)
        self.assertIsNone(m.task)

if __name__=='__main__': unittest.main()
