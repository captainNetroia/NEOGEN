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
