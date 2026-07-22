# grading.py — Credit-Based Mark Distribution & Max Score Lookup Policy

# Table 3.2 Credit-Based Mark Distribution
CREDIT_DISTRIBUTION = {
    5: {
        'total': 125,
        'cca': 50,
        'ISA': 10,
        'CP': 10,
        'LB': 15,
        'LD': 15,
        'SEA1': 15,
        'SEA2': 60
    },
    4: {
        'total': 100,
        'cca': 40,
        'ISA': 10,
        'CP': 10,
        'LB': 10,
        'LD': 10,
        'SEA1': 20,
        'SEA2': 40
    },
    3: {
        'total': 75,
        'cca': 30,
        'ISA': 7.5,
        'CP': 7.5,
        'LB': 7.5,
        'LD': 7.5,
        'SEA1': 15,
        'SEA2': 30
    },
    2: {
        'total': 50,
        'cca': 20,
        'ISA': 5,
        'CP': 5,
        'LB': 5,
        'LD': 5,
        'SEA1': 10,
        'SEA2': 20
    }
}

def get_max_score_for_subject_and_exam(credits, exam_type):
    """
    Returns max score limit based on credit value and exam type.
    Defaults to 100 if credit or exam_type is missing/unrecognized.
    """
    credit_rules = CREDIT_DISTRIBUTION.get(int(credits if credits else 4))
    if not credit_rules:
        return 100.0

    return float(credit_rules.get(exam_type, 100.0))
