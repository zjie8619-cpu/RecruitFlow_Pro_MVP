# backend/services/resume_parser.py
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import chardet
import fitz
import pandas as pd
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# optional imports (best-effort)
try:  # pragma: no cover
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None

try:  # pragma: no cover
    import docx2txt  # type: ignore
except Exception:  # pragma: no cover
    docx2txt = None

default_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if default_tesseract.exists():
    pytesseract.pytesseract.tesseract_cmd = str(default_tesseract)

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


def extract_pdf_text(path: Path) -> str:
    """提取PDF文本,使用多种方法确保成功"""
    text = ""
    
    # 方法1: 使用 PyMuPDF (fitz) - 最常用且快速
    try:
        doc = fitz.open(str(path))
        raw_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            # 优先使用标准文本提取
            page_text = page.get_text("text") or ""
            # 如果标准方法失败,尝试使用blocks方法
            if not page_text.strip():
                blocks = page.get_text("blocks")
                if blocks:
                    page_text = "\n".join([str(block[4]) for block in blocks if len(block) > 4 and isinstance(block[4], str)])
            raw_parts.append(page_text)
        doc.close()
        text = "\n".join(raw_parts)
        text = _clean_text(text)
        # 如果提取到足够的文本,直接返回
        if len(text.strip()) >= 50:
            return text
    except Exception as e:
        # 如果 PyMuPDF 失败,继续尝试其他方法
        pass
    
    # 方法2: 使用 pdfplumber (如果可用) - 对某些PDF格式更有效
    if pdfplumber:
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    # 如果标准提取失败,尝试提取表格和文本
                    if not page_text.strip():
                        # 尝试提取表格
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                for row in table:
                                    if row:
                                        page_text += " ".join([str(cell) if cell else "" for cell in row]) + "\n"
                    pages.append(page_text)
            new_text = "\n".join(pages)
            new_text = _clean_text(new_text)
            # 如果pdfplumber提取到更多文本,使用它
            if len(new_text.strip()) > len(text.strip()):
                text = new_text
            if len(text.strip()) >= 50:
                return text
        except Exception as e:
            # pdfplumber 也失败,继续尝试其他方法
            pass
    
    return text


def ocr_pdf(path: Path) -> str:
    """使用OCR提取PDF文本(用于扫描版PDF)"""
    try:
        poppler_path = os.getenv("POPPLER_PATH")
        # 尝试转换PDF为图片
        pages = convert_from_path(str(path), dpi=300, poppler_path=poppler_path)
        text_chunks: List[str] = []
        for page in pages:
            try:
                # 尝试中文OCR,如果失败则使用英文
                page_text = pytesseract.image_to_string(page, lang="chi_sim+eng")
                if not page_text.strip():
                    page_text = pytesseract.image_to_string(page, lang="eng")
                text_chunks.append(page_text)
            except Exception:
                # 如果OCR失败,尝试只使用英文
                try:
                    page_text = pytesseract.image_to_string(page, lang="eng")
                    text_chunks.append(page_text)
                except Exception:
                    text_chunks.append("")
        result = _clean_text("\n".join(text_chunks))
        return result
    except Exception as e:
        # OCR失败,返回空字符串
        return ""


def parse_pdf(path: Path) -> Tuple[str, Dict[str, str]]:
    """解析PDF文件,优先使用文本提取,失败时使用OCR"""
    # 首先尝试直接提取文本
    text = extract_pdf_text(path)
    
    # 如果提取的文本太少(可能是扫描版PDF),尝试OCR
    if len(text.strip()) < 100:
        ocr_text = ocr_pdf(path)
        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
            text = ocr_text
    
    # 如果仍然没有文本,尝试使用PyMuPDF的其他方法
    if not text.strip():
        try:
            doc = fitz.open(str(path))
            raw_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                # 尝试不同的文本提取方法
                page_text = page.get_text("text") or ""
                if not page_text.strip():
                    # 尝试获取原始文本
                    page_text = page.get_text("rawdict") or ""
                    if isinstance(page_text, dict):
                        page_text = str(page_text)
                raw_parts.append(page_text)
            doc.close()
            text = "\n".join(raw_parts)
            text = _clean_text(text)
        except Exception:
            pass
    
    # 提取联系信息
    contacts = extract_contacts(text)
    
    return text, contacts


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
    try:
        with Image.open(str(path)) as img:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
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
        
        # 解析文件
        text, contacts = parse_one_to_text(tmp_path)
        
        # 如果解析失败(文本为空或太短),尝试其他方法
        if not text.strip() or len(text.strip()) < 50:
            # 对于PDF文件,尝试更激进的解析方法
            if suffix == ".pdf":
                try:
                    # 再次尝试使用PyMuPDF,使用不同的参数
                    doc = fitz.open(str(tmp_path))
                    raw_parts = []
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        # 尝试多种文本提取方法
                        page_text = page.get_text("text") or ""
                        if not page_text.strip():
                            # 尝试使用blocks方法
                            blocks = page.get_text("blocks")
                            if blocks:
                                page_text = "\n".join([block[4] for block in blocks if len(block) > 4])
                        raw_parts.append(page_text)
                    doc.close()
                    text = "\n".join(raw_parts)
                    text = _clean_text(text)
                except Exception:
                    pass
        
        # 限制文本长度
        text = text[:max_chars] if text else ""
        
        rows.append(
            {
                "candidate_id": cid,
                "file": tmp_path.name,
                "resume_text": text,
                "text_len": len(text),
                "email": contacts.get("email", ""),
                "phone": contacts.get("phone", ""),
            }
        )
        cid += 1

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["candidate_id", "file", "resume_text", "text_len", "email", "phone"])

    source_columns = ["resume_text", "text", "full_text", "content", "parsed_text"]

    def _coalesce_resume_text(row):
        for col in source_columns:
            if col in row and isinstance(row[col], str) and row[col].strip():
                return row[col].strip()
        for col in source_columns:
            if col in row and row[col]:
                return str(row[col]).strip()
        return ""

    df["resume_text"] = df.apply(_coalesce_resume_text, axis=1)
    df["resume_text"] = df["resume_text"].fillna("").astype(str)
    df["text_len"] = df["resume_text"].str.len()

    drop_columns = [c for c in ["text", "full_text", "content", "parsed_text"] if c in df.columns]
    if drop_columns:
        df = df.drop(columns=drop_columns)

    return df


    return _clean_text(text), extract_contacts(text)


def parse_image(path: Path) -> Tuple[str, Dict[str, str]]:
    text = ""
    try:
        with Image.open(str(path)) as img:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
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
        
        # 解析文件
        text, contacts = parse_one_to_text(tmp_path)
        
        # 如果解析失败(文本为空或太短),尝试其他方法
        if not text.strip() or len(text.strip()) < 50:
            # 对于PDF文件,尝试更激进的解析方法
            if suffix == ".pdf":
                try:
                    # 再次尝试使用PyMuPDF,使用不同的参数
                    doc = fitz.open(str(tmp_path))
                    raw_parts = []
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        # 尝试多种文本提取方法
                        page_text = page.get_text("text") or ""
                        if not page_text.strip():
                            # 尝试使用blocks方法
                            blocks = page.get_text("blocks")
                            if blocks:
                                page_text = "\n".join([block[4] for block in blocks if len(block) > 4])
                        raw_parts.append(page_text)
                    doc.close()
                    text = "\n".join(raw_parts)
                    text = _clean_text(text)
                except Exception:
                    pass
        
        # 限制文本长度
        text = text[:max_chars] if text else ""
        
        rows.append(
            {
                "candidate_id": cid,
                "file": tmp_path.name,
                "resume_text": text,
                "text_len": len(text),
                "email": contacts.get("email", ""),
                "phone": contacts.get("phone", ""),
            }
        )
        cid += 1

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["candidate_id", "file", "resume_text", "text_len", "email", "phone"])

    source_columns = ["resume_text", "text", "full_text", "content", "parsed_text"]

    def _coalesce_resume_text(row):
        for col in source_columns:
            if col in row and isinstance(row[col], str) and row[col].strip():
                return row[col].strip()
        for col in source_columns:
            if col in row and row[col]:
                return str(row[col]).strip()
        return ""

    df["resume_text"] = df.apply(_coalesce_resume_text, axis=1)
    df["resume_text"] = df["resume_text"].fillna("").astype(str)
    df["text_len"] = df["resume_text"].str.len()

    drop_columns = [c for c in ["text", "full_text", "content", "parsed_text"] if c in df.columns]
    if drop_columns:
        df = df.drop(columns=drop_columns)

    return df

