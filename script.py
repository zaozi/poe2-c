# -*- coding: utf-8 -*-
"""
Path of Exile 自动化装备检查脚本 (基于坐标和 DashScope OCR & LLM 判断)
功能：
1. 根据预设坐标右键点击物品，左键点击装备槽。
2. 截取指定区域，调用 DashScope 通义千问VL API 进行 OCR 识别属性。
3. 将 OCR 识别出的属性文本和用户设定的自然语言预期描述，发送给 DashScope 文本模型进行判断。
4. 可配置为单次执行或循环执行。
注意：此版本不包含 API Key 验证步骤，使用大模型判断属性是否符合预期。
"""

import pyautogui
import time
import logging
import sys
import os
import base64
import io
from PIL import ImageGrab

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 导入 DashScope 库 ---
try:
    import dashscope
    from dashscope import MultiModalConversation, Generation  # 导入多模态和文本生成模块
except ImportError as e:
    logging.critical(f"导入 dashscope 库失败: {e}。请确保已通过 'pip install dashscope' 安装。")
    sys.exit(1)
# --------------------------

# --- PyAutoGUI 设置 ---
# 启用安全机制：将鼠标快速移到左上角 (0,0) 可以紧急停止脚本
pyautogui.FAILSAFE = True
# 设置默认的暂停时间，使操作更稳定
pyautogui.PAUSE = 0.1
# ----------------------

# ====================== API KEY 设置位置 ======================
# 方法一：【推荐】在这里硬编码你的API KEY（仅用于测试，生产环境请注意安全）
# 删除下面这行代码前面的注释符号 (#)，并将 "YOUR_ACTUAL_API_KEY_HERE" 替换为你的真实API Key
os.environ["DASHSCOPE_API_KEY"] = "" # <-- 示例，请替换
dashscope.api_key = "" # <-- 示例，请替换

# 方法二：从环境变量 DASHSCOPE_API_KEY 读取 (更安全)
# 你需要在运行脚本前设置环境变量，例如在命令行中执行:
# Windows CMD: set DASHSCOPE_API_KEY=your_actual_key_here
# Windows PS:  $env:DASHSCOPE_API_KEY="your_actual_key_here"
# Linux/macOS: export DASHSCOPE_API_KEY=your_actual_key_here
# =============================================================

# ====================== 辅助函数 ======================
def image_to_base64(image):
    """将 PIL Image 对象转换为 Base64 编码字符串"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_str

def extract_text_from_region(region):
    """
    使用 DashScope MultiModalConversation API 对指定区域进行 OCR。
    :param region: tuple (left, top, width, height) 定义要截取的屏幕区域
    :return: string 提取出的文字，如果失败则返回 None
    """
    left, top, width, height = region
    try:
        # 1. 截取屏幕指定区域
        screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))
        logging.debug(f"已截取区域: {region}")

        # 2. 转换为 Base64
        img_base64 = image_to_base64(screenshot)
        logging.debug("图像已转换为 Base64")

        # 3. 构造 DashScope 请求消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"data:image/png;base64,{img_base64}"},
                    {"text": "请精确识别图片中的所有中文和英文文字，包括数字和符号。只输出识别出的文字内容，不要添加任何额外的说明或格式。"}
                ]
            }
        ]

        # 4. 调用 DashScope OCR API (使用 qwen-vl-plus 或 qwen-vl-max 通常精度更高)
        ocr_model = 'qwen-vl-plus' # 可根据需要更换为 'qwen-vl-max'
        logging.info(f"正在调用 DashScope OCR API ({ocr_model})...")
        response = MultiModalConversation.call(model=ocr_model, messages=messages)

        # 5. 解析响应
        if response.status_code == 200:
            text_content = response.output.choices[0]['message']['content']
            # 如果返回的是列表（包含多个部分），则提取文本部分
            if isinstance(text_content, list):
                extracted_text = ""
                for item in text_content:
                    if item.get('text'):
                        extracted_text += item['text'] + "\n"
            else:
                extracted_text = text_content

            logging.info("OCR 识别成功")
            logging.debug(f"OCR 结果: \n{extracted_text}")
            return extracted_text
        else:
            logging.error(f"OCR API 调用失败: 状态码 {response.status_code}, 错误代码 {getattr(response, 'code', 'N/A')}, 信息: {getattr(response, 'message', 'N/A')}")
            return None

    except Exception as e:
        logging.error(f"OCR 过程中发生错误: {e}", exc_info=True)
        return None

def check_expected_stats_with_llm(stats_text, expected_description, llm_model='qwen-turbo'):
    """
    使用 DashScope 文本模型判断 OCR 识别出的属性是否符合用户提供的自然语言预期描述。
    :param stats_text: string, OCR 识别出的所有属性文本
    :param expected_description: string, 用户用自然语言描述的预期属性 (例如："我想要所有元素抗性大于等于8，并且有法术伤害词缀")
    :param llm_model: string, 用于判断的 DashScope 文本模型名称 (例如 'qwen-turbo', 'qwen-plus', 'qwen-max')
    :return: boolean, True 表示符合预期，False 表示不符合或判断出错
    """
    if not stats_text:
        logging.warning("检查属性时，输入的 OCR 文本为空。")
        return False
    if not expected_description:
        logging.warning("检查属性时，预期描述为空。")
        return True # 如果没有预期，则认为满足

    try:
        # 构造发送给 LLM 的提示词 (Prompt)
        prompt = (
            f"你是一位专业的《流放之路》(Path of Exile) 装备属性分析员。\n\n"
            f"请仔细阅读以下信息并严格按照指令回答：\n\n"
            f"**装备属性文本:**\n{stats_text}\n\n"
            f"**用户预期描述:**\n{expected_description}\n\n"
            f"请根据装备属性文本，判断该装备是否**完全满足**用户的预期描述。\n\n"
            f"**判断规则:**\n"
            f"- 必须满足预期描述中的**所有**明确要求。\n"
            f"- 如果预期描述中有量化的要求（如“大于等于8”），必须严格遵守。\n"
            f"- 如果预期描述中有定性的要求（如“有法术伤害词缀”），只要属性文本中能找到相关表述即可。\n"
            f"- 如果有任何一项要求不满足，则判定为不满足。\n\n"
            f"**你的回答只能是以下两种之一，且必须严格遵守格式：**\n"
            f"- **满足**\n"
            f"- **不满足**\n\n"
            f"请开始你的判断："
        )

        logging.info(f"正在调用 DashScope 文本模型 ({llm_model}) 进行属性判断...")
        logging.debug(f"发送给 LLM 的 Prompt:\n{prompt}")

        # 调用 DashScope 文本生成 API
        response = Generation.call(
            model=llm_model,
            prompt=prompt,
            # 可以设置一些参数来控制输出，例如：
            max_tokens=100, # 回复很短，限制 token 数
            temperature=0.0, # 设置为 0 使输出更确定性和一致
            top_p=0.9,
            seed=12345 # 固定种子以增加可重复性
        )

        # 解析响应
        if response.status_code == 200:
            llm_output = response.output.text.strip()
            logging.info(f"LLM 判断结果: {llm_output}")
            logging.debug(f"LLM 完整回复: {response}")

            # 严格匹配 LLM 的输出
            if "满足" in llm_output and "不满足" not in llm_output:
                 logging.info("🎉 LLM 判断结果：装备属性符合预期！")
                 return True
            elif "不满足" in llm_output:
                 logging.info("😞 LLM 判断结果：装备属性不符合预期。")
                 return False
            else:
                 logging.warning(f"LLM 返回了无法解析的结果: '{llm_output}'。默认判定为不满足。")
                 return False
        else:
            logging.error(f"LLM 判断 API 调用失败: 状态码 {response.status_code}, 错误代码 {getattr(response, 'code', 'N/A')}, 信息: {getattr(response, 'message', 'N/A')}")
            return False

    except Exception as e:
        logging.error(f"使用 LLM 判断属性时发生错误: {e}", exc_info=True)
        return False


def click_at_coordinates(x, y, button='left', clicks=1, interval=0.0, duration=0.0, tween=pyautogui.linear, log_action="点击"):
    """
    在指定的屏幕坐标执行点击操作。
    :param x: 屏幕 X 坐标
    :param y: 屏幕 Y 坐标
    :param button: 鼠标按键 ('left', 'middle', 'right')，默认 'left'
    :param clicks: 点击次数，默认 1
    :param interval: 多次点击之间的间隔（秒），默认 0.0
    :param duration: 移动鼠标到目标位置所需的时间（秒），默认 0.0 (瞬间移动)
    :param tween: 移动过程中的动画函数，默认 linear
    :param log_action: 日志中描述此动作的前缀
    :return: True 如果操作成功，False 否则
    """
    try:
        pyautogui.moveTo(x, y, duration=duration, tween=tween)
        logging.info(f"{log_action}: 鼠标已移动到 ({x}, {y})")
        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
        logging.info(f"{log_action}: 已在 ({x}, {y}) 使用 {button} 键点击 {clicks} 次。")
        return True
    except Exception as e:
        logging.error(f"{log_action}: 在坐标 ({x}, {y}) 点击时发生错误: {e}")
        return False

# ======================================================

# ====================== 主流程函数 ======================
def process_item_and_equipment(item_coords, equipment_coords, delay_between_actions=0.5, expected_description=None, stats_panel_region=None, llm_model_for_judgment='qwen-turbo'):
    """
    主流程：右键点击物品坐标，然后左键点击装备坐标，并检查装备属性。
    :param item_coords: 元组 (x, y)，表示物品图标的屏幕坐标 (将被右键点击)
    :param equipment_coords: 元组 (x, y)，表示装备图标的屏幕坐标 (将被左键点击)
    :param delay_between_actions: 两次点击之间的延迟（秒）
    :param expected_description: string, 用户用自然语言描述的预期属性
    :param stats_panel_region: 用于 OCR 的属性面板区域 (left, top, width, height)
    :param llm_model_for_judgment: 用于判断属性是否满足的 LLM 模型名称
    :return: Boolean - 是否满足预期属性
    """
    logging.info("--- 开始 '右键点击物品坐标 -> 左键点击装备坐标 -> 检查属性' 流程 ---")

    item_x, item_y = item_coords
    equipment_x, equipment_y = equipment_coords

    # 第一步：右键点击物品坐标
    item_success = click_at_coordinates(
        item_x, item_y,
        button='right',
        log_action="右键点击物品坐标"
    )

    if not item_success:
        logging.error("流程中断：未能右键点击物品坐标。")
        return False

    time.sleep(delay_between_actions)

    # 第二步：左键点击装备坐标
    equipment_success = click_at_coordinates(
        equipment_x, equipment_y,
        button='left',
        log_action="左键点击装备坐标"
    )

    if not equipment_success:
        logging.error("流程中断：未能左键点击装备坐标。")
        return False

    # 等待属性面板出现
    logging.info("等待属性面板显示...")
    time.sleep(0.1)

    # 从属性面板区域提取文本
    if stats_panel_region is None:
        logging.error("错误：未指定属性面板区域 (stats_panel_region)。")
        return False

    stats_text = extract_text_from_region(stats_panel_region)
    if not stats_text:
         logging.warning("未能从属性面板区域提取到任何文本。")
         return False

    # 使用 LLM 判断是否符合预期
    if expected_description:
        is_match = check_expected_stats_with_llm(stats_text, expected_description, llm_model=llm_model_for_judgment)
        if is_match:
            logging.info("🎉 装备属性符合预期！停止循环。")
            return True
        else:
            logging.info("😞 装备属性不符合预期，继续循环。")
            return False
    else:
         logging.info("未提供预期属性描述，跳过属性检查。")
         return True # 如果没有预期，可以认为是成功的

    logging.info("--- '右键点击物品坐标 -> 左键点击装备坐标 -> 检查属性' 流程完成 ---")
    return False

# ======================================================

# ====================== 主函数 ======================
def main():
    # ====================== API KEY 设置位置 ======================
    # 【重要】请在此处设置你的 DashScope API Key
    # 方法一：硬编码 (请取消注释并替换 YOUR_ACTUAL_API_KEY_HERE)
    # YOUR_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # <-- 请替换为你的真实API Key
    # os.environ["DASHSCOPE_API_KEY"] = YOUR_API_KEY
    # dashscope.api_key = YOUR_API_KEY

    # 方法二：从环境变量读取 (推荐)
    # =============================================================

    # --- 配置 ---
    # 替换为你要右键点击的物品图标的屏幕坐标 (x, y)
    ITEM_COORDS = (87, 595)  # <--- 请修改为实际坐标
    # 替换为你想要左键点击的装备图标的屏幕坐标 (x, y)
    EQUIPMENT_COORDS = (2084, 1028) # <--- 请修改为实际坐标

    DELAY_BETWEEN_ACTIONS = 0.3 # 两次点击间的延迟
    DELAY_BETWEEN_CYCLES = 0.3 # 循环周期延迟

    # === 定义预期的属性 (自然语言描述) ===
    # 请用清晰、具体的中文描述你想要的属性
    EXPECTED_DESCRIPTION = """
    装备必须满足以下条件之一：
    2. 出现投射物技能的等级+3
    """ # <--- 请修改为你自己的预期描述

    # 定义属性面板的 OCR 区域 (left, top, width, height) - 请务必修改这个值 !!!
    STATS_PANEL_REGION = (1915, 837, 355, 170) # <--- 请务必修改为实际区域 !!!

    # 选择用于判断属性是否满足的 LLM 模型
    # 'qwen-turbo' (最快最便宜), 'qwen-plus' (平衡), 'qwen-max' (最强大最贵)
    LLM_MODEL_FOR_JUDGMENT = 'qwen-plus' # <--- 可根据需要修改

    # 选择运行模式: "once" (执行一次) 或 "cycle" (循环执行)
    MODE = "cycle" # <--- 修改此处
    # ----------

    # --- 日志和提示 ---
    logging.info("=== PoE 自动化装备检查脚本 (坐标版 + LLM 属性判断) ===")
    logging.info(f"物品坐标 (右键): {ITEM_COORDS}")
    logging.info(f"装备坐标 (左键): {EQUIPMENT_COORDS}")
    logging.info(f"操作间延迟: {DELAY_BETWEEN_ACTIONS}s, 循环延迟: {DELAY_BETWEEN_CYCLES}s")
    logging.info(f"运行模式: {MODE}")
    if EXPECTED_DESCRIPTION:
        logging.info(f"预期属性描述: {EXPECTED_DESCRIPTION.strip()}")
    else:
        logging.info("预期属性描述: 未设置 (跳过属性检查)")
    logging.info(f"OCR 区域: {STATS_PANEL_REGION}")
    logging.info(f"用于判断的 LLM 模型: {LLM_MODEL_FOR_JUDGMENT}")
    logging.info("================================")
    print("请在 5 秒内切换到 PoE 游戏窗口...")
    time.sleep(5)
    # -----------------

    # --- API Key 检查 ---
    if not dashscope.api_key or dashscope.api_key == "YOUR_ACTUAL_API_KEY_HERE":
        logging.critical("启动失败: 未找到有效的 API Key。请通过环境变量 DASHSCOPE_API_KEY 或在代码中设置 dashscope.api_key。")
        sys.exit(1)
    else:
       logging.info("DashScope API Key 已设置。")
    # ---------------------

    # --- 主循环 ---
    try:
        if MODE == "once":
            logging.info("执行单次操作模式。")
            success = process_item_and_equipment(
                ITEM_COORDS, EQUIPMENT_COORDS,
                delay_between_actions=DELAY_BETWEEN_ACTIONS,
                expected_description=EXPECTED_DESCRIPTION,
                stats_panel_region=STATS_PANEL_REGION,
                llm_model_for_judgment=LLM_MODEL_FOR_JUDGMENT
            )
            if success:
                logging.info("单次操作成功，找到满足条件的装备，程序退出。")
            else:
                logging.info("单次操作完成，未找到满足条件的装备，程序退出。")
            sys.exit(0)

        elif MODE == "cycle":
            logging.info("执行循环操作模式。")
            cycle_count = 0
            while True:
                cycle_count += 1
                logging.info(f"--- 开始第 {cycle_count} 次循环 ---")

                success = process_item_and_equipment(
                    ITEM_COORDS, EQUIPMENT_COORDS,
                    delay_between_actions=DELAY_BETWEEN_ACTIONS,
                    expected_description=EXPECTED_DESCRIPTION,
                    stats_panel_region=STATS_PANEL_REGION,
                    llm_model_for_judgment=LLM_MODEL_FOR_JUDGMENT
                )

                if success:
                    logging.info("✅ 找到满足条件的装备，脚本结束。")
                    break
                else:
                    logging.info("本次循环未找到满足条件的装备。")

                logging.info(f"--- 第 {cycle_count} 次循环结束 ---")
                time.sleep(DELAY_BETWEEN_CYCLES)

        else:
            logging.error(f"未知的运行模式: {MODE}")
            sys.exit(1)

    except KeyboardInterrupt:
        logging.info("检测到 Ctrl+C，程序退出。")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"程序运行时发生未处理的异常: {e}", exc_info=True)
        sys.exit(1)

# ======================================================

# --- 程序入口 ---
if __name__ == "__main__":
    main()