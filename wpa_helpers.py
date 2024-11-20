import socket
import time
import re
import os
from typing import Dict, List, Tuple, ContextManager
import netifaces as ni
import subprocess as sp

class WPASupplicantControllerSocket:
    def __init__(self, ctrl_path: str):
        self.socket_remote = ctrl_path
        self.socket_local = f'/tmp/wpa-{str(int(time.time()%10000))}'

        if os.path.exists(self.socket_local):
            os.remove(self.socket_local)

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self.socket_local)
        self.sock.connect(self.socket_remote)
        self.sock.settimeout(0.2)
        pass

    def send_and_recv(self, cmd: str) -> str:
        self.sock.sendto(str.encode(cmd), self.socket_remote)

        result = []
        try:
            while True:
                (bytes, address) = self.sock.recvfrom(1024)
                inmsg = bytes.decode('utf-8')
                result.append(inmsg)

                if len(bytes) == 0:
                    break
        except TimeoutError as _:
            pass
        return ''.join(result)
    
    def close(self):
        self.sock.close()
        os.remove(self.socket_local)

class WPASupplicantException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class WPASupplicantController(ContextManager):
    def __init__(self, ctrl_path: str):
        self.sock = WPASupplicantControllerSocket(ctrl_path)

        if self.sock.send_and_recv('ATTACH') != 'OK\n':
            raise WPASupplicantException("Unable to attach")

    def list_networks(self):
        results = self.sock.send_and_recv('LIST_NETWORKS').split('\n')
        network_info: List[Tuple[int, str, str]] = []

        for i in range(1, len(results)):
            
            cols = results[i].split('\t',maxsplit=4)

            if len(cols) != 4:
                continue

            network_info.append((int(cols[0]), cols[1].strip(), cols[2].strip()))

        return network_info
    def checked_socket_cmd(self, result: str, expected = 'OK\n'):
        if result != expected:
            raise WPASupplicantException("Command failed")
        pass

    def config_open_network(self, id: int, ssid: str) -> None:
        self.checked_socket_cmd(self.sock.send_and_recv(f'SET_NETWORK {id} ssid "{ssid}"'))
        self.checked_socket_cmd(self.sock.send_and_recv(f'SET_NETWORK {id} key_mgmt NONE'))
        self.checked_socket_cmd(self.sock.send_and_recv(f'SET_NETWORK {id} mesh_fwding 1'))

        self.sock.send_and_recv("SAVE_CONFIG")
        
        pass

    def new_network(self) -> int:
        result = self.sock.send_and_recv("ADD_NETWORK")
        digits = result.split(' ')[1]
        return int(digits[slice(len(digits) // 2)])

    def del_network(self, id: int):
        self.sock.send_and_recv(f"REMOVE_NETWORK {id}")

    def select_network(self, id: int):
        return self.sock.send_and_recv(f"SELECT_NETWORK {id}")

    def enable_network(self, id: int):
        return self.sock.send_and_recv(f"ENABLE_NETWORK {id}")

    def get_status(self) -> Dict[str, str]:
        result = self.sock.send_and_recv("STATUS").split('\n')
        result_dict: Dict[str, str] = dict()
        for i in result:
            items = i.split('=', maxsplit=2)
            if len(items) != 2:
                continue
            result_dict[items[0]] = items[1]

        return result_dict

    def close(self):
        self.sock.close()
    def __entry__(self):
        pass
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
def allocate_network(supp: WPASupplicantController, ssid: str) -> int:
    networks = supp.list_networks()
    for i in networks:
        if i[1] == ssid:
            return i[0]
    
    return supp.new_network()

def wpa_recover_open(ctrl_if: str, if_name:str, ssid: str, attempts: int = 20, timeout: float = 1) -> bool:
    with WPASupplicantController(os.path.join(ctrl_if, if_name)) as supp:
        status = supp.get_status()
        if 'wpa_state' in status:
            if status['wpa_state'] == 'INTERFACE_DISABLED':
                print(f"Interface {if_name} disabled. Try start")

                sp.run(['ip', 'link', 'set', if_name, 'up'])
        
        time.sleep(5)
        status = supp.get_status()
        if status['wpa_state'] == 'INTERFACE_DISABLED':
            print(f"Interface {if_name} still disabled. Failed")
            return False

        network = allocate_network(supp, ssid)
        supp.config_open_network(network, ssid)

        supp.enable_network(network)
        supp.select_network(network)

        connect_success = False
        for i in range(attempts):
            status = supp.get_status()
            if 'wpa_state' in status:
                if status['wpa_state'] == 'COMPLETED':
                    connect_success = True
                    break
            time.sleep(timeout)

        if not connect_success:
            return False
        
        print("Connect successful")

        if socket.AF_INET in ni.ifaddresses(if_name):
            print("Clear DHCP Address and reassign")
            sp.run(['/sbin/dhclient','-r',if_name])

            if socket.AF_INET in ni.ifaddresses(if_name):
                raise WPASupplicantException("Unable to clear DHCP address")

        sp.run(['/sbin/dhclient',if_name])

        if socket.AF_INET in ni.ifaddresses(if_name):
            print("Address reassign success")

        return True
    pass

def get_local_ip(if_name:str) -> str:
    address_info = ni.ifaddresses(if_name)
    if socket.AF_INET in ni.ifaddresses(if_name):
        return address_info[socket.AF_INET][0]['addr']
    return '<None>'

if __name__=="__main__":
    supp = WPASupplicantController('/var/run/wpa_supplicant/wlp68s0')

    network = allocate_network(supp, 'BUAA-WiFi')
    supp.config_open_network(network, 'BUAA-WiFi')

    print(supp.enable_network(network))
    print(supp.select_network(network))

    while True:
        status = supp.get_status()
        if 'wpa_state' in status:
            if status['wpa_state'] == 'COMPLETED':
                break
        time.sleep(0.5)


    if socket.AF_INET in ni.ifaddresses('wlp68s0'):
        print("Clear DHCP Address and reassign")
        sp.run(['/sbin/dhclient','-r','wlp68s0'])

        if socket.AF_INET in ni.ifaddresses('wlp68s0'):
            raise WPASupplicantException("Unable to clear DHCP address")

    sp.run(['/sbin/dhclient','wlp68s0'])

    if socket.AF_INET in ni.ifaddresses('wlp68s0'):
        print("Address reassign success")
