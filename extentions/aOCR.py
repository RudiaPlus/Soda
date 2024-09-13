from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_gpu = False,
    lang = "japan",
    max_text_length = 20
)