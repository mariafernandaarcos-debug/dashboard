#!/usr/bin/env python3
"""
Genera una tarjeta HTML con el total de viajes en 2025 para una empresa.

Uso:
  python show_trips_card.py --csv "Viajes por empresa.csv" --empresa "Nombre Empresa" --out trips_card.html

El script intenta usar pandas si está disponible, sino usa el módulo csv.
"""
import argparse
import html
import os
import sys

def read_csv_fallback(path):
    import csv
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows

def load_csv(path):
    try:
        import pandas as pd
        df = pd.read_csv(path, dtype=str, encoding='utf-8')
        df = df.fillna('')
        return df.to_dict(orient='records')
    except Exception:
        return read_csv_fallback(path)

def normalize_key(k):
    return str(k).strip().lower()

def find_key(keys, candidates):
    low = {normalize_key(k):k for k in keys}
    for c in candidates:
        if c in low:
            return low[c]
    return None

def sum_trips_for_2025(rows, empresa_name):
    if not rows:
        return 0
    keys = list(rows[0].keys())
    k_empresa = find_key(keys, ['empresa','company','company name','nombre','name'])
    k_year = find_key(keys, ['año','ano','año','year','year\n','year '])
    # possible numeric columns
    k_count = find_key(keys, ['viajes','trips','count','cantidad','numero','num','n'])

    empresa_lower = empresa_name.strip().lower()
    filtered = []
    for r in rows:
        # match company
        val = ''
        if k_empresa:
            val = str(r.get(k_empresa,'')).strip().lower()
        else:
            # try any field that contains the empresa name
            for v in r.values():
                if isinstance(v, str) and empresa_lower and empresa_lower == v.strip().lower():
                    val = v.strip().lower(); break
        if not val or val != empresa_lower:
            continue
        # filter by year if present
        if k_year:
            y = str(r.get(k_year,'')).strip()
            if y and not y.startswith('2025'):
                continue
        filtered.append(r)

    if not filtered:
        return 0

    if k_count:
        total = 0
        for r in filtered:
            try:
                total += int(float(str(r.get(k_count,0)).replace(',','') or 0))
            except Exception:
                pass
        return total

    # no explicit count column: treat each row as a trip
    return len(filtered)

def render_html(company, trips_count, out_path):
    safe_company = html.escape(company)
    safe_count = html.escape(f"{trips_count:,}")
    html_doc = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Viajes {safe_company} 2025</title>
  <style>
    body{{font-family:Inter,Arial,Helvetica,sans-serif;background:#f6fbf7;margin:20px}}
    .card{{background:#fff;padding:18px;border-radius:10px;box-shadow:0 8px 24px rgba(11,107,79,0.06);display:flex;align-items:center;justify-content:space-between}}
    .label{{font-weight:700;color:#2f4f3f}}
    .value{{font-size:38px;font-weight:800;color:#0b6b4f}}
    .unit{{font-size:13px;color:#6b8b7a}}
  </style>
</head>
<body>
  <div class="card">
    <div>
      <div class="label">Viajes realizados por {safe_company} en 2025:</div>
    </div>
    <div style="text-align:right">
      <div class="value">{safe_count}</div>
      <div class="unit">viajes</div>
    </div>
  </div>
</body>
</html>
'''
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_doc)

def main():
    p = argparse.ArgumentParser(description='Genera tarjeta HTML con viajes 2025 por empresa')
    p.add_argument('--csv', default='Viajes por empresa.csv', help='Ruta al CSV de viajes')
    p.add_argument('--empresa', '-e', required=True, help='Nombre exacto de la empresa a buscar')
    p.add_argument('--out', default='trips_card.html', help='Archivo HTML de salida')
    args = p.parse_args()

    if not os.path.exists(args.csv):
        print('CSV no encontrado:', args.csv, file=sys.stderr); sys.exit(2)

    rows = load_csv(args.csv)
    total = sum_trips_for_2025(rows, args.empresa)
    render_html(args.empresa, total, args.out)
    print('Generado', args.out, '->', total, 'viajes')

if __name__ == '__main__':
    main()
