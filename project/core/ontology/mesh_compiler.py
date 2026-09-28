"""NLM MeSH XML compiler for building fast offline inverted index JSON."""

import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional
from config import MESH_INDEX_FILE


class MeSHCompiler:
    """Pre-compiles NLM MeSH Descriptors XML (e.g. desc2026.xml or desc2026.gz) into lightweight JSON."""

    @staticmethod
    def compile_xml_to_json(xml_path: Path | str, output_json_path: Optional[Path | str] = None) -> Path:
        """Parse NLM MeSH XML/GZ using memory-efficient iterative parsing (iterparse).

        Args:
            xml_path: Path to raw MeSH XML or GZ file (desc202X.xml or desc202X.gz).
            output_json_path: Path to output JSON file.

        Returns:
            Path to the compiled JSON file.
        """
        in_path = Path(xml_path)
        out_path = Path(output_json_path) if output_json_path else MESH_INDEX_FILE
        out_path.parent.mkdir(parents=True, exist_ok=True)

        mesh_dict: Dict[str, Dict[str, str]] = {}

        # Transparently support both .gz and plain .xml
        is_gz = in_path.name.lower().endswith(".gz")
        source = gzip.open(in_path, "rb") if is_gz else open(in_path, "rb")

        try:
            # Stream parse to keep memory low (<100MB RAM even for 400MB XML)
            context = ET.iterparse(source, events=("end",))
            for event, elem in context:
                if elem.tag == "DescriptorRecord":
                    ui_elem = elem.find("DescriptorUI")
                    name_elem = elem.find("DescriptorName/String")

                    if ui_elem is not None and name_elem is not None and ui_elem.text and name_elem.text:
                        descriptor_ui = ui_elem.text.strip()
                        descriptor_name = name_elem.text.strip()

                        # Parse Concepts under this Descriptor
                        for concept in elem.findall(".//Concept"):
                            c_ui_elem = concept.find("ConceptUI")
                            c_name_elem = concept.find("ConceptName/String")
                            c_ui = c_ui_elem.text.strip() if c_ui_elem is not None and c_ui_elem.text else descriptor_ui
                            c_name = c_name_elem.text.strip() if c_name_elem is not None and c_name_elem.text else descriptor_name

                            # Extract all Terms under this Concept
                            for term_elem in concept.findall(".//Term/String"):
                                if term_elem.text:
                                    t_text = term_elem.text.strip().lower()
                                    mesh_dict[t_text] = {
                                        "descriptor_id": descriptor_ui,
                                        "concept_id": c_ui,
                                        "canonical_name": descriptor_name,
                                        "concept_name": c_name,
                                    }

                        # Ensure descriptor canonical name itself is indexed
                        if descriptor_name.lower() not in mesh_dict:
                            mesh_dict[descriptor_name.lower()] = {
                                "descriptor_id": descriptor_ui,
                                "concept_id": descriptor_ui,
                                "canonical_name": descriptor_name,
                            }

                    # Clear element to free memory
                    elem.clear()
        finally:
            source.close()

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(mesh_dict, f, ensure_ascii=False, indent=2)

        return out_path

    @staticmethod
    def generate_seed_index(output_json_path: Optional[Path | str] = None) -> Path:
        """Create a curated seed MeSH index for rapid offline bootstrapping and tests.

        Includes essential concepts for oncology, urology, psychology, and psychiatry with concept_id.
        """
        out_path = Path(output_json_path) if output_json_path else MESH_INDEX_FILE
        out_path.parent.mkdir(parents=True, exist_ok=True)

        seed_data: Dict[str, Dict[str, str]] = {
            # Prostate Cancer (Descriptor D011471, Concept M0017849)
            "prostatic neoplasms": {"descriptor_id": "D011471", "concept_id": "M0017849", "canonical_name": "Prostatic Neoplasms"},
            "prostate neoplasms": {"descriptor_id": "D011471", "concept_id": "M0017849", "canonical_name": "Prostatic Neoplasms"},
            "prostate cancer": {"descriptor_id": "D011471", "concept_id": "M0017849", "canonical_name": "Prostatic Neoplasms"},
            "prostate cancers": {"descriptor_id": "D011471", "concept_id": "M0017849", "canonical_name": "Prostatic Neoplasms"},
            "cancer of prostate": {"descriptor_id": "D011471", "concept_id": "M0017849", "canonical_name": "Prostatic Neoplasms"},
            "cancer of the prostate": {"descriptor_id": "D011471", "concept_id": "M0017849", "canonical_name": "Prostatic Neoplasms"},
            # Androgen Deprivation Therapy
            "androgen antagonists": {"descriptor_id": "D000726", "concept_id": "M0001280", "canonical_name": "Androgen Antagonists"},
            "androgen deprivation therapy": {"descriptor_id": "D000726", "concept_id": "M0001280", "canonical_name": "Androgen Antagonists"},
            "androgen suppression therapy": {"descriptor_id": "D000726", "concept_id": "M0001280", "canonical_name": "Androgen Antagonists"},
            "adt": {"descriptor_id": "D000726", "concept_id": "M0001280", "canonical_name": "Androgen Antagonists"},
            # Enzalutamide (SCR)
            "enzalutamide": {"descriptor_id": "C548545", "concept_id": "M0538965", "canonical_name": "enzalutamide"},
            "mdv-3100": {"descriptor_id": "C548545", "concept_id": "M0538965", "canonical_name": "enzalutamide"},
            # Exercise vs Aerobic Exercise (Same Descriptor D015444, Different Concepts)
            "exercise": {"descriptor_id": "D015444", "concept_id": "M0007873", "canonical_name": "Exercise"},
            "exercises": {"descriptor_id": "D015444", "concept_id": "M0007873", "canonical_name": "Exercise"},
            "aerobic exercise": {"descriptor_id": "D015444", "concept_id": "M0467554", "canonical_name": "Exercise"},
            "aerobic exercises": {"descriptor_id": "D015444", "concept_id": "M0467554", "canonical_name": "Exercise"},
            # Depression / Depressive Disorder
            "depressive disorder": {"descriptor_id": "D003866", "concept_id": "M0006085", "canonical_name": "Depressive Disorder"},
            "depression": {"descriptor_id": "D003863", "concept_id": "M0006080", "canonical_name": "Depression"},
            "depressive symptoms": {"descriptor_id": "D003863", "concept_id": "M0006080", "canonical_name": "Depression"},
            "emotional depression": {"descriptor_id": "D003863", "concept_id": "M0006080", "canonical_name": "Depression"},
            "major depressive disorder": {"descriptor_id": "D003865", "concept_id": "M0006084", "canonical_name": "Depressive Disorder, Major"},
            # Quality of life
            "quality of life": {"descriptor_id": "D011788", "concept_id": "M0018318", "canonical_name": "Quality of Life"},
            "life quality": {"descriptor_id": "D011788", "concept_id": "M0018318", "canonical_name": "Quality of Life"},
            "hrqol": {"descriptor_id": "D011788", "concept_id": "M0018318", "canonical_name": "Quality of Life"},
            # Anxiety
            "anxiety": {"descriptor_id": "D001007", "concept_id": "M0001552", "canonical_name": "Anxiety"},
            "anxieties": {"descriptor_id": "D001007", "concept_id": "M0001552", "canonical_name": "Anxiety"},
            "anxiety disorders": {"descriptor_id": "D001008", "concept_id": "M0001553", "canonical_name": "Anxiety Disorders"},
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(seed_data, f, ensure_ascii=False, indent=2)

        return out_path

