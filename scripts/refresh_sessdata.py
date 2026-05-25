import os
import requests
import subprocess
import time
import json

QR_GENERATE = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

sess = requests.Session()


def get_qrcode():
    resp = sess.get(QR_GENERATE).json()
    if resp.get("code") != 0:
        print("Failed to get QR code:", resp)
        return None, None
    data = resp["data"]
    return data["url"], data["qrcode_key"]


def poll_login(qrcode_key):
    for _ in range(120):
        resp = sess.get(QR_POLL, params={"qrcode_key": qrcode_key}).json()
        code = resp.get("code")
        if code == 0:
            sessdata = None
            for c in sess.cookies:
                if c.name == "SESSDATA":
                    sessdata = c.value
                    break
            return sessdata
        elif code == 86038:
            print("QR code expired")
            return None
        elif code == 86090:
            pass
        time.sleep(2)
    return None


def update_github_secret(sessdata):
    try:
        subprocess.run(
            ["gh", "secret", "set", "SESSDATA", "--body", sessdata, "--repo", "gokairin/BiliBiliDataSync"],
            check=True,
        )
        print("GitHub Secret SESSDATA updated")
    except subprocess.CalledProcessError:
        print("Failed to update GitHub Secret. Ensure gh CLI is installed and authenticated.")
        print(f"SESSDATA={sessdata}")


if __name__ == "__main__":
    import urllib.parse

    url, key = get_qrcode()
    if not url:
        exit(1)

    print("Scan the QR code with Bilibili app to log in:")
    os.system(f"start {url}")

    sessdata = poll_login(key)
    if sessdata:
        print(f"SESSDATA obtained: {sessdata[:8]}...{sessdata[-4:]}")
        update_github_secret(sessdata)
    else:
        print("Login failed or expired")
