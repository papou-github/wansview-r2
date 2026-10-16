#!/usr/bin/env python3
"""Experimental AJCloud login/device diagnostic. No camera settings changed."""
import argparse, asyncio, base64, getpass, hashlib, hmac, json, logging, os, time, uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
import aiohttp
from nacl.public import Box, PrivateKey, PublicKey

BASE = 'https://uac-eu.ajcloud.net/api'
SAFE = {'rtc','localRtsp','onvif','privLiveStream','battery','prodName','fwVersion','build','deviceMode','vendorCode','deviceType','onlineStatus','conStatus','webrtcEnable','codec','quality'}

def sanitized(value, key=''):
    if key in {'context', 'config'} and isinstance(value, str):
        try:
            decoded=json.loads(value)
        except (ValueError, TypeError):
            return '<masqué>'
        if isinstance(decoded, (dict,list)):
            return sanitized(decoded)
    if isinstance(value, dict):
        return {k: sanitized(v, k) for k,v in value.items()}
    if isinstance(value, list):
        return [sanitized(v, key) for v in value]
    if key in SAFE or isinstance(value, (bool, type(None))):
        return value
    return '<masqué>'

class Client:
    def __init__(self, session):
        self.session=session; self.agent=str(uuid.uuid4()); self.access=None; self.sign=None
    async def post(self, route, data, signed=False, base=BASE, device_id=None):
        meta={'locale':'fr','localtz':int(datetime.now().astimezone().utcoffset().total_seconds()/60),
              'localtzn':'Europe/Paris','appName':'wansview','appVersion':'2.0.26012704',
              'appVendorCode':'WVC','agentName':'SM-S926B','appCountryCode':'FR','appContinentCode':'EU'}
        if signed: meta['accessToken']=self.access
        if device_id: meta['deviceId']=device_id
        body=json.dumps({'meta':meta,'data':data},separators=(',',':'),ensure_ascii=False)
        parsed=urlsplit(base)
        if parsed.scheme!='https' or not parsed.hostname or not (parsed.hostname=='ajcloud.net' or parsed.hostname.endswith('.ajcloud.net')) or parsed.username or parsed.password:
            raise RuntimeError('Serveur inattendu : requête annulée')
        url=base.rstrip('/')+route
        headers={'Content-Type':'application/json;charset=utf-8','x-agent-token':self.agent,
                 'User-Agent':'15; en-us; SM-S926B Build/AP3A.240905.015.A2;wansview/V2.0.26012704'}
        if signed:
            ts=str(int(time.time()*1000)+1000)
            canonical='POST\n'+urlsplit(url).path+'\n'+hashlib.sha256(body.encode()).hexdigest()+'\n'
            message='HMAC-SHA256\n'+ts+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
            sig=base64.urlsafe_b64encode(hmac.new(self.sign.encode(),message.encode(),hashlib.sha256).digest()).decode().rstrip('=')
            headers.update({'Authorization':'Bearer '+self.access,'X-UAC-Signature':'UAC1-HMAC-SHA256;'+ts+';'+sig})
        try:
            async with self.session.post(url,data=body,headers=headers,allow_redirects=False) as response:
                if response.status!=200: raise RuntimeError('Réponse HTTP '+str(response.status))
                result=await response.json(content_type=None)
        except Exception as error:
            error.diagnostic_hostname = parsed.hostname
            error.diagnostic_route = route
            raise
        if result.get('status')!='ok' or result.get('code') not in (None,0,'0'):
            raise RuntimeError('AJCloud refuse la requête ; code='+str(result.get('code')))
        return result.get('result',{})
    async def login(self,email,password):
        challenge=await self.post('/v3/outer-challenge',{'username':email,'action':'signin','agentName':'SM-S926B','agentToken':self.agent})
        nonce=os.urandom(24)
        box=Box(PrivateKey(base64.b64decode(challenge['clientSecretKey'])),PublicKey(base64.b64decode(challenge['serverPubKey'])))
        encrypted=base64.b64encode(box.encrypt(password.encode(),nonce).ciphertext).decode()
        result=await self.post('/v1/signin',{'username':email,'password':encrypted,'nonce':base64.b64encode(nonce).decode(),
            'agentName':'SM-S926B','modelName':'SM-S926B','agentToken':self.agent,'osName':'android','origin':'mobile phone','grantType':'password','scope':'all'})
        self.access=result['accessToken']; self.sign=result['signToken']

