import os
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def add_page_numbers_to_pdf(pdf_path):
    """
    Reads the given PDF file, adds 'Page X of Y' to the bottom right of every page
    (except the first page), and overwrites the file.
    """
    if not os.path.exists(pdf_path):
        return

    reader = PdfReader(pdf_path)
    num_pages = len(reader.pages)
    
    if num_pages <= 1:
        return # No need to number a 1-page document
        
    writer = PdfWriter()
    
    for i in range(num_pages):
        page = reader.pages[i]
        
        if i > 0:
            # Create a temporary PDF with reportlab just for this page's number
            temp_pdf_path = f"{pdf_path}_temp_page_{i}.pdf"
            
            try:
                # Note: We use the page's mediaBox to position the text
                # assuming standard 8.5x11 (letter) for this app, but let's 
                # get exact dimensions from the page.
                box = page.mediabox
                width = float(box.width)
                height = float(box.height)
                
                c = canvas.Canvas(temp_pdf_path, pagesize=(width, height))
                c.setFont("Helvetica", 7.5)
                
                # Position: bottom right, inside the margin
                # In Concept_A, footer has right margin of ~0.5in = 36 points. 
                text = f"Page {i+1} of {num_pages}"
                text_width = c.stringWidth(text, "Helvetica", 7.5)
                
                x = width - text_width - 36  # 0.5 inch from right
                y = 24 # cleanly below the fixed footer text (padding-bottom is 50px = 37.5pt)
                
                # Match the #999999 gray color of the "In accordance with..." text
                c.setFillColorRGB(0.6, 0.6, 0.6)
                c.drawString(x, y, text)
                c.save()
                
                # Merge with the page
                overlay_reader = PdfReader(temp_pdf_path)
                overlay_page = overlay_reader.pages[0]
                page.merge_page(overlay_page)
                
            finally:
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                
        writer.add_page(page)
        
    with open(pdf_path, "wb") as f:
        writer.write(f)
