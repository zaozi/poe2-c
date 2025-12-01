import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os

class MainTierMatcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("主词条 + 右侧T阶图标匹配测试工具（整行搜索版）")
        self.root.geometry("1200x750")
        self.root.resizable(True, True)

        # 图像路径与数据
        self.screenshot_path = None
        self.template_main_path = None      # 主词条模板
        self.template_tier_path = None      # T阶图标模板（如 t1.png）
        self.screenshot_img = None          # 原始 BGR
        self.template_main_img = None       # 原始 BGR
        self.template_tier_img = None       # 原始 BGR

        # 阈值变量
        self.main_thresh = tk.DoubleVar(value=0.85)
        self.tier_thresh = tk.DoubleVar(value=0.90)

        self.create_widgets()

    def create_widgets(self):
        # === 控制区 ===
        control_frame = ttk.Frame(self.root, padding="10")
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
        self.result_text = tk.Text(self.root, height=4, state='disabled', bg='#f0f0f0')
        self.result_text.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0,10))

        # === 三视图区 ===
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
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

    def log(self, msg):
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
            self.log(f"✅ 已加载截图: {os.path.basename(path)}")
            self.update_original_views()

    def load_template_main(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path:
            self.template_main_path = path
            self.template_main_img = cv2.imread(path)
            self.log(f"✅ 已加载主词条模板: {os.path.basename(path)}")
            self.update_original_views()

    def load_template_tier(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path:
            self.template_tier_path = path
            self.template_tier_img = cv2.imread(path)
            self.log(f"✅ 已加载T阶图标模板: {os.path.basename(path)}")
            self.update_original_views()

    def update_original_views(self):
        if self.screenshot_img is not None:
            self.show_image_on_canvas(self.screenshot_img, self.canvas_orig_screen)
            proc_screen = self.preprocess(self.screenshot_img)
            self.show_image_on_canvas(proc_screen, self.canvas_proc_screen, is_gray=True)

        if self.template_main_img is not None:
            self.show_image_on_canvas(self.template_main_img, self.canvas_orig_main, max_h=60)
            proc_main = self.preprocess(self.template_main_img)
            self.show_image_on_canvas(proc_main, self.canvas_proc_main, max_h=60, is_gray=True)

        if self.template_tier_img is not None:
            self.show_image_on_canvas(self.template_tier_img, self.canvas_orig_tier, max_h=40)
            proc_tier = self.preprocess(self.template_tier_img)
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

    def preprocess(self, img):
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def run_matching(self):
        if self.screenshot_img is None or self.template_main_img is None or self.template_tier_img is None:
            messagebox.showwarning("警告", "请先加载截图、主词条模板和T阶图标模板！")
            return

        self.log("\n🔄 开始匹配流程...")
        try:
            screen_gray = self.preprocess(self.screenshot_img)
            template_main_gray = self.preprocess(self.template_main_img)
            template_tier_gray = self.preprocess(self.template_tier_img)

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
            self.log(f"🎯 主词条匹配: 得分={max_val_main:.4f} @ ({x}, {y})")

            if max_val_main < self.main_thresh.get():
                self.log("❌ 主词条未达到阈值，匹配失败")
                return

            # === 第2步：在主词条右侧整行剩余区域搜索T阶图标 ===
            search_x_start = x + w_main
            search_x_end = w_scr  # 搜到截图最右边
            search_y_start = y
            search_y_end = y + h_main

            max_val_tier = 0.0
            tier_global_x = tier_global_y = tier_right = tier_bottom = 0

            if search_x_start >= search_x_end or search_y_end > h_scr:
                self.log("⚠️ 主词条已到右边缘，无右侧区域可搜索T阶图标")
            elif h_tier > (search_y_end - search_y_start) or w_tier > (search_x_end - search_x_start):
                self.log("⚠️ T阶模板大于右侧可用区域，无法匹配")
            else:
                search_region = screen_gray[search_y_start:search_y_end, search_x_start:search_x_end]
                res_tier = cv2.matchTemplate(search_region, template_tier_gray, cv2.TM_CCOEFF_NORMED)
                _, max_val_tier, _, max_loc_tier = cv2.minMaxLoc(res_tier)
                offset_x, offset_y = max_loc_tier

                tier_global_x = search_x_start + offset_x
                tier_global_y = search_y_start + offset_y
                tier_right = tier_global_x + w_tier
                tier_bottom = tier_global_y + h_tier

                self.log(f"🔍 T阶图标匹配: 得分={max_val_tier:.4f} @ 全局({tier_global_x}, {tier_global_y})")

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
            self.log("💾 已保存 debug_result_visual.png")

            final_msg = f"🎉 匹配完成！{'通过' if main_ok and tier_ok else '失败'}"
            self.log(final_msg)

        except Exception as e:
            error_msg = f"💥 错误: {str(e)}"
            self.log(error_msg)
            messagebox.showerror("匹配出错", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = MainTierMatcherApp(root)
    root.mainloop()