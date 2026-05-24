import os
import subprocess
import socket
import requests
import sys
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# --- CONFIGURATION ---
M1_USER = 'aatifquamre'
M2_USER = 'azmatsaif'
M1_PATH = '/Users/aatifquamre/cipher'
M2_PATH = '/Users/azmatsaif/cipher'
M1_FREQTRADE_API = 'http://100.90.68.42:8080/api/v1'

# Load environment
load_dotenv(f"{M1_PATH}/.env")

M1_IP = os.getenv("M1_TAILSCALE_IP", "127.0.0.1")
M2_IP = os.getenv("M2_TAILSCALE_IP", "100.74.110.36")
FT_USER = os.getenv("FREQTRADE_UI_USERNAME")
FT_PASS = os.getenv("FREQTRADE_UI_PASSWORD")

def get_current_device():
    """Detect location and return device context."""
    user = os.getenv("USER") or os.getenv("USERNAME")
    hostname = socket.gethostname()
    cwd = os.getcwd()
    
    if "azmatsaif" in cwd or user == M2_USER:
        device = "M2"
        user = M2_USER
    else:
        device = "M1"
        user = M1_USER
        
    is_m1 = (device == "M1")
    
    return {
        "device": device,
        "user": user,
        "hostname": hostname,
        "cipher_path": M1_PATH if is_m1 else M2_PATH,
        "role": "execution" if is_m1 else "intelligence",
        "can_reach_freqtrade_directly": is_m1,
        "other_device": "M2" if is_m1 else "M1",
        "other_device_ip": M2_IP if is_m1 else M1_IP
    }

DEVICE_CONTEXT = get_current_device()

def run_on_m1(command, capture=True):
    """Route command to M1 (Execution Node)."""
    # Import log_action inside to avoid circular dependencies if any
    try:
        sys.path.insert(0, DEVICE_CONTEXT["cipher_path"] + '/qnt/memory')
        from memory_manager import log_action
    except ImportError:
        def log_action(*args, **kwargs): pass

    if DEVICE_CONTEXT["device"] == "M1":
        # Local execution
        proc = subprocess.run(command, shell=True, capture_output=capture, text=True)
        log_action(f"run_on_m1_local", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode
    else:
        # Remote execution via SSH
        ssh_cmd = f"ssh {M1_USER}@{M1_IP} '{command}'"
        proc = subprocess.run(ssh_cmd, shell=True, capture_output=capture, text=True)
        log_action(f"run_on_m1_remote", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode

def run_on_m2(command, capture=True):
    """Route command to M2 (Intelligence Node)."""
    try:
        sys.path.insert(0, DEVICE_CONTEXT["cipher_path"] + '/qnt/memory')
        from memory_manager import log_action
    except ImportError:
        def log_action(*args, **kwargs): pass

    if DEVICE_CONTEXT["device"] == "M2":
        # Local execution
        proc = subprocess.run(command, shell=True, capture_output=capture, text=True)
        log_action(f"run_on_m2_local", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode
    else:
        # Remote execution via SSH
        ssh_cmd = f"ssh {M2_USER}@{M2_IP} '{command}'"
        proc = subprocess.run(ssh_cmd, shell=True, capture_output=capture, text=True)
        log_action(f"run_on_m2_remote", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode

def call_freqtrade_api(endpoint, method='GET', data=None):
    """Calls Freqtrade API on M1 from anywhere."""
    # Strip leading slash if present
    endpoint = endpoint.lstrip('/')
    
    if DEVICE_CONTEXT["device"] == "M1":
        base_url = M1_FREQTRADE_API
    else:
        base_url = f"http://{M1_IP}:8080/api/v1"
        
    url = f"{base_url}/{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(url, auth=HTTPBasicAuth(FT_USER, FT_PASS), timeout=10)
        elif method == 'POST':
            response = requests.post(url, auth=HTTPBasicAuth(FT_USER, FT_PASS), json=data, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise RuntimeError(f"Freqtrade API unreachable at {url}: {e}")

def is_other_device_reachable():
    """Ping other device via Tailscale."""
    ip = DEVICE_CONTEXT["other_device_ip"]
    # -c 1 (1 packet), -W 3 (3s timeout)
    res = subprocess.run(f"ping -c 1 -W 3 {ip}", shell=True, capture_output=True)
    return res.returncode == 0

if __name__ == "__main__":
    print(f"Device context: {DEVICE_CONTEXT}")
    print(f"Other device reachable: {is_other_device_reachable()}")
