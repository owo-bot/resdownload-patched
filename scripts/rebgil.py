import os
import time
import re
from pathlib import Path
from typing import List, Dict
import UnityPy
import requests
from io import BytesIO

MANIFEST_NAME = "webgl"

def load_manifest_from_bytes(data: bytes) -> Dict:
    env = UnityPy.load(BytesIO(data))
    for obj in env.objects:
        if obj.type.name == "AssetBundleManifest":
            return obj.read_typetree()
    raise ValueError("AssetBundleManifest not found")

def parse_manifest(tree: Dict, base_url: str) -> List[Dict]:
    index_to_name = {int(idx): name for idx, name in tree.get("AssetBundleNames", [])}
    results = []
    for entry in tree.get("AssetBundleInfos", []):
        idx = int(entry[0])
        raw = entry[1]
        name = index_to_name.get(idx, f"<Unknown:{idx}>")
        h_bytes = raw["AssetBundleHash"]
        hash_hex = "".join(f"{h_bytes[f'bytes[{i}]']:02x}" for i in range(16))
        deps_idx = raw.get("AssetBundleDependencies", [])
        deps_names = [index_to_name.get(d, f"<Unknown:{d}>") for d in deps_idx]
        url = f"{base_url}/bundle/webgl/{name}?v={hash_hex}"
        results.append({
            "index": idx,
            "name": name,
            "hash": hash_hex,
            "url": url,
            "deps_index": deps_idx,
            "deps_name": deps_names,
        })
    return results

useful_prefixes = [
    'assets-dialogxml-cn',
    'assets-bundles-loaddata-dialogbackground',
    'assets-dialogvoice',
    'assets-bundles-loaddata-hcg-cn',
    'assets-bundles-heropic',
    'assets-bundles-herospine',
]
def export_aria2_txt(data: List[Dict]):
    lines = []
    useless_lines = []
    for item in data:
        name : str = item['name']
        if any(name.startswith(prefix) for prefix in useful_prefixes):
            lines.append(item["url"])
            lines.append(f"  out={item['name']}")
        else:
            useless_lines.append(item["url"])
            useless_lines.append(f"  out={item['name']}")
    Path("rebgil_useless.txt").write_text("\n".join(useless_lines), encoding="utf-8")
    Path("rebgil.txt").write_text("\n".join(lines), encoding="utf-8")


def get_game_url() -> str:
    url = "https://game.ero-labs.cool/api/v2/cloud/135?lang=cn&hgameCloudConnectInfoId=369"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        info = resp.json()
        cloud_data = info.get("data", {}).get("cloudConnectData", [])
        if not cloud_data:
            print("cloudConnectData 为空，无法获取 gameUrl")
            return ""

        return cloud_data[0].get("gameUrl", "")
    except Exception as e:
        print(f"获取 gameUrl 失败: {e}")
        return ""


def main():
    game_url = get_game_url()
    html = requests.get(game_url).text
    m = re.search(r'var\s+res_url\s*=\s*"([^"]+)"', html)
    if not m:
        raise ValueError("解析 res_url 失败")
    BASE_URL = m.group(1).rstrip('/')
    print("解析到 BASE_URL:", BASE_URL)
    timestamp = int(time.time())
    manifest_url = f"{BASE_URL}/bundle/webgl/{MANIFEST_NAME}?v={timestamp}"
    print("Downloading manifest:", manifest_url)
    resp = requests.get(manifest_url)
    resp.raise_for_status()
    tree = load_manifest_from_bytes(resp.content)
    parsed = parse_manifest(tree, BASE_URL)
    export_aria2_txt(parsed)
    os.system(f"aria2c -i rebgil.txt -j 32 -s 16 -x 16 --check-certificate=false --dir=resdownload/魔竞革命")

if __name__ == "__main__":
    main()
