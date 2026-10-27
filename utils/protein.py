import re
from config import PROTEIN_TABLE

def estimate_protein(text: str):
    if not text:
        return 0.0
    t = text.lower()
    total = 0.0
    for name, p100 in PROTEIN_TABLE.items():
        if name in t:
            # попытаемся найти кол-во грамм
            m = re.findall(r'(\d+)\s*г', t)
            if m:
                try:
                    g = float(m[0])
                    total += g * p100 / 100.0
                    continue
                except:
                    pass
            total += 30.0 * p100 / 100.0  # ориентир
    return round(total, 1)
