import re
import os

path = r"c:\Projects\__CSPM\src\python\backend\controllers\billing_controller.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_method = """
    @Slot(str, str)
    def exportHtmlToPdf(self, html_content: str, output_path: str):
        \"\"\"Generates a PDF explicitly sized as Letter using a 2-pass method for perfect footers.\"\"\"
        try:
            from PySide6.QtWebEngineCore import QWebEnginePage
            from PySide6.QtGui import QPageLayout, QPageSize
            from PySide6.QtCore import QMarginsF
            import fitz
            import tempfile
            
            if not hasattr(self, '_pdf_state'):
                self._pdf_state = {}
                
            temp_dir = tempfile.gettempdir()
            pass1_path = os.path.join(temp_dir, "pass1.pdf")
            pass2_path = os.path.join(temp_dir, "pass2.pdf")
            
            page1 = QWebEnginePage()
            page2 = QWebEnginePage()
            self._pdf_state['page1'] = page1
            self._pdf_state['page2'] = page2
            
            layout = QPageLayout(
                QPageSize(QPageSize.Letter),
                QPageLayout.Portrait,
                QMarginsF(0, 0, 0, 0)
            )
            
            def finalize_merge():
                try:
                    doc1 = fitz.open(pass1_path)
                    doc2 = fitz.open(pass2_path)
                    final_doc = fitz.open()
                    
                    total_pages = doc1.page_count
                    if total_pages > 1:
                        final_doc.insert_pdf(doc1, to_page=total_pages - 2)
                        final_doc.insert_pdf(doc2, from_page=total_pages - 1, to_page=total_pages - 1)
                    else:
                        final_doc.insert_pdf(doc2)
                        
                    final_doc.save(output_path)
                    final_doc.close()
                    doc1.close()
                    doc2.close()
                    self.toast.emit(f"Exported to {output_path}")
                except Exception as e:
                    self.error.emit(f"Failed to merge PDFs: {e}")
                finally:
                    if 'page1' in self._pdf_state:
                        self._pdf_state['page1'].deleteLater()
                        del self._pdf_state['page1']
                    if 'page2' in self._pdf_state:
                        self._pdf_state['page2'].deleteLater()
                        del self._pdf_state['page2']
            
            printed = {"pass1": False, "pass2": False}
            def check_done():
                if printed["pass1"] and printed["pass2"]:
                    finalize_merge()
            
            def on_pdf1_printed(filepath, success):
                printed["pass1"] = success
                check_done()
                
            def on_pdf2_printed(filepath, success):
                printed["pass2"] = success
                check_done()
            
            page1.pdfPrintingFinished.connect(on_pdf1_printed)
            page2.pdfPrintingFinished.connect(on_pdf2_printed)
            
            def on_load1_finished(ok):
                if ok: page1.printToPdf(pass1_path, layout)
                else: self.error.emit("Failed to load pass1 HTML")
                
            def on_load2_finished(ok):
                if ok: page2.printToPdf(pass2_path, layout)
                else: self.error.emit("Failed to load pass2 HTML")
                
            page1.loadFinished.connect(on_load1_finished)
            page2.loadFinished.connect(on_load2_finished)
            
            html1 = html_content.replace('</head>', '<style>.footer-final-wrapper { display: none !important; } .footer-intermediate { display: flex !important; }</style></head>')
            html2 = html_content.replace('</head>', '<style>.footer-final-wrapper { display: flex !important; } .footer-intermediate { display: none !important; }</style></head>')
            
            page1.setHtml(html1)
            page2.setHtml(html2)
            
        except Exception as exc:
            self.error.emit(f"Could not initialize PDF export: {exc}")
"""

target = "    # ── List Drafts ──────────────────────────────────────────────────────────"
if target in content:
    content = content.replace(target, new_method + "\n" + target)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched successfully.")
else:
    print("Target not found.")
