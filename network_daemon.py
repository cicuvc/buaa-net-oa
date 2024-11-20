from argparse import ArgumentParser
import functools
import grp
import json
import os
import signal
import sys
import time
from typing import Callable, List, NamedTuple, Tuple

from daemon import DaemonContext
import lockfile
from network_detect import check_network_access
from srun_auth import srun_auth_recover
from wpa_helpers import wpa_recover_open, get_local_ip
from cf_helper import update_local_ip

class DaemonConfiguration(NamedTuple):
    check_interval_sec: float = 60 # Time interval for detecting network conditions
    inet_check_url: str = 'http://www.qq.com/'  # Test website for detecting network
    gw_check_url: str =  'https://gw.buaa.edu.cn/' # Test address for checking availability of SRUN gateway
    fix_attempts: int = 5 # number of attempts to try to recover network
    fix_retry_interval_sec: float = 6 # Interval for attempts
    infinity_retry_interval_sec: float = 3600 # if all {fix_attempts} attempts fail, retry in {infinity_retry_interval_sec} seconds
    wpa_ctrl_interface: str = '/var/run/wpa_supplicant/' # wpa control interface
    interface_name: str = 'wlp68s0' # wifi adapter name
    ssid: str = 'BUAA-WiFi' # ssid
    gw_server: str =  'gw.buaa.edu.cn' # SRUN gateway
    username: str = None # username for SRUN auth
    password: str = None # password for SRUN auth
    auth_n: int = 200 # SRUN internal parameter
    auth_n_type: int = 1 # SRUN internal parameter
    auth_acid: int = 68 # SRUN internal parameter
    cf_api_token: str = None # Cloudflare Token for accessing KV storage
    cf_api_key: str = None # Cloudflare Key
    cf_api_email:str = None
    cf_retry_interval_sec: float = 600 # if Cloudflare KV access fails, retry in {cf_retry_interval_sec} seconds

class DaemonConfigurationHelpers:
    @staticmethod
    def load_config(path: os.PathLike) -> DaemonConfiguration:
        with open(path,'r') as f:
            dict_value = json.load(f)
            return DaemonConfiguration(**dict_value)

        
    @staticmethod
    def store_config(path: os.PathLike, config: DaemonConfiguration) -> None:
        dict_obj = config._asdict()
        with open(path,'w+') as f:
            json.dump(dict_obj, f, indent=4)

        os.chmod(path, 777)


class NetworkDaemon:
    def __init__(self, config_path: os.PathLike | None = None):
        if config_path is None:
            config_path = "./default_cfg.json"
            DaemonConfigurationHelpers.store_config(config_path, DaemonConfiguration())

        self.config_path = config_path
        self.action_queue: List[Tuple[float, Callable[[],None]]] = []
        self.loop_run = True
        
        self.update_config()

    def update_config(self) -> None:
        self.config = DaemonConfigurationHelpers.load_config(self.config_path)
    
    def apply_action(self, time: float, action: Callable[[], None]) -> None:
        self.action_queue.append((time, action))

    def daemon_stop(self) -> None:
        self.loop_run = False

    def daemon_loop(self) -> None:
        while self.loop_run:
            current_time = time.time()
            due_tasks = [i for i in self.action_queue if i[0] <= current_time]

            

            for i in due_tasks:
                self.action_queue.remove(i)
                i[1]()

            time.sleep(0.05)
        
        print('Daemon exit gracefully.')

    def action_update_new_ip(self) -> None:
        ip = get_local_ip(self.config.interface_name)
        if update_local_ip(self.config.cf_api_email, self.config.cf_api_token, self.config.cf_api_key, ip):
            print(f"Uploaded IP to Cloudflare KV. New IP = {ip}")
        else:
            self.apply_action(time.time() + self.config.cf_retry_interval_sec, self.action_update_new_ip)

    def action_try_fix_inet(self, remain_attempts: int) -> None:
        if remain_attempts == 0:
            print(f"Remain attempts = 0. Retry in {self.config.infinity_retry_interval_sec} seconds")
            self.apply_action(
                time.time() + self.config.infinity_retry_interval_sec, 
                functools.partial(
                    self.action_try_fix_inet, 
                    remain_attempts = self.config.fix_attempts))
            return
        
        print(f"INET recover attempt = {remain_attempts}. Start diagnosing issues.")

        print(f"Check availability of SRUN gateway server {self.config.gw_check_url}")

        gw_state = check_network_access(self.config.gw_check_url)

        print(f"Gateway server access = {gw_state}")

        if gw_state == 'NoAccess':
            print("Try to re-establish WiFi link")

            success = wpa_recover_open(
                self.config.wpa_ctrl_interface,
                self.config.interface_name,
                self.config.ssid
            )

            if success:
                if check_network_access(self.config.gw_check_url) == 'FullAccess':
                    print("WiFi connection issue solved.")
                    gw_state = 'FullAccess'

        if gw_state == 'FullAccess': # Auth issues
            print("Try to fix authentication issues.")
            print(f"Use profile username = {self.config.username}, acid = {self.config.auth_acid}")

            success = srun_auth_recover(
                self.config.gw_server,
                self.config.auth_n_type,
                self.config.auth_n,
                self.config.auth_acid,
                self.config.username,
                self.config.password
            )

            if success:
                if check_network_access(self.config.inet_check_url) == 'FullAccess':
                    print("Auth issue solved. Inet connection recovered !!")
                    self.apply_action(time.time(), functools.partial(self.action_check_inet, from_recover = True))
                    return
                
        print(f"Failed at GW state {gw_state}. Retry in {self.config.fix_retry_interval_sec} seconds")
        self.apply_action(
            time.time() + self.config.fix_retry_interval_sec, 
            functools.partial(
                self.action_try_fix_inet, 
                remain_attempts = self.config.fix_attempts - 1))
        return
            

    def action_check_inet(self, from_recover: bool = False) -> None:
        inet_status = check_network_access(self.config.inet_check_url)

        if inet_status == 'FullAccess':
            # print(f"Internet access successful. Test server = {self.config.inet_check_url}")

            if from_recover:
                self.apply_action(time.time(), self.action_update_new_ip)

            self.apply_action(time.time() + self.config.check_interval_sec, self.action_check_inet)
        else:
            print("Internet access failed. Try recover.")
            self.apply_action(
                time.time(), 
                functools.partial(
                    self.action_try_fix_inet, 
                    remain_attempts = self.config.fix_attempts))

def ctrl_reload_program_config(signum, frame, daemon: NetworkDaemon | None= None):
    daemon.update_config()

def ctrl_daemon_stop(signum, frame, daemon: NetworkDaemon | None= None):
    daemon.daemon_stop()

def run_daemon(config_path: os.PathLike, work_dir: os.PathLike = '/var/lib/bnaod'):
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    if not os.path.exists(config_path):
        if not os.path.exists(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path))
        DaemonConfigurationHelpers.store_config(config_path, DaemonConfiguration())

    daemon = NetworkDaemon(config_path)
        
    context = DaemonContext(
        working_directory=work_dir,
        umask=0o002,
        pidfile=lockfile.FileLock('/var/run/bnaod.pid'),
        stdout=sys.stdout,
        stderr=sys.stderr)
    
    context.signal_map = {
        signal.SIGTERM: functools.partial(ctrl_daemon_stop, daemon = daemon),
        signal.SIGHUP: functools.partial(ctrl_daemon_stop, daemon = daemon),
        signal.SIGUSR1: functools.partial(ctrl_reload_program_config, daemon = daemon),
        }
    
    context.gid = grp.getgrnam('root').gr_gid
    context.files_preserve = [sys.stdout, sys.stderr]

    with context:
        print(f"Network daemon started. Using configuration file = {config_path}")

        daemon.apply_action(time.time(), functools.partial(daemon.action_check_inet, from_recover = True))
        daemon.daemon_loop()


if __name__=="__main__":
    parser = ArgumentParser("BUAA Network always-online daemon")
    parser.add_argument('--daemon', '-d', action='store_true', default=False, help='Run as daemon. Default false')
    parser.add_argument('--config','-c', type=str, default='/etc/bnaod/default_cfg.json', help='Configuration file. Default default_cfg.json')
    parser.add_argument('--action','-a', type=str, choices=['start', 'stop', 'restart','update'])
    
    args = parser.parse_args(sys.argv[1:])

    if args.daemon:
        run_daemon(args.config)

    
