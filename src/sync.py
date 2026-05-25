import os
import sys
import time
import subprocess
import requests
import pandas as pd
from datetime import datetime, timezone

API_URL = "https://api.bilibili.com/x/web-interface/history/cursor"


class AuthError(Exception):
    pass

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def make_headers(sessdata):
    return {
        **BROWSER_HEADERS,
        "Cookie": f"SESSDATA={sessdata}",
    }
OUTPUT_DIR = "output"
EXCEL_PATH = os.path.join(OUTPUT_DIR, "BilibiliHistory.xlsx")


def get_cutoff():
    if not os.path.exists(EXCEL_PATH):
        return 0
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
    if df.empty:
        return 0
    return int(pd.to_datetime(df["观看时间"]).max().timestamp())


def load_existing_rows():
    if not os.path.exists(EXCEL_PATH):
        return []
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
    return df.to_dict("records")


def fetch_history(sessdata):
    headers = make_headers(sessdata)
    params = {"ps": 30, "view_at": ""}
    records = []

    cutoff = get_cutoff()
    print(f"Cutoff: {cutoff} ({datetime.fromtimestamp(cutoff, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if cutoff else 'none'})")

    while True:
        resp = requests.get(API_URL, headers=headers, params=params)
        print(f"Request: status={resp.status_code}")
        if resp.status_code != 200:
            print(f"HTTP error: {resp.status_code}")
            raise AuthError(f"HTTP {resp.status_code}")
        data = resp.json()
        if data.get("code") != 0:
            raise AuthError(f"API error: code={data['code']}, msg={data.get('message','')}")

        items = data.get("data", {}).get("list", [])
        if not items:
            print("Empty page, stopping")
            break

        page_new = 0
        for item in items:
            if item["view_at"] > cutoff:
                records.append(item)
                page_new += 1

        print(f"Page: {len(items)} items, {page_new} new (newest={items[0]['view_at']}, oldest={items[-1]['view_at']})")

        if page_new < len(items):
            break

        cursor = data["data"].get("cursor", {})
        params["max"] = cursor.get("max")
        params["view_at"] = cursor.get("view_at")
        time.sleep(0.5)

    return records


def fmt_duration(seconds):
    if not seconds:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


def to_rows(records):
    return [{
        "观看时间": datetime.fromtimestamp(r["view_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "视频标题": r.get("title", ""),
        "BV号": r.get("history", {}).get("bvid", ""),
        "UP主": r.get("author_name", ""),
        "分区": r.get("tag_name", ""),
        "时长": fmt_duration(r.get("duration", 0)),
    } for r in records]


def write_excel(rows):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")
    print(f"Excel saved: {EXCEL_PATH} ({len(rows)} records)")


def _git_run(args, timeout=60):
    try:
        return subprocess.run(
            ["git"] + args, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        print("错误：未找到 Git，请先安装 https://git-scm.com")
        return None
    except subprocess.TimeoutExpired:
        print(f"Git 操作超时")
        return None


def git_pull():
    print(">>> 拉取 GitHub 最新数据...")
    r = _git_run(["pull", "--rebase", "origin", "master"])
    if r is None:
        return False
    if r.returncode != 0:
        print(r.stderr.strip())
        return False
    return True


def git_push():
    r = _git_run(["add", "output/BilibiliHistory.xlsx"])
    if r is None or r.returncode != 0:
        return False
    r = _git_run(["diff", "--cached", "--quiet"])
    if r is None:
        return False
    if r.returncode == 0:
        print("无变更，无需提交")
        return True
    r = _git_run(["commit", "-m", "chore: update BilibiliHistory.xlsx"])
    if r is None or r.returncode != 0:
        return False
    print(">>> 上传到 GitHub...")
    r = _git_run(["push", "origin", "master"])
    if r is None or r.returncode != 0:
        if r and r.stderr:
            print(r.stderr.strip())
        return False
    print("上传成功")
    return True


def main():
    is_local = "GITHUB_ACTIONS" not in os.environ

    if is_local:
        print("=" * 40)
        print("  本地模式")
        print("=" * 40)
        print()
        if not git_pull():
            print("错误：无法连接到 GitHub，请检查网络连接")
            sys.exit(1)
        print()

    sessdata = os.environ.get("SESSDATA")
    if not sessdata:
        print("ERROR: SESSDATA not set")
        sys.exit(1)

    try:
        new_records = fetch_history(sessdata)
    except AuthError as e:
        print()
        print("=" * 60)
        print(f"B站API异常：{e}")
        print("=" * 60)
        print()
        print("可能是 SESSDATA 已失效，请重新设置：")
        print()
        print("如何获取新的 SESSDATA：")
        print("1. 打开浏览器，访问 https://www.bilibili.com 并登录")
        print("2. 按 F12 打开开发者工具")
        print("3. 切换到 Application (应用) 标签页")
        print("4. 在左侧找到 Cookies → https://www.bilibili.com")
        print("5. 找到名为 SESSDATA 的条目，复制其 Value")
        if is_local:
            print()
            print("设置方法：set SESSDATA=你的值")
        else:
            print()
            print("如何设置新的 SESSDATA：")
            print("1. 打开仓库 Settings → Secrets and variables → Actions")
            print("2. 找到 SESSDATA secret，点击 Update")
            print("3. 粘贴新的值，保存")
            print("4. 手动触发 workflow 重试")
        print()
        print("或者运行: python scripts/refresh_sessdata.py")
        print()
        sys.exit(1)

    existing_rows = load_existing_rows()
    new_rows = to_rows(new_records)

    if new_rows:
        all_rows = new_rows + existing_rows
        print(f"New: {len(new_rows)}, Total: {len(all_rows)}")
    else:
        all_rows = existing_rows
        print("No new records")

    write_excel(all_rows)

    if is_local:
        print()
        if not git_push():
            print()
            print("=" * 40)
            print("  警告：上传 GitHub 失败")
            print("  数据已保存在本地 output/BilibiliHistory.xlsx")
            print("  可手动提交推送，或稍后重新运行脚本")
            print("=" * 40)
        else:
            print(">>> 同步本地状态...")
            git_pull()
            print()
            print("=" * 40)
            print("  同步完成")
            print("=" * 40)


if __name__ == "__main__":
    main()
