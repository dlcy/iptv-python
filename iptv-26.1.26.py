import os
import sys
import urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import datetime
import ntplib
import vlc
import requests
import re
import time
from datetime import timezone
import json
import random

class IPTVPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows IPTV播放器 - 专业全屏版")
        self.root.geometry("1000x700")

        # ========= 新增：统一 User-Agent（唯一新增变量） =========
        self.user_agent = (
            "Mozilla/5.0 (Linux; Android 9; IPTV) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/88.0.4324.93 Safari/537.36"
        )

        self.channel_list = []
        self.server_list = []
        self.current_server = ""
        self.ntp_offset = 0
        self.is_playing = False
        self.current_channel = None
        self.fullscreen_window = None
        self.fullscreen_canvas = None
        self.current_media = None
        self.current_channel_template = ""
        self.current_channel_name = ""

        self.ntp_config_file = "ntp_config.json"
        self.server_config_file = "server_config.json"
        self.channel_config_file = "channel_config.json"

        self.ntp_servers = [
            "124.232.139.1",
            "ntp.ntsc.ac.cn",
            "cn.ntp.org.cn",
            "time.windows.com",
            "pool.ntp.org"
        ]
        self.current_ntp_server = self.ntp_servers[0]

        self.create_widgets()
        self.load_server_config()
        self.load_channel_config()

        if not self.channel_list:
            self.load_demo_data()

        self.sync_time()

    # --------------------------------------------------

    def check_server_available(self, url):
        try:
            parsed = urllib.parse.urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            headers = {"User-Agent": self.user_agent}

            r = requests.head(base_url, headers=headers, timeout=3)
            return r.status_code == 200
        except:
            try:
                r = requests.get(base_url, headers=headers, timeout=3, stream=True)
                return r.status_code == 200
            except:
                return False

    # --------------------------------------------------

    def create_widgets(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.left_panel = ttk.Frame(self.main_frame, width=250)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)

        self.right_panel = ttk.Frame(self.main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.play_btn = ttk.Button(self.left_panel, text="播放", command=self.play_channel)
        self.play_btn.pack(fill=tk.X, pady=5)

        self.stop_btn = ttk.Button(self.left_panel, text="停止", command=self.stop_playback)
        self.stop_btn.pack(fill=tk.X, pady=5)

        self.fullscreen_btn = ttk.Button(self.left_panel, text="全屏", command=self.enter_fullscreen)
        self.fullscreen_btn.pack(fill=tk.X, pady=5)

        self.channel_tree = ttk.Treeview(
            self.right_panel, columns=("name", "url"), show="headings"
        )
        self.channel_tree.heading("name", text="频道名称")
        self.channel_tree.heading("url", text="播放地址")
        self.channel_tree.pack(fill=tk.BOTH, expand=True)
        self.channel_tree.bind("<<TreeviewSelect>>", self.on_channel_select)

        self.instance = vlc.Instance("--no-xlib")
        self.media_player = self.instance.media_player_new()

        self.canvas = tk.Canvas(self.right_panel, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        if sys.platform == "win32":
            self.media_player.set_hwnd(self.canvas.winfo_id())
        else:
            self.media_player.set_xwindow(self.canvas.winfo_id())

    # --------------------------------------------------

    def play_channel(self):
        if not self.current_channel:
            return

        index = self.channel_tree.index(self.channel_tree.selection()[0])
        info = self.channel_list[index]

        self.current_channel_template = info["url"]
        play_url = self.generate_play_url(info["url"])

        media = self.instance.media_new(play_url)

        # ========= 新增：VLC 注入 User-Agent =========
        media.add_option(f":http-user-agent={self.user_agent}")

        media.add_option(":network-caching=300")
        media.add_option(":clock-jitter=0")
        media.add_option(":clock-synchro=0")

        self.media_player.set_media(media)
        self.media_player.play()

        self.current_media = media
        self.is_playing = True

    # --------------------------------------------------

    def enter_fullscreen(self):
        if not self.is_playing:
            return

        self.media_player.stop()

        self.fullscreen_window = tk.Toplevel(self.root)
        self.fullscreen_window.attributes("-fullscreen", True)
        self.fullscreen_canvas = tk.Canvas(self.fullscreen_window, bg="black")
        self.fullscreen_canvas.pack(fill=tk.BOTH, expand=True)

        if sys.platform == "win32":
            self.media_player.set_hwnd(self.fullscreen_canvas.winfo_id())
        else:
            self.media_player.set_xwindow(self.fullscreen_canvas.winfo_id())

        play_url = self.generate_play_url(self.current_channel_template)
        media = self.instance.media_new(play_url)

        # ========= 新增：VLC 注入 User-Agent =========
        media.add_option(f":http-user-agent={self.user_agent}")

        media.add_option(":network-caching=300")
        self.media_player.set_media(media)
        self.media_player.play()

    # --------------------------------------------------

    def stop_playback(self):
        self.media_player.stop()
        self.is_playing = False

    # --------------------------------------------------

    def generate_play_url(self, template_url):
        ts = datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.00Z")

        if "{server}" in template_url and self.server_list:
            template_url = template_url.replace(
                "{server}", random.choice(self.server_list)
            )

        return template_url.replace("{timestamp}", ts)

    # --------------------------------------------------

    def on_channel_select(self, event):
        sel = self.channel_tree.selection()
        if sel:
            self.current_channel = sel[0]

    # --------------------------------------------------

    def load_demo_data(self):
        self.server_list = ["192.168.99.1:7088"]
        demo = [
            ("测试频道", "http://{server}/udp/239.76.253.151:9000")
        ]
        for n, u in demo:
            self.channel_list.append({"name": n, "url": u})
            self.channel_tree.insert("", "end", values=(n, u))

    # --------------------------------------------------

    def load_server_config(self): pass
    def load_channel_config(self): pass
    def sync_time(self): pass

# ======================================================

def main():
    root = tk.Tk()
    app = IPTVPlayer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
