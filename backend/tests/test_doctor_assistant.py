
import unittest

from src.services.doctor_assistant.retrieval import (
    knowledge_base_status,
    retrieve_evidence,
)
from src.LLM.doctor_assist import _normalize_response
import json
from pathlib import Path


class DoctorAssistantRetrievalTests(unittest.TestCase):
    def test_both_knowledge_bases_are_indexed(self):
        status = knowledge_base_status()
        self.assertTrue(status["available"])
        self.assertGreater(status["chunk_count"], 0)
        self.assertEqual(len(status["source_collections"]), 2)

    def test_kidney_query_returns_traceable_evidence(self):
        hits = retrieve_evidence(
            "creatinine urea BUN renal kidney glomerular filtration rate",
            top_k=5,
        )
        self.assertTrue(hits)
        self.assertTrue(any("kidney" in hit["path"].lower() for hit in hits))
        for hit in hits:
            self.assertTrue(hit["source_id"].startswith("kb_"))
            self.assertTrue(hit["path"].startswith("knowledgeBaseForLabAI/"))
            self.assertTrue(hit["excerpt"])


    def test_generated_values_are_grounded_to_report(self):
        backend = Path(__file__).resolve().parents[1]
        report_path = backend / "data/processed/preprocessing_test/Capture3-768x715_processed_normalized.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        fake = {
            "key_findings": [{
                "test_name": "Fasting Blood Glucose",
                "result": "999",
                "unit": "invented",
                "reference_range": "invented",
                "status": "above_range",
                "clinical_significance": "test",
                "evidence_sources": ["not-a-real-source"],
            }],
            "evidence_supported_pathways": [],
        }
        grounded = _normalize_response(fake, [], report)
        finding = grounded["key_findings"][0]
        self.assertEqual(finding["result"], "85")
        self.assertEqual(finding["unit"], "mg/dL")
        self.assertEqual(finding["reference_range"], "70 – 99")
        self.assertEqual(finding["status"], "within_range")
        self.assertEqual(finding["evidence_sources"], [])

    def test_retrieval_ids_are_stable(self):
        query = "hemoglobin hematocrit MCV anemia red cell indices"
        first = retrieve_evidence(query, top_k=3)
        second = retrieve_evidence(query, top_k=3)
        self.assertEqual(
            [item["source_id"] for item in first],
            [item["source_id"] for item in second],
        )


if __name__ == "__main__":
    unittest.main()
