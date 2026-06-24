"""
NEOGEN - Outils de lecture et création de fichiers.
Formats : PDF, PPTX, DOCX (lecture + création DOCX).
Dépendances optionnelles : pypdf, python-pptx, python-docx
"""
from __future__ import annotations
import base64
import io
import os
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAPPORTS_DIR = os.path.join(BASE_DIR, "data", "rapports")
MAX_CHARS = 12000


def extraire_texte_b64(fichier_b64: str, nom: str) -> str:
    """Extrait le texte d'un fichier encodé en base64 (PDF/PPTX/DOCX/TXT)."""
    ext = nom.lower().rsplit(".", 1)[-1] if "." in nom else ""
    data = base64.b64decode(fichier_b64)
    return _extraire(data, ext, nom)


def lire_fichier_chemin(chemin: str) -> str:
    """Lit un fichier depuis un chemin local (PDF/PPTX/DOCX/TXT)."""
    if not os.path.exists(chemin):
        return f"[Fichier introuvable : {chemin}]"
    ext = chemin.lower().rsplit(".", 1)[-1] if "." in chemin else ""
    with open(chemin, "rb") as f:
        data = f.read()
    return _extraire(data, ext, os.path.basename(chemin))


def _extraire(data: bytes, ext: str, nom: str) -> str:
    if ext == "pdf":
        return _lire_pdf(data)
    if ext in ("pptx", "ppt"):
        return _lire_pptx(data)
    if ext in ("docx", "doc"):
        return _lire_docx(data)
    if ext in ("txt", "md", "csv"):
        try:
            return data.decode("utf-8", errors="replace")[:MAX_CHARS]
        except Exception:
            return "[Lecture texte échouée]"
    return f"[Format .{ext} non supporté — acceptés : PDF, PPTX, DOCX, TXT]"


def _lire_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            t = (page.extract_text() or "").strip()
            if t:
                pages.append(f"[Page {i}]\n{t}")
        return "\n\n".join(pages)[:MAX_CHARS] or "[PDF sans texte extractible]"
    except ImportError:
        return "[pypdf non installé — rebuild Docker requis]"
    except Exception as e:
        return f"[Erreur lecture PDF : {e}]"


def _lire_pptx(data: bytes) -> str:
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        slides = []
        for i, slide in enumerate(prs.slides, 1):
            textes = [s.text.strip() for s in slide.shapes if hasattr(s, "text") and s.text.strip()]
            if textes:
                slides.append(f"[Diapo {i}]\n" + "\n".join(textes))
        return "\n\n".join(slides)[:MAX_CHARS] or "[PPTX sans texte extractible]"
    except ImportError:
        return "[python-pptx non installé — rebuild Docker requis]"
    except Exception as e:
        return f"[Erreur lecture PPTX : {e}]"


def _lire_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paras)[:MAX_CHARS] or "[DOCX sans texte extractible]"
    except ImportError:
        return "[python-docx non installé — rebuild Docker requis]"
    except Exception as e:
        return f"[Erreur lecture DOCX : {e}]"


def creer_rapport_pdf(titre: str, contenu: str) -> str | None:
    """Crée un rapport PDF structuré. Retourne le nom de fichier ou None si fpdf2 absent."""
    try:
        from fpdf import FPDF
    except ImportError:
        return None
    os.makedirs(RAPPORTS_DIR, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, (titre or "Rapport NEOGEN").encode("latin-1", "replace").decode("latin-1"))
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    for ligne in contenu.splitlines():
        if ligne.startswith("## ") or ligne.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            texte = ligne.lstrip("#").strip()
            pdf.multi_cell(0, 8, texte.encode("latin-1", "replace").decode("latin-1"))
            pdf.set_font("Helvetica", size=11)
        elif ligne.strip():
            pdf.multi_cell(0, 7, ligne.encode("latin-1", "replace").decode("latin-1"))
        else:
            pdf.ln(3)
    nom = f"rapport_{uuid.uuid4().hex[:8]}.pdf"
    pdf.output(os.path.join(RAPPORTS_DIR, nom))
    return nom


def creer_rapport_excel(titre: str, contenu: str) -> str | None:
    """Crée un fichier Excel à partir de contenu tabulaire (CSV ou lignes séparées par |).
    Retourne le nom de fichier ou None si openpyxl absent."""
    try:
        from openpyxl import Workbook
    except ImportError:
        return None
    os.makedirs(RAPPORTS_DIR, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = (titre or "Données")[:31]
    lignes = [l for l in contenu.splitlines() if l.strip()]
    for row_idx, ligne in enumerate(lignes, 1):
        if "|" in ligne:
            cellules = [c.strip() for c in ligne.split("|") if c.strip()]
        elif "," in ligne:
            import csv as _csv
            import io as _io
            cellules = next(_csv.reader(_io.StringIO(ligne)))
        else:
            cellules = [ligne.strip()]
        for col_idx, val in enumerate(cellules, 1):
            ws.cell(row=row_idx, column=col_idx, value=val)
    nom = f"rapport_{uuid.uuid4().hex[:8]}.xlsx"
    wb.save(os.path.join(RAPPORTS_DIR, nom))
    return nom


def creer_rapport_csv(titre: str, contenu: str) -> str | None:
    """Crée un fichier CSV. Retourne le nom de fichier."""
    os.makedirs(RAPPORTS_DIR, exist_ok=True)
    nom = f"rapport_{uuid.uuid4().hex[:8]}.csv"
    with open(os.path.join(RAPPORTS_DIR, nom), "w", encoding="utf-8-sig", newline="") as f:
        if titre:
            f.write(f"# {titre}\n")
        f.write(contenu)
    return nom


def creer_rapport_docx(titre: str, contenu: str) -> str | None:
    """Crée un rapport DOCX structuré. Retourne le nom de fichier ou None si erreur."""
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        return None
    os.makedirs(RAPPORTS_DIR, exist_ok=True)
    doc = Document()
    doc.add_heading(titre or "Rapport NEOGEN", level=1)
    for ligne in contenu.splitlines():
        if ligne.startswith("### "):
            doc.add_heading(ligne[4:], level=3)
        elif ligne.startswith("## "):
            doc.add_heading(ligne[3:], level=2)
        elif ligne.startswith("# "):
            doc.add_heading(ligne[2:], level=1)
        elif ligne.strip():
            doc.add_paragraph(ligne)
    nom = f"rapport_{uuid.uuid4().hex[:8]}.docx"
    doc.save(os.path.join(RAPPORTS_DIR, nom))
    return nom
