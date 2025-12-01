import json
import cv2
import numpy as np
import pyautogui
import time
import os
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# === 必需依赖 ===
try:
    import keyboard
except ImportError:
    print("❌ 请安装 keyboard 库: pip install keyboard")
    exit(1)

try:
    from pynput import mouse
except ImportError:
    print("⚠️ 建议安装 pynput 以支持点击拾取: pip install pynput")


# === 配置文件路径 ===
CONFIG_FILE = "config.json"


# ==================== 工具函数 ====================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 配置文件加载失败: {e}")
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"⚠️ 配置保存失败: {e}")


# ==================== 【仅使用原始 Otsu 二值化】====================
def preprocess_image(img):
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def load_and_preprocess_template(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"模板文件未找到: {path}")
    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"无法加载模板图像: {path}")
    return preprocess_image(template)


# 🔍 模板匹配（带得分打印）
def match_all_templates(screen_gray, templates, threshold):
    h_screen, w_screen = screen_gray.shape
    all_matched = True

    for i, template in enumerate(templates):
        h_tpl, w_tpl = template.shape[:2]
        if h_tpl > h_screen or w_tpl > w_screen:
            print(f"❌ 模板 #{i+1} 尺寸过大！模板: {w_tpl}x{h_tpl}，截图: {w_screen}x{h_screen}")
            return False

        res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        status = "✅ 成功" if max_val >= threshold else "❌ 失败"
        print(f"🔍 模板 #{i+1}: 得分 = {max_val:.4f} | 阈值 = {threshold:.2f} → {status}")

        if max_val < threshold:
            all_matched = False

    return all_matched


# ==================== 拖拽区域选择 ====================
def select_region_by_drag(parent=None):
    if parent is None:
        raise ValueError("必须提供 parent Tk 窗口")

    selector = tk.Toplevel(parent)
    selector.title("区域选择")
    selector.attributes('-fullscreen', True)
    selector.attributes('-topmost', True)
    selector.wait_visibility(selector)
    selector.wm_attributes('-alpha', 0.3)
    selector.config(bg='black')
    selector.overrideredirect(True)

    canvas = tk.Canvas(selector, bg='black', highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    start_x, start_y = None, None
    rect_id = None
    selected_region = None
    done = False

    def on_mouse_down(event):
        nonlocal start_x, start_y
        start_x, start_y = event.x, event.y

    def on_mouse_move(event):
        nonlocal rect_id
        if start_x is None:
            return
        if rect_id:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(
            start_x, start_y, event.x, event.y,
            outline='cyan', width=2, dash=(5, 5)
        )

    def on_mouse_up(event):
        nonlocal selected_region, done
        if start_x is None:
            selector.destroy()
            return

        x1, y1 = start_x, start_y
        x2, y2 = event.x, event.y
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        if w < 10 or h < 10:
            messagebox.showwarning("区域太小", "请选择至少 10×10 像素的区域！", parent=selector)
            return

        selected_region = (x, y, w, h)
        done = True
        selector.destroy()

    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    messagebox.showinfo(
        "区域选择",
        "请在屏幕上拖动鼠标选择整个属性窗口。\n"
        "你会看到一个青色虚线框，松开鼠标完成选择。",
        parent=parent
    )

    while not done and selector.winfo_exists():
        try:
            parent.update()
        except tk.TclError:
            break
        time.sleep(0.02)

    if selected_region is None:
        raise RuntimeError("用户取消了区域选择")

    return selected_region


# ==================== 主 GUI 类 ====================
class PoeReforgeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("POE2 自动洗练工具 v7.7（全延迟可调 + 高速模式）")
        self.root.geometry("620x680")
        self.root.resizable(False, False)
        self.template_paths = []

        config = load_config()
        self.orb_pos = tk.StringVar(value=config.get("orb_pos", "(?, ?)"))
        self.equip_pos = tk.StringVar(value=config.get("equip_pos", "(?, ?)"))
        self.mod_region = tk.StringVar(value=config.get("mod_region", "(?, ?, ?, ?)"))
        self.threshold = tk.DoubleVar(value=float(config.get("threshold", 0.85)))
        self.max_attempts = tk.IntVar(value=int(config.get("max_attempts", 200)))

        # ===== 延迟配置变量 =====
        self.delay_vars = {
            "orb_delay": tk.DoubleVar(value=float(config.get("orb_delay", 0.30))),
            "equip_click_delay": tk.DoubleVar(value=float(config.get("equip_click_delay", 1.20))),
            "alt_screenshot_delay": tk.DoubleVar(value=float(config.get("alt_screenshot_delay", 0.00))),  # 默认 0.0
            "post_screenshot_delay": tk.DoubleVar(value=float(config.get("post_screenshot_delay", 0.10))),
            "loop_random_max": tk.DoubleVar(value=float(config.get("loop_random_max", 0.15))),
        }

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="12")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        coords = [
            ("洗练石位置:", self.orb_pos, "orb"),
            ("目标装备位置:", self.equip_pos, "equip"),
            ("属性显示区域:", self.mod_region, "mod")
        ]
        for i, (label, var, key) in enumerate(coords):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            ttk.Entry(frame, textvariable=var, width=25, state='readonly').grid(row=i, column=1, padx=5)
            btn_text = "点击拾取" if key != "mod" else "拖拽选取"
            ttk.Button(frame, text=btn_text, command=lambda k=key: self.pick_coordinate(k)).grid(row=i, column=2)
        ttk.Label(frame, text="（支持任意大小）", foreground="gray").grid(row=3, column=1, sticky=tk.W)

        ttk.Label(frame, text="目标词条模板 (PNG):").grid(row=4, column=0, sticky=tk.W, pady=(10, 5))
        self.listbox = tk.Listbox(frame, height=5, width=60)
        self.listbox.grid(row=5, column=0, columnspan=3, pady=5)
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=5, sticky=tk.W)
        ttk.Button(btn_frame, text="添加 PNG", command=self.add_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="移除选中", command=self.remove_template).pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="匹配阈值:").grid(row=7, column=0, sticky=tk.W, pady=5)
        ttk.Scale(frame, from_=0.70, to=0.99, variable=self.threshold, orient=tk.HORIZONTAL).grid(row=7, column=1, sticky=(tk.W, tk.E))
        ttk.Label(frame, textvariable=self.threshold, width=6).grid(row=7, column=2)

        ttk.Label(frame, text="最大尝试次数:").grid(row=8, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.max_attempts, width=10).grid(row=8, column=1, sticky=tk.W)

        # ===== 高级延迟设置 =====
        ttk.Label(frame, text="⏱️ 高级延迟设置 (秒):", foreground="blue").grid(row=9, column=0, sticky=tk.W, pady=(15, 5))

        delay_items = [
            ("洗练石操作后:", "orb_delay"),
            ("装备点击后:", "equip_click_delay"),
            ("Alt按下后截图延迟:", "alt_screenshot_delay"),
            ("截图后处理延迟:", "post_screenshot_delay"),
            ("循环间隔随机上限:", "loop_random_max"),
        ]

        row_offset = 10
        for label_text, key in delay_items:
            ttk.Label(frame, text=label_text).grid(row=row_offset, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(frame, textvariable=self.delay_vars[key], width=8)
            entry.grid(row=row_offset, column=1, sticky=tk.W)
            row_offset += 1

        # 开始按钮
        ttk.Button(frame, text="✅ 开始自动洗练", command=self.start_reforge).grid(
            row=row_offset, column=0, columnspan=3, pady=20, ipadx=10, ipady=5
        )

    def pick_coordinate(self, target_type):
        if target_type == "mod":
            try:
                region = select_region_by_drag(parent=self.root)
                x, y, w, h = region
                self.mod_region.set(f"({x}, {y}, {w}, {h})")
                messagebox.showinfo("属性区域已设置", f"✅ 选区成功！\n左上角: ({x}, {y})\n宽: {w}, 高: {h}", parent=self.root)
            except Exception as e:
                messagebox.showerror("区域选择失败", f"❌ {str(e)}", parent=self.root)
            return

        titles = {"orb": "洗练石", "equip": "目标装备"}
        target_name = titles[target_type]

        messagebox.showinfo("坐标拾取", f"📌 将鼠标移到 {target_name} 上，然后 **单击左键**。", parent=self.root)

        clicked = False
        def on_click(x, y, button, pressed):
            nonlocal clicked
            if pressed and button.name == 'left':
                clicked = True
                return False

        try:
            with mouse.Listener(on_click=on_click) as listener:
                while not clicked:
                    time.sleep(0.01)
        except Exception:
            time.sleep(1.5)
        x, y = pyautogui.position()

        if target_type == "orb":
            self.orb_pos.set(f"({x}, {y})")
        elif target_type == "equip":
            self.equip_pos.set(f"({x}, {y})")

        messagebox.showinfo("成功", f"{target_name} 坐标设为 ({x}, {y})", parent=self.root)

    def add_template(self):
        files = filedialog.askopenfilenames(title="选择 PNG 模板", filetypes=[("PNG 图像", "*.png")])
        for f in files:
            if f not in self.template_paths:
                self.template_paths.append(f)
                self.listbox.insert(tk.END, f)

    def remove_template(self):
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            self.listbox.delete(idx)
            del self.template_paths[idx]

    def parse_tuple(self, s):
        cleaned = s.strip("() ")
        parts = [int(x.strip()) for x in cleaned.split(",") if x.strip()]
        return tuple(parts)

    def start_reforge(self):
        try:
            if not self.template_paths:
                messagebox.showwarning("缺少模板", "请至少添加一个 PNG 模板！", parent=self.root)
                return

            orb_pos = self.parse_tuple(self.orb_pos.get())
            equip_pos = self.parse_tuple(self.equip_pos.get())
            mod_region = self.parse_tuple(self.mod_region.get())
            if len(orb_pos) != 2 or len(equip_pos) != 2 or len(mod_region) != 4:
                raise ValueError("坐标格式错误")

            # 收集所有配置
            config = {
                "REFORGE_ORB_POS": orb_pos,
                "TARGET_EQUIP_POS": equip_pos,
                "MOD_DISPLAY_REGION": mod_region,
                "MATCH_THRESHOLD": self.threshold.get(),
                "MAX_ATTEMPTS": self.max_attempts.get(),
                "TARGET_TEMPLATE_PATHS": self.template_paths.copy(),
                "ORB_DELAY": self.delay_vars["orb_delay"].get(),
                "EQUIP_CLICK_DELAY": self.delay_vars["equip_click_delay"].get(),
                "ALT_SCREENSHOT_DELAY": self.delay_vars["alt_screenshot_delay"].get(),
                "POST_SCREENSHOT_DELAY": self.delay_vars["post_screenshot_delay"].get(),
                "LOOP_RANDOM_MAX": self.delay_vars["loop_random_max"].get(),
            }

            if not messagebox.askyesno("确认", "▶ 洗练过程中按 F12 键可随时退出！", parent=self.root):
                return

            # 保存配置（含延迟）
            save_config({
                "orb_pos": self.orb_pos.get(),
                "equip_pos": self.equip_pos.get(),
                "mod_region": self.mod_region.get(),
                "threshold": self.threshold.get(),
                "max_attempts": self.max_attempts.get(),
                "orb_delay": self.delay_vars["orb_delay"].get(),
                "equip_click_delay": self.delay_vars["equip_click_delay"].get(),
                "alt_screenshot_delay": self.delay_vars["alt_screenshot_delay"].get(),
                "post_screenshot_delay": self.delay_vars["post_screenshot_delay"].get(),
                "loop_random_max": self.delay_vars["loop_random_max"].get(),
            })

            self.root.destroy()
            self.run_reforge(config)

        except Exception as e:
            messagebox.showerror("配置错误", f"❌ {str(e)}", parent=self.root)

    def run_reforge(self, config):
        print("\n" + "="*50)
        print("🚀 开始自动洗练流程（v7.7 全延迟可调）...")
        print("💡 按 F12 可随时退出")
        print("📸 每次截图将保存 debug_actual.png 和 debug_actual_processed.png")
        print("="*50)
        time.sleep(1)

        templates = []
        for path in config["TARGET_TEMPLATE_PATHS"]:
            tpl = load_and_preprocess_template(path)
            h, w = tpl.shape
            templates.append(tpl)
            print(f"✅ 加载模板: {os.path.basename(path)} ({w}x{h})")

        orb_x, orb_y = config["REFORGE_ORB_POS"]
        equip_x, equip_y = config["TARGET_EQUIP_POS"]
        mod_region = config["MOD_DISPLAY_REGION"]
        threshold = config["MATCH_THRESHOLD"]
        max_attempts = config["MAX_ATTEMPTS"]

        # 解包延迟
        orb_delay = config["ORB_DELAY"]
        equip_click_delay = config["EQUIP_CLICK_DELAY"]
        alt_screenshot_delay = config["ALT_SCREENSHOT_DELAY"]
        post_screenshot_delay = config["POST_SCREENSHOT_DELAY"]
        loop_random_max = config["LOOP_RANDOM_MAX"]

        print(f"\n➡️ 步骤1: 右键洗练石 ({orb_x}, {orb_y})")
        pyautogui.moveTo(orb_x, orb_y, duration=0.15)
        time.sleep(0.25)  # 移动微延迟（固定）
        pyautogui.rightClick()
        time.sleep(orb_delay)

        print("➡️ 步骤2: 按住 SHIFT（连续洗练）")
        pyautogui.keyDown('shift')
        time.sleep(0.2)

        success = False
        attempt = 0

        try:
            while attempt < max_attempts:
                if keyboard.is_pressed('f12'):
                    print("\n🛑 检测到 F12，正在安全退出...")
                    break

                attempt += 1
                print(f"\n🔄 尝试 #{attempt}/{max_attempts}")

                pyautogui.moveTo(equip_x, equip_y, duration=0.1)
                time.sleep(0.15)
                pyautogui.click()
                time.sleep(equip_click_delay)

                # === 截图部分（关键：Alt 延迟可调，默认 0.0）===
                x, y, w, h = mod_region
                if w <= 0 or h <= 0:
                    raise ValueError(f"无效区域尺寸: {mod_region}")

                pyautogui.keyDown('alt')
                if alt_screenshot_delay > 0:
                    time.sleep(alt_screenshot_delay)
                raw_screenshot = pyautogui.screenshot(region=(x, y, w, h))
                pyautogui.keyUp('alt')
                time.sleep(post_screenshot_delay)

                raw_img_bgr = cv2.cvtColor(np.array(raw_screenshot), cv2.COLOR_RGB2BGR)
                cv2.imwrite("debug_actual.png", raw_img_bgr)

                screen_gray = preprocess_image(raw_img_bgr)
                cv2.imwrite("debug_actual_processed.png", screen_gray)

                if attempt == 1 and templates:
                    cv2.imwrite("debug_template_processed.png", templates[0])
                    print("💾 已保存模板预处理图")

                print("📸 已保存当前装备属性图用于调试")

                if match_all_templates(screen_gray, templates, threshold):
                    print("🎉 所有目标词条匹配成功！")
                    success = True
                    break
                else:
                    print("❌ 条件未满足，继续...")

                time.sleep(random.uniform(0.02, loop_random_max))

        except KeyboardInterrupt:
            print("\n🛑 用户中断 (Ctrl+C)")
        except Exception as e:
            print(f"\n💥 运行错误: {e}")
            success = False
        finally:
            pyautogui.keyUp('shift')
            print("\n✅ 已释放 SHIFT 键")

        result = "成功" if success else "已停止"
        print(f"\n🏁 洗练{result}！共尝试 {attempt} 次。")
        try:
            messagebox.showinfo("完成", f"洗练{result}！\n共尝试 {attempt} 次。")
        except:
            pass


# ==================== 启动程序 ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = PoeReforgeGUI(root)
    root.mainloop()