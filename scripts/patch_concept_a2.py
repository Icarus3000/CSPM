import re
import os

path = r"c:\Projects\__CSPM\src\templates\invoices\Concept_A2.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add @page rule to <style>
if "@page {" not in content:
    content = content.replace("<style>", "<style>\n    @page {\n        size: Letter portrait;\n        margin: 0;\n    }\n")

# 2. Extract footer-intermediate and footer-final-wrapper
inter_match = re.search(r'<div class="footer-intermediate">.*?</div>', content, re.DOTALL)
final_match = re.search(r'<div class="footer-final-wrapper">.*?</div>\s*</div>', content, re.DOTALL)

if inter_match and final_match:
    inter_html = inter_match.group(0)
    final_html = final_match.group(0)
    
    # Remove them from their original locations
    content = content.replace(inter_html, "")
    content = content.replace(final_html, "")
    
    # Replace the tfoot content with a spacer
    tfoot_old = re.search(r'<tfoot>.*?</tfoot>', content, re.DOTALL)
    if tfoot_old:
        content = content.replace(tfoot_old.group(0), '<tfoot>\n        <tr>\n            <td style="height: 1.6in; border: none;"></td>\n        </tr>\n    </tfoot>')

    # Modify the extracted footers to have absolute positioning and insert them before </body>
    # Wait, the intermediate footer was inside `footer-container` maybe? No, it was directly under `body` in v6, but wait...
    # In my regex, I grabbed them.
    # Let's wrap them in a container that sits at the bottom
    
    new_footers = f"""
    <!-- Fixed Footers for PDF 2-pass Generation -->
    <div class="footer-intermediate" style="position: fixed; bottom: 0.45in; left: 0.8in; right: 0.8in; z-index: 5; display: flex; justify-content: space-between; font-size: 8pt; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; border-top: 1px solid var(--border-color); padding-top: 0.15in;">
        <span><strong>Cory Schneider Law Office</strong> &nbsp;&nbsp;&middot;&nbsp;&nbsp; Invoice {{{{ invoice_number_raw }}}}</span>
        <span>Page <span class="page-number" style="counter-increment: page; content: counter(page);"></span></span>
    </div>
    
    <div class="footer-final-wrapper" style="position: fixed; bottom: 0.45in; left: 0.8in; right: 0.8in; z-index: 10; background: white; border-top: 1px solid var(--border-color); padding-top: 0.15in; display: none;">
        <div class="footer-line" style="display: flex; justify-content: space-between; font-size: 8pt; color: var(--text-main); font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.05in;">
            <span><strong>Cory Schneider Law Office</strong> &nbsp;&nbsp;&middot;&nbsp;&nbsp; 14 Parsons Court, Thornhill, ON L4J 6Z4</span>
            <span>416-725-9364 &nbsp;&nbsp;&middot;&nbsp;&nbsp; cory@coryschneiderlaw.ca</span>
        </div>
        <div class="footer-line" style="display: flex; justify-content: space-between; font-size: 8pt; color: #64748B; margin-bottom: 0.1in;">
            <span>HST No. 78621 8222 RT0001</span>
            <span>For wire, cheque, or other payment arrangements, please contact the firm.</span>
        </div>
        <div class="interest-clause" style="font-size: 7.5pt; color: #94A3B8; line-height: 1.3; text-align: justify; text-align-last: center;">In accordance with s. 33 of the <em>Solicitors Act</em> (Ontario), interest will be charged at 3.0% per annum on unpaid amounts starting one month after delivery. E-transfer payments may be directed to cory@coryschneiderlaw.ca.</div>
    </div>
"""
    content = content.replace("</body>", new_footers + "\n</body>")
    
    # Also fix the CSS for .page-number
    if ".page-number::after" not in content:
        content = content.replace("</style>", "    .page-number::after { content: counter(page); }\n</style>")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Concept_A2 patched successfully.")
