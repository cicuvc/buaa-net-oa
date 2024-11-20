
import socket
from typing import Callable
import requests

from requests.adapters import HTTPAdapter, Retry

import urllib3.util.connection as urllib3_cn 
from urllib3.connectionpool import HTTPConnectionPool
   
def allowed_gai_family():
    return socket.AF_INET

urllib3_cn.allowed_gai_family = allowed_gai_family

def srun_network_check(content: str) -> str:
    if 'https://gw.buaa.edu.cn/' in content:
        return 'NoAuth'
    
    return 'FullAccess'

def check_network_access(url: str, auth_check: Callable[[str], str] = srun_network_check, timeout: float = 2, retry: int = 3) -> str:
    s = requests.Session()
    retries = Retry(total=retry, backoff_factor=0.1, status_forcelist=[ 500, 502, 503, 504 ])
    s.mount('http://', HTTPAdapter(max_retries=retries))

    try:
        response = s.get(url, timeout = timeout)
        return auth_check(response.text)
    except requests.ConnectTimeout as timeout:
        return 'NoAccess'
    except requests.exceptions.ConnectionError as ce:
        return 'NoAccess'
    return 'NoAccess'
    
    
if __name__=="__main__":
    print(check_network_access('http://www.baidu.com/'))
