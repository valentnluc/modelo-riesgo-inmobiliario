"""
Modelo de Riesgo Inmobiliario - Aplicación Streamlit.

Vista unificada con misma estructura para determinístico y Monte Carlo.
"""

import streamlit as st

import model
import viz
from constants import format_currency, format_percent
from presets import COSTOS_PRESETS, TIERRA_PRESETS, VENTAS_PRESETS


st.set_page_config(
    page_title="Modelo de Riesgo Inmobiliario",
    layout="wide",
    initial_sidebar_state="expanded",
)


def cargar_css() -> None:
    """Carga el tema Core Infra."""
    try:
        with open("styles/core_infra.css", encoding="utf-8") as css_file:
            st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


def crear_inputs_curva(prefix: str, duration: int, defaults: dict | None = None) -> dict:
    defaults = defaults or {}
    col1, col2 = st.columns(2)
    with col1:
        mode = st.slider(
            "Mes Pico",
            0,
            int(duration),
            defaults.get("moda", int(duration / 2)),
            key=f"{prefix}_mode",
        )
        alpha = st.number_input(
            "Asimetria",
            value=defaults.get("alpha", 0.0),
            step=0.1,
            key=f"{prefix}_alpha",
        )
    with col2:
        scale = st.number_input("Dispersion", value=defaults.get('scale', 5.0), min_value=0.1, step=0.5, key=f"{prefix}_scale")
    return {'moda': mode, 'alpha': alpha, 'scale': scale}

def render_altair_stretch(chart):
    """Render helper to avoid inline nested calls and keep chart rendering syntax simple."""
    st.altair_chart(chart, width="stretch")

MAX_MC_ITERACIONES = 10000


@st.cache_data(show_spinner=False)
def _ejecutar_montecarlo_cacheado(
    n_iteraciones: int,
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: tuple,
    meses_obra: tuple,
    tasa_anual: float,
    cv_ventas: float,
    cv_costos: float,
    semilla: int | None,
):
    return model.ejecutar_montecarlo(
        n_iteraciones,
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales,
        meses_obra,
        tasa_descuento=tasa_anual,
        variacion_ventas=cv_ventas,
        variacion_costos=cv_costos,
        semilla=semilla,
        retornar_curvas=True,
        max_curvas=200,
        usar_cache=True,
    )


@st.cache_data(show_spinner=False)
def _ejecutar_sensibilidad_cacheado(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: tuple,
    meses_obra: tuple,
    tasa_anual: float,
    pasos: int = 4,
):
    return model.ejecutar_analisis_sensibilidad(
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales,
        meses_obra,
        tasa_anual,
        pasos=pasos,
        usar_cache=True,
    )


# =============================================================================
# HEADER
# =============================================================================

st.title("Modelo de Riesgo Inmobiliario")
st.markdown("---")


def render_altair_stretch(chart) -> None:
    st.altair_chart(chart, width="stretch")


def render_sidebar() -> tuple[model.ProjectConfig, dict]:
    st.sidebar.header("Configuracion")

    tasa_anual = st.sidebar.number_input(
        "Tasa Descuento Anual", value=0.12, step=0.01, format="%.2f"
    )

    with st.sidebar.expander("1. Proyecto", expanded=True):
        m2_terreno = st.number_input("Superficie (m2)", value=350.0, step=50.0, min_value=1.0)
        fot = st.number_input("FOT", value=3.5, step=0.1, min_value=0.1)
        efficiency = st.slider("Eficiencia Vendible", 0.5, 1.0, 0.80)

        m2_construidos = m2_terreno * fot
        sup_vendible = m2_construidos * efficiency
        st.caption(f"Construible: {m2_construidos:,.0f} m2 | Vendible: {sup_vendible:,.0f} m2")

    with st.sidebar.expander("2. Cronograma", expanded=True):
        duracion_proy = st.number_input("Duracion (meses)", value=36, step=6, min_value=6)
        col1, col2 = st.columns(2)
        inicio_obra = col1.number_input("Inicio Obra", value=0, step=1, min_value=0)
        duracion_obra = col2.number_input("Duracion Obra", value=30, step=1, min_value=1)

    ventas_preset_dict = None
    ventas_custom_dict = None
    with st.sidebar.expander("3. Ventas", expanded=False):
        avg_price = st.number_input("Precio (USD/m2)", value=1800.0, step=50.0, min_value=1.0)
        total_sales_raw = sup_vendible * avg_price
        st.caption(f"Total Bruto: {format_currency(total_sales_raw)}")

        sales_mode = st.selectbox("Distribucion", ["Preset", "Personalizada"])
        if sales_mode == "Preset":
            sales_preset_key = st.selectbox("Preset", list(VENTAS_PRESETS.keys()))
            ventas_preset_dict = VENTAS_PRESETS[sales_preset_key].copy()
            st.caption(ventas_preset_dict["descripcion"])
            preview_sales = viz.get_preset_preview_chart(
                ventas_preset_dict,
                months=(0, int(duracion_proy)),
                total_value=total_sales_raw,
                kind="ventas",
            )
            st.altair_chart(preview_sales, width="stretch")
        else:
            ventas_custom_dict = crear_inputs_curva("ventas", duracion_proy).copy()

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
            st.caption(costos_preset_dict["descripcion"])
            preview_costs = viz.get_preset_preview_chart(
                costos_preset_dict,
                months=(int(inicio_obra), int(inicio_obra + duracion_obra)),
                total_value=total_capex,
                kind="costos",
            )
            st.altair_chart(preview_costs, width="stretch")
        else:
            curve_p = crear_inputs_curva("costos", duracion_obra, {"alpha": -0.5})
            costos_custom_dict = {
                "moda": inicio_obra + curve_p["moda"],
                "alpha": curve_p["alpha"],
                "scale": curve_p["scale"],
            }

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
            st.caption(f"Se descuenta {canje_pct:.0%} de ventas.")

    with st.sidebar.expander("6. Monte Carlo", expanded=False):
        mc_iteraciones = st.number_input("Iteraciones", value=500, step=100, min_value=100)
        mc_semilla = st.number_input("Semilla (0=aleatorio)", value=0, step=1, min_value=0)
        col1, col2 = st.columns(2)
        cv_ventas = col1.number_input(
            "CV Ventas", value=0.15, step=0.01, min_value=0.0, max_value=1.0
        )
        cv_costos = col2.number_input(
            "CV Costos", value=0.10, step=0.01, min_value=0.0, max_value=1.0
        )

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
        canje_pct=canje_pct,
    )

    parametros_mc = {
        "n_sims": int(mc_iteraciones),
        "seed": mc_semilla if mc_semilla > 0 else None,
        "sales_cv": cv_ventas,
        "cost_cv": cv_costos,
        "tasa_anual": tasa_anual,
    }
    return project_config, parametros_mc

# --- Monte Carlo Config ---
with st.sidebar.expander("6. Monte Carlo", expanded=False):
    mc_iteraciones = st.number_input("Iteraciones", value=500, step=100, min_value=100)
    mc_semilla = st.number_input("Semilla (0=aleatorio)", value=0, step=1, min_value=0)
    col1, col2 = st.columns(2)
    cv_ventas = col1.number_input("CV Ventas", value=0.15, step=0.01, min_value=0.0, max_value=1.0)
    cv_costos = col2.number_input("CV Costos", value=0.10, step=0.01, min_value=0.0, max_value=1.0)

    mc_iteraciones_solicitadas = int(mc_iteraciones)
    mc_iteraciones_efectivas = min(mc_iteraciones_solicitadas, MAX_MC_ITERACIONES)

    if mc_iteraciones_solicitadas > MAX_MC_ITERACIONES:
        st.warning(
            f"Se limitaron las iteraciones a {MAX_MC_ITERACIONES:,} para mantener tiempos de respuesta razonables. "
            f"Solicitaste {mc_iteraciones_solicitadas:,}."
        )
    elif mc_iteraciones_efectivas >= int(MAX_MC_ITERACIONES * 0.8):
        st.info(
            f"Carga alta: {mc_iteraciones_efectivas:,} simulaciones pueden demorar. "
            "Se reutilizarán resultados cacheados si no cambian los parámetros relevantes."
        )

    parametros_mc = {
        "n_sims": mc_iteraciones_efectivas,
        "seed": mc_semilla if mc_semilla > 0 else None,
        "sales_cv": cv_ventas,
        "cost_cv": cv_costos,
    }

def run_model(project_config: model.ProjectConfig, parametros_mc: dict) -> dict:
    parametros_ventas, parametros_costos, parametros_tierra = (
        project_config.generar_parametros_simulacion()
    )

    df_base, metricas_base = model.ejecutar_deterministico(
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales=project_config.meses_totales,
        meses_obra=project_config.meses_obra,
        tasa_anual=parametros_mc["tasa_anual"],
    )

    with st.spinner(f"Calculando {parametros_mc['n_sims']:,} escenarios..."):
        df_mc, df_curvas = model.ejecutar_montecarlo(
            parametros_mc["n_sims"],
            parametros_ventas,
            parametros_costos,
            parametros_tierra,
            project_config.meses_totales,
            project_config.meses_obra,
            tasa_descuento=parametros_mc["tasa_anual"],
            variacion_ventas=parametros_mc["sales_cv"],
            variacion_costos=parametros_mc["cost_cv"],
            semilla=parametros_mc["seed"],
            retornar_curvas=True,
            max_curvas=200,
        )

    with st.spinner("Calculando sensibilidad..."):
        df_sens = model.ejecutar_analisis_sensibilidad(
            parametros_ventas,
            parametros_costos,
            parametros_tierra,
            project_config.meses_totales,
            project_config.meses_obra,
            parametros_mc["tasa_anual"],
            pasos=4,
        )

with st.spinner(f"Calculando {parametros_mc['n_sims']:,} escenarios..."):
    df_mc, df_curvas = _ejecutar_montecarlo_cacheado(
        parametros_mc['n_sims'],
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales,
        meses_obra,
        tasa_anual,
        parametros_mc['sales_cv'],
        parametros_mc['cost_cv'],
        parametros_mc['seed'],
    )

with st.spinner("Calculando sensibilidad..."):
    df_sens = _ejecutar_sensibilidad_cacheado(
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales,
        meses_obra,
        tasa_anual,
        pasos=4,
    )

    st.info(
        "Con 90% de confianza, el VAN estará entre "
        f"{format_currency(van_stats['5%'])} y {format_currency(van_stats['95%'])}. "
        f"Riesgo de pérdida: {format_percent(prob_loss)}."
    )


def render_escenarios(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: tuple,
    meses_obra: tuple,
    tasa_anual: float,
) -> None:
    st.markdown("### 5. Comparación de Escenarios")
    st.caption(
        "Supuestos por escenario: Base (precio 100% / costo 100%), "
        "Pesimista (precio -10% / costo +10%), Optimista (precio +10% / costo -10%)."
    )

    escenarios = {
        "Base": (1.0, 1.0, "Precio = base | Costo = base"),
        "Pesimista": (0.9, 1.1, "Precio -10% | Costo +10%"),
        "Optimista": (1.1, 0.9, "Precio +10% | Costo -10%"),
    }

    cols = st.columns(3)
    for col, (label, (f_precio, f_costo, detalle)) in zip(cols, escenarios.items()):
        params_ventas = parametros_ventas.copy()
        params_costos = parametros_costos.copy()
        params_ventas["area_n"] = params_ventas.get("area_n", 0) * f_precio
        params_costos["limite_n"] = params_costos.get("limite_n", 0) * f_costo

        _, metrics = model.ejecutar_deterministico(
            params_ventas,
            params_costos,
            parametros_tierra,
            meses_totales=meses_totales,
            meses_obra=meses_obra,
            tasa_anual=tasa_anual,
        )
        with col:
            st.subheader(label)
            st.caption(detalle)
            st.metric("VAN", format_currency(metrics["VAN"]))
            st.metric("TIR", format_percent(metrics["TIR"]))
            st.metric("Capital Trabajo", format_currency(metrics["MaxFinancingNeed"]))


def render_distribuciones(df_mc, chart_tir, chart_ventas, chart_costos, chart_sens_tir) -> None:
    if df_mc is None:
        return

    st.markdown("### 6. Distribuciones (Monte Carlo)")
    st.caption("Fila 1: resultado financiero del proyecto (VAN y TIR).")
    c1, c2 = st.columns(2)
    with c1:
        render_altair_stretch(chart_van)
    with c2:
        render_altair_stretch(chart_ventas)

    c3, c4 = st.columns(2)
    with c3:
        render_altair_stretch(chart_ventas)
    with c4:
        render_altair_stretch(chart_costos)

    st.caption("Lectura sugerida: P05 es un escenario conservador, P50 la mediana esperada y P95 un escenario optimista para cada métrica.")


def render_bajo_capot(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: tuple,
    meses_obra: tuple,
    tasa_anual: float,
    df_mc,
    df_base,
) -> None:
    st.markdown("### 7. Bajo el capot")
    with st.expander("Bajo el capot"):
        st.markdown("#### Sensibilidad rápida")
        col_a, col_b = st.columns(2)
        with col_a:
            precio_factor = st.slider("Precio vs Base", 0.7, 1.3, 1.0, 0.05, format="%.2f")
        with col_b:
            costo_factor = st.slider("Costo vs Base", 0.7, 1.3, 1.0, 0.05, format="%.2f")

        params_ventas_sens = parametros_ventas.copy()
        params_costos_sens = parametros_costos.copy()
        params_ventas_sens["area_n"] = params_ventas_sens.get("area_n", 0) * precio_factor
        params_costos_sens["limite_n"] = params_costos_sens.get("limite_n", 0) * costo_factor

        _, metricas_sens = model.ejecutar_deterministico(
            params_ventas_sens,
            params_costos_sens,
            parametros_tierra,
            meses_totales=meses_totales,
            meses_obra=meses_obra,
            tasa_anual=tasa_anual,
        )
        st.caption("Ajuste rápido de precio y costo sobre el escenario base.")
        st.write(
            f"VAN: {format_currency(metricas_sens['VAN'])} | "
            f"TIR: {format_percent(metricas_sens['TIR'])} | "
            f"Capital Trabajo: {format_currency(metricas_sens['MaxFinancingNeed'])}"
        )

        st.markdown("#### Datos")
        st.dataframe(df_mc if df_mc is not None else df_base, width="stretch")


def main() -> None:
    cargar_css()
    st.title("Modelo de Riesgo Inmobiliario")
    st.markdown("---")

    project_config, parametros_mc = render_sidebar()
    outputs = run_model(project_config, parametros_mc)

    render_kpis(outputs["metricas_base"], outputs["df_mc"])

    flow_data = outputs["df_curvas"] if outputs["df_curvas"] is not None else outputs["df_base"]
    flow_chart = viz.crear_dashboard_detallado(
        df_mensual=flow_data,
        es_montecarlo=outputs["df_curvas"] is not None,
        fin_obra=outputs["meses_obra"][1],
        break_even_month=outputs["metricas_base"].get("BreakEvenMonth"),
    )
    chart_van, chart_tir = viz.crear_graficos_montecarlo(outputs["df_mc"])
    chart_sens_van, chart_sens_tir = viz.crear_matrices_sensibilidad(outputs["df_sens"])
    chart_ventas, chart_costos = viz.crear_graficos_distribucion_montecarlo(outputs["df_mc"])

    st.markdown("### 1-2. Evolución del Saldo (Riesgo) + Ingresos vs Egresos (Neto)")
    st.caption("Incluye arriba Ingresos vs Egresos (Neto) y abajo la curva de saldo acumulado.")
    render_altair_stretch(flow_chart)

    st.markdown("### 3. Distribución VAN")
    render_altair_stretch(chart_van)

    st.markdown("### 4. Sensibilidad VAN (Bubbles)")
    render_altair_stretch(chart_sens_van)

    render_escenarios(
        outputs["parametros_ventas"],
        outputs["parametros_costos"],
        outputs["parametros_tierra"],
        outputs["meses_totales"],
        outputs["meses_obra"],
        parametros_mc["tasa_anual"],
    )
    render_distribuciones(outputs["df_mc"], chart_tir, chart_ventas, chart_costos, chart_sens_tir)
    render_bajo_capot(
        outputs["parametros_ventas"],
        outputs["parametros_costos"],
        outputs["parametros_tierra"],
        outputs["meses_totales"],
        outputs["meses_obra"],
        parametros_mc["tasa_anual"],
        outputs["df_mc"],
        outputs["df_base"],
    )


if __name__ == "__main__":
    main()
