"""Multi-format document parser supporting PDF, DOCX, HTML, TXT, and Markdown."""
import os
import re
from typing import List, Dict, Any
from pypdf import PdfReader
from docx import Document as DocxDocument
from bs4 import BeautifulSoup
from backend.app.core.logging import logger


class ParsedPage:
    def __init__(self, page_number: int, text: str, section: str = ""):
        self.page_number = page_number
        self.text = text.strip()
        self.section = section


class DocumentParser:
    """Parses various file formats into structured pages/sections with metadata."""

    @staticmethod
    def parse(file_path: str, file_type: str) -> List[ParsedPage]:
        ext = file_type.lower().lstrip(".")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if ext == "pdf":
            return DocumentParser._parse_pdf(file_path)
        elif ext in ["docx", "doc"]:
            return DocumentParser._parse_docx(file_path)
        elif ext in ["html", "htm"]:
            return DocumentParser._parse_html(file_path)
        elif ext in ["txt", "md", "markdown"]:
            return DocumentParser._parse_text(file_path)
        else:
            # Fallback to plain text read
            return DocumentParser._parse_text(file_path)

    @staticmethod
    def _parse_pdf(file_path: str) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        try:
            reader = PdfReader(file_path)
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                # Clean up excessive whitespace
                cleaned_text = re.sub(r"[ \t]+", " ", text).strip()
                if cleaned_text:
                    pages.append(ParsedPage(page_number=idx + 1, text=cleaned_text))
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            raise ValueError(f"Failed to parse PDF: {str(e)}")
        return pages

    @staticmethod
    def _parse_docx(file_path: str) -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        try:
            doc = DocxDocument(file_path)
            current_section = "General"
            current_text: List[str] = []
            page_num = 1

            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                if p.style.name.startswith("Heading"):
                    current_section = text
                current_text.append(text)
                # Group roughly every 500 words as a logical page
                if sum(len(t.split()) for t in current_text) >= 500:
                    pages.append(ParsedPage(
                        page_number=page_num,
                        text="\n\n".join(current_text),
                        section=current_section
                    ))
                    current_text = []
                    page_num += 1

            if current_text:
                pages.append(ParsedPage(
                    page_number=page_num,
                    text="\n\n".join(current_text),
                    section=current_section
                ))
        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {e}")
            raise ValueError(f"Failed to parse DOCX: {str(e)}")
        return pages

    @staticmethod
    def _parse_html(file_path: str) -> List[ParsedPage]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")

            # Remove scripts and style elements
            for script_or_style in soup(["script", "style", "nav", "footer"]):
                script_or_style.decompose()

            text = soup.get_text(separator="\n")
            cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
            full_text = "\n".join(cleaned_lines)

            # Split into pseudo-pages of ~2000 characters
            pages: List[ParsedPage] = []
            step = 2000
            for i in range(0, len(full_text), step):
                chunk = full_text[i:i + step]
                pages.append(ParsedPage(
                    page_number=(i // step) + 1,
                    text=chunk,
                    section="Web Content"
                ))
            return pages if pages else [ParsedPage(page_number=1, text="")]
        except Exception as e:
            logger.error(f"Error parsing HTML {file_path}: {e}")
            raise ValueError(f"Failed to parse HTML: {str(e)}")

    @staticmethod
    def _parse_text(file_path: str) -> List[ParsedPage]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            pages: List[ParsedPage] = []
            step = 2500
            for i in range(0, max(len(content), 1), step):
                chunk = content[i:i + step]
                pages.append(ParsedPage(
                    page_number=(i // step) + 1,
                    text=chunk
                ))
            return pages
        except Exception as e:
            logger.error(f"Error parsing text {file_path}: {e}")
            raise ValueError(f"Failed to parse text: {str(e)}")
