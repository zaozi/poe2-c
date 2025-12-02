
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab, Image, ImageTk
import json
import os
import sys

# 导入keyboard和pynput库，如果不存在则提示安装
try:
    import keyboard
except ImportError:
    print("❌ 请安装 keyboard: pip install keyboard")
    keyboard = None

try:
    from pynput import mouse
except ImportError:
    print("⚠️ 建议安装 pynput: pip install pynput")
    mouse = None

class CombinedApp:
    def __init__(self, root):
        self.root = root
        self.root.title("多功能工具集成")
        self.root.geometry("900x700")

        # 创建主框架和选项卡
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 创建各个功能选项卡
        self.create_flask_tab()
        self.create_equipment_tab()

    def create_flask_tab(self):
        """创建flask功能选项卡"""
        self.flask_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.flask_tab, text="自动喝药")

        # 初始化flask相关的变量
        self.hp_key = tk.StringVar(value="1")
        self.hp_threshold = tk.DoubleVar(value=35.0)
        self.disable_hp = tk.BooleanVar(value=False)
        self.enable_hp_timer = tk.BooleanVar(value=False)
        self.hp_timer_interval = tk.DoubleVar(value=5.0)
        self.last_hp_timer = 0

        self.mp_key = tk.StringVar(value="2")
        self.mp_threshold = tk.DoubleVar(value=35.0)
        self.disable_mp = tk.BooleanVar(value=False)
        self.enable_mp_timer = tk.BooleanVar(value=False)
        self.mp_timer_interval = tk.DoubleVar(value=8.0)
        self.last_mp_timer = 0

        self.check_interval = tk.DoubleVar(value=0.3)
        self.is_monitoring = False
        self.monitor_thread = None

        self.current_hp = tk.StringVar(value="--%")
        self.current_mp = tk.StringVar(value="--%")

        self.hp_region = None
        self.mp_region = None

        # 创建flask界面
        flask_frame = ttk.Frame(self.flask_tab, padding="10")
        flask_frame.pack(fill=tk.BOTH, expand=True)

        # 手动选区按钮
        btn_frame1 = ttk.Frame(flask_frame)
        btn_frame1.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame1, text="🩸 手动选血条（请框选一个竖条区域）", command=self.select_hp_region).pack(side=tk.LEFT)
        self.hp_region_label = ttk.Label(btn_frame1, text="未设置", foreground="red")
        self.hp_region_label.pack(side=tk.LEFT, padx=10)

        btn_frame2 = ttk.Frame(flask_frame)
        btn_frame2.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame2, text="💧 手动选蓝条（请框选一个竖条区域）", command=self.select_mp_region).pack(side=tk.LEFT)
        self.mp_region_label = ttk.Label(btn_frame2, text="未设置", foreground="blue")
        self.mp_region_label.pack(side=tk.LEFT, padx=10)

        # 实时百分比显示
        pct_frame = ttk.Frame(flask_frame)
        pct_frame.pack(fill=tk.X, pady=10)
        ttk.Label(pct_frame, text="血量:").pack(side=tk.LEFT)
        ttk.Label(pct_frame, textvariable=self.current_hp, font=("Arial", 10, "bold"), foreground="red").pack(side=tk.LEFT, padx=5)
        ttk.Label(pct_frame, text="蓝量:").pack(side=tk.LEFT, padx=(20, 0))
        ttk.Label(pct_frame, textvariable=self.current_mp, font=("Arial", 10, "bold"), foreground="blue").pack(side=tk.LEFT, padx=5)

        # HP 配置
        hp_frame = ttk.LabelFrame(flask_frame, text="🩸 生命药水", padding=8)
        hp_frame.pack(fill=tk.X, pady=5)
        self.create_potion_ui(hp_frame, self.hp_key, self.hp_threshold,
                              self.disable_hp, self.enable_hp_timer, self.hp_timer_interval)

        # MP 配置
        mp_frame = ttk.LabelFrame(flask_frame, text="💧 魔法药水", padding=8)
        mp_frame.pack(fill=tk.X, pady=5)
        self.create_potion_ui(mp_frame, self.mp_key, self.mp_threshold,
                              self.disable_mp, self.enable_mp_timer, self.mp_timer_interval)

        # 全局选项
        opt_frame = ttk.Frame(flask_frame)
        opt_frame.pack(fill=tk.X, pady=10)
        ttk.Label(opt_frame, text="检测间隔(秒):").pack(side=tk.LEFT)
        ttk.Spinbox(opt_frame, from_=0.1, to=1.0, increment=0.1, textvariable=self.check_interval, width=6).pack(side=tk.LEFT, padx=5)

        io_frame = ttk.Frame(flask_frame)
        io_frame.pack(fill=tk.X, pady=5)
        ttk.Button(io_frame, text="💾 导出配置", command=self.export_config).pack(side=tk.LEFT)
        ttk.Button(io_frame, text="📂 导入配置", command=self.import_config).pack(side=tk.LEFT, padx=10)

        # 控制按钮
        btn_frame = ttk.Frame(flask_frame)
        btn_frame.pack(pady=15)
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始", command=self.start_monitoring, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止", command=self.stop_monitoring, state=tk.DISABLED, width=12)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 日志
        log_frame = ttk.LabelFrame(flask_frame, text="📋 日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log("✅ PoE2 自动喝药 v7.3 启动（纯手动竖条识别，精准支持 0%~100%）")

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

    def create_equipment_tab(self):
        """创建cEquipment功能选项卡"""
        self.equipment_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.equipment_tab, text="装备洗练")

        # 创建二级选项卡
        self.equipment_notebook = ttk.Notebook(self.equipment_tab)
        self.equipment_notebook.pack(fill=tk.BOTH, expand=True)

        # 创建主洗练功能
        self.create_turbo_reforge_tab()
        # 创建weizhi功能作为子功能
        self.create_weizhi_tab()

    def create_turbo_reforge_tab(self):
        """创建主洗练功能选项卡"""
        self.turbo_tab = ttk.Frame(self.equipment_notebook)
        self.equipment_notebook.add(self.turbo_tab, text="极速洗练")

        # 初始化cEquipment相关的变量
        self.main_template_paths = []
        self.tier_template_path = None

        self.orb_pos = tk.StringVar(value="(?, ?)")
        self.equip_pos = tk.StringVar(value="(?, ?)")
        self.mod_region = tk.StringVar(value="(?, ?, ?, ?)")
        self.main_threshold = tk.DoubleVar(value=0.85)
        self.tier_threshold = tk.DoubleVar(value=0.90)
        self.max_attempts = tk.IntVar(value=200)

        self.delay_vars = {
            "orb_delay": tk.DoubleVar(value=0.25),
            "equip_click_delay": tk.DoubleVar(value=0.75),
            "alt_screenshot_delay": tk.DoubleVar(value=0.0),
            "loop_random_max": tk.DoubleVar(value=0.02),
        }

        # 创建cEquipment界面
        frame = ttk.Frame(self.turbo_tab, padding="12")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        coords = [("洗练石:", self.orb_pos, "orb"), ("装备:", self.equip_pos, "equip"), ("属性区域:", self.mod_region, "mod")]
        for i, (label, var, key) in enumerate(coords):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            ttk.Entry(frame, textvariable=var, width=25, state='readonly').grid(row=i, column=1, padx=5)
            btn_text = "拾取" if key != "mod" else "拖选"
            ttk.Button(frame, text=btn_text, command=lambda k=key: self.pick_coordinate(k)).grid(row=i, column=2)

        # 主词条模板
        ttk.Label(frame, text="主词条模板 (PNG):").grid(row=3, column=0, sticky=tk.W, pady=(10,5))
        self.listbox_main = tk.Listbox(frame, height=4, width=65)
        self.listbox_main.grid(row=4, column=0, columnspan=3, pady=5)
        btn_f1 = ttk.Frame(frame)
        btn_f1.grid(row=5, column=0, columnspan=3, pady=5, sticky=tk.W)
        ttk.Button(btn_f1, text="添加", command=self.add_main_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f1, text="移除", command=self.remove_main_template).pack(side=tk.LEFT, padx=5)

        # T阶模板
        ttk.Label(frame, text="T阶图标模板 (PNG):").grid(row=6, column=0, sticky=tk.W, pady=(10,5))
        self.tier_entry = ttk.Entry(frame, width=50, state='readonly')
        self.tier_entry.grid(row=7, column=0, columnspan=2, padx=5, pady=5)
        ttk.Button(frame, text="选择", command=self.select_tier_template).grid(row=7, column=2)

        # 阈值
        ttk.Label(frame, text="主词条阈值:").grid(row=8, column=0, sticky=tk.W, pady=5)
        ttk.Scale(frame, from_=0.70, to=0.95, variable=self.main_threshold, orient=tk.HORIZONTAL).grid(row=8, column=1, sticky=(tk.W, tk.E))
        ttk.Label(frame, textvariable=self.main_threshold, width=6).grid(row=8, column=2)

        ttk.Label(frame, text="T阶图标阈值:").grid(row=9, column=0, sticky=tk.W, pady=5)
        ttk.Scale(frame, from_=0.80, to=0.98, variable=self.tier_threshold, orient=tk.HORIZONTAL).grid(row=9, column=1, sticky=(tk.W, tk.E))
        ttk.Label(frame, textvariable=self.tier_threshold, width=6).grid(row=9, column=2)

        # 最大尝试
        ttk.Label(frame, text="最大尝试:").grid(row=10, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.max_attempts, width=10).grid(row=10, column=1, sticky=tk.W)

        # 延迟
        ttk.Label(frame, text="⏱️ 延迟 (秒):", foreground="blue").grid(row=11, column=0, sticky=tk.W, pady=(10,5))
        delay_items = [
            ("洗练石后:", "orb_delay"),
            ("装备点击后:", "equip_click_delay"),
            ("Alt截图延迟:", "alt_screenshot_delay"),
            ("循环间隔上限:", "loop_random_max"),
        ]
        row = 12
        for label, key in delay_items:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            ttk.Entry(frame, textvariable=self.delay_vars[key], width=8).grid(row=row, column=1, sticky=tk.W)
            row += 1

        self.start_btn = ttk.Button(
            frame,
            text="🚀 开始极速洗练（主词条+T阶图标匹配）",
            command=self.start_reforge
        )
        self.start_btn.grid(row=row, column=0, columnspan=3, pady=20, ipadx=15, ipady=6)

    def create_weizhi_tab(self):
        """创建weizhi功能选项卡"""
        self.weizhi_tab = ttk.Frame(self.equipment_notebook)
        self.equipment_notebook.add(self.weizhi_tab, text="匹配测试")

        # 初始化weizhi相关的变量
        self.screenshot_path = None
        self.template_main_path = None      # 主词条模板
        self.template_tier_path = None      # T阶图标模板（如 t1.png）
        self.screenshot_img = None          # 原始 BGR
        self.template_main_img = None       # 原始 BGR
        self.template_tier_img = None       # 原始 BGR

        # 阈值变量
        self.main_thresh = tk.DoubleVar(value=0.85)
        self.tier_thresh = tk.DoubleVar(value=0.90)

        # 创建weizhi界面
        # === 控制区 ===
        control_frame = ttk.Frame(self.weizhi_tab, padding="10")
        control_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(control_frame, text="选择截图", command=self.load_screenshot).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="选择主词条模板", command=self.load_template_main).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="选择T阶图标模板", command=self.load_template_tier).pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="主词条阈值:").pack(side=tk.LEFT, padx=(20,5))
        ttk.Scale(control_frame, from_=0.7, to=0.98, variable=self.main_thresh, orient=tk.HORIZONTAL, length=120).pack(side=tk.LEFT)
        ttk.Label(control_frame, textvariable=self.main_thresh, width=5).pack(side=tk.LEFT, padx=(5,15))

        ttk.Label(control_frame, text="T阶图标阈值:").pack(side=tk.LEFT)
        ttk.Scale(control_frame, from_=0.8, to=0.99, variable=self.tier_thresh, orient=tk.HORIZONTAL, length=120).pack(side=tk.LEFT)
        ttk.Label(control_frame, textvariable=self.tier_thresh, width=5).pack(side=tk.LEFT, padx=(5,15))

        ttk.Button(control_frame, text="🔍 开始匹配", command=self.run_matching).pack(side=tk.LEFT, padx=(20,0))

        # === 日志区 ===
        self.result_text = tk.Text(self.weizhi_tab, height=4, state='disabled', bg='#f0f0f0')
        self.result_text.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0,10))

        # === 三视图区 ===
        paned = ttk.PanedWindow(self.weizhi_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frame1 = ttk.LabelFrame(paned, text="1. 原始图像")
        paned.add(frame1, weight=1)
        self.canvas_orig_screen = tk.Canvas(frame1, bg='white')
        self.canvas_orig_screen.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas_orig_main = tk.Canvas(frame1, bg='lightgray', height=60)
        self.canvas_orig_main.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,2))
        self.canvas_orig_tier = tk.Canvas(frame1, bg='lightblue', height=40)
        self.canvas_orig_tier.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5))

        frame2 = ttk.LabelFrame(paned, text="2. 预处理图像（二值化）")
        paned.add(frame2, weight=1)
        self.canvas_proc_screen = tk.Canvas(frame2, bg='white')
        self.canvas_proc_screen.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas_proc_main = tk.Canvas(frame2, bg='lightgray', height=60)
        self.canvas_proc_main.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,2))
        self.canvas_proc_tier = tk.Canvas(frame2, bg='lightblue', height=40)
        self.canvas_proc_tier.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0,5))

        frame3 = ttk.LabelFrame(paned, text="3. 匹配结果（绿框=主词条，蓝框=T阶图标）")
        paned.add(frame3, weight=1)
        self.canvas_result = tk.Canvas(frame3, bg='white')
        self.canvas_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # === Flask功能相关方法 ===
    def log(self, msg):
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

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
                if x2 - x1 > 5 and y2 - y1 > 10:  # 至少高一点
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

    def calculate_percentage_from_strip(self, img, color='red'):
        """
        适用于 PoE2：资源条从底部向上填充（0% = 无色，100% = 全满）
        img: RGB 格式的 numpy 数组 (H, W, 3)
        """
        if img.size == 0 or img.shape[0] < 10 or img.shape[1] < 3:
            return None

        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        if color == 'red':
            # 宽松红：覆盖 PoE2 暗红、亮红
            lower1 = np.array([0, 70, 60])
            upper1 = np.array([20, 255, 255])
            lower2 = np.array([160, 70, 60])
            upper2 = np.array([180, 255, 255])
            mask = cv2.bitwise_or(
                cv2.inRange(hsv, lower1, upper1),
                cv2.inRange(hsv, lower2, upper2)
            )
        else:  # blue
            lower = np.array([90, 70, 60])
            upper = np.array([140, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)

        # 去噪（可选，避免闪烁）
        kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        h, w = mask.shape
        colored_rows = np.where(np.any(mask > 0, axis=1))[0]

        if len(colored_rows) == 0:
            return 0.0

        # ✅ 关键修正：找最顶部的有色行（最小 y）
        top_most_colored_row = np.min(colored_rows)  # y 值最小，位置最高
        filled_height = h - top_most_colored_row  # 从该行到底部的高度
        percentage = (filled_height / h) * 100

        return max(0.0, min(100.0, percentage))

    def is_valid_bar(self, img, color='red'):
        """
        判断给定的图像是否包含足够的有效颜色区域
        :param img: 输入的RGB图像
        :param color: 需要判断的颜色类型 ('red' 或 'blue')
        :return: True 表示有效；False 表示无效
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        if color == 'red':
            lower1 = np.array([0, 50, 40])
            upper1 = np.array([25, 255, 255])
            lower2 = np.array([150, 50, 40])
            upper2 = np.array([180, 255, 255])
            mask = cv2.bitwise_or(
                cv2.inRange(hsv, lower1, upper1),
                cv2.inRange(hsv, lower2, upper2)
            )
        else:  # blue
            lower = np.array([80, 50, 40])
            upper = np.array([150, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)

        total_pixels = mask.size
        colored_pixels = cv2.countNonZero(mask)

        # 如果有效颜色像素占比低于一定比例（如10%），则认为不是有效的血条/蓝条区域
        return (colored_pixels / total_pixels) > 0.1

    def monitor_loop(self):
        while self.is_monitoring:
            try:
                current_hp_val = None
                current_mp_val = None
                now = time.time()

                screen = np.array(ImageGrab.grab())

                # HP
                if self.hp_region:
                    x, y, w, h = self.hp_region
                    if x + w <= screen.shape[1] and y + h <= screen.shape[0]:
                        hp_img = screen[y:y + h, x:x + w]
                        current_hp_val = self.calculate_percentage_from_strip(hp_img, 'red')

                        # 增加前置检查
                        if not self.is_valid_bar(hp_img, 'red'):
                            self.current_hp.set("--%")
                            current_hp_val = None  # 标记为无效状态
                        else:
                            self.current_hp.set(f"{current_hp_val:.1f}%" if current_hp_val is not None else "??%")
                    else:
                        self.current_hp.set("--%")
                else:
                    self.current_hp.set("--%")

                # MP
                if self.mp_region:
                    x, y, w, h = self.mp_region
                    if x + w <= screen.shape[1] and y + h <= screen.shape[0]:
                        mp_img = screen[y:y + h, x:x + w]
                        current_mp_val = self.calculate_percentage_from_strip(mp_img, 'blue')

                        # 增加前置检查
                        if not self.is_valid_bar(mp_img, 'blue'):
                            self.current_mp.set("--%")
                            current_mp_val = None  # 标记为无效状态
                        else:
                            self.current_mp.set(f"{current_mp_val:.1f}%" if current_mp_val is not None else "??%")
                    else:
                        self.current_mp.set("--%")
                else:
                    self.current_mp.set("--%")

                # 只有在识别到有效血条/蓝条时才进行喝药逻辑
                if current_hp_val is not None:
                    if not self.disable_hp.get() and current_hp_val < self.hp_threshold.get():
                        pyautogui.press(self.hp_key.get())
                        self.log(f"🩸 HP {current_hp_val:.1f}% → 按 '{self.hp_key.get()}'")

                if current_mp_val is not None:
                    if not self.disable_mp.get() and current_mp_val < self.mp_threshold.get():
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

        # 更新 UI 显示
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

    # === cEquipment功能相关方法 ===
    def pick_coordinate(self, target_type):
        if target_type == "mod":
            region = self.select_region_by_drag(self.root)
            self.mod_region.set(f"({region[0]}, {region[1]}, {region[2]}, {region[3]})")
            return

        messagebox.showinfo("拾取", f"将鼠标移到{target_type}上，单击左键。", parent=self.root)
        clicked = False
        def on_click(x, y, button, pressed):
            nonlocal clicked
            if pressed and button.name == 'left':
                clicked = True
                return False
        try:
            with mouse.Listener(on_click=on_click):
                while not clicked:
                    time.sleep(0.01)
        except:
            time.sleep(1.5)
        x, y = pyautogui.position()
        var = self.orb_pos if target_type == "orb" else self.equip_pos
        var.set(f"({x}, {y})")

    def select_region_by_drag(self, parent):
        selector = tk.Toplevel(parent)
        selector.attributes('-fullscreen', True, '-topmost', True, '-alpha', 0.3)
        selector.overrideredirect(True)
        canvas = tk.Canvas(selector, bg='black', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        start_x = start_y = rect_id = None
        selected_region = None
        done = False

        def on_mouse_down(e):
            nonlocal start_x, start_y
            start_x, start_y = e.x, e.y

        def on_mouse_move(e):
            nonlocal rect_id
            if start_x is None:
                return
            if rect_id:
                canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(start_x, start_y, e.x, e.y, outline='cyan', width=2, dash=(5,5))

        def on_mouse_up(e):
            nonlocal selected_region, done
            if start_x is None:
                selector.destroy()
                return
            x = min(start_x, e.x)
            y = min(start_y, e.y)
            w, h = abs(e.x - start_x), abs(e.y - start_y)
            if w < 10 or h < 10:
                messagebox.showwarning("区域太小", "请选择至少 10×10 像素！", parent=selector)
                return
            selected_region = (x, y, w, h)
            done = True
            selector.destroy()

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_move)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        messagebox.showinfo("区域选择", "拖动选择属性窗口（青色虚线框）", parent=parent)
        while not done and selector.winfo_exists():
            parent.update()
            time.sleep(0.02)
        if selected_region is None:
            raise RuntimeError("用户取消")
        return selected_region

    def add_main_template(self):
        files = filedialog.askopenfilenames(filetypes=[("PNG", "*.png")])
        for f in files:
            if f not in self.main_template_paths:
                self.main_template_paths.append(f)
                self.listbox_main.insert(tk.END, f)

    def remove_main_template(self):
        sel = self.listbox_main.curselection()
        if sel:
            del self.main_template_paths[sel[0]]
            self.listbox_main.delete(sel[0])

    def select_tier_template(self):
        file = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if file:
            self.tier_template_path = file
            self.tier_entry.config(state='normal')
            self.tier_entry.delete(0, tk.END)
            self.tier_entry.insert(0, file)
            self.tier_entry.config(state='readonly')

    def parse_tuple(self, s):
        parts = [int(x.strip()) for x in s.strip("() ").split(",") if x.strip()]
        return tuple(parts)

    def preprocess_image(self, img):
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def load_and_preprocess_template(self, path):
        template = cv2.imread(path, cv2.IMREAD_COLOR)
        if template is None:
            raise ValueError(f"无法加载模板: {path}")
        return self.preprocess_image(template)

    def match_main_and_get_template(self, screen_gray, templates_with_path, threshold, attempt_num):
        print(f"\n🔄 第 {attempt_num} 次洗练 - 主词条匹配:")
        best_score = -1
        best_template = None
        best_path = None
        best_loc = None
        for path, template in templates_with_path:
            h_tpl, w_tpl = template.shape[:2]
            h_scr, w_scr = screen_gray.shape
            if h_tpl > h_scr or w_tpl > w_scr:
                print(f" ❌ 模板 {os.path.basename(path)}: 尺寸过大（跳过）")
                continue
            res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            status = "✅" if max_val >= threshold else "❌"
            print(f" 🔍 {os.path.basename(path)}: 得分={max_val:.4f} → {status}")
            if max_val >= threshold and max_val > best_score:
                best_score = max_val
                best_template = template
                best_path = path
                best_loc = max_loc
        if best_template is not None:
            print(f" 🎯 主词条匹配成功！模板: {os.path.basename(best_path)} | 得分={best_score:.4f} | 位置={best_loc}")
            return True, best_template, best_path, best_loc, best_score
        return False, None, None, None, -1

    def start_reforge(self):
        if not self.main_template_paths:
            messagebox.showwarning("错误", "请添加主词条模板！", parent=self.root)
            return
        if not self.tier_template_path:
            messagebox.showwarning("错误", "请选择T阶图标模板！", parent=self.root)
            return

        try:
            orb_pos = self.parse_tuple(self.orb_pos.get())
            equip_pos = self.parse_tuple(self.equip_pos.get())
            mod_region = self.parse_tuple(self.mod_region.get())
            if len(orb_pos) != 2 or len(equip_pos) != 2 or len(mod_region) != 4:
                raise ValueError("坐标格式错误")

            config = {
                "REFORGE_ORB_POS": orb_pos,
                "TARGET_EQUIP_POS": equip_pos,
                "MOD_DISPLAY_REGION": mod_region,
                "MAIN_THRESHOLD": self.main_threshold.get(),
                "TIER_THRESHOLD": self.tier_threshold.get(),
                "MAX_ATTEMPTS": self.max_attempts.get(),
                "ORB_DELAY": self.delay_vars["orb_delay"].get(),
                "EQUIP_CLICK_DELAY": self.delay_vars["equip_click_delay"].get(),
                "ALT_SCREENSHOT_DELAY": self.delay_vars["alt_screenshot_delay"].get(),
                "LOOP_RANDOM_MAX": self.delay_vars["loop_random_max"].get(),
                "MAIN_TEMPLATE_PATHS": self.main_template_paths.copy(),
                "TIER_TEMPLATE_PATH": self.tier_template_path,
            }

            # 保存配置
            config_file = "config_turbo.json"
            config_to_save = {
                "orb_pos": self.orb_pos.get(),
                "equip_pos": self.equip_pos.get(),
                "mod_region": self.mod_region.get(),
                "main_threshold": self.main_threshold.get(),
                "tier_threshold": self.tier_threshold.get(),
                "max_attempts": self.max_attempts.get(),
                **{k: v.get() for k, v in self.delay_vars.items()},
                "main_template_paths": self.main_template_paths,
                "tier_template_path": self.tier_template_path,
            }
            try:
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_to_save, f, indent=4)
            except Exception as e:
                print(f"⚠️ 配置保存失败: {e}")

            self.root.withdraw()
            self.run_reforge(config)
            self.root.deiconify()

        except Exception as e:
            if self.root.winfo_exists():
                messagebox.showerror("启动失败", str(e), parent=self.root)
            else:
                print(f"\n❌ 启动失败: {e}")

    def run_reforge(self, config):
        print("\n" + "="*70)
        print("⚡ 极速洗练启动（主词条 + 右侧T阶图标匹配 | 整行搜索）")
        print("🛑 按 F12 可随时中断洗练（返回主界面）")
        print("="*70)
        time.sleep(0.5)

        # 加载主词条模板
        main_templates_with_path = [
            (path, self.load_and_preprocess_template(path))
            for path in config["MAIN_TEMPLATE_PATHS"]
        ]

        # 加载T阶模板
        tier_template = self.load_and_preprocess_template(config["TIER_TEMPLATE_PATH"])
        h_tier, w_tier = tier_template.shape

        orb_x, orb_y = config["REFORGE_ORB_POS"]
        equip_x, equip_y = config["TARGET_EQUIP_POS"]
        x, y, w, h = config["MOD_DISPLAY_REGION"]
        main_thresh = config["MAIN_THRESHOLD"]
        tier_thresh = config["TIER_THRESHOLD"]
        max_attempts = config["MAX_ATTEMPTS"]
        equip_click_delay = config["EQUIP_CLICK_DELAY"]
        orb_delay = config["ORB_DELAY"]

        pyautogui.moveTo(orb_x, orb_y, duration=0.03)
        pyautogui.rightClick()
        time.sleep(orb_delay)
        pyautogui.keyDown('shift')

        success = False
        attempt = 0

        try:
            while attempt < max_attempts:
                if keyboard and keyboard.is_pressed('f12'):
                    print("\n⏸️ 用户按下 F12，洗练已中断。")
                    break

                attempt += 1
                pyautogui.moveTo(equip_x, equip_y, duration=0.03)
                pyautogui.click()
                time.sleep(equip_click_delay)

                pyautogui.keyDown('alt')
                raw_screenshot = pyautogui.screenshot(region=(x, y, w, h))
                pyautogui.keyUp('alt')

                raw_img_bgr = cv2.cvtColor(np.array(raw_screenshot), cv2.COLOR_RGB2BGR)
                screen_gray = self.preprocess_image(raw_img_bgr)

                # === 第1步：主词条匹配 ===
                main_matched, matched_main_tpl, matched_main_path, match_loc, score = self.match_main_and_get_template(
                    screen_gray, main_templates_with_path, main_thresh, attempt
                )

                if not main_matched:
                    continue

                # === 第2步：在右侧整行区域匹配T阶图标 ===
                h_scr, w_scr = screen_gray.shape
                h_main, w_main = matched_main_tpl.shape
                x_main, y_main = match_loc

                search_x_start = x_main + w_main
                search_x_end = w_scr
                search_y_start = y_main
                search_y_end = y_main + h_main

                tier_matched = False
                if search_x_start < search_x_end and search_y_end <= h_scr:
                    if h_tier <= (search_y_end - search_y_start) and w_tier <= (search_x_end - search_x_start):
                        search_region = screen_gray[search_y_start:search_y_end, search_x_start:search_x_end]
                        res_tier = cv2.matchTemplate(search_region, tier_template, cv2.TM_CCOEFF_NORMED)
                        _, max_val_tier, _, _ = cv2.minMaxLoc(res_tier)
                        print(f" 🔍 T阶图标匹配得分: {max_val_tier:.4f} | 阈值: {tier_thresh:.2f}")
                        tier_matched = max_val_tier >= tier_thresh
                    else:
                        print(" ⚠️ T阶模板大于右侧可用区域")
                else:
                    print(" ⚠️ 主词条右侧无有效搜索区域")

                if tier_matched:
                    print(" ✅ 主词条 + T阶图标均匹配成功！洗练成功！")
                    success = True
                    break
                else:
                    print(" ⚠️ T阶图标未匹配，跳过本次结果")

                time.sleep(0.01)

        finally:
            pyautogui.keyUp('shift')

        result = "成功" if success else "已中断" if (keyboard and keyboard.is_pressed('f12')) else "已达上限"
        msg = f"{result}！共 {attempt} 次。"
        print(f"\n🏁 {msg}")
        messagebox.showinfo("洗练结束", msg)

    # === weizhi功能相关方法 ===
    def weizhi_log(self, msg):
        self.result_text.config(state='normal')
        self.result_text.insert(tk.END, msg + "\n")
        self.result_text.see(tk.END)
        self.result_text.config(state='disabled')
        print(msg)

    def load_screenshot(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path:
            self.screenshot_path = path
            self.screenshot_img = cv2.imread(path)
            self.weizhi_log(f"✅ 已加载截图: {os.path.basename(path)}")
            self.update_original_views()

    def load_template_main(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path:
            self.template_main_path = path
            self.template_main_img = cv2.imread(path)
            self.weizhi_log(f"✅ 已加载主词条模板: {os.path.basename(path)}")
            self.update_original_views()

    def load_template_tier(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path:
            self.template_tier_path = path
            self.template_tier_img = cv2.imread(path)
            self.weizhi_log(f"✅ 已加载T阶图标模板: {os.path.basename(path)}")
            self.update_original_views()

    def update_original_views(self):
        if self.screenshot_img is not None:
            self.show_image_on_canvas(self.screenshot_img, self.canvas_orig_screen)
            proc_screen = self.preprocess_image(self.screenshot_img)
            self.show_image_on_canvas(proc_screen, self.canvas_proc_screen, is_gray=True)

        if self.template_main_img is not None:
            self.show_image_on_canvas(self.template_main_img, self.canvas_orig_main, max_h=60)
            proc_main = self.preprocess_image(self.template_main_img)
            self.show_image_on_canvas(proc_main, self.canvas_proc_main, max_h=60, is_gray=True)

        if self.template_tier_img is not None:
            self.show_image_on_canvas(self.template_tier_img, self.canvas_orig_tier, max_h=40)
            proc_tier = self.preprocess_image(self.template_tier_img)
            self.show_image_on_canvas(proc_tier, self.canvas_proc_tier, max_h=40, is_gray=True)

    def show_image_on_canvas(self, img, canvas, max_h=None, is_gray=False):
        if img is None:
            return
        if is_gray:
            img_display = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        else:
            img_display = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        h, w = img_display.shape[:2]
        if max_h and h > max_h:
            scale = max_h / h
            new_w, new_h = int(w * scale), max_h
            img_resized = cv2.resize(img_display, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            img_resized = img_display

        pil_img = Image.fromarray(img_resized)
        tk_img = ImageTk.PhotoImage(pil_img)

        canvas.delete("all")
        canvas.image = tk_img
        canvas.create_image(0, 0, anchor=tk.NW, image=tk_img)
        canvas.config(scrollregion=canvas.bbox(tk.ALL))

    def run_matching(self):
        if self.screenshot_img is None or self.template_main_img is None or self.template_tier_img is None:
            messagebox.showwarning("警告", "请先加载截图、主词条模板和T阶图标模板！")
            return

        self.weizhi_log("\n🔄 开始匹配流程...")
        try:
            screen_gray = self.preprocess_image(self.screenshot_img)
            template_main_gray = self.preprocess_image(self.template_main_img)
            template_tier_gray = self.preprocess_image(self.template_tier_img)

            h_scr, w_scr = screen_gray.shape
            h_main, w_main = template_main_gray.shape
            h_tier, w_tier = template_tier_gray.shape

            # 尺寸检查
            if h_main > h_scr or w_main > w_scr:
                raise ValueError("主词条模板尺寸大于截图！")
            if h_tier > h_scr or w_tier > w_scr:
                raise ValueError("T阶图标模板尺寸大于截图！")

            # === 第1步：主词条匹配 ===
            res_main = cv2.matchTemplate(screen_gray, template_main_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val_main, _, max_loc = cv2.minMaxLoc(res_main)
            x, y = max_loc
            self.weizhi_log(f"🎯 主词条匹配: 得分={max_val_main:.4f} @ ({x}, {y})")

            if max_val_main < self.main_thresh.get():
                self.weizhi_log("❌ 主词条未达到阈值，匹配失败")
                return

            # === 第2步：在主词条右侧整行剩余区域搜索T阶图标 ===
            search_x_start = x + w_main
            search_x_end = w_scr  # 搜到截图最右边
            search_y_start = y
            search_y_end = y + h_main

            max_val_tier = 0.0
            tier_global_x = tier_global_y = tier_right = tier_bottom = 0

            if search_x_start >= search_x_end or search_y_end > h_scr:
                self.weizhi_log("⚠️ 主词条已到右边缘，无右侧区域可搜索T阶图标")
            elif h_tier > (search_y_end - search_y_start) or w_tier > (search_x_end - search_x_start):
                self.weizhi_log("⚠️ T阶模板大于右侧可用区域，无法匹配")
            else:
                search_region = screen_gray[search_y_start:search_y_end, search_x_start:search_x_end]
                res_tier = cv2.matchTemplate(search_region, template_tier_gray, cv2.TM_CCOEFF_NORMED)
                _, max_val_tier, _, max_loc_tier = cv2.minMaxLoc(res_tier)
                offset_x, offset_y = max_loc_tier

                tier_global_x = search_x_start + offset_x
                tier_global_y = search_y_start + offset_y
                tier_right = tier_global_x + w_tier
                tier_bottom = tier_global_y + h_tier

                self.weizhi_log(f"🔍 T阶图标匹配: 得分={max_val_tier:.4f} @ 全局({tier_global_x}, {tier_global_y})")

            # === 第3步：最终判定 ===
            main_ok = max_val_main >= self.main_thresh.get()
            tier_ok = max_val_tier >= self.tier_thresh.get()

            # 可视化
            output = self.screenshot_img.copy()
            cv2.rectangle(output, (x, y), (x + w_main, y + h_main), (0, 255, 0), 2)  # 绿框：主词条
            if max_val_tier > 0:
                cv2.rectangle(output, (tier_global_x, tier_global_y), (tier_right, tier_bottom), (255, 0, 0), 2)  # 蓝框：T阶

            status = "✅ PASS" if main_ok and tier_ok else "❌ FAIL"
            color = (0, 255, 0) if main_ok and tier_ok else (0, 0, 255)
            cv2.putText(output, f"{status} (main={max_val_main:.3f}, tier={max_val_tier:.3f})",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            cv2.imwrite("debug_result_visual.png", output)
            self.show_image_on_canvas(output, self.canvas_result)
            self.weizhi_log("💾 已保存 debug_result_visual.png")

            final_msg = f"🎉 匹配完成！{'通过' if main_ok and tier_ok else '失败'}"
            self.weizhi_log(final_msg)

        except Exception as e:
            error_msg = f"💥 错误: {str(e)}"
            self.weizhi_log(error_msg)
            messagebox.showerror("匹配出错", str(e))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedApp(root)
    app.run()
