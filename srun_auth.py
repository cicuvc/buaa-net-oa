"""SRUN auth library"""

import re
import time
import json
from typing import Literal, Tuple
import requests

from encryption.srun_hash import get_md5, get_sha1
from encryption.srun_base64 import get_base64
from encryption.srun_xencode import get_xencode


class SrAuthSession(object):
    """SRUN Auth session"""
    def __init__(self,
			gw_server: str,
			n_type: int,
			n: int,
			ac_id: int,
			encode_type: Literal['srun_bx1'] = 'srun_bx1',
			protocol: Literal['https'] | Literal['http'] = 'https'):

        assert protocol in {'https','http'}
        assert encode_type in {'srun_bx1'}

        self.gw_server = gw_server
        self.protocol = protocol
        self.n = n
        self.n_type = n_type
        self.encode_type = encode_type
        self.ac_id = ac_id

        self.base_url = f'{protocol}://{gw_server}'
        self.get_challenge_api = f'{self.base_url}/cgi-bin/get_challenge'
        self.srun_portal_api = f'{self.base_url}/cgi-bin/srun_portal'
        self.get_info_api = f'{self.base_url}/cgi-bin/rad_user_info?callback=jQuery_11414'

        self.headers = {
			'referer': f'{self.base_url}/srun_portal_success?ac_id={ac_id}',
			'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64)'+
			    ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.26 Safari/537.36'
        }

    def get_chksum(self, hmd5:str, ip:str, token:str, username: str, info: str):
        """Make check sum string"""
        chkstr = token+username
        chkstr += token+hmd5
        chkstr += token+str(self.ac_id)
        chkstr += token+ip
        chkstr += token+str(self.n)
        chkstr += token+str(self.n_type)
        chkstr += token+info
        return chkstr

    def get_info(self, ip:str, username:str, password: str) -> str:
        """Make info json"""
        info_temp={
            "username":username,
            "password":password,
            "ip":ip,
            "acid":str(self.ac_id),
            "enc_ver":str(self.encode_type)
	    }

        return json.dumps(info_temp)

    def get_state(self) -> object:
        """Get auth state"""
        init_res=requests.get(self.get_info_api,headers=self.headers, timeout=2000)
        response = init_res.text
        response_json = re.search(r'jQuery_11414\((.*?)\)',response)[1]
        init_info = json.loads(response_json)
        return init_info

    def get_ip(self) -> str:
        """Get local IP"""
        print('Initializting IP address.')
        init_info = self.get_state()
        
        ip: str = init_info['client_ip'] if 'client_ip' in init_info.keys() else init_info['online_ip']

        print(f'[AUTH] Got IP = {ip}')

        return ip

    def get_token(self, username:str, ip: str):
        """Request challege token"""
        get_challenge_params={
            "callback": "jQuery112404953340710317169_"+str(int(time.time()*1000)),
            "username":username,
            "ip":ip,
            "_":int(time.time()*1000),
	    }
        get_challenge_res = requests.get(
            self.get_challenge_api,
            params=get_challenge_params,
            headers=self.headers,
            timeout = 2000)
        
        get_challenge_json_value = re.search(
            f"{get_challenge_params['callback']}\\((.*?)\\)", get_challenge_res.text)[1]
        get_challenge_json = json.loads(get_challenge_json_value)
        
        challenge = get_challenge_json['challenge']
        print(f'[AUTH] got challenge {challenge}')

        return challenge

    def encrypt(self, ip:str, username:str, password:str) -> Tuple[str, str, str, str]:
        """Encrypt login info"""
        info = self.get_info(ip, username, password)
        token = self.get_token(username, ip)
        info_tex = "{SRBX1}"+get_base64(get_xencode(info,token))
        hmd5=get_md5(password,token)
        chksum=get_sha1(self.get_chksum(hmd5, ip, token, username, info_tex))
        return token, info_tex, hmd5, chksum

    def logout(self, username: str) -> bool:
        ip = self.get_ip()
        srun_portal_params = {
            'callback': 'jQuery11240645308969735664_'+str(int(time.time()*1000)),
            "action": "logout",
            "ac_id": str(self.ac_id),
            "ip": ip,
            "username": username
        }

        srun_portal_res = requests.get(
            self.srun_portal_api,
            params=srun_portal_params,
            headers=self.headers,
            timeout = 2000)

        srun_portal_json_val = re.search(
            f'{srun_portal_params['callback']}\\((.*?)\\)', srun_portal_res.text)[1]

        srun_portal_json = json.loads(srun_portal_json_val)

        return srun_portal_json['error'] == 'ok'
        
        
    def login(self, username:str, password:str, attempts: int = 6):
        """Login auth"""
        ip = self.get_ip()

        for i in range(attempts):
            _, info_tex, hmd5, chksum = self.encrypt(ip, username, password)

            srun_portal_params={
                'callback': 'jQuery11240645308969735664_'+str(int(time.time()*1000)),
                'action':'login',
                'username':username,
                'password':'{MD5}'+hmd5,
                'ac_id':str(self.ac_id),
                'ip':ip,
                'chksum':chksum,
                'info':info_tex,
                'n':str(self.n),
                'type':str(self.n_type),
                'os':'windows+10',
                'name':'windows',
                'double_stack':'0',
                '_':int(time.time()*1000)
            }

            srun_portal_res = requests.get(
                self.srun_portal_api,
                params=srun_portal_params,
                headers=self.headers,
                timeout = 2000)

            srun_portal_json_val = re.search(
                f'{srun_portal_params['callback']}\\((.*?)\\)', srun_portal_res.text)[1]

            srun_portal_json = json.loads(srun_portal_json_val)

            if srun_portal_json['error'] == 'ok':
                break

            print(f'Login failed. Error = {srun_portal_json['error']}. Retry')
        
        return srun_portal_json

def srun_auth_recover(
        gw_server: str, 
        auth_n_type: int, 
        auth_n: int, 
        auth_acid: int, 
        username:str, 
        password: str,
        attempt: int = 5,
        attempt_interval: float = 1) -> bool:
    
    session = SrAuthSession(gw_server, auth_n_type, auth_n, auth_acid)
    state = session.get_state()

    if state['error'] == 'ok':
        print("Already login. Try logout.")
        session.logout(username)
        time.sleep(3)

    session.login(username, password)

    time.sleep(1)

    for i in range(attempt):
        time.sleep(attempt_interval)
        state = session.get_state()
        if state['error'] == 'ok':
            return True
    
    return False

if __name__ == '__main__':
    session = SrAuthSession('gw.buaa.edu.cn', 1, 200, 68)

    print(session.get_state())
    exit(0)
 