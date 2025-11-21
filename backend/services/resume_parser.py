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

try:  # pragma: no cover
    from docx import Document  # type: ignore
except Exception:  # pragma: no cover
    Document = None

import zipfile
from xml.etree import ElementTree

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
    """提取联系方式，兼容含空格/连字符的手机号与被分隔的邮箱"""
    clean_text = text or ""
    # 邮箱：允许中间有空格或换行，通过移除空白后再匹配
    email = ""
    compact_email_text = re.sub(r"\s+", "", clean_text)
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", compact_email_text)
    if email_match:
        email = email_match.group(0)
    else:
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", clean_text)
        if email_match:
            email = email_match.group(0)

    # 手机号：允许空格、短横线、点号作为分隔
    phone = ""
    phone_pattern = re.compile(r"(?:\+?86[-\s.]*)?(1[3-9]\d)[-\s.]*([\d][-\s.]?){8}")
    match = phone_pattern.search(clean_text)
    if match:
        digits = re.sub(r"[^\d]", "", match.group(0))
        if digits.startswith("86") and len(digits) > 11:
            digits = digits[-11:]
        phone = digits
    else:
        phone_match = re.search(r"(?<!\d)(1[3-9]\d{9})(?!\d)", clean_text)
        if phone_match:
            phone = phone_match.group(1)

    return {"email": email.strip(), "phone": phone.strip()}


NAME_PATTERNS = [
    re.compile(r"(?:姓名|Name)[:：\s]*([\u4e00-\u9fa5·]{2,8})"),
    re.compile(r"^([\u4e00-\u9fa5·]{2,8})[，,。\s]*(?:男|女)\b", re.MULTILINE),
    re.compile(r"^\s*([\u4e00-\u9fa5·]{2,6})\s*(?:\d{2}|19|20)\d{2}", re.MULTILINE),
]

NAME_STOP_WORDS = {
    "课程顾问",
    "顾问",
    "老师",
    "班主任",
    "物理竞赛",
    "数学竞赛",
    "岗位",
    "职位",
    "简历",
    "应聘",
    "求职",
    "个人简历",
    "教育经历",
    "教育背景",
    "工作经历",
    "项目经历",
    "联系方式",
    "联系",
    "电话",
    "邮箱",
    "面试",
    "面销",
    "机构",
    "尚德机构",
    "成长经历",
    "性别",
    "男",
    "女",
    "联系方法",
    "联系方式",
    "联系方式：",
}

NAME_DISALLOWED_SUBSTRINGS = {
    "课程",
    "规划",
    "机构",
    "方式",
    "渠道",
    "顾问",
    "老师",
    "教师",
    "教练",
    "班主任",
    "校长",
    "院长",
    "主任",
    "经理",
    "主管",
    "教育",
    "经历",
    "背景",
    "信息",
    "简历",
    "职位",
    "岗位",
    "招聘",
    "面试",
    "面销",
    "求职",
    "联系",
}

STOP_LINE_KEYWORDS = {
    "联系方式",
    "联系",
    "电话",
    "邮箱",
    "机构",
    "教育经历",
    "教育背景",
    "项目经历",
    "工作经历",
    "自我评价",
    "面试",
    "面销",
    "性别",
    "籍贯",
    "婚姻",
    "出生日期",
    "出生年月",
}

JOB_KEYWORDS = {
    "老师",
    "教师",
    "教练",
    "班主任",
    "顾问",
    "校长",
    "经理",
    "主管",
    "班主任",
    "数学",
    "物理",
    "英语",
    "语文",
    "化学",
    "政治",
    "历史",
    "地理",
    "生物",
    "体育",
    "课程",
    "招生",
}

FILENAME_NAME_PATTERNS = [
    re.compile(r"(?:姓名|name|Name)[\s:_-]*([\u4e00-\u9fa5·]{2,6})"),
    re.compile(r"([\u4e00-\u9fa5·]{2,4})\s*(?:\d{1,2}年)"),
    re.compile(r"([\u4e00-\u9fa5·]{2,4})(?:简历|求职|面试|作品)"),
]

CITY_WORDS = {"北京", "上海", "广州", "深圳", "杭州", "西安", "成都", "重庆", "苏州", "南京"}


def _is_valid_name(token: str) -> bool:
    if not token:
        return False
    if not (2 <= len(token) <= 6):
        return False
    if token in NAME_STOP_WORDS or token in CITY_WORDS:
        return False
    for substr in NAME_DISALLOWED_SUBSTRINGS:
        if substr in token:
            return False
    return True


def _extract_name_from_text(text: str) -> str:
    if not text:
        return ""
    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if match and _is_valid_name(match.group(1)):
            return match.group(1)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    candidates: List[Tuple[str, float]] = []

    def _line_score(line: str) -> float:
        score = 0.0
        if "姓名" in line or "Name" in line:
            score += 3
        if re.search(r"(男|女)", line):
            score += 1
        if any(keyword in line for keyword in ("基本信息", "个人信息", "联系方式", "联系方式：")):
            score += 1.5
        if re.search(r"\d{2}岁|\d{4}年", line):
            score += 0.5
        return score

    for line in lines[:40]:
        if any(keyword in line for keyword in STOP_LINE_KEYWORDS):
            continue
        tokens = re.findall(r"[\u4e00-\u9fa5·]{2,6}", line)
        score = _line_score(line)
        for token in tokens:
            if _is_valid_name(token):
                candidates.append((token, score))

    if candidates:
        candidates.sort(key=lambda x: (x[1], len(x[0])), reverse=True)
        best = candidates[0]
        if best[1] >= 1:
            return best[0]
    return ""


def _extract_name_from_filename(filename: str) -> str:
    raw_stem = Path(filename).stem
    # 常见形式：...】姓名_x年 / ...]姓名
    direct_match = re.search(r"[】\]]\s*([\u4e00-\u9fa5·]{2,6})", raw_stem)
    if direct_match:
        candidate = direct_match.group(1)
        if _is_valid_name(candidate):
            return candidate

    stem = raw_stem
    # 去除首尾括号包裹的标签
    stem = re.sub(r"^[\[\(（【].*?[\]\)）】]", "", stem).strip()
    stem = re.sub(r"[\(\（][^)\）]*[\)\）]", " ", stem)
    stem = stem.replace("_", " ").replace("-", " ").replace("（", " ").replace("）", " ")
    stem = re.sub(r"[【】\[\]\(\)（）]", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = stem.lstrip("】] ")
    for pattern in FILENAME_NAME_PATTERNS:
        match = pattern.search(stem)
        if match:
            candidate = match.group(1)
            if _is_valid_name(candidate):
                return candidate

    # 评分策略：越靠近末尾、后接“年/岁/简历”等词得分越高
    tokens = list(re.finditer(r"[\u4e00-\u9fa5·]{2,6}", stem))
    scored: List[Tuple[str, float]] = []
    for match in tokens:
        token = match.group(0)
        if not _is_valid_name(token):
            continue
        start = match.start()
        end = match.end()
        score = 1.0
        if len(stem) - end < 8:
            score += 1.5
        if re.match(r"(?:\d{1,2}年|\d{1,2}岁)", stem[end:end + 3]):
            score += 1.5
        if any(keyword in stem[max(0, start - 4):end + 4] for keyword in ("姓名", "name", "Name")):
            score += 2
        prev_chunk = stem[max(0, start - 6):start]
        if any(keyword in prev_chunk for keyword in JOB_KEYWORDS):
            score -= 1.5
        scored.append((token, score))
    if scored:
        scored.sort(key=lambda x: x[1], reverse=True)
        if scored[0][1] >= 1.5:
            return scored[0][0]

    # 若仍无法识别，反向遍历中文片段
    chinese_chunks = re.findall(r"[\u4e00-\u9fa5·]+", stem)
    if chinese_chunks:
        for chunk in reversed(chinese_chunks):
            chunk = chunk.strip()
            if not chunk:
                continue
            # 优先使用 2-4 位的尾部片段
            for size in range(4, 1, -1):
                if len(chunk) >= size:
                    candidate = chunk[-size:]
                    if _is_valid_name(candidate):
                        return candidate
    return ""


def infer_candidate_name(text: str, filename: str) -> str:
    name = _extract_name_from_text(text)
    if name:
        return name
    return _extract_name_from_filename(filename)


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
    if (not text or len(text.strip()) < 20) and Document:
        try:
            doc = Document(str(path))
            parts = []
            for para in doc.paragraphs:
                if para.text:
                    parts.append(para.text)
            for table in getattr(doc, "tables", []):
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text]
                    if cells:
                        parts.append(" ".join(cells))
            text = "\n".join(parts)
        except Exception:
            pass
    if not text or len(text.strip()) < 20:
        text = _extract_docx_via_xml(path)
    cleaned = _clean_text(text)
    return cleaned, extract_contacts(cleaned)


def _extract_docx_via_xml(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ElementTree.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for para in root.findall(".//w:p", ns):
            texts = [node.text for node in para.findall(".//w:t", ns) if node.text]
            if texts:
                paragraphs.append("".join(texts))
        return "\n".join(paragraphs)
    except Exception:
        return ""


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
        candidate_name = infer_candidate_name(text, tmp_path.name)
        
        rows.append(
            {
                "candidate_id": cid,
                "file": tmp_path.name,
                "name": candidate_name,
                "resume_text": text,
                "text_len": len(text),
                "email": contacts.get("email", ""),
                "phone": contacts.get("phone", ""),
            }
        )
        cid += 1

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["candidate_id", "file", "name", "resume_text", "text_len", "email", "phone"])

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

