import os
import logging
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)

class InvoiceDocumentService:
    def __init__(self, templates_dir: str):
        self.templates_dir = templates_dir
        self.jinja_env = Environment(loader=FileSystemLoader(self.templates_dir))

    def generate_html(self, template_name: str, payload: Dict[str, Any]) -> str:
        """Render an invoice as an HTML string using Jinja2."""
        template_file = f"{template_name}.html"
        try:
            template = self.jinja_env.get_template(template_file)
            return template.render(**payload)
        except Exception as e:
            logger.error(f"Failed to render HTML template {template_file}: {e}", exc_info=True)
            raise

    def generate_docx(self, template_name: str, payload: Dict[str, Any], output_path: str) -> str:
        """Render an invoice as a DOCX file using docxtpl."""
        template_file = os.path.join(self.templates_dir, f"{template_name}.docx")
        try:
            doc = DocxTemplate(template_file)
            doc.render(payload)
            doc.save(output_path)
            return output_path
        except Exception as e:
            logger.error(f"Failed to render DOCX template {template_file}: {e}", exc_info=True)
            raise
