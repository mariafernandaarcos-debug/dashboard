import streamlit as st
import pandas as pd
import plotly.express as px
import pycountry


# Score por empresa
st.title("Score de Prioridad de Empresas Exportadoras")

df = pd.read_csv('/Users/ferarrcos/Desktop/CL CIRCULAR/analisis de riesgo.csv')

# normalize column names to strip BOM / stray whitespace
df.columns = df.columns.str.replace('\ufeff','').str.strip()

# quitar filas vacías
df = df.dropna(subset=["Empresa"])

# slider para alpha
alpha = st.slider("Importancia de Sensibilidad Térmica", 0.0, 2.0, 1.0)

# tiene o no certificado (menos riesgo)
df["FSC_riesgo"] = 1 - df["FSC 22000"]

# producto principal produce o no todo el ano
df["produccion_riesgo"] = 1 - df["Produccion_todo_el_ano"]

# normalizar variables de riesgo (1-5)
cols_riesgo = [
"Logistica_cadena_de_frio",
"FDA_FSMA",
"T-MEC"
]

for col in cols_riesgo:
    df[col+"_norm"] = (df[col] - 1) / 4

df["sens_term_norm"] = (df["Sensibilidad_Termica"] - 1) / 4

# score final
#0 = bajo riesgo, 1 = alto riesgo
df["score_logistico"] = (
    0.35 * df["Logistica_cadena_de_frio_norm"]
    + 0.25 * df["sens_term_norm"]
    + 0.20 * df["produccion_riesgo"]
    + 0.10 * df["FDA_FSMA_norm"]
    + 0.07 * df["T-MEC_norm"]
    + 0.03 * df["FSC_riesgo"]
)

# normalización ventas
df["ventas_norm"] = (
(df["Tamano_ventas(USD_B)"] - df["Tamano_ventas(USD_B)"].min())
/
(df["Tamano_ventas(USD_B)"].max() - df["Tamano_ventas(USD_B)"].min())
) + 0.05

# normalizacion dependencia USA
df["dependencia_norm"] = df["Dependencia_USA(%ventas)"] / 100

#score prioridad
df["Prioridad_raw"] = (
    df["score_logistico"]
    * df["ventas_norm"]
    * df["dependencia_norm"]
    * (1 + alpha * df["sens_term_norm"])
)

# escalar a 0-100
df["Prioridad"] = 100 * df["Prioridad_raw"] / df["Prioridad_raw"].max()

# filtro por empresa
empresa = st.selectbox("Selecciona empresa", df["Empresa"].unique())

empresa_df = df[df["Empresa"] == empresa]

st.metric(
    "Score de Prioridad",
    round(empresa_df["Prioridad"].values[0], 3)
)

# GRAFICO DE CONTRIBUCION POR RIESGO
empresa_df["riesgo_frio"] = 0.35 * empresa_df["Logistica_cadena_de_frio_norm"]
empresa_df["riesgo_termico"] = 0.25 * empresa_df["sens_term_norm"]
empresa_df["riesgo_produccion"] = 0.20 * empresa_df["produccion_riesgo"]
empresa_df["riesgo_fda"] = 0.10 * empresa_df["FDA_FSMA_norm"]
empresa_df["riesgo_tmec"] = 0.07 * empresa_df["T-MEC_norm"]
empresa_df["riesgo_fsc"] = 0.03 * empresa_df["FSC_riesgo"]

contrib = pd.DataFrame({
"Factor":[
"Cadena de frío",
"Sensibilidad térmica",
"Producción no anual",
"FDA FSMA",
"T-MEC",
"FSC22000"
],
"Contribucion":[
empresa_df["riesgo_frio"].values[0],
empresa_df["riesgo_termico"].values[0],
empresa_df["riesgo_produccion"].values[0],
empresa_df["riesgo_fda"].values[0],
empresa_df["riesgo_tmec"].values[0],
empresa_df["riesgo_fsc"].values[0]
]
})

fig = px.bar(
contrib,
x="Factor",
y="Contribucion",
color='Contribucion',
color_continuous_scale=px.colors.sequential.Greens,
title="Contribución al riesgo logístico"
)

st.plotly_chart(fig)

#MAPA MUNDIAL

st.subheader("Mapa Global de Shipments por Empresa")

# cargar datos
exports = pd.read_csv(
    '/Users/ferarrcos/Desktop/CL CIRCULAR/exportación porcentaje por empresa.csv',
    encoding='utf-8-sig'
)
# normalize column names (strip BOM / whitespace)
exports.columns = exports.columns.str.replace('\ufeff','').str.strip()

# arreglar algunos nombres comunes
fix = {
"USA":"United States",
"South Korea":"Korea, Republic of",
"Taiwan":"Taiwan, Province of China"
}

exports["pais"] = exports["pais"].replace(fix)

# función país → ISO
def get_iso3(country):
    try:
        return pycountry.countries.lookup(country).alpha_3
    except:
        return None

exports["iso"] = exports["pais"].apply(get_iso3)

# filtro por empresa
exports_empresa = exports[exports["Empresa"] == empresa]


# mapa
fig = px.choropleth(
    exports_empresa,
    locations="iso",
    color="Porcentaje",
    hover_name="pais",
    hover_data={"Porcentaje":":.2f"},
    projection="natural earth",

    # escala verde
    color_continuous_scale=px.colors.sequential.Greens
)

# diseño visual
fig.update_traces(
    marker_line_color="white",   # bordes blancos
    marker_line_width=0.7
)

fig.update_geos(
    showcountries=True,          # dibuja todos los países
    countrycolor="white",        # color del delineado
    showcoastlines=False,
    showframe=False,
    bgcolor="rgba(0,0,0,0)"
)

fig.update_layout(
    margin={"r":0,"t":0,"l":0,"b":0},
    paper_bgcolor="rgb(0,0,0,0)" ,
    plot_bgcolor="rgb(0,0,0,0)" ,
    coloraxis_colorbar=dict(title="% Shipments")
)

st.plotly_chart(fig, use_container_width=True)

# GRAFICO DE PIE
st.subheader("Market Share Global")

market = pd.read_csv(
    '/Users/ferarrcos/Desktop/CL CIRCULAR/market share.csv',
    encoding='utf-8-sig'
)
market.columns = market.columns.str.replace('\ufeff','').str.strip()

# escala de verdes para todos
greens = [
"#e8f5e9",
"#c8e6c9",
"#a5d6a7",
"#81c784",
"#66bb6a",
"#4caf50",
"#388e3c"
]

colors = []
pull = []

for i, e in enumerate(market["Empresa"]):

    if e == empresa:
        colors.append("#1b5e20")  # highlight verde oscuro
        pull.append(0.06)
    else:
        colors.append(greens[i % len(greens)])
        pull.append(0)

fig = px.pie(
    market,
    names="Empresa",
    values="Market Share",
    hole=0.55
)

fig.update_traces(
    marker=dict(
        colors=colors,
        line=dict(color="white", width=2)   # separa visualmente cada segmento
    ),
    pull=pull,
    textinfo="percent+label"
)

fig.update_layout(
    showlegend=True,
    margin=dict(t=20,b=20,l=20,r=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)"
)

st.plotly_chart(fig, use_container_width=True)