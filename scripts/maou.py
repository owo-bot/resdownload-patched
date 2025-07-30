from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import shutil
import subprocess
import requests
from PIL import Image

useproxy = False
proxyaddr = ''

def zzmwdownloader(overwrite):
    VALID_SUFFIXES = ('.basis', '.json', '.atlas.txt', '.mp3')
    DOWNLOAD_DIR = "resdownload/转职魔王X"
    TEMP_DIR = os.path.join(DOWNLOAD_DIR, "temp")
    BASISU_EXE = "basis_universal/bin/basisu"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    file_map = {}
    # if not os.path.exists(BASISU_EXE):
    #     print(f"请下载依赖{BASISU_EXE}")
    #     newWin = Tk()
    #     newWin.withdraw()
    #     confirm = messagebox.askyesno("需要下载依赖", f"此功能依赖{BASISU_EXE}是否自动下载", parent=newWin)
    #     newWin.destroy()
    #     if confirm:
    #         os.system(f"aria2c https://resdownload.7sec.fun/resdownloader/{BASISU_EXE}")
    #         print("请重新运行此功能")
    #     return

    def get_game_url():
        api_url = "https://game.ero-labs.gold/api/v2/cloud/136?lang=cn"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "SUCCESS" and data.get("data"):
                cloud_connect_data = data["data"].get("cloudConnectData", [])
                if cloud_connect_data:
                    game_url = cloud_connect_data[0].get("gameUrl")
                    if game_url:
                        return game_url.replace("/index/", "/game/")
        except Exception as e:
            print(f"获取游戏URL出错: {e}")
        return None

    def get_settings_js_url(game_url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(game_url, headers=headers)
            response.raise_for_status()
            manifest_pattern = r'<link rel="manifest" href="([^"]+manifest\.json)"'
            settings_pattern = r'<script src="([^"]+__settings__\.js)"'

            manifest_match = re.search(manifest_pattern, response.text)
            settings_match = re.search(settings_pattern, response.text)

            if settings_match:
                return settings_match.group(1)
            elif manifest_match:
                # 如果不能直接找到settings.js，尝试从manifest URL推断
                manifest_url = manifest_match.group(1)
                base_url = manifest_url.split("/manifest.json")[0]
                return f"{base_url}/__settings__.js"
        except Exception as e:
            print(f"获取settings.js URL出错: {e}")
        return None

    def get_cdn_prefix(settings_js_url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(settings_js_url, headers=headers)
            response.raise_for_status()
            asset_prefix_pattern = r'window\.ASSET_PREFIX\s*=\s*"([^"]+)"'
            match = re.search(asset_prefix_pattern, response.text)

            if match:
                asset_prefix = match.group(1)
                cdn_prefix = asset_prefix[:-1]
                return cdn_prefix
        except Exception as e:
            print(f"获取CDN_PREFIX出错: {e}")
        return None

    def get_config_filename(settings_js_url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(settings_js_url, headers=headers)
            response.raise_for_status()

            config_pattern = r'window\.CONFIG_FILENAME\s*=\s*"([^"]+)"'
            match = re.search(config_pattern, response.text)

            if match:
                return match.group(1)
        except Exception as e:
            print(f"获取CONFIG_FILENAME出错: {e}")
        return None

    def get_config_data(config_url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(config_url, headers=headers)
            response.raise_for_status()
            with open(f"{DOWNLOAD_DIR}/config.json", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("config.json 已保存")
            return response.json()
        except Exception as e:
            print(f"获取config.json数据出错: {e}")
        return None

    def basis_to_png_threadsafe(basis_path):
        basename = os.path.splitext(os.path.basename(basis_path))[0]
        work_dir = os.path.join(TEMP_DIR, basename)

        try:
            os.makedirs(work_dir, exist_ok=True)

            temp_basis_path = os.path.join(work_dir, os.path.basename(basis_path))
            shutil.copy(basis_path, temp_basis_path)

            result = subprocess.run(
                [os.path.abspath(BASISU_EXE), "-file", os.path.basename(temp_basis_path)],
                cwd=work_dir
            )

            if result.returncode != 0:
                print(f"[!] basisu解码失败: {basis_path}")
                return False

            candidates = [
                f"{basename}_unpacked_rgba_BC7_RGBA_0000.png"]

            for png_file in candidates:
                temp_png_path = os.path.join(work_dir, png_file)
                if os.path.exists(temp_png_path):
                    final_png_path = os.path.join(DOWNLOAD_DIR, f"{basename}.png")
                    shutil.move(temp_png_path, final_png_path)
                    print(f"[+] 转换成功: {basis_path} → {final_png_path}")
                    return True

            print(f"[!] 没找到有效PNG: {basis_path}")
            return False

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def clean_temp():
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
            print("[*] 已清理临时目录")

    def getpngmain():
        basis_files = [
            os.path.join(DOWNLOAD_DIR, f)
            for f in os.listdir(DOWNLOAD_DIR)
            if f.endswith(".basis")
        ]

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_path = {executor.submit(basis_to_png_threadsafe, path): path for path in basis_files}

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    if future.result():
                        os.remove(path)
                        print(f"[+] 删除原文件: {path}")
                except Exception as e:
                    print(f"[!] 处理失败 {path}: {e}")

        clean_temp()

    def organize_files_by_prefix(spine_prefixes, adv_names):
        for prefix in spine_prefixes:
            folder_path = os.path.join(DOWNLOAD_DIR, prefix)
            os.makedirs(folder_path, exist_ok=True)

            for f in os.listdir(DOWNLOAD_DIR):
                if f == prefix:
                    continue
                if f.startswith(prefix) and os.path.isfile(os.path.join(DOWNLOAD_DIR, f)):
                    src = os.path.join(DOWNLOAD_DIR, f)
                    dst = os.path.join(folder_path, f)
                    shutil.move(src, dst)
                    print(f"[+] 移动: {f} → {folder_path}")
        for adv_name in adv_names:
            folder_path = os.path.join(DOWNLOAD_DIR, "adv" + adv_name)
            os.makedirs(folder_path, exist_ok=True)

            for f in os.listdir(DOWNLOAD_DIR):
                if f == adv_name:
                    continue
                if adv_name in f and os.path.isfile(os.path.join(DOWNLOAD_DIR, f)):
                    src = os.path.join(DOWNLOAD_DIR, f)
                    dst = os.path.join(folder_path, f)
                    shutil.move(src, dst)
                    print(f"[+] 移动: {f} → {folder_path}")

    def rename_atlas_txt():
        for f in os.listdir(DOWNLOAD_DIR):
            if f.endswith(".atlas.txt"):
                old_path = os.path.join(DOWNLOAD_DIR, f)
                new_name = f[:-4]
                new_path = os.path.join(DOWNLOAD_DIR, new_name)
                os.rename(old_path, new_path)
                print(f"[+] 重命名: {f} → {new_name}")

    def mainload():
        # 执行完整流程
        game_url = get_game_url()
        if not game_url:
            print("无法获取游戏URL")
            return

        print(f"游戏URL: {game_url}")

        settings_js_url = get_settings_js_url(game_url)
        if not settings_js_url:
            print("无法获取__settings__.js URL")
            return

        #print(f"获取到的__settings__.js URL: {settings_js_url}")

        cdn_prefix = get_cdn_prefix(settings_js_url)
        if not cdn_prefix:
            print("无法获取CDN_PREFIX")
            return

        #print(f"获取到的CDN_PREFIX: {cdn_prefix}")

        config_url = get_config_filename(settings_js_url)
        if not config_url:
            print("无法获取CONFIG_FILENAME")
            return

        print(f"config.json URL: {config_url}")

        data = get_config_data(config_url)
        if not data:
            print("无法获取config.json数据")
            return
        assets = data.get("assets", {})
        for asset_id, asset_info in assets.items():
            file_info = asset_info.get("file")
            if not file_info:
                continue

            url = None
            filename: str = None

            basis_variant = file_info.get("variants", {}).get("basis")
            if basis_variant:
                filename = basis_variant.get("filename")
                url = basis_variant.get("url")

            if not url or not filename:
                filename = file_info.get("filename")
                url = file_info.get("url")

            if not filename or not url:
                continue

            if not filename.endswith(VALID_SUFFIXES):
                continue

            NO_DOWNLOAD_SUBSTRINGS = [
                "unit_enemy", "buf", "usk", "rule", "Help", "gacha", "thumb", "hit", "aoe", "attack",
                "recommend", "VIP", "unit_chara", "login", "sale", "arena", "ef", "sef", "skill", "BGM",
                "charagrowth", "unit_mokujin", "limited", "pass"
            ]
            if any(sub in filename for sub in NO_DOWNLOAD_SUBSTRINGS):
                continue

            # Skil non-H
            if filename.endswith(".mp3"):
                if filename[filename.find("_")+1] == "E":
                    continue
                if (filename.startswith("RIT") or filename.startswith("CAT")):
                    continue
                if len(filename) == 7 and all(c.isdigit() for c in filename[:3]):
                    continue

            full_url = f"{cdn_prefix}/{url}"  #cdn_prefix + url
            print(full_url)

            file_map[filename] = full_url

        with open("zzmw.txt", "w", encoding="utf-8") as out_file:
            for fname, url in file_map.items():
                url: str
                if fname.endswith(".basis"):
                    continue
                if fname.endswith(".json"):
                    out_file.write(f"{url}\n   out={fname}\n\n")
                    if fname.startswith("adv") or ("still" in fname and "anim" in fname):
                        nosuffix = fname.removesuffix('.json')
                        out_file.write(f"{url.replace('en', 'cn')}\n   out={nosuffix}-cn.json\n\n")
                        out_file.write(f"{url.replace('en', 'tw')}\n   out={nosuffix}-tw.json\n\n")
                else:
                    print(f"跳过非json文件: {fname}")

        os.system(f"aria2c -i zzmw.txt -j 16 -s 16 -x 16 --check-certificate=false --auto-file-renaming=false {f'{proxyaddr} ' if useproxy else ''}{'--allow-overwrite=true ' if overwrite else ''}--dir={DOWNLOAD_DIR}")
        print("正在解析json...")
        spine_prefixes = set()
        adv_names = set()
        for fname in os.listdir(DOWNLOAD_DIR):
            fname: str
            if fname.endswith(".json"):
                fpath = os.path.join(DOWNLOAD_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        j = json.load(f)
                        do_download = "skeleton" in j and isinstance(j["skeleton"], dict) and "spine" in j["skeleton"]
                        if do_download:
                            name_prefix = os.path.splitext(fname)[0]
                            if "cn" not in fname and "tw" not in fname:
                                spine_prefixes.add(name_prefix)
                        if "entities" in j:
                            os.remove(fpath)
                    if fname.startswith("adv"):
                        adv_names.add(fname[3:fname.index("_")])
                except Exception:
                    pass

        with open("zzmw.txt", "w", encoding="utf-8") as out_file:
            for fname, url in file_map.items():
                if fname.endswith(".json"):
                    continue
                out_file.write(f"{url}\n   out={fname}\n\n")

        os.system(f"aria2c -i zzmw.txt -j 32 -s 16 -x 16 --check-certificate=false --auto-file-renaming=false {f'{proxyaddr} ' if useproxy else ''}{'--allow-overwrite=true ' if overwrite else ''}--dir={DOWNLOAD_DIR}")
        getpngmain()
        rename_atlas_txt()
        organize_files_by_prefix(spine_prefixes, adv_names)
    
    def postprocess():
        config = json.load(open(f"{DOWNLOAD_DIR}/config.json", "r", encoding="utf-8"))
        for asset_id, asset_info in config.get("assets", {}).items():
            name: str = asset_info.get("name", "")
            if name.startswith("king_adv") and name.endswith(".png"):
                frames = asset_info.get("data", {}).get("frames", {})
                noprefix = name.removeprefix("king_adv")
                folder = "adv" + noprefix[:noprefix.index("_")]
                og_img = os.path.join(DOWNLOAD_DIR, folder, name)
                for frame_id, frame_info in frames.items():
                    frame_name = frame_info.get("name", "")
                    rect = frame_info.get("rect", [])
                    Image.open(og_img).crop((1, 1, rect[2], rect[3])).save(os.path.join(DOWNLOAD_DIR, folder, frame_name))
                    print(f"[+] 处理完毕: {name} → {frame_name}")
                os.remove(og_img)
            else:
                continue

    mainload()
    postprocess()

zzmwdownloader(False)
