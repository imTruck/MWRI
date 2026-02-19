import json
import base64
import logging
import copy

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"

WARP_CONFIGS = [
    {
        "tag": "warp",
        "protocol": "wireguard",
        "address": "162.159.192.1",
        "port": 2408,
        "params": {
            "secretKey": "YFYRsGrvEhESsID3mGbJhwMFR7PqJPNGyM9C6wiJd1o=",
            "publicKey": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
            "address": ["172.16.0.2/32", "2606:4700:110:8a36:df92:102a:9602:fa18/128"],
            "reserved": [78, 135, 76],
            "mtu": 1280
        }
    },
    {
        "tag": "warp-ir",
        "protocol": "wireguard",
        "address": "188.114.98.0",
        "port": 1701,
        "params": {
            "secretKey": "YFYRsGrvEhESsID3mGbJhwMFR7PqJPNGyM9C6wiJd1o=",
            "publicKey": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
            "address": ["172.16.0.2/32", "2606:4700:110:8a36:df92:102a:9602:fa18/128"],
            "reserved": [78, 135, 76],
            "mtu": 1280
        }
    }
]

WARP_ENDPOINTS = [
    "162.159.192.1:2408",
    "162.159.193.1:2408",
    "162.159.195.1:2408",
    "162.159.204.1:2408",
    "188.114.96.1:2408",
    "188.114.97.1:2408",
    "188.114.98.1:2408",
    "188.114.99.1:2408",
    "162.159.192.1:1701",
    "162.159.193.1:1701",
    "162.159.195.1:1701",
    "188.114.96.1:1701",
    "188.114.97.1:1701",
    "188.114.98.1:1701",
    "162.159.192.1:864",
    "162.159.193.1:864",
    "188.114.96.1:864",
    "188.114.97.1:864",
    "162.159.192.1:908",
    "162.159.193.1:908",
    "188.114.96.1:908",
    "188.114.97.1:908",
    "162.159.192.1:928",
    "162.159.193.1:928",
    "162.159.192.1:934",
    "162.159.193.1:934",
    "162.159.192.1:939",
    "162.159.193.1:939",
    "162.159.192.1:942",
    "162.159.193.1:942",
    "162.159.192.1:1018",
    "162.159.193.1:1018",
    "162.159.192.1:1843",
    "162.159.193.1:1843",
    "162.159.192.1:2371",
    "162.159.193.1:2371",
    "162.159.192.1:2506",
    "162.159.193.1:2506",
    "162.159.192.1:3138",
    "162.159.193.1:3138",
    "162.159.192.1:3476",
    "162.159.193.1:3476",
    "162.159.192.1:4177",
    "162.159.193.1:4177",
    "162.159.192.1:4198",
    "162.159.193.1:4198",
    "162.159.192.1:7559",
    "162.159.193.1:7559",
    "162.159.192.1:8319",
    "162.159.193.1:8319",
]


def generate_warp_wireguard():
    """Generate WireGuard configs for Hiddify/v2rayNG"""
    configs = []

    for i, endpoint in enumerate(WARP_ENDPOINTS):
        ip, port = endpoint.rsplit(":", 1)
        name = "\U00002601\U0000FE0F " + PREFIX + " WARP#" + str(i + 1)

        wg_url = "wireguard://" + WARP_CONFIGS[0]["params"]["secretKey"]
        wg_url += "@" + ip + ":" + port
        wg_url += "?publickey=" + WARP_CONFIGS[0]["params"]["publicKey"]
        wg_url += "&reserved=" + str(WARP_CONFIGS[0]["params"]["reserved"][0])
        wg_url += "," + str(WARP_CONFIGS[0]["params"]["reserved"][1])
        wg_url += "," + str(WARP_CONFIGS[0]["params"]["reserved"][2])
        wg_url += "&address=172.16.0.2/32"
        wg_url += "&mtu=1280"
        wg_url += "#" + name.replace(" ", "%20")

        configs.append(wg_url)

    logger.info("Generated " + str(len(configs)) + " WARP configs")
    return configs


def generate_warp_wgcf():
    """Generate WGCF format configs"""
    configs_text = ""
    for i, endpoint in enumerate(WARP_ENDPOINTS):
        ip, port = endpoint.rsplit(":", 1)
        cfg = "[Interface]\n"
        cfg += "PrivateKey = " + WARP_CONFIGS[0]["params"]["secretKey"] + "\n"
        cfg += "Address = 172.16.0.2/32\n"
        cfg += "Address = 2606:4700:110:8a36:df92:102a:9602:fa18/128\n"
        cfg += "DNS = 1.1.1.1, 1.0.0.1\n"
        cfg += "MTU = 1280\n\n"
        cfg += "[Peer]\n"
        cfg += "PublicKey = " + WARP_CONFIGS[0]["params"]["publicKey"] + "\n"
        cfg += "AllowedIPs = 0.0.0.0/0, ::/0\n"
        cfg += "Endpoint = " + endpoint + "\n\n"
        configs_text += cfg + "---\n\n"

    return configs_text


def save_warp(output_dir):
    """Save all WARP configs"""
    from pathlib import Path
    warp_dir = output_dir + "/warp"
    Path(warp_dir).mkdir(parents=True, exist_ok=True)

    # WireGuard URLs (for Hiddify/v2rayNG)
    wg_configs = generate_warp_wireguard()
    with open(warp_dir + "/warp.txt", "w") as f:
        for c in wg_configs:
            f.write(c + "\n")

    # Base64
    raw = "\n".join(wg_configs)
    b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    with open(warp_dir + "/warp_sub.txt", "w") as f:
        f.write(b64)

    # WGCF format
    wgcf = generate_warp_wgcf()
    with open(warp_dir + "/wgcf.conf", "w") as f:
        f.write(wgcf)

    logger.info("WARP saved: " + str(len(wg_configs)) + " configs")
    return len(wg_configs)
