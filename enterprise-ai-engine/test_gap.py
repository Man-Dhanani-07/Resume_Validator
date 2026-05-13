from datetime import datetime
from app.agents.resume_integrity import detect_employment_gaps, parse_date , detect_overlapping_jobs

# Mock extracted_json
test_data = {
    "experience": [
        {
            "start_date": "Jan 2018",
            "end_date": "Dec 2020"
        },
        {
            "start_date": "Jan 2020",
            "end_date": "Dec 2022"
        }
    ]
}
penalty, details = detect_employment_gaps(test_data)
overlap_penalty, overlap_details = detect_overlapping_jobs(test_data)
print("Penalty:", penalty)
print("Details:", details)
print("Overlap Penalty:", overlap_penalty)
print("Overlap Details:", overlap_details)