from app.agents.resume_integrity import *
from app.db.database import SessionLocal
from app.db.models import WorkflowRun
import json

def test_latest_resume():

    db = SessionLocal()
    run = db.query(WorkflowRun).order_by(WorkflowRun.id.desc()).first()
    db.close()

    if not run:
        print("No resume found in DB.")
        return

    text = run.document_text
    extracted_json = {}

    if run.processed_data:
        try:
            data = json.loads(run.processed_data)
            # Handle double-encoded JSON
            if isinstance(data, str):
                extracted_json = json.loads(data)
            else:
                extracted_json = data
        except:
            print("Could not parse processed_data")

    print("\n==============================")
    print("TESTING RESUME INTEGRITY LAYER")
    print("==============================")

    print("\n--- Section Presence Score ---")
    print(section_presence_score(text))

    print("\n--- Resume Density Score ---")
    print(resume_density_score(text))

    print("\n--- Garbage Score ---")
    print(garbage_ratio_score(text))

    print("\n--- Contact Score ---")
    print(contact_info_score(text))

    print("\n--- Structure Score ---")
    print(structure_score(extracted_json))

    print("\n--- Keyword Penalty ---")
    penalty, triggers = detect_keyword_penalties(text)
    print("Penalty:", penalty)
    print("Triggers:", triggers)

    print("\n--- Employment Gap ---")
    p, d = detect_employment_gaps(extracted_json)
    print("Penalty:", p)
    print("Details:", d)

    print("\n--- Overlapping Jobs ---")
    p, d = detect_overlapping_jobs(extracted_json)
    print("Penalty:", p)
    print("Details:", d)

    print("\n--- Academic Fraud ---")
    p, d = detect_impossible_academics(extracted_json)
    print("Penalty:", p)
    print("Details:", d)

    print("\n--- Future Dates ---")
    p, d = detect_future_dates(extracted_json)
    print("Penalty:", p)
    print("Details:", d)

    print("\n==============================")

if __name__ == "__main__":
    test_latest_resume()