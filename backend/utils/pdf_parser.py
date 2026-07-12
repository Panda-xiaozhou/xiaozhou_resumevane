"""
文件解析工具
============
提取 PDF、Word 文件中的纯文本内容。

支持格式：
  - PDF: PyPDF2 逐页提取
  - DOCX: python-docx 逐段落提取

已知局限：
  - PDF 图片中的文字（扫描件）需要 OCR，当前不支持
  - 复杂排版的 PDF（多栏、表格）可能提取顺序错乱
  - DOC 格式（旧版 Word）需额外处理或转为 DOCX

维护注意：
  - 新增格式支持时在此模块添加函数（如 extract_text_from_image 用 OCR）
  - 返回文本过长时需要调用方自行截断（parser_node 截断至 6000 字符）
"""
from PyPDF2 import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    """
    从 PDF 文件中提取纯文本。

    参数:
        file_path: PDF 文件绝对路径
    返回:
        所有页面文本拼接后的字符串，空白页面跳过
    """
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def extract_text_from_docx(file_path: str) -> str:
    """
    从 Word (.docx) 文件中提取纯文本。

    参数:
        file_path: DOCX 文件绝对路径
    返回:
        所有段落文本拼接后的字符串，空段落跳过
    """
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)
