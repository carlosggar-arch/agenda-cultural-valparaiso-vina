from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.public_category_rules import classify_public_category

URL="https://example.org/activities/laboratorio-de-sonidos"
DATE="2026-11-07T15:00:00-03:00"

def event():
    return {
        "id":"verified-demo",
        "title":"Laboratorio de sonidos electrónicos",
        "source_id":"verified_festival",
        "source_url":URL,
        "links":{"official":URL+"/"},
        "schedule":{"start":DATE},
        "primary_category":{"id":"otros","label":"Otros panoramas"},
        "categories":[{"id":"otros","label":"Otros panoramas"}],
        "semantics":{"source_category":{"id":"musica","label":"Música"}},
        "provenance":{"verified_category_evidence":{
            "contract":"verified-category-evidence/1",
            "authority":"verified_public_events",
            "category":{"id":"musica","label":"Música"},
            "source_id":"verified_festival","source_url":URL,
            "start":DATE,"function_id":"source-slot-demo","evidence_url":URL}},
    }

def test_bound_verified_decision_takes_precedence_over_title_inference():
    result=classify_public_category(event())
    assert result["category"]["id"]=="musica"
    assert result["evidence"][0]["kind"]=="verified_category_evidence"

def test_mismatched_or_untrusted_proof_cannot_claim_reviewed_priority():
    for field,value in [("source_id","other"),("start","2026-11-08T15:00:00-03:00"),
                        ("source_url","https://example.org/other"),("authority","external"),
                        ("contract","untrusted/1")]:
        broken=copy.deepcopy(event())
        broken["provenance"]["verified_category_evidence"][field]=value
        result=classify_public_category(broken)
        assert not any(r["kind"]=="verified_category_evidence" for r in result["evidence"]),field
    missing=event()
    del missing["provenance"]["verified_category_evidence"]
    assert not any(r["kind"]=="verified_category_evidence"
                   for r in classify_public_category(missing)["evidence"])

def test_verified_dance_alias_converges_to_existing_shared_theatre_category():
    example=event()
    example["provenance"]["verified_category_evidence"]["category"]={"id":"danza","label":"Danza"}
    example["semantics"]["source_category"]={"id":"danza","label":"Danza"}
    assert classify_public_category(example)["category"]["id"]=="teatro"

if __name__=="__main__":
    test_bound_verified_decision_takes_precedence_over_title_inference()
    test_mismatched_or_untrusted_proof_cannot_claim_reviewed_priority()
    test_verified_dance_alias_converges_to_existing_shared_theatre_category()
    print("BOUND_VERIFIED_CATEGORY_EVIDENCE_OK")
