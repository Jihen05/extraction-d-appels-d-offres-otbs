import pytesseract
from PIL import Image

# Décommentée et activée :
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

image = Image.open("test.png")
texte = pytesseract.image_to_string(image, lang="fra")
print(texte)
