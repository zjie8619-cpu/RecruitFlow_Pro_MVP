# backend/services/resume_parser.py
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import chardet
import pandas as pd
from PIL import Image

# optional imports (best-effort)
try:  # pragma: no cover
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None

try:  # pragma: no cover
    import docx2txt  # type: ignore
except Exception:  # pragma: no cover
    docx2txt = None

try:  # pragma: no cover
    from pdf2image import convert_from_path  # type: ignore
except Exception:  # pragma: no cover
    convert_from_path = None

try:  # pragma: no cover
    import pytesseract  # type: ignore
    from pytesseract import image_to_string  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None
    image_to_string = None

SUPPORTED_EXT = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_encoding_and_read(raw: bytes) -> str:
    enc = chardet.detect(raw).get("encoding") or "utf-8"
    try:
        return raw.decode(enc, errors="ignore")
    except Exception:
        return raw.decode("utf-8", errors="ignore")


def extract_contacts(text: str) -> Dict[str, str]:
    email = ""
    phone = ""
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if email_match:
        email = email_match.group(0)
    phone_match = re.search(r"(?<!\d)(1[3-9]\d{9})(?!\d)", text)
    if phone_match:
        phone = phone_match.group(1)
    return {"email": email, "phone": phone}


def parse_pdf(path: Path) -> Tuple[str, Dict[str, str]]:
    text = ""
    if pdfplumber:
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages)
        except Exception:
            text = ""
    text = _clean_text(text)

    if (not text or len(text) < 50) and convert_from_path and image_to_string:
        try:
            poppler_path = os.getenv("POPPLER_PATH")
            images = convert_from_path(str(path), dpi=200, poppler_path=poppler_path)
            ocr_texts: List[str] = []
            for img in images:
                ocr_texts.append(image_to_string(img, lang="chi_sim+eng"))
            text = _clean_text("\n".join(ocr_texts))
        except Exception:
            pass

    return text, extract_contacts(text)


def parse_docx(path: Path) -> Tuple[str, Dict[str, str]]:
    text = ""
    if docx2txt:
        try:
            text = docx2txt.process(str(path)) or ""
        except Exception:
            text = ""
    return _clean_text(text), extract_contacts(text)


def parse_txt(path: Path) -> Tuple[str, Dict[str, str]]:
    raw = path.read_bytes()
    text = _detect_encoding_and_read(raw)
    return _clean_text(text), extract_contacts(text)


def parse_image(path: Path) -> Tuple[str, Dict[str, str]]:
    text = ""
    if image_to_string:
        try:
            with Image.open(str(path)) as img:
                text = image_to_string(img, lang="chi_sim+eng")
        except Exception:
            text = ""
    return _clean_text(text), extract_contacts(text)


def parse_one_to_text(path: Path) -> Tuple[str, Dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".txt":
        return parse_txt(path)
    if suffix in {".jpg", ".jpeg", ".png"}:
        return parse_image(path)
    return "", {"email": "", "phone": ""}


def save_uploaded_to_tmp(uploaded_file, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(uploaded_file.name).name
    tmp_path = out_dir / filename
    tmp_path.write_bytes(uploaded_file.getbuffer())
    return tmp_path


def parse_uploaded_files_to_df(files: List, max_chars: int = 20000) -> pd.DataFrame:
    rows = []
    out_dir = Path("data/uploads")
    out_dir.mkdir(parents=True, exist_ok=True)

    cid = 1
    for uploaded in files:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in SUPPORTED_EXT:
            continue
        tmp_path = save_uploaded_to_tmp(uploaded, out_dir)
        text, contacts = parse_one_to_text(tmp_path)
        text = text[:max_chars]
        rows.append(
            {
                "candidate_id": cid,
                "file": tmp_path.name,
                "text": text,
                "text_len": len(text),
                "email": contacts.get("email", ""),
                "phone": contacts.get("phone", ""),
            }
        )
        cid += 1

    return pd.DataFrame(rows)

