import sys
import fitz

def check_pdf_size(pdf_path):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return False

    TARGET_WIDTH = 612.0
    TARGET_HEIGHT = 792.0
    TOLERANCE = 1.0

    all_ok = True
    for i, page in enumerate(doc):
        rect = page.rect
        w = rect.width
        h = rect.height
        if abs(w - TARGET_WIDTH) > TOLERANCE or abs(h - TARGET_HEIGHT) > TOLERANCE:
            print(f"Page {i+1} size mismatch: Expected {TARGET_WIDTH}x{TARGET_HEIGHT}, got {w}x{h}")
            all_ok = False
        else:
            print(f"Page {i+1} size OK: {w}x{h}")
            
    doc.close()
    return all_ok

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python qa_check_pdf_size.py <path_to_pdf>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    if check_pdf_size(pdf_path):
        print(f"SUCCESS: {pdf_path} is Letter size.")
        sys.exit(0)
    else:
        print(f"FAILED: {pdf_path} has incorrect dimensions.")
        sys.exit(1)
