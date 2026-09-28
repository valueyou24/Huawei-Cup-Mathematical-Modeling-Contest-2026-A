"""Structural QA for the generated paper when no DOCX renderer is installed."""
from pathlib import Path
import zipfile
from lxml import etree
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"通用神经网络处理器下的多核调度优化模型_论文.docx"
doc=Document(P)
text="\n".join(p.text for p in doc.paragraphs)
assert len(doc.sections)==2
assert len(doc.tables)>=6
assert len(doc.inline_shapes)==6
assert "徐铭言" not in text and "汤思情" not in text and "温雪元" not in text
assert "通用神经网络处理器下的多核调度优化模型" in "".join(text.split())
assert "case_100" in "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
with zipfile.ZipFile(P) as z:
    bad=z.testzip(); assert bad is None
    names=set(z.namelist()); xml=z.read("word/document.xml")
    etree.fromstring(xml)
    media=[n for n in names if n.startswith("word/media/")]
    rels=etree.fromstring(z.read("word/_rels/document.xml.rels"))
    ids={r.get("Id") for r in rels}
    used=set()
    root=etree.fromstring(xml)
    ns={"r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    used.update(root.xpath("//@r:embed",namespaces=ns)); used.update(root.xpath("//@r:id",namespaces=ns))
    missing=used-ids; assert not missing,missing
print({"paragraphs":len(doc.paragraphs),"tables":len(doc.tables),"inline_images":len(doc.inline_shapes),"sections":len(doc.sections),"media_files":len(media),"text_chars":len(text),"size_bytes":P.stat().st_size})
