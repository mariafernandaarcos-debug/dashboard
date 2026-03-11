import pandas as pd
import json, unicodedata, re, os
import plotly.express as px
from plotly.subplots import make_subplots

CSV = 'Expor:Impor por Estado.csv'
GEO = 'mexico_states.geojson'
OUT_HTML = 'map_2022_export_import.html'
YEAR = 2022


def normalize(s):
    if s is None: return ''
    s = str(s)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[^A-Za-z0-9\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

# manual alias map for known variants -> GeoJSON canonical name
ALIAS = {
    'veracruzdeignaciodelallave': 'Veracruz',
    'veracruzdeignacio': 'Veracruz',
    'edomex': 'México',
    'estado de mexico': 'México',
    'mexico': 'México',
    'df': 'Ciudad de México',
    'distrito federal': 'Ciudad de México',
    'ciudad de mexico': 'Ciudad de México'
}


def load_data():
    # try encodings
    try:
        df = pd.read_csv(CSV, encoding='utf-8')
    except Exception:
        df = pd.read_csv(CSV, encoding='latin1')
    return df


def build_geo_index(geo):
    gi = {}
    for f in geo.get('features', []):
        props = f.get('properties', {})
        name = props.get('name') or props.get('NAME') or props.get('NOMBRE')
        if name:
            gi[normalize(name)] = name
    return gi


def map_state_name(s, geo_index):
    n = normalize(s)
    if n in geo_index:
        return geo_index[n]
    if n in ALIAS:
        return ALIAS[n]
    # try contains/token matching
    for gnorm, gname in geo_index.items():
        if n in gnorm or gnorm in n:
            return gname
        for t in gnorm.split():
            if t and t in n:
                return gname
    return None


def prepare_for_plot(df, geo_index, year=YEAR):
    # detect column names heuristically
    cols = [c.upper() for c in df.columns]
    col_state = next((c for c in df.columns if 'ESTAD' in c.upper()), 'ESTADO')
    col_val = next((c for c in df.columns if 'VAL' in c.upper()), 'VALOR')
    col_year = next((c for c in df.columns if 'AÑO' in c.upper() or 'ANO' in c.upper() or 'YEAR' in c.upper()), 'AÑO')
    col_series = next((c for c in df.columns if 'EXPORT' in c.upper() or 'IMPORT' in c.upper() or 'SERIE' in c.upper()), None)

    df_year = df[df[col_year].astype(str) == str(year)].copy()
    if col_series is None:
        raise RuntimeError('Could not detect series column in CSV')

    # aggregate
    agg = df_year.groupby([col_state, col_series])[col_val].sum().reset_index()
    # pivot
    piv = agg.pivot(index=col_state, columns=col_series, values=col_val).fillna(0)
    piv = piv.reset_index().rename(columns={col_state: 'ESTADO'})

    # map names
    mapped = []
    for _, row in piv.iterrows():
        estado = row['ESTADO']
        mapped_name = map_state_name(estado, geo_index)
        mapped.append(mapped_name)
    piv['geo_name'] = mapped
    return piv


def make_maps(piv, geo):
    # series names present
    series_cols = [c for c in piv.columns if c not in ('ESTADO', 'geo_name')]
    # ensure both Exportaciones and Importaciones present keys
    export_col = next((c for c in series_cols if 'EXPORT' in str(c).upper()), None)
    import_col = next((c for c in series_cols if 'IMPORT' in str(c).upper()), None)

    figs = []
    for col, title in [(export_col, 'Exportaciones 2022'), (import_col, 'Importaciones 2022')]:
        if col is None:
            figs.append(None)
            continue
        df_plot = piv[piv['geo_name'].notnull()].copy()
        fig = px.choropleth(df_plot,
                            geojson=geo,
                            locations='geo_name',
                            featureidkey='properties.name',
                            color=col,
                            color_continuous_scale='Greens',
                            labels={col:'Miles de dólares'},
                            title=title)
        # zoom to Mexico only: fit to locations then constrain lat/lon to Mexico envelope
        fig.update_geos(fitbounds='locations', visible=False)
        fig.update_layout(geo=dict(
            scope='north america',
            showland=True,
            landcolor='#ffffff',
            showcountries=False,
            lataxis=dict(range=[14,33]),
            lonaxis=dict(range=[-118,-86]),
            center=dict(lon=-102.5, lat=23.0)
        ))
        figs.append(fig)
    return figs


def combine_and_save(figs, out_html=OUT_HTML):
    # if both figs present, combine side-by-side using subplots
    if figs[0] and figs[1]:
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=1, cols=2, specs=[[{"type":"choropleth"}, {"type":"choropleth"}]])
        # add traces
        for i, f in enumerate(figs):
            for trace in f.data:
                # adjust colorbar for second trace to show on its side
                if i == 1 and hasattr(trace, 'colorbar'):
                    trace.colorbar = dict(title='Miles de dólares', x=0.95)
                fig.add_trace(trace, row=1, col=i+1)
        # enforce Mexico-focused geo settings for both subplots
        fig.update_layout(title_text='Exportaciones & Importaciones por Estado (2022)', height=700)
        fig.update_geos(fitbounds='locations', visible=False, row=1, col=1)
        fig.update_geos(fitbounds='locations', visible=False, row=1, col=2)
        fig.update_layout(geo=dict(lataxis=dict(range=[14,33]), lonaxis=dict(range=[-118,-86]), center=dict(lon=-102.5, lat=23.0)))
        try:
            fig.write_html(out_html)
            print('Wrote', out_html)
        except Exception as e:
            print('Could not write HTML:', e)
    else:
        # save whichever exists
        for f, name in zip(figs, ['exportaciones_2022.html', 'importaciones_2022.html']):
            if f:
                try:
                    f.write_html(name)
                    print('Wrote', name)
                except Exception as e:
                    print('Could not write', name, e)


if __name__ == '__main__':
    if not os.path.exists(CSV):
        print('CSV not found:', CSV); raise SystemExit(1)
    if not os.path.exists(GEO):
        print('GeoJSON not found:', GEO); raise SystemExit(1)

    df = load_data()
    with open(GEO, 'r', encoding='utf-8') as f:
        geo = json.load(f)
    geo_index = build_geo_index(geo)
    piv = prepare_for_plot(df, geo_index, year=YEAR)

    # report mapping status
    mapped = piv['geo_name'].notnull().sum()
    total = len(piv)
    print(f'States with data: {total}, mapped to GeoJSON: {mapped}')
    if mapped < total:
        print('Unmapped states:')
        print(piv[piv['geo_name'].isnull()]['ESTADO'].tolist())

    figs = make_maps(piv, geo)
    combine_and_save(figs)
