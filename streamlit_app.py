"""
Modelo de Riesgo Inmobiliario - Aplicación Streamlit.

Vista unificada con misma estructura para determinístico y Monte Carlo.
"""

import streamlit as st

import model
import viz
from constants import format_currency, format_percent
from presets import COSTOS_PRESETS, TIERRA_PRESETS, VENTAS_PRESETS

MAX_MC_ITERACIONES = 10000


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
        scale = st.number_input(
            "Dispersion",
            value=defaults.get("scale", 5.0),
            min_value=0.1,
            step=0.5,
            key=f"{prefix}_scale",
        )
    return {"moda": mode, "alpha": alpha, "scale": scale}


def render_altair_stretch(chart) -> None:
    st.altair_chart(chart, width="stretch")


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


def recalcular_metricas_escenario(
    parametros_ventas_base: dict,
    parametros_costos_base: dict,
    parametros_tierra: dict,
    meses_totales: tuple,
    meses_obra: tuple,
    tasa_anual: float,
    factor_precio: float = 1.0,
    factor_costo: float = 1.0,
) -> dict:
    """Recalcula métricas determinísticas aplicando factores sobre ventas/costos."""
    params_ventas = parametros_ventas_base.copy()
    params_costos = parametros_costos_base.copy()

    params_ventas["area_n"] = params_ventas.get("area_n", 0) * factor_precio
    params_costos["limite_n"] = params_costos.get("limite_n", 0) * factor_costo

    _, metricas = model.ejecutar_deterministico(
        params_ventas,
        params_costos,
        parametros_tierra,
        meses_totales=meses_totales,
        meses_obra=meses_obra,
        tasa_anual=tasa_anual,
    )
    return metricas


def clasificar_escenario(metricas: dict) -> tuple[str, str]:
    """Devuelve etiqueta y comentario simple de atractivo/riesgo del escenario."""
    van = metricas.get("VAN", 0)
    tir = metricas.get("TIR", 0)
    capital_trabajo = metricas.get("MaxFinancingNeed", 0)

    if van > 0 and tir >= 0.18 and capital_trabajo < 0.4 * van:
        return "🟢 Atractivo", "Buen margen y presión financiera manejable."
    if van > 0 and tir >= 0.12:
        return "🟡 Requiere mitigación", "Rentable, pero con sensibilidad a ejecución/financiación."
    return "🔴 Frágil", "Perfil vulnerable: revisar supuestos, costos y estrategia comercial."


def formatear_delta(valor_escenario: float, valor_base: float, formatter) -> str:
    """Formatea delta absoluto versus el escenario base con signo explícito."""
    delta_valor = valor_escenario - valor_base
    signo = "+" if delta_valor > 0 else "" if delta_valor == 0 else "-"
    return f"{signo}{formatter(abs(delta_valor))}"


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
        cv_ventas = col1.number_input("CV Ventas", value=0.15, step=0.01, min_value=0.0, max_value=1.0)
        cv_costos = col2.number_input("CV Costos", value=0.10, step=0.01, min_value=0.0, max_value=1.0)

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
        "n_sims": min(int(mc_iteraciones), MAX_MC_ITERACIONES),
        "seed": int(mc_semilla) if int(mc_semilla) > 0 else None,
        "sales_cv": float(cv_ventas),
        "cost_cv": float(cv_costos),
        "tasa_anual": float(tasa_anual),
    }
    return project_config, parametros_mc


def render_kpis(metricas_base: dict, df_mc) -> None:
    st.markdown("### 0. Metricas clave")

    has_mc_data = df_mc is not None and not getattr(df_mc, "empty", False) and "VAN" in df_mc
    if has_mc_data:
        van_stats = df_mc["VAN"].describe(percentiles=[0.05, 0.5, 0.95])
        prob_loss = (df_mc["VAN"] < 0).mean()
    else:
        van_stats = {"5%": metricas_base["VAN"], "95%": metricas_base["VAN"]}
        prob_loss = 0.0

    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("VAN Base", format_currency(metricas_base["VAN"]), help="Valor Actual Neto escenario base")
    k2.metric("TIR", format_percent(metricas_base["TIR"]), help="Tasa Interna de Retorno")
    k3.metric(
        "Capital Trabajo",
        format_currency(metricas_base["MaxFinancingNeed"]),
        help="Maxima necesidad financiera (Déficit acumulado)",
    )
    k4.metric("VAN P05", format_currency(van_stats["5%"]), help="Percentil 05 (pesimista)")
    k5.metric("VAN P95", format_currency(van_stats["95%"]), help="Percentil 95 (optimista)")
    k6.metric("Prob. Perdida", format_percent(prob_loss), help="% escenarios VAN < 0")
    k7.metric(
        "Break Even",
        f"M{int(metricas_base.get('BreakEvenMonth'))}" if metricas_base.get("BreakEvenMonth") else "-",
    )

    if has_mc_data:
        st.info(
            "Con 90% de confianza, el VAN estará entre "
            f"{format_currency(van_stats['5%'])} y {format_currency(van_stats['95%'])}. "
            f"Riesgo de pérdida: {format_percent(prob_loss)}."
        )
    else:
        st.warning("No se pudieron calcular estadísticas Monte Carlo; mostrando métricas del escenario base.")


def render_distribuciones(df_base, meses_obra: tuple, df_mc, df_sens) -> None:
    flow_chart = viz.get_unified_flow_chart(
        df_base,
        is_montecarlo=False,
        construction_end=meses_obra[1],
    )

    chart_van = chart_tir = None
    if df_mc is not None and not getattr(df_mc, "empty", False):
        chart_van, chart_tir = viz.crear_graficos_montecarlo(df_mc)

    chart_sens_van = chart_sens_tir = None
    if df_sens is not None and not getattr(df_sens, "empty", False):
        chart_sens_van, chart_sens_tir = viz.crear_matrices_sensibilidad(df_sens)

    st.markdown("### 1-2. Evolución del Saldo (Riesgo) + Ingresos vs Egresos (Neto)")
    st.caption("Incluye arriba Ingresos vs Egresos (Neto) y abajo la curva de saldo acumulado.")
    render_altair_stretch(flow_chart)

    st.markdown("### 3. Distribución VAN")
    if chart_van is not None:
        render_altair_stretch(chart_van)
    else:
        st.warning("No se pudo generar la distribución VAN para la corrida actual.")

    st.markdown("### 4. Sensibilidad VAN (Bubbles)")
    if chart_sens_van is not None:
        render_altair_stretch(chart_sens_van)
    else:
        st.warning("No se pudo generar la matriz de sensibilidad para la corrida actual.")

    if df_mc is not None and not getattr(df_mc, "empty", False) and chart_tir is not None:
        st.markdown("### 6. Distribuciones (Monte Carlo)")
        st.caption("Fila 1: resultado financiero del proyecto (VAN y TIR).")
        c1, c2 = st.columns(2)
        with c1:
            render_altair_stretch(chart_van)
        with c2:
            render_altair_stretch(chart_tir)

        if chart_sens_tir is not None:
            render_altair_stretch(chart_sens_tir)


def render_comparacion_escenarios(
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
    metricas_escenarios = {
        label: recalcular_metricas_escenario(
            parametros_ventas,
            parametros_costos,
            parametros_tierra,
            meses_totales,
            meses_obra,
            tasa_anual,
            factor_precio=f_precio,
            factor_costo=f_costo,
        )
        for label, (f_precio, f_costo, _) in escenarios.items()
    }
    metricas_base_escenario = metricas_escenarios["Base"]

    cols = st.columns(3)
    for col, (label, (_, _, detalle)) in zip(cols, escenarios.items()):
        metrics = metricas_escenarios[label]
        insight_label, insight_text = clasificar_escenario(metrics)

        with col:
            st.subheader(label)
            st.caption(detalle)
            st.metric(
                "VAN",
                format_currency(metrics["VAN"]),
                delta=formatear_delta(metrics["VAN"], metricas_base_escenario["VAN"], format_currency),
            )
            st.metric(
                "TIR",
                format_percent(metrics["TIR"]),
                delta=formatear_delta(metrics["TIR"], metricas_base_escenario["TIR"], format_percent),
            )
            st.metric(
                "Capital Trabajo",
                format_currency(metrics["MaxFinancingNeed"]),
                delta=formatear_delta(
                    metrics["MaxFinancingNeed"],
                    metricas_base_escenario["MaxFinancingNeed"],
                    format_currency,
                ),
            )
            if "Atractivo" in insight_label:
                st.success(f"{insight_label} · {insight_text}")
            elif "Requiere mitigación" in insight_label:
                st.warning(f"{insight_label} · {insight_text}")
            else:
                st.error(f"{insight_label} · {insight_text}")


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

        metricas_sens = recalcular_metricas_escenario(
            parametros_ventas,
            parametros_costos,
            parametros_tierra,
            meses_totales,
            meses_obra,
            tasa_anual,
            factor_precio=precio_factor,
            factor_costo=costo_factor,
        )
        st.metric("VAN ajustado", format_currency(metricas_sens["VAN"]))
        st.metric("TIR ajustada", format_percent(metricas_sens["TIR"]))

        st.markdown("#### Datos")
        if df_mc is not None and not getattr(df_mc, "empty", False):
            st.dataframe(df_mc, width="stretch")
        else:
            st.dataframe(df_base, width="stretch")


def main() -> None:
    st.set_page_config(
        page_title="Modelo de Riesgo Inmobiliario",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    cargar_css()

    st.title("Modelo de Riesgo Inmobiliario")
    st.markdown("---")

    project_config, parametros_mc = render_sidebar()
    parametros_ventas, parametros_costos, parametros_tierra = project_config.generar_parametros_simulacion()
    meses_totales = project_config.meses_totales
    meses_obra = project_config.meses_obra

    df_base, metricas_base = model.ejecutar_deterministico(
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales=meses_totales,
        meses_obra=meses_obra,
        tasa_anual=parametros_mc["tasa_anual"],
    )

    with st.spinner(f"Calculando {parametros_mc['n_sims']:,} escenarios..."):
        df_mc, _df_curvas = _ejecutar_montecarlo_cacheado(
            parametros_mc["n_sims"],
            parametros_ventas,
            parametros_costos,
            parametros_tierra,
            meses_totales,
            meses_obra,
            parametros_mc["tasa_anual"],
            parametros_mc["sales_cv"],
            parametros_mc["cost_cv"],
            parametros_mc["seed"],
        )

    with st.spinner("Calculando sensibilidad..."):
        df_sens = _ejecutar_sensibilidad_cacheado(
            parametros_ventas,
            parametros_costos,
            parametros_tierra,
            meses_totales,
            meses_obra,
            parametros_mc["tasa_anual"],
            pasos=4,
        )

    render_kpis(metricas_base, df_mc)
    render_distribuciones(df_base, meses_obra, df_mc, df_sens)
    render_comparacion_escenarios(
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales,
        meses_obra,
        parametros_mc["tasa_anual"],
    )
    render_bajo_capot(
        parametros_ventas,
        parametros_costos,
        parametros_tierra,
        meses_totales,
        meses_obra,
        parametros_mc["tasa_anual"],
        df_mc,
        df_base,
    )


if __name__ == "__main__":
    main()
