import os
import subprocess
import socket
import requests
import sys
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# --- CONFIGURATION ---
M1_USER = 'aatifquamre'
M2_USER = 'azmatsaif'          # Legacy M2 / 8GB node
M1_PATH = '/Users/aatifquamre/masterbot'
M2_PATH = '/Users/azmatsaif/masterbot'
M1_FREQTRADE_API = 'http://100.90.68.42:8080/api/v1'

# Load environment
load_dotenv(f"{M1_PATH}/.env")

M1_IP       = os.getenv("M1_TAILSCALE_IP",       "100.90.68.42")
M2_IP       = os.getenv("M2_TAILSCALE_IP",        "100.74.110.36")
M2_8GB_IP   = os.getenv("M2_8GB_TAILSCALE_IP",    "")
M2_16GB_IP  = os.getenv("M2_16GB_TAILSCALE_IP",   "")
M2_8GB_USER  = os.getenv("M2_8GB_USER",  "m2_8gb_user")
M2_16GB_USER = os.getenv("M2_16GB_USER", "m2_16gb_user")
M2_8GB_PATH  = f"/Users/{M2_8GB_USER}/masterbot"
M2_16GB_PATH = f"/Users/{M2_16GB_USER}/masterbot"

FT_USER = os.getenv("FREQTRADE_UI_USERNAME")
FT_PASS = os.getenv("FREQTRADE_UI_PASSWORD")

# ---------------------------------------------------------------------------
# Device capabilities matrix — used by get_optimal_ml_node()
# ---------------------------------------------------------------------------
DEVICE_CAPABILITIES = {
    "M1": {
        "role": "execution",
        "ram_gb": 8,
        "hyperopt_epochs": 0,
        "parallel_strategies": 0,
        "freqai_training": False,
        "sentiment_pipeline": False,
    },
    "M2": {
        "role": "intelligence",
        "ram_gb": 8,
        "hyperopt_epochs": 100,
        "parallel_strategies": 1,
        "freqai_training": True,
        "sentiment_pipeline": True,
    },
    "M2_8GB": {
        "role": "intelligence",
        "ram_gb": 8,
        "hyperopt_epochs": 75,       # conservative — leaves headroom for macOS
        "parallel_strategies": 1,
        "freqai_training": True,
        "sentiment_pipeline": True,
    },
    "M2_16GB": {
        "role": "ml_research",
        "ram_gb": 16,
        "hyperopt_epochs": 200,      # 2× more epochs vs 8GB node
        "parallel_strategies": 2,    # run 2 strategies concurrently
        "freqai_training": True,
        "sentiment_pipeline": True,
        "extended_pairs": True,      # can analyse more coin pairs
        "large_model": True,         # supports bigger FreqAI architectures
    },
}


def _detect_ram_gb() -> int:
    """Return installed RAM in GB, rounded to nearest power of 2."""
    try:
        import psutil
        raw = psutil.virtual_memory().total / (1024 ** 3)
        if raw < 12:
            return 8
        if raw < 24:
            return 16
        return 32
    except Exception:
        return 8


def get_current_device() -> dict:
    """Detect which machine we're running on and return full device context."""
    user = os.getenv("USER") or os.getenv("USERNAME", "")
    hostname = socket.gethostname()
    ram_gb = _detect_ram_gb()

    # Priority: explicit username match → RAM-based variant for M2 family
    if user == M2_16GB_USER:
        device = "M2_16GB"
        path   = M2_16GB_PATH
        ip     = M2_16GB_IP
    elif user == M2_8GB_USER:
        device = "M2_8GB"
        path   = M2_8GB_PATH
        ip     = M2_8GB_IP
    elif user == M2_USER or "azmatsaif" in os.getcwd():
        # Legacy M2 — auto-classify by actual RAM so behaviour scales correctly
        if ram_gb >= 16:
            device = "M2_16GB"
        else:
            device = "M2_8GB"
        path = M2_PATH
        ip   = M2_IP
    else:
        device = "M1"
        path   = M1_PATH
        ip     = M1_IP

    is_m1 = (device == "M1")
    caps  = DEVICE_CAPABILITIES.get(device, DEVICE_CAPABILITIES["M2"])

    return {
        "device":                    device,
        "user":                      user,
        "hostname":                  hostname,
        "ram_gb":                    ram_gb,
        "masterbot_path":            path,
        "role":                      caps["role"],
        "can_reach_freqtrade_directly": is_m1,
        "other_device":              "M2" if is_m1 else "M1",
        "other_device_ip":           M2_IP if is_m1 else M1_IP,
        "capabilities":              caps,
    }


DEVICE_CONTEXT = get_current_device()


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def _ssh_run(user, ip, command, capture=True):
    ssh_cmd = f"ssh {user}@{ip} '{command}'"
    proc = subprocess.run(ssh_cmd, shell=True, capture_output=capture, text=True)
    return proc.stdout, proc.stderr, proc.returncode


def run_on_m1(command, capture=True):
    """Route command to M1 (Execution Node)."""
    try:
        sys.path.insert(0, DEVICE_CONTEXT["masterbot_path"] + '/qnt/memory')
        from memory_manager import log_action
    except ImportError:
        def log_action(*args, **kwargs): pass

    if DEVICE_CONTEXT["device"] == "M1":
        proc = subprocess.run(command, shell=True, capture_output=capture, text=True)
        log_action("run_on_m1_local", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode
    else:
        result = _ssh_run(M1_USER, M1_IP, command, capture)
        log_action("run_on_m1_remote", f"Cmd: {command[:50]}... | Exit: {result[2]}")
        return result


def run_on_m2(command, capture=True):
    """Route command to legacy M2 (azmatsaif) / 8GB intelligence node."""
    try:
        sys.path.insert(0, DEVICE_CONTEXT["masterbot_path"] + '/qnt/memory')
        from memory_manager import log_action
    except ImportError:
        def log_action(*args, **kwargs): pass

    if DEVICE_CONTEXT["device"] in ("M2", "M2_8GB") and DEVICE_CONTEXT.get("user") == M2_USER:
        proc = subprocess.run(command, shell=True, capture_output=capture, text=True)
        log_action("run_on_m2_local", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode
    else:
        result = _ssh_run(M2_USER, M2_IP, command, capture)
        log_action("run_on_m2_remote", f"Cmd: {command[:50]}... | Exit: {result[2]}")
        return result


def run_on_m2_8gb(command, capture=True):
    """Route command to the dedicated M2 8GB intelligence node."""
    if not M2_8GB_IP:
        raise RuntimeError("M2_8GB_TAILSCALE_IP not configured in .env")

    try:
        sys.path.insert(0, DEVICE_CONTEXT["masterbot_path"] + '/qnt/memory')
        from memory_manager import log_action
    except ImportError:
        def log_action(*args, **kwargs): pass

    if DEVICE_CONTEXT["device"] == "M2_8GB":
        proc = subprocess.run(command, shell=True, capture_output=capture, text=True)
        log_action("run_on_m2_8gb_local", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode
    else:
        result = _ssh_run(M2_8GB_USER, M2_8GB_IP, command, capture)
        log_action("run_on_m2_8gb_remote", f"Cmd: {command[:50]}... | Exit: {result[2]}")
        return result


def run_on_m2_16gb(command, capture=True):
    """Route command to the high-capacity M2 16GB ML/research node."""
    if not M2_16GB_IP:
        raise RuntimeError("M2_16GB_TAILSCALE_IP not configured in .env")

    try:
        sys.path.insert(0, DEVICE_CONTEXT["masterbot_path"] + '/qnt/memory')
        from memory_manager import log_action
    except ImportError:
        def log_action(*args, **kwargs): pass

    if DEVICE_CONTEXT["device"] == "M2_16GB":
        proc = subprocess.run(command, shell=True, capture_output=capture, text=True)
        log_action("run_on_m2_16gb_local", f"Cmd: {command[:50]}... | Exit: {proc.returncode}")
        return proc.stdout, proc.stderr, proc.returncode
    else:
        result = _ssh_run(M2_16GB_USER, M2_16GB_IP, command, capture)
        log_action("run_on_m2_16gb_remote", f"Cmd: {command[:50]}... | Exit: {result[2]}")
        return result


def get_optimal_ml_node(task: str = "hyperopt") -> str:
    """
    Return the device name best suited for a given ML task.

    Priority order: M2_16GB → M2_8GB → M2 (legacy) → None
    Falls back to next available reachable node.
    """
    candidates = [
        ("M2_16GB", M2_16GB_IP, M2_16GB_USER),
        ("M2_8GB",  M2_8GB_IP,  M2_8GB_USER),
        ("M2",      M2_IP,      M2_USER),
    ]

    for name, ip, _ in candidates:
        if not ip:
            continue
        if _ping(ip):
            return name

    return "M2"   # fallback — always keep legacy M2 as default


def _ping(ip: str) -> bool:
    res = subprocess.run(f"ping -c 1 -W 3 {ip}", shell=True, capture_output=True)
    return res.returncode == 0


def call_freqtrade_api(endpoint, method='GET', data=None):
    """Call Freqtrade REST API on M1 from any node."""
    endpoint = endpoint.lstrip('/')
    base_url = M1_FREQTRADE_API if DEVICE_CONTEXT["device"] == "M1" else f"http://{M1_IP}:8080/api/v1"
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
    """Ping the primary 'other' device (M2 from M1 or M1 from M2)."""
    return _ping(DEVICE_CONTEXT["other_device_ip"])


def fleet_status() -> dict:
    """Return reachability and RAM tier for every known node."""
    nodes = {
        "M1":      M1_IP,
        "M2":      M2_IP,
        "M2_8GB":  M2_8GB_IP,
        "M2_16GB": M2_16GB_IP,
    }
    return {
        name: {"ip": ip, "reachable": _ping(ip) if ip else False}
        for name, ip in nodes.items()
    }


if __name__ == "__main__":
    print(f"Device context: {DEVICE_CONTEXT}")
    print(f"Other device reachable: {is_other_device_reachable()}")
    print(f"Optimal ML node: {get_optimal_ml_node()}")
    print(f"Fleet status: {fleet_status()}")
