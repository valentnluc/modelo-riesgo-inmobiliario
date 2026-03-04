"""
Modelo de Riesgo Inmobiliario - Aplicación Streamlit.

Vista unificada con misma estructura para determinístico y Monte Carlo.
"""

import streamlit as st
import model
import viz
from constants import format_currency, format_percent
from presets import VENTAS_PRESETS, COSTOS_PRESETS, TIERRA_PRESETS


# CONFIGURACIÓN

st.set_page_config(
    page_title="Modelo de Riesgo Inmobiliario", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def cargar_css():
    """Carga el tema Core Infra"""
    try:
        with open('styles/core_infra.css') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

cargar_css()


# HELPERS

def crear_inputs_curva(prefix: str, duration: int, defaults: dict = None) -> dict:
    defaults = defaults or {}
    col1, col2 = st.columns(2)
    with col1:
        mode = st.slider("Mes Pico", 0, int(duration), defaults.get('moda', int(duration/2)), key=f"{prefix}_mode")
        alpha = st.number_input("Asimetria", value=defaults.get('alpha', 0.0), step=0.1, key=f"{prefix}_alpha")
    with col2:
        scale = st.number_input("Dispersion", value=defaults.get('scale', 5.0), min_value=0.1, step=0.5, key=f"{prefix}_scale")
    return {'moda': mode, 'alpha': alpha, 'scale': scale}


# =============================================================================
# HEADER
# =============================================================================

st.title("Modelo de Riesgo Inmobiliario")
st.markdown("---")


# SIDEBAR

st.sidebar.header("Configuracion")

sim_type = "Monte Carlo"
is_mc = True

# --- Proyecto ---
with st.sidebar.expander("1. Proyecto", expanded=True):
    m2_terreno = st.number_input("Superficie (m2)", value=350.0, step=50.0, min_value=1.0)
    fot = st.number_input("FOT", value=3.5, step=0.1, min_value=0.1)
    efficiency = st.number_input("Eficiencia Vendible", value=0.80, min_value=0.5, max_value=1.0, step=0.01)
    
    # Visual feedback only - calculation moved to Model
    m2_construidos = m2_terreno * fot
    sup_vendible = m2_construidos * efficiency
    st.caption(f"Construible: {m2_construidos:,.0f} m2 | Vendible: {sup_vendible:,.0f} m2")

# --- Cronograma ---
with st.sidebar.expander("2. Cronograma", expanded=True):
    duracion_proy = st.number_input("Duracion (meses)", value=36, step=6, min_value=6)
    col1, col2 = st.columns(2)
    inicio_obra = col1.number_input("Inicio Obra", value=0, step=1, min_value=0)
    duracion_obra = col2.number_input("Duracion Obra", value=30, step=1, min_value=1)

# --- Ventas ---
ventas_preset_dict = None
ventas_custom_dict = None

with st.sidebar.expander("3. Ventas", expanded=False):
    avg_price = st.number_input("Precio (USD/m2)", value=1800.0, step=50.0, min_value=1.0)
    # Visual feedback based on raw calc (actual value managed by Config)
    total_sales_raw = sup_vendible * avg_price
    st.caption(f"Total Bruto: {format_currency(total_sales_raw)}")
    
    sales_mode = st.selectbox("Distribucion", ["Preset", "Personalizada"])
    if sales_mode == "Preset":
        sales_preset_key = st.selectbox("Preset", list(VENTAS_PRESETS.keys()))
        ventas_preset_dict = VENTAS_PRESETS[sales_preset_key].copy()
        
        # Caption extendido
        st.caption(f"{ventas_preset_dict['descripcion']}")
        
        # Graficar preset
        from presets import generar_curva_ventas
        p = {**ventas_preset_dict, 'area_n': total_sales_raw}
        x, y = generar_curva_ventas(p, (0, int(duracion_proy)))
        st.altair_chart(viz.get_single_preset_chart(x, y, '#3B82F6', 'Ventas'), use_container_width=True)
        
    else:
        curve_p = crear_inputs_curva("ventas", duracion_proy)
        ventas_custom_dict = curve_p.copy()
        from presets import generar_curva_ventas
        p = {**ventas_custom_dict, 'area_n': total_sales_raw}
        x, y = generar_curva_ventas(p, (0, int(duracion_proy)))
        st.altair_chart(viz.get_single_preset_chart(x, y, '#3B82F6', 'Ventas'), use_container_width=True)

# --- Costos ---
costos_preset_dict = None
costos_custom_dict = None

with st.sidebar.expander("4. Costos", expanded=False):
    cost_m2 = st.number_input("Costo (USD/m2)", value=950.0, step=50.0, min_value=1.0)
    total_capex = m2_construidos * cost_m2
    st.caption(f"CAPEX Estimado: {format_currency(total_capex)}")
    
    cost_mode = st.selectbox("Distribucion", ["Preset", "Personalizada"], key="cost_mode")
    if cost_mode == "Preset":
        cost_preset_key = st.selectbox("Preset", list(COSTOS_PRESETS.keys()), key="cost_preset")
        costos_preset_dict = COSTOS_PRESETS[cost_preset_key].copy()
        st.caption(costos_preset_dict['descripcion'])
        
        # Graficar preset
        from presets import generar_curva_inversion
        p = {**costos_preset_dict, 'limite_n': total_capex}
        x, y = generar_curva_inversion(p, (int(inicio_obra), int(inicio_obra) + int(duracion_obra)))
        st.altair_chart(viz.get_single_preset_chart(x, y, '#EF4444', 'Costos'), use_container_width=True)
        
    else:
        curve_p = crear_inputs_curva("costos", duracion_obra, {'alpha': -0.5})
        costos_custom_dict = {
            'moda': inicio_obra + curve_p['moda'], 
            'alpha': curve_p['alpha'], 
            'scale': curve_p['scale']
        }
        from presets import generar_curva_inversion
        p = {**costos_custom_dict, 'limite_n': total_capex}
        x, y = generar_curva_inversion(p, (int(inicio_obra), int(inicio_obra) + int(duracion_obra)))
        st.altair_chart(viz.get_single_preset_chart(x, y, '#EF4444', 'Costos'), use_container_width=True)

# --- Tierra ---
tierra_preset_dict = None
tierra_valor = 0.0
canje_pct = 0.0

with st.sidebar.expander("5. Tierra", expanded=False):
    land_options = {"Contado": "contado", "Cuotas": "cuotas", "Canje": "canje_30"}
    land_choice = st.selectbox("Modalidad", list(land_options.keys()))
    land_preset_key = land_options[land_choice]
    
    if land_choice != "Canje":
        tierra_valor = st.number_input("Valor", value=350000.0, step=10000.0, min_value=0.0)
        tierra_preset_dict = TIERRA_PRESETS[land_preset_key].copy()
    else:
        canje_pct = st.slider("% Canje", 0, 100, 30) / 100.0
        # Feedback visual de neto
        st.caption(f"Se descuenta {canje_pct:.0%} de ventas.")

# --- Instanciar Config del Proyecto ---
project_config = model.ProjectConfig(
    m2_terreno=m2_terreno,
    fot=fot,
    efficiency=efficiency,
    duracion_proy=int(duracion_proy),
    inicio_obra=int(inicio_obra),
    duracion_obra=int(duracion_obra),
    precio_promedio=avg_price,
    ventas_preset=ventas_preset_dict,
    ventas_custom=ventas_custom_dict,
    costo_m2=cost_m2,
    costos_preset=costos_preset_dict,
    costos_custom=costos_custom_dict,
    tierra_preset=tierra_preset_dict,
    tierra_valor=tierra_valor,
    canje_pct=canje_pct
)

# Generar params derivados
parametros_ventas, parametros_costos, parametros_tierra = project_config.generar_parametros_simulacion()
meses_totales = project_config.meses_totales
meses_obra = project_config.meses_obra


# --- Finanzas ---
with st.sidebar.expander("6. Finanzas", expanded=False):
    tasa_anual = st.number_input("Tasa Descuento Anual", value=0.12, step=0.01, format="%.2f")
    st.markdown("##### Nivel de Incertidumbre")
    col1, col2 = st.columns(2)
    cv_ventas = col1.number_input("Variacion Precio (%)", value=0.15, step=0.01, min_value=0.0, max_value=1.0)
    cv_costos = col2.number_input("Variacion Costo (%)", value=0.10, step=0.01, min_value=0.0, max_value=1.0)

# --- Monte Carlo Config ---
with st.sidebar.expander("7. Simulacion y Riesgo", expanded=False):
    mc_iteraciones = st.number_input("Cantidad de Escenarios", value=500, step=100, min_value=100)
    mc_semilla = st.number_input("Fijar Escenario (0=aleatorio)", value=0, step=1, min_value=0)
    parametros_mc = {"n_sims": int(mc_iteraciones), "seed": mc_semilla if mc_semilla > 0 else None, "sales_cv": cv_ventas, "cost_cv": cv_costos}


# EJECUCIÓN MODELO

# Base (1 simulación sin varianza de Monte Carlo)
# Nos sirve para extraer métricas puras
df_base, df_base_curvas = model.ejecutar_montecarlo(
    n_iteraciones=1,
    parametros_ventas=parametros_ventas,
    parametros_costos=parametros_costos,
    parametros_tierra=parametros_tierra,
    meses_totales=meses_totales,
    meses_obra=meses_obra,
    tasa_descuento=tasa_anual,
    variacion_ventas=0.0,
    variacion_costos=0.0,
    semilla=None,
    retornar_curvas=True
)
metricas_base = df_base.iloc[0].to_dict()

# Monte Carlo (Principal)
with st.spinner(f"Calculando {parametros_mc['n_sims']:,} escenarios..."):
    df_mc, df_curvas = model.ejecutar_montecarlo(
        parametros_mc['n_sims'], parametros_ventas, parametros_costos, parametros_tierra,
        meses_totales, meses_obra, tasa_descuento=tasa_anual,
        variacion_ventas=parametros_mc['sales_cv'], variacion_costos=parametros_mc['cost_cv'],
        semilla=parametros_mc['seed'], retornar_curvas=True, max_curvas=200
    )


# KPIs

st.markdown("### Metricas Clave")

# KPIs Monte Carlo
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
van_stats = df_mc['VAN'].describe(percentiles=[0.05, 0.5, 0.95])
prob_loss = (df_mc['VAN'] < 0).mean()

df_sim_0 = df_curvas[df_curvas['sim_id'] == 0]
break_even_mask = df_sim_0['Cash_Acumulado'] > 0
break_even_month = int(df_sim_0.loc[break_even_mask, 'Mes'].iloc[0]) if break_even_mask.any() else None

k1.metric("VAN Base", format_currency(metricas_base['VAN']), help="Valor Actual esperado en el escenario modelo")
k2.metric("TIR", format_percent(metricas_base['TIR']), help="Retorno esperado en el escenario modelo")
k3.metric("Capital Trabajo", format_currency(df_sim_0['Cash_Acumulado'].min()), help="Máxima necesidad de capital inicial")
k4.metric("VAN P05", format_currency(van_stats['5%']), help="Escenario Pesimista (mínimo probable)")
k5.metric("VAN P95", format_currency(van_stats['95%']), help="Escenario Optimista (máximo probable)")
k6.metric("Prob. Pérdida", format_percent(prob_loss), help="Probabilidad de que el proyecto de pérdidas")
k7.metric("Break Even", f"M{break_even_month}" if break_even_month else "-")



# GRÁFICOS FRONTAJES

st.markdown("### Flujos del Proyecto")

# Usar funciones unificadas
st.altair_chart(viz.crear_dashboard_detallado(
    df_curvas,
    es_montecarlo=True,
    fin_obra=meses_obra[1],
    break_even_month=break_even_month
), use_container_width=True)


# SENSIBILIDAD

st.markdown("### Analisis de Sensibilidad")
st.caption("Los gráficos muestran el impacto cruzado al variar el ratio base de Precio vs Costo. La **línea blanca punteada** marca matemáticamente la frontera neutral ($0 para VAN, o 0% para TIR) separando escenarios rentables de deficitarios.")

with st.spinner("Calculando..."):
    df_sens = model.ejecutar_analisis_sensibilidad(
        parametros_ventas, parametros_costos, parametros_tierra,
        meses_totales, meses_obra, tasa_anual,
        pasos=4  # Menos dimensiones, números más grandes
    )
    chart_sens_van, chart_sens_tir = viz.crear_matrices_sensibilidad(df_sens)
    
c1, c2 = st.columns(2)
with c1:
    st.altair_chart(chart_sens_van, use_container_width=True)
with c2:
    st.altair_chart(chart_sens_tir, use_container_width=True)

# RESUMEN
st.markdown("---")
st.markdown("### Resumen")

# Helpers de formato condicional
def color_metric(val, string_val, inverse=False):
    # Si inverse=True, valores positivos son ROJOS (ej. Probabilidad de pérdida)
    is_positive = val > 0
    if inverse:
        return f":red[{string_val}]" if is_positive else f":blue[{string_val}]"
    else:
        return f":blue[{string_val}]" if val >= 0 else f":red[{string_val}]"

# Variables previamente armadas en KPIs para reciclar
van_val = metricas_base['VAN']
tir_val = metricas_base['TIR']
max_cap_val = df_sim_0['Cash_Acumulado'].min()

van_base_str = color_metric(van_val, format_currency(van_val))
tir_base_str = color_metric(tir_val, format_percent(tir_val))
max_def_str = color_metric(max_cap_val, format_currency(max_cap_val))
prob_loss_str = color_metric(prob_loss, format_percent(prob_loss), inverse=True) # Mayor prob. perdida = peor

st.markdown(f"""
- **Rentabilidad Base:** El proyecto neutro arroja un VAN de **{van_base_str}** y una TIR del **{tir_base_str}**.
- **Exposición Máxima:** La máxima necesidad de **Capital de Trabajo** requerida alcanza los **{max_def_str}**.
- **Riesgo:** Bajo los supuestos de variabilidad (Monte Carlo), existe un **{prob_loss_str}** de probabilidad de obtener rendimientos negativos (VAN < 0).
""")

# SEMAFORO FINAL
if van_val < 0 or prob_loss > 0.50:
    st.error(f"🔴 **No viable:** El escenario base arroja destrucción de valor nominal, o su riesgo probabilístico de entrar en pérdida es críticamente alto (>{format_percent(0.50)}).")
elif van_val > 0 and prob_loss <= 0.20:
    st.success(f"🟢 **Saludable:** El escenario base nominal es rentable y presenta un margen de seguridad cómodo ante variabilidades (Riesgo <{format_percent(0.20)}).")
else:
    st.warning("🟡 **Riesgo moderado:** Si bien el escenario nominal es positivo, la sensibilidad proyectada arroja ciertas fragilidades sobre el retorno buscado bajo condiciones de alto estrés.")

st.markdown("---")

# DEBUG / DATA (Al final de todo)

with st.expander("Analisis Detallado"):
    
    st.markdown("#### Escenarios Simulados")
    chart_van, chart_tir = viz.crear_graficos_montecarlo(df_mc)
    c1, c2 = st.columns(2)
    with c1:
        st.altair_chart(chart_van, use_container_width=True)
    with c2:
        st.altair_chart(chart_tir, use_container_width=True)
    
    chart_ventas, chart_costos = viz.crear_graficos_distribucion_montecarlo(df_mc)
    c3, c4 = st.columns(2)
    with c3:
       st.altair_chart(chart_ventas, use_container_width=True)
    with c4:
       st.altair_chart(chart_costos, use_container_width=True)
    
    st.markdown("#### Registro de Simulaciones")
    st.dataframe(df_mc, width="stretch")
