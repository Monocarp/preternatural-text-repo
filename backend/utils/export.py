"""
Export module - Functions for exporting stories to various formats.

Extracted from utils_legacy.py as part of P2-1 modularization.
"""

import os
import io
import json
import base64
import zipfile
import subprocess

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ImportError:
    canvas = None
    letter = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

from utils_legacy import logger
from utils.storage import load_full_md, load_story_positions
from utils.rendering import find_book_slug


def export_stories(stories, format='md', is_single=True):
    """Export stories to markdown, PDF, or Word format."""
    try:
        format = format.lower()
        logger.debug(f"Exporting stories, format={format}, is_single={is_single}")
        content = ""
        for story in stories:
            book_slug = story.get('book_slug')
            if book_slug is None:
                book_slug = find_book_slug(story['title'])
            full_md = load_full_md(book_slug)
            title = story['title']
            pages = story['pages']
            keywords = story['keywords']
            start = story.get('start_char', 0)
            end = story.get('end_char', len(full_md))
            text = full_md[start:end]
            logger.debug(f"Exporting story '{title}' from {book_slug} with slice [{start}:{end}], text length: {len(text)}")
            content += f"# {title}\n\nSource: {book_slug.replace('_', ' ').title()}\nPages: {pages}\nKeywords: {keywords}\n\n{text}\n\n---\n\n"
        
        base_filename = "export_single" if is_single else "export_list"
        temp_md = f"/tmp/{base_filename}.md"
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(content)
        
        if format == 'md':
            filepath = temp_md
            mime = 'text/markdown'
            ext = 'md'
        elif format == 'pdf':
            filepath = f"/tmp/{base_filename}.pdf"
            try:
                subprocess.run(['pandoc', temp_md, '-o', filepath], check=True)
            except:
                logger.warning("Pandoc failed; using reportlab fallback.")
                if canvas and letter:
                    c = canvas.Canvas(filepath, pagesize=letter)
                    y = 750
                    for line in content.split('\n')[:50]:  # Limit for prototype
                        c.drawString(50, y, line[:100])
                        y -= 15
                    c.save()
                else:
                    raise RuntimeError("Neither pandoc nor reportlab available for PDF export")
            mime = 'application/pdf'
            ext = 'pdf'
        elif format == 'word':
            filepath = f"/tmp/{base_filename}.docx"
            try:
                subprocess.run(['pandoc', temp_md, '-o', filepath], check=True)
            except:
                logger.warning("Pandoc failed; using python-docx fallback.")
                if DocxDocument:
                    doc = DocxDocument()
                    doc.add_paragraph(content)
                    doc.save(filepath)
                else:
                    raise RuntimeError("Neither pandoc nor python-docx available for Word export")
            mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ext = 'docx'
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return {'mime': mime, 'data': data, 'filename': f"{base_filename}.{ext}"}
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return None


def export_updated_jsons(pending_updates):
    """Export updated story_positions.json files as a ZIP archive."""
    try:
        if not pending_updates:
            return ""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for book_slug, updates in pending_updates.items():
                original_positions = load_story_positions(book_slug).copy()
                for title, bounds in updates.items():
                    if title in original_positions:
                        for key, val in bounds.items():
                            original_positions[title][key] = val
                    else:
                        logger.warning(f"Title {title} not found in {book_slug}; skipping update.")
                json_data = json.dumps(original_positions, indent=4, ensure_ascii=False).encode('utf-8')
                zip_file.writestr(f"updated_story_positions_{book_slug}.json", json_data)
        zip_buffer.seek(0)
        data = base64.b64encode(zip_buffer.read()).decode('utf-8')
        data_uri = f"data:application/zip;base64,{data}"
        return f'<a href="{data_uri}" download="updated_story_positions.zip">Download Updated JSONs ZIP</a>'
    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        return "Export failed."
