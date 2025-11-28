from PIL import Image
import pytesseract

def test_ocr_on_image(image_path):
    img = Image.open(image_path)
    custom_config = r'--oem 1 --psm 7' # 单行文本模式作为示例
    text = pytesseract.image_to_string(img, config=custom_config)
    print(f"OCR 结果:\n{text}")

test_ocr_on_image('debug_preprocessed_ocr_image.png')