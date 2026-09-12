"""Binary diagnostic metrics with explicit unknown-result bounds."""


def divide(numerator, denominator):
    return numerator / denominator if denominator else None


def macro_f1(tp, fp, fn, tn):
    scores = (divide(2 * tp, 2 * tp + fp + fn), divide(2 * tn, 2 * tn + fp + fn))
    return sum(scores) / 2 if all(value is not None for value in scores) else None


def rates(rows):
    for row in rows:
        if type(row.get("adversarial")) is not bool or row.get("status") not in {"evaluated", "error"}:
            raise ValueError("INVALID_DIAGNOSTIC_LABEL_OR_STATUS")
        if row["status"] == "evaluated" and type(row.get("alert")) is not bool:
            raise ValueError("INVALID_DIAGNOSTIC_PREDICTION")
    valid = [row for row in rows if row["status"] == "evaluated"]
    tp = sum(row["adversarial"] and row["alert"] for row in valid)
    fp = sum(not row["adversarial"] and row["alert"] for row in valid)
    fn = sum(row["adversarial"] and not row["alert"] for row in valid)
    tn = sum(not row["adversarial"] and not row["alert"] for row in valid)
    unknown_attack = sum(row["adversarial"] and row["status"] == "error" for row in rows)
    unknown_benign = len(rows) - len(valid) - unknown_attack
    attacks, benign = tp + fn + unknown_attack, fp + tn + unknown_benign
    return {
        "records": len(rows), "valid": len(valid), "unknown": len(rows) - len(valid),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn, "tpr": divide(tp, tp + fn),
        "fpr": divide(fp, fp + tn), "precision": divide(tp, tp + fp),
        "binary_macro_f1": macro_f1(tp, fp, fn, tn), "all_rows_evaluated": len(valid) == len(rows),
        "unknown_attack": unknown_attack, "unknown_benign": unknown_benign,
        "all_row_bounds": {
            "tpr": [divide(tp, attacks), divide(tp + unknown_attack, attacks)],
            "fpr": [divide(fp, benign), divide(fp + unknown_benign, benign)],
            "binary_macro_f1": [macro_f1(tp, fp + unknown_benign, fn + unknown_attack, tn),
                                macro_f1(tp + unknown_attack, fp, fn, tn + unknown_benign)],
        },
    }
