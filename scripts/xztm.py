from pathlib import Path
import requests
import json
import os

useful_prefixes = [
    'event',
    'hscene',
    'spinechar',
    'bg',
    'cv',
]
def get_filelist_and_generate_urls():
    # 请求文件列表
    url = "https://msdq.tuanziwo.com/ob/update/android/filelist"
    try:
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        filelist = response.json()

        # 生成下载链接并写入文件
        lines = []
        useless_lines = []
        for item in filelist:
            if any(item["filename"].startswith(prefix) for prefix in useful_prefixes):
                filename = item["filename"]
                download_url = f"https://msdq.tuanziwo.com/ob/update/android/{filename}"
                lines.append(download_url)
                lines.append(f"  out={filename}")
            else:
                filename = item["filename"]
                download_url = f"https://msdq.tuanziwo.com/ob/update/android/{filename}"
                useless_lines.append(download_url)
                useless_lines.append(f"  out={filename}")
        Path("xztm_useless.txt").write_text("\n".join(useless_lines), encoding="utf-8")
        Path("xztm.txt").write_text("\n".join(lines), encoding="utf-8")


        print("下载链接已成功导出到xztm.txt")
        os.system(f"aria2c -i xztm.txt -j 32 -s 16 -x 16 --check-certificate=false --dir=resdownload/贤者同盟")
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
    except json.JSONDecodeError:
        print("解析JSON数据失败")


if __name__ == "__main__":
    get_filelist_and_generate_urls()