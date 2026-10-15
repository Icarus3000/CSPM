# Quieter invoice continuation headers

Invoice PDFs previously repeated the firm name and invoice number across
both the top and bottom of every page after page one. Continuation headers
now show only the billing-client name at the left and the invoice date at the
right, in regular muted text. The existing first-page presentation, footer
identification, page numbering, Letter layout and financial calculations stay
unchanged.

The shared Python PDF post-processor applies this behavior on Windows and
Fedora, including draft and finalized invoices. Long client names are shortened
with an ellipsis before the date column, preserving a measured gap. Invoice
metadata is escaped in the default HTML template and decoded before it is
written as PDF text, preserving ampersands and quotation marks. The unused
legacy merge function was removed so there is one continuation-header renderer.

Focused regressions generate real multipage PDF files without WebEngine and
check header regions, footer preservation, first-page behavior, special
characters, long-name bounds and missing metadata. The installed Fedora GUI
export is separately validated with a synthetic multipage invoice outside the
sandbox; its private evidence and exact package identity are recorded after
building, without placing practice workbooks or exported invoices in Git.
