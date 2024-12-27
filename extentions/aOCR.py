from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_gpu = True,
    lang = "japan",
    max_text_length = 20
)