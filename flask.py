import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import json
import os

CONFIG_FILE = "poe2_auto_config_v73.json"


class Poe2AutoPotionV7_3:
    def __init__(self, root):
        self.root = root
        self.root.title("🧪 PoE2 自动喝药 v7.3（支持红/绿血条）")
        self.root.geometry("640x1050")
        self.root.resizable(False, False)

        # HP 设置
        self.hp_key = tk.StringVar(value="1")
        self.hp_threshold = tk.DoubleVar(value=35.0)
        self.disable_hp = tk.BooleanVar(value=False)
        self.enable_hp_timer = tk.BooleanVar(value=False)
        self.hp_timer_interval = tk.DoubleVar(value=5.0)
        self.last_hp_timer = 0

        # MP 设置
        self.mp_key = tk.StringVar(value="2")
        self.mp_threshold = tk.DoubleVar(value=35.0)
        self.disable_mp = tk.BooleanVar(value=False)
        self.enable_mp_timer = tk.BooleanVar(value=False)
        self.mp_timer_interval = tk.DoubleVar(value=8.0)
        self.last_mp_timer = 0

        # 全局设置
        self.check_interval = tk.DoubleVar(value=0.3)
        self.is_monitoring = False
        self.monitor_thread = None

        self.current_hp = tk.StringVar(value="--%")
        self.current_mp = tk.StringVar(value="--%")

        # 手动区域（直接存储为 (x, y, w, h)）
        self.hp_region = None
        self.mp_region = None

        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 手动选区按钮
        btn_frame1 = ttk.Frame(main_frame)
        btn_frame1.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame1, text="🩸 手动选血条（请框选一个竖条区域）", command=self.select_hp_region).pack(side=tk.LEFT)
        self.hp_region_label = ttk.Label(btn_frame1, text="未设置", foreground="red")
        self.hp_region_label.pack(side=tk.LEFT, padx=10)

        btn_frame2 = ttk.Frame(main_frame)
        btn_frame2.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame2, text="💧 手动选蓝条（请框选一个竖条区域）", command=self.select_mp_region).pack(side=tk.LEFT)
        self.mp_region_label = ttk.Label(btn_frame2, text="未设置", foreground="blue")
        self.mp_region_label.pack(side=tk.LEFT, padx=10)

        # 实时百分比显示
        pct_frame = ttk.Frame(main_frame)
        pct_frame.pack(fill=tk.X, pady=10)
        ttk.Label(pct_frame, text="血量:").pack(side=tk.LEFT)
        ttk.Label(pct_frame, textvariable=self.current_hp, font=("Arial", 10, "bold"), foreground="red").pack(side=tk.LEFT, padx=5)
        ttk.Label(pct_frame, text="蓝量:").pack(side=tk.LEFT, padx=(20, 0))
        ttk.Label(pct_frame, textvariable=self.current_mp, font=("Arial", 10, "bold"), foreground="blue").pack(side=tk.LEFT, padx=5)

        # HP 配置
        hp_frame = ttk.LabelFrame(main_frame, text="🩸 生命药水", padding=8)
        hp_frame.pack(fill=tk.X, pady=5)
        self.create_potion_ui(hp_frame, self.hp_key, self.hp_threshold,
                              self.disable_hp, self.enable_hp_timer, self.hp_timer_interval)

        # MP 配置
        mp_frame = ttk.LabelFrame(main_frame, text="💧 魔法药水", padding=8)
        mp_frame.pack(fill=tk.X, pady=5)
        self.create_potion_ui(mp_frame, self.mp_key, self.mp_threshold,
                              self.disable_mp, self.enable_mp_timer, self.mp_timer_interval)

        # 全局选项
        opt_frame = ttk.Frame(main_frame)
        opt_frame.pack(fill=tk.X, pady=10)
        ttk.Label(opt_frame, text="检测间隔(秒):").pack(side=tk.LEFT)
        ttk.Spinbox(opt_frame, from_=0.1, to=1.0, increment=0.1, textvariable=self.check_interval, width=6).pack(side=tk.LEFT, padx=5)

        io_frame = ttk.Frame(main_frame)
        io_frame.pack(fill=tk.X, pady=5)
        ttk.Button(io_frame, text="💾 导出配置", command=self.export_config).pack(side=tk.LEFT)
        ttk.Button(io_frame, text="📂 导入配置", command=self.import_config).pack(side=tk.LEFT, padx=10)

        # 控制按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始", command=self.start_monitoring, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止", command=self.stop_monitoring, state=tk.DISABLED, width=12)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 日志
        log_frame = ttk.LabelFrame(main_frame, text="📋 日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log("✅ PoE2 自动喝药 v7.3 启动（自动支持红/绿血条）")

    def create_potion_ui(self, parent, key_var, thresh_var, disable_var, timer_var, timer_interval_var):
        row1 = ttk.Frame(parent)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="按键:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=key_var, width=6).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="阈值(%):").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Spinbox(row1, from_=1, to=100, textvariable=thresh_var, width=6).pack(side=tk.LEFT, padx=5)

        row2 = ttk.Frame(parent)
        row2.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(row2, text="🚫 禁止喝此药", variable=disable_var).pack(side=tk.LEFT)
        ttk.Checkbutton(row2, text="⏱️ 定时喝药", variable=timer_var).pack(side=tk.LEFT, padx=(20, 0))
        ttk.Label(row2, text="每").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Spinbox(row2, from_=1, to=60, increment=0.5, textvariable=timer_interval_var, width=6).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="秒").pack(side=tk.LEFT)

    def log(self, msg):
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

    # ========== 手动选区 ==========
    def select_region_tk(self, title="选择区域"):
        try:
            screen_img = ImageGrab.grab()
            w, h = screen_img.size

            selector = tk.Toplevel(self.root)
            selector.title(title)
            selector.geometry(f"{w}x{h}+0+0")
            selector.overrideredirect(True)
            selector.attributes("-alpha", 0.3)
            selector.attributes("-topmost", True)

            canvas = tk.Canvas(selector, width=w, height=h, cursor="cross")
            canvas.pack()

            start_x = start_y = end_x = end_y = 0
            rect_id = None

            def on_press(event):
                nonlocal start_x, start_y
                start_x, start_y = event.x, event.y

            def on_drag(event):
                nonlocal rect_id, end_x, end_y
                end_x, end_y = event.x, event.y
                if rect_id:
                    canvas.delete(rect_id)
                rect_id = canvas.create_rectangle(start_x, start_y, end_x, end_y, outline="red", width=2)

            def on_release(event):
                x1, y1 = min(start_x, end_x), min(start_y, end_y)
                x2, y2 = max(start_x, end_x), max(start_y, end_y)
                selector.destroy()
                if x2 - x1 > 5 and y2 - y1 > 10:
                    self.selected_region = (x1, y1, x2 - x1, y2 - y1)
                else:
                    self.selected_region = None

            canvas.bind("<ButtonPress-1>", on_press)
            canvas.bind("<B1-Motion>", on_drag)
            canvas.bind("<ButtonRelease-1>", on_release)
            selector.wait_window()

            return getattr(self, 'selected_region', None)
        except Exception as e:
            self.log(f"❌ 选区失败: {e}")
            return None

    def select_hp_region(self):
        r = self.select_region_tk("请选择血条的竖条区域（窄而高）")
        if r:
            self.hp_region = r
            self.hp_region_label.config(text=f"({r[0]},{r[1]}) {r[2]}x{r[3]}")
            self.log("✅ 血条区域已设")

    def select_mp_region(self):
        r = self.select_region_tk("请选择蓝条的竖条区域（窄而高）")
        if r:
            self.mp_region = r
            self.mp_region_label.config(text=f"({r[0]},{r[1]}) {r[2]}x{r[3]}")
            self.log("✅ 蓝条区域已设")

    # ========== 核心：支持红+绿血条 ==========
    def calculate_percentage_from_strip(self, img):
        """
        自动检测红色或绿色血条，返回最高填充百分比。
        img: RGB 格式的 numpy 数组 (H, W, 3)
        """
        if img.size == 0 or img.shape[0] < 10 or img.shape[1] < 3:
            return None

        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        # 红色掩码
        lower_red1 = np.array([0, 70, 60])
        upper_red1 = np.array([20, 255, 255])
        lower_red2 = np.array([160, 70, 60])
        upper_red2 = np.array([180, 255, 255])
        mask_red = cv2.bitwise_or(
            cv2.inRange(hsv, lower_red1, upper_red1),
            cv2.inRange(hsv, lower_red2, upper_red2)
        )

        # 绿色掩码
        lower_green = np.array([40, 70, 60])
        upper_green = np.array([80, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)

        # 合并掩码（用于去噪）
        combined_mask = cv2.bitwise_or(mask_red, mask_green)

        kernel = np.ones((2, 2), np.uint8)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)

        h, w = combined_mask.shape
        colored_rows = np.where(np.any(combined_mask > 0, axis=1))[0]

        if len(colored_rows) == 0:
            return 0.0

        top_most_colored_row = np.min(colored_rows)
        filled_height = h - top_most_colored_row
        percentage = (filled_height / h) * 100
        return max(0.0, min(100.0, percentage))

    def is_valid_bar(self, img):
        """判断图像是否包含有效的红或绿血条"""
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        mask_red1 = cv2.inRange(hsv, np.array([0, 50, 40]), np.array([25, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([150, 50, 40]), np.array([180, 255, 255]))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)

        mask_green = cv2.inRange(hsv, np.array([40, 50, 40]), np.array([80, 255, 255]))

        combined = cv2.bitwise_or(mask_red, mask_green)
        total = combined.size
        colored = cv2.countNonZero(combined)
        return (colored / total) > 0.1

    # ========== 主监控循环 ==========
    def monitor_loop(self):
        while self.is_monitoring:
            try:
                current_hp_val = None
                current_mp_val = None
                now = time.time()

                screen = np.array(ImageGrab.grab())

                # HP（自动支持红/绿）
                if self.hp_region:
                    x, y, w, h = self.hp_region
                    if x + w <= screen.shape[1] and y + h <= screen.shape[0]:
                        hp_img = screen[y:y + h, x:x + w]
                        if self.is_valid_bar(hp_img):
                            current_hp_val = self.calculate_percentage_from_strip(hp_img)
                            self.current_hp.set(f"{current_hp_val:.1f}%")
                        else:
                            self.current_hp.set("--%")
                            current_hp_val = None
                    else:
                        self.current_hp.set("--%")
                else:
                    self.current_hp.set("--%")

                # MP（仅蓝色）
                if self.mp_region:
                    x, y, w, h = self.mp_region
                    if x + w <= screen.shape[1] and y + h <= screen.shape[0]:
                        mp_img = screen[y:y + h, x:x + w]
                        if self.is_valid_bar_blue(mp_img):
                            current_mp_val = self.calculate_percentage_from_strip_blue(mp_img)
                            self.current_mp.set(f"{current_mp_val:.1f}%")
                        else:
                            self.current_mp.set("--%")
                            current_mp_val = None
                    else:
                        self.current_mp.set("--%")
                else:
                    self.current_mp.set("--%")

                # 喝药逻辑
                if current_hp_val is not None and not self.disable_hp.get() and current_hp_val < self.hp_threshold.get():
                    pyautogui.press(self.hp_key.get())
                    self.log(f"🩸 HP {current_hp_val:.1f}% → 按 '{self.hp_key.get()}'")

                if current_mp_val is not None and not self.disable_mp.get() and current_mp_val < self.mp_threshold.get():
                    pyautogui.press(self.mp_key.get())
                    self.log(f"💧 MP {current_mp_val:.1f}% → 按 '{self.mp_key.get()}'")

                # 定时喝药
                if current_hp_val is not None and not self.disable_hp.get() and self.enable_hp_timer.get():
                    if now - self.last_hp_timer >= self.hp_timer_interval.get():
                        pyautogui.press(self.hp_key.get())
                        self.log(f"⏱️ 定时喝 HP（每 {self.hp_timer_interval.get()}s）")
                        self.last_hp_timer = now

                if current_mp_val is not None and not self.disable_mp.get() and self.enable_mp_timer.get():
                    if now - self.last_mp_timer >= self.mp_timer_interval.get():
                        pyautogui.press(self.mp_key.get())
                        self.log(f"⏱️ 定时喝 MP（每 {self.mp_timer_interval.get()}s）")
                        self.last_mp_timer = now

                time.sleep(self.check_interval.get())

            except Exception as e:
                self.log(f"⚠️ 异常: {e}")
                time.sleep(1)

    # 蓝条专用函数（保持原逻辑）
    def calculate_percentage_from_strip_blue(self, img):
        if img.size == 0 or img.shape[0] < 10 or img.shape[1] < 3:
            return None
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        lower = np.array([90, 70, 60])
        upper = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        h, w = mask.shape
        colored_rows = np.where(np.any(mask > 0, axis=1))[0]
        if len(colored_rows) == 0:
            return 0.0
        top_most = np.min(colored_rows)
        filled = h - top_most
        return max(0.0, min(100.0, (filled / h) * 100))

    def is_valid_bar_blue(self, img):
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, np.array([80, 50, 40]), np.array([150, 255, 255]))
        total = mask.size
        colored = cv2.countNonZero(mask)
        return (colored / total) > 0.1

    def start_monitoring(self):
        if not self.hp_region and not self.mp_region:
            messagebox.showwarning("警告", "请先设置血条或蓝条区域！")
            return
        self.is_monitoring = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("▶ 开始监控")
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.is_monitoring = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.current_hp.set("--%")
        self.current_mp.set("--%")
        self.log("⏹ 已停止")

    # ========== 配置管理 ==========
    def get_config(self):
        return {
            "hp_region": self.hp_region,
            "mp_region": self.mp_region,
            "hp_key": self.hp_key.get(),
            "hp_threshold": self.hp_threshold.get(),
            "disable_hp": self.disable_hp.get(),
            "enable_hp_timer": self.enable_hp_timer.get(),
            "hp_timer_interval": self.hp_timer_interval.get(),

            "mp_key": self.mp_key.get(),
            "mp_threshold": self.mp_threshold.get(),
            "disable_mp": self.disable_mp.get(),
            "enable_mp_timer": self.enable_mp_timer.get(),
            "mp_timer_interval": self.mp_timer_interval.get(),

            "check_interval": self.check_interval.get(),
        }

    def set_config(self, cfg):
        self.hp_region = cfg.get("hp_region")
        self.mp_region = cfg.get("mp_region")
        self.hp_key.set(cfg.get("hp_key", "1"))
        self.hp_threshold.set(cfg.get("hp_threshold", 35.0))
        self.disable_hp.set(cfg.get("disable_hp", False))
        self.enable_hp_timer.set(cfg.get("enable_hp_timer", False))
        self.hp_timer_interval.set(cfg.get("hp_timer_interval", 5.0))

        self.mp_key.set(cfg.get("mp_key", "2"))
        self.mp_threshold.set(cfg.get("mp_threshold", 35.0))
        self.disable_mp.set(cfg.get("disable_mp", False))
        self.enable_mp_timer.set(cfg.get("enable_mp_timer", False))
        self.mp_timer_interval.set(cfg.get("mp_timer_interval", 8.0))

        self.check_interval.set(cfg.get("check_interval", 0.3))

        if self.hp_region:
            x, y, w, h = self.hp_region
            self.hp_region_label.config(text=f"({x},{y}) {w}x{h}")
        if self.mp_region:
            x, y, w, h = self.mp_region
            self.mp_region_label.config(text=f"({x},{y}) {w}x{h}")

    def export_config(self):
        cfg = self.get_config()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="poe2_v73_config.json"
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            self.log(f"💾 配置已导出: {os.path.basename(file_path)}")

    def import_config(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.set_config(cfg)
                self.log(f"📂 配置已导入: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.set_config(cfg)
            except:
                pass

    def save_config_on_exit(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.get_config(), f, indent=4, ensure_ascii=False)
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.save_config_on_exit)
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = Poe2AutoPotionV7_3(root)
    app.run()


if __name__ == "__main__":
    main()