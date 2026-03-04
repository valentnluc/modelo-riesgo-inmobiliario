import os
from typing import Tuple, Optional
import pandas as pd
import numpy as np
import altair as alt

from constants import (
    COLORS, COLOR_INCOME, COLOR_EXPENSE,  COLOR_ACCUM,
    CHART_CONFIG, CHART_WIDTH, CHART_HEIGHT_MAIN, CHART_HEIGHT_SMALL,
    format_currency
)
from presets import VENTAS_PRESETS, COSTOS_PRESETS, TIERRA_PRESETS
from presets import generar_curva_ventas, generar_curva_inversion

# Color primario para elementos destacados
COLOR_PRIMARY = COLORS['brand']

# Configurar tema Altair para Core Infra
def core_infra_theme():
    return {
        'config': {
            'background': '#000000',
            'title': {'color': '#FFFFFF', 'font': 'Inter', 'fontSize': 14},
            'axis': {
                'labelColor': '#A1A1AA',
                'titleColor': '#A1A1AA',
                'gridColor': '#1F1F1F',
                'domainColor': '#333333',
                'tickColor': '#333333',
                'labelFont': 'Inter',
                'titleFont': 'Inter',
            },
            'legend': {
                'labelColor': '#A1A1AA',
                'titleColor': '#FFFFFF',
                'labelFont': 'Inter',
            },
            'view': {'stroke': '#1F1F1F'},
            'range': {
                'category': ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']
            }
        }
    }

alt.themes.register('core_infra', core_infra_theme)
alt.themes.enable('core_infra')


# =============================================================================
# HELPERS
# =============================================================================



# =============================================================================
# GRÁFICOS DE COMPARACIÓN DE PRESETS
# =============================================================================

def get_sales_comparison_chart(months: Tuple[int, int]) -> alt.Chart:
    """Gráfico comparativo de presets de ventas."""
    rows = []
    for name, params in VENTAS_PRESETS.items():
        p = {**params, 'area_n': 5000}
        x, y = generar_curva_ventas(p, months)
        for xi, yi in zip(x, y):
            rows.append({'Mes': xi, 'Valor': yi, 'Preset': name})
    
    df = pd.DataFrame(rows)
    return alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=alt.X('Mes:Q', title='Mes'),
        y=alt.Y('Valor:Q', title='Ritmo de Ventas'),
        color=alt.Color('Preset:N')
    ).properties(title='Curvas de Ventas', width=CHART_WIDTH, height=CHART_HEIGHT_MAIN)


def get_cost_comparison_chart(months: Tuple[int, int], inversion_total: float) -> alt.Chart:
    """Gráfico comparativo de presets de costos."""
    rows = []
    for name, params in COSTOS_PRESETS.items():
        p = {**params, 'limite_n': inversion_total}
        x, y = generar_curva_inversion(p, months)
        for xi, yi in zip(x, y):
            rows.append({'Mes': xi, 'Valor': yi, 'Preset': name})
    
    df = pd.DataFrame(rows)
    return alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=alt.X('Mes:Q', title='Mes'),
        y=alt.Y('Valor:Q', title='Inversión Acumulada', axis=alt.Axis(format='$,.2f')),
        color=alt.Color('Preset:N')
    ).properties(title='Curvas de Costos', width=CHART_WIDTH, height=CHART_HEIGHT_MAIN)


def get_single_preset_chart(x: np.ndarray, y: np.ndarray, color: str, ylabel: str) -> alt.Chart:
    """Gráfico simple de la curva de un preset (para mostrar en el sidebar)."""
    df = pd.DataFrame({'Mes': x, 'Valor': y})
    
    line = alt.Chart(df).mark_line(color=color, strokeWidth=2).encode(
        x=alt.X('Mes:Q', title=None, axis=alt.Axis(labels=True, ticks=False)),
        y=alt.Y('Valor:Q', title=ylabel, axis=alt.Axis(labels=True, format='$,.2f', ticks=False)),
    )
    
    return line.properties(height=120).configure_view(strokeWidth=0)


# --- Dashboards Principales ---

def get_cashflow_chart(
    df_flow: pd.DataFrame,
    construction_end_month: Optional[int] = None,
    title: Optional[str] = None
) -> alt.VConcatChart:
    """
    Dashboard de flujos del proyecto - diseño minimalista.
    
    Gráfico superior: barras de ingresos/egresos + línea de flujo neto
    Gráfico inferior: área de cash acumulado (destacado)
    """
    # La data ahora ya viene en meses enteros directos discretizados
    df = df_flow.copy()
    df_agg = df.groupby('Mes').agg({
        'Ventas': 'sum',
        'Egresos_Obra': 'sum',
        'Egresos_Tierra': 'sum',
        'Flujo_Neto': 'sum',
        'Cash_Acumulado': 'last'
    }).reset_index()
    
    # Preparar datos para barras apiladas
    df_bars = pd.melt(
        df_agg,
        id_vars=['Mes'],
        value_vars=['Ventas', 'Egresos_Obra', 'Egresos_Tierra'],
        var_name='Tipo',
        value_name='Monto'
    )
    # Egresos como negativos
    df_bars.loc[df_bars['Tipo'].str.contains('Egresos'), 'Monto'] *= -1
    
    # Renombrar para leyenda limpia
    df_bars['Tipo'] = df_bars['Tipo'].map({
        'Ventas': 'Ingresos',
        'Egresos_Obra': 'Costos Obra',
        'Egresos_Tierra': 'Costos Tierra'
    })
    
    # --- Gráfico Superior: Flujos ---
    bars = alt.Chart(df_bars).mark_bar(opacity=0.8).encode(
        x=alt.X('Mes:O', title=None, axis=alt.Axis(labelAngle=0, tickSize=0)),
        y=alt.Y('Monto:Q', title='Flujo Mensual', axis=alt.Axis(format='$,.2f')),
        color=alt.Color('Tipo:N',
            scale=alt.Scale(
                domain=['Ingresos', 'Costos Obra', 'Costos Tierra'],
                range=[COLOR_INCOME, COLOR_EXPENSE, COLORS['tertiary']]
            ),
            legend=alt.Legend(orient='top', title=None, labelFontSize=10)
        ),
        tooltip=[
            alt.Tooltip('Mes:O', title='Mes'),
            alt.Tooltip('Tipo:N'),
            alt.Tooltip('Monto:Q', format='$,.2f')
        ]
    )
    
    # Línea de flujo neto (blanco para mejor visibilidad)
    line_net = alt.Chart(df_agg).mark_line(
        color='white',
        strokeWidth=2.5,
        strokeDash=[4, 2]
    ).encode(
        x='Mes:O',
        y='Flujo_Neto:Q'
    )
    
    top_chart = alt.layer(bars, line_net).properties(
        title=alt.TitleParams(
            title or 'Flujos Mensuales',
            fontSize=14,
            anchor='start'
        ),
        height=CHART_HEIGHT_MAIN
    )
    
    # --- Gráfico Inferior: Cash Acumulado (DESTACADO) ---
    # Área con color sólido
    area = alt.Chart(df_agg).mark_area(
        color=COLOR_ACCUM,
        opacity=0.3,
        line={'color': COLOR_ACCUM, 'strokeWidth': 3}
    ).encode(
        x=alt.X('Mes:O', title='Mes', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Cash_Acumulado:Q', 
                title='Cash Acumulado',
                axis=alt.Axis(format='$,.2f'))
    )
    
    # Línea de cero
    zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
        color=COLORS['text_light'],
        strokeDash=[4, 4]
    ).encode(y='y:Q')
    
    # Punto del mínimo (máxima inversión)
    min_idx = df_agg['Cash_Acumulado'].idxmin()
    min_row = df_agg.loc[min_idx]
    df_min = pd.DataFrame([{
        'Mes': min_row['Mes'],
        'Cash_Acumulado': min_row['Cash_Acumulado'],
    }])
    
    point_min = alt.Chart(df_min).mark_circle(
        size=80,
        color=COLOR_EXPENSE
    ).encode(
        x='Mes:O',
        y='Cash_Acumulado:Q'
    )
    
    label_min = alt.Chart(df_min).mark_text(
        align='left',
        dx=8,
        dy=0,
        fontSize=10,
        fontWeight='bold',
        color=COLOR_EXPENSE
    ).encode(
        x='Mes:O',
        y='Cash_Acumulado:Q',
        text=alt.value('Max Inversión')
    )
    
    bottom_layers = [area, zero_line, point_min, label_min]
    
    # Línea de fin de obra
    if construction_end_month is not None:
        df_const = pd.DataFrame([{'Mes': construction_end_month}])
        rule_const = alt.Chart(df_const).mark_rule(
            color=COLORS['text_light'],
            strokeDash=[2, 2]
        ).encode(x='Mes:O')
        bottom_layers.append(rule_const)
    
    bottom_chart = alt.layer(*bottom_layers).properties(
        title=alt.TitleParams('Evolución del Saldo (Riesgo)', fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=100# Más compacto
    )
    
    return alt.vconcat(top_chart, bottom_chart).resolve_scale(x='shared')


def crear_dashboard_detallado(
    df_mensual: pd.DataFrame,
    fin_obra: Optional[int] = None,
    es_montecarlo: bool = False,
    break_even_month: Optional[float] = None
) -> alt.VConcatChart:
    """
    Dashboard detallado: Flujos mensuales (arriba) y Balance acumulado (abajo).
    """
    df = df_mensual.copy()
    max_month = int(df['Mes'].max())
    meses_range = np.arange(0, max_month + 1)
    
    # --- PREPARACIÓN DE DATOS ---
    
    # Función auxiliar para interpolar a meses enteros
    def interpolar_sim(df_sim):
        # Asumiendo que df_sim ya está ordenada por mes
        x = df_sim['Mes'].values
        
        # Interpolar acumulados para consistencia
        ventas_acum = np.interp(meses_range, x, np.cumsum(df_sim['Ventas'].values))
        egresos_acum = np.interp(meses_range, x, np.cumsum(df_sim['Egresos_Obra'].values + df_sim['Egresos_Tierra'].values))
        cash_acum = np.interp(meses_range, x, df_sim['Cash_Acumulado'].values)
        
        # Derivar mensuales
        ventas = np.diff(ventas_acum, prepend=0)
        egresos = np.diff(egresos_acum, prepend=0)
        neto = ventas - egresos
        
        return pd.DataFrame({
            'Mes_Int': meses_range,
            'Ingresos': ventas,
            'Egresos': egresos, # Positivo para graficar
            'Flujo_Neto': neto,
            'Cash_Acumulado': cash_acum
        })

    if es_montecarlo and 'sim_id' in df.columns:
        # Procesar Monte Carlo
        sims = []
        # Optimizacion: Si hay muchas sim, tomar sample para performance visual
        unique_sims = df['sim_id'].unique()
        if len(unique_sims) > 100:
            unique_sims = unique_sims[:100]
            
        for sid in unique_sims:
            df_s = df[df['sim_id'] == sid].sort_values('Mes')
            s_interp = interpolar_sim(df_s)
            s_interp['sim_id'] = sid
            sims.append(s_interp)
        df_all = pd.concat(sims)
        
        # Estadísticas para Balance (Fan Chart)
        stats_balance = df_all.groupby('Mes_Int')['Cash_Acumulado'].quantile([0.05, 0.5, 0.95]).unstack()
        stats_balance.columns = ['P05', 'P50', 'P95']
        stats_balance = stats_balance.reset_index()
        
        # Estadísticas para Flujos
        stats_flow_median = df_all.groupby('Mes_Int')[['Ingresos', 'Egresos', 'Flujo_Neto']].median().reset_index()
        
        # CI para Ingresos y Egresos (Whiskers) + Flujo Neto (Area)
        stats_flow_ci = df_all.groupby('Mes_Int')[['Ingresos', 'Egresos', 'Flujo_Neto']].quantile([0.05, 0.95]).unstack()
        stats_flow_ci.columns = ['Ingresos_P05', 'Ingresos_P95', 'Egresos_P05', 'Egresos_P95', 'Flow_P05', 'Flow_P95']
        
        # Merge de todo
        stats_flow = pd.merge(stats_flow_median, stats_flow_ci, on='Mes_Int')
        
    else:
        # Determinístico
        stats_flow = interpolar_sim(df.sort_values('Mes'))
        stats_balance = pd.DataFrame({
            'Mes_Int': stats_flow['Mes_Int'],
            'P50': stats_flow['Cash_Acumulado'] 
        })

    # --- GRÁFICO 1: FLUJOS MENSUALES (Arriba) ---
    
    # Preparar datos tidy para barras
    df_bars = pd.melt(stats_flow, id_vars=['Mes_Int'], value_vars=['Ingresos', 'Egresos'], var_name='Tipo', value_name='Monto')
    # Egresos negativos visualmente
    df_bars.loc[df_bars['Tipo'] == 'Egresos', 'Monto'] *= -1
    
    top_layers = []
    
    base_flow = alt.Chart(df_bars).encode(x=alt.X('Mes_Int:Q', title=None, axis=alt.Axis(labelAngle=0, tickMinStep=1, tickSize=0)))
    
    bars = base_flow.mark_bar(cornerRadius=4, opacity=0.8, width=15).encode(
        y=alt.Y('Monto:Q', title='Flujo Mensual', axis=alt.Axis(format='$,.2f')),
        color=alt.Color('Tipo:N', scale=alt.Scale(domain=['Ingresos', 'Egresos'], range=['#3B82F6', '#EF4444']), legend=None),
        tooltip=['Mes_Int', 'Tipo', alt.Tooltip('Monto', format='$,.2f')]
    )
    top_layers.append(bars)
    
    # Intervalo de Confianza (Whiskers)
    if es_montecarlo and 'Ingresos_P05' in stats_flow.columns:
        # Calcular columnas neg para Egresos
        stats_flow['Egresos_P05_Neg'] = -stats_flow['Egresos_P05']
        stats_flow['Egresos_P95_Neg'] = -stats_flow['Egresos_P95']
        
        # 1. Ingresos CI (Azul Oscuro)
        ci_ing_rule = alt.Chart(stats_flow).mark_rule(color='#172554', opacity=0.8, strokeWidth=2).encode(
            x='Mes_Int:Q', y='Ingresos_P05:Q', y2='Ingresos_P95:Q'
        )
        # ci_ing_p05 y p95 eliminados para reducir ruido visual
        top_layers.append(ci_ing_rule)
        
        # 2. Egresos CI (Rojo Oscuro) - Invertidos
        ci_egr_rule = alt.Chart(stats_flow).mark_rule(color='#7F1D1D', opacity=0.8, strokeWidth=2).encode(
            x='Mes_Int:Q', y='Egresos_P05_Neg:Q', y2='Egresos_P95_Neg:Q'
        )
        # ci_egr_p05 y p95 eliminados para reducir ruido visual
        top_layers.append(ci_egr_rule)
        
        # 3. Flujo Neto CI (Lineas Verticales Blancas) - Petición de usuario
        if 'Flow_P05' in stats_flow.columns:
            ci_net_flow = alt.Chart(stats_flow).mark_rule(color='white', opacity=0.4, strokeWidth=2).encode(
                x='Mes_Int:Q', y='Flow_P05:Q', y2='Flow_P95:Q'
            )
            top_layers.append(ci_net_flow)

    # Ticks de Flujo Neto (Blanco)
    ticks_net = alt.Chart(stats_flow).mark_tick(thickness=2, size=12, opacity=0.9, color='white', orient='horizontal').encode(
        x='Mes_Int:Q',
        y='Flujo_Neto:Q',
        tooltip=['Mes_Int', alt.Tooltip('Flujo_Neto', format='$,.2f')]
    )
    top_layers.append(ticks_net)
    
    # Fin de Obra
    if fin_obra:
        df_const = pd.DataFrame([{'Mes_Int': fin_obra}])
        rule_const = alt.Chart(df_const).mark_rule(color=COLORS['text_muted'], strokeDash=[4,4], strokeWidth=2).encode(x='Mes_Int:Q')
        top_layers.append(rule_const)

    top_chart = alt.layer(*top_layers).properties(
        title=alt.TitleParams('Ingresos vs Egresos (Neto)', fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=CHART_HEIGHT_MAIN
    )

    # --- GRÁFICO 2: BALANCE ACUMULADO (Abajo) ---
    
    bottom_layers = []
    
    base_bal = alt.Chart(stats_balance).encode(x=alt.X('Mes_Int:Q', title='Mes', axis=alt.Axis(labelAngle=0, tickMinStep=1)))
    
    if es_montecarlo and 'P05' in stats_balance.columns:
        # Fan Chart
        band_ci = base_bal.mark_area(opacity=0.3, color='white').encode(
            y='P05:Q',
            y2='P95:Q'
        )
        bottom_layers.append(band_ci)
        
    # Línea Mediana
    line_main = base_bal.mark_line(color='white', strokeWidth=3).encode(
        y=alt.Y('P50:Q', title='Balance Acumulado', axis=alt.Axis(format='$,.2f')),
        tooltip=[alt.Tooltip('P50', title='Balance', format='$,.2f')]
    )
    bottom_layers.append(line_main)
    
    # Línea Cero
    zero = alt.Chart(pd.DataFrame({'y':[0]})).mark_rule(color=COLORS['text_muted'], strokeDash=[4,4]).encode(y='y:Q')
    bottom_layers.append(zero)
    
    # --- HITOS ---
    min_idx = stats_balance['P50'].idxmin()
    min_val = stats_balance.loc[min_idx, 'P50']
    
    # Peak Exposure
    if min_val < 0:
        df_min = stats_balance.loc[[min_idx]]
        pt_min = alt.Chart(df_min).mark_circle(size=100, color='#EF4444', opacity=1).encode(
            x='Mes_Int:Q', y='P50:Q', tooltip=[alt.Tooltip('P50', title='Capital Trabajo', format='$,.2f')]
        )
        # Etiqueta
        txt_min = alt.Chart(df_min).mark_text(align='center', dy=20, fontSize=11, color='#EF4444', fontStyle='italic').encode(
            x='Mes_Int:Q', y='P50:Q', text=alt.Text('P50', format='$,.2f')
        )
        bottom_layers.extend([pt_min, txt_min])
        
    if break_even_month and break_even_month > 0:
        # Break Even EXACTO en Y=0
        df_be = pd.DataFrame([{'Mes_Int': break_even_month, 'P50': 0}])
        pt_be = alt.Chart(df_be).mark_circle(size=100, color='#10B981', opacity=1).encode(
            x=alt.X('Mes_Int:Q', title='Mes'), 
            y='P50:Q', 
            tooltip=[alt.Tooltip('Mes_Int', title='Mes Break Even', format='.1f')]
        )
        bottom_layers.append(pt_be)
        
    if fin_obra:
        df_const = pd.DataFrame([{'Mes_Int': fin_obra}])
        rule_const = alt.Chart(df_const).mark_rule(color=COLORS['text_muted'], strokeDash=[4,4], strokeWidth=2).encode(x='Mes_Int:Q')
        txt_const = alt.Chart(df_const).mark_text(align='center', dy=-10, fontSize=10, color=COLORS['text_muted']).encode(x='Mes_Int:Q', y=alt.value(0), text=alt.value('Fin Obra'))
        bottom_layers.extend([rule_const, txt_const])
        
    bottom_chart = alt.layer(*bottom_layers).properties(
        title=alt.TitleParams('Evolución del Saldo (Riesgo)', fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=200
    )
    
    return alt.vconcat(top_chart, bottom_chart).resolve_scale(x='shared')


# =============================================================================
# MAPAS DE CALOR DE SENSIBILIDAD (lado a lado)
# =============================================================================

def crear_matrices_sensibilidad(df_sens: pd.DataFrame) -> alt.HConcatChart:
    """
    Genera gráficos de burbujas (Bubble Matrix) para sensibilidad
    montados sobre una curva frontera (métrica ~= 0).
    X: Var Precio, Y: Var Costo, Size: Magnitud, Color: Signo.
    """
    # Reemplazar NaN para evitar errores de JSON
    df_clean = df_sens.copy()
    df_clean['TIR'] = df_clean['TIR'].fillna(0)
    df_clean['VAN'] = df_clean['VAN'].fillna(0)
    
    # Calcular absolutos para el tamaño de la burbuja
    df_clean['abs_VAN'] = df_clean['VAN'].abs()
    df_clean['abs_TIR'] = df_clean['TIR'].abs()
    
    def make_bubble_with_zero_line(metric: str, abs_col: str, title: str):
        format_str = '~s' if metric == 'VAN' else '.1%'
        
        # 1. Base chart for axes (Cambiado a Q para permitir interpolacion continua)
        base = alt.Chart(df_clean).encode(
            x=alt.X('Variacion_Precio:Q', title='Var. Precio', 
                    axis=alt.Axis(format='%', labelAngle=0)),
            y=alt.Y('Variacion_Costo:Q', title='Var. Costo', 
                    scale=alt.Scale(reverse=True),
                    axis=alt.Axis(format='%'))
        )
        
        # 2. Bubble layer
        bubbles = base.mark_circle().encode(
            size=alt.Size(f'{abs_col}:Q', legend=None, scale=alt.Scale(range=[100, 1000])), 
            color=alt.condition(
                alt.datum[metric] >= 0,
                alt.value('#3B82F6'), # Blue (Positivo)
                alt.value('#EF4444')  # Red (Negativo)
            ),
            tooltip=[
                alt.Tooltip('Variacion_Precio:Q', format='+.2%', title='Var. Precio'),
                alt.Tooltip('Variacion_Costo:Q', format='+.2%', title='Var. Costo'),
                alt.Tooltip(f'{metric}:Q', format=format_str)
            ]
        )
        
        # 3. Frontera Cero (Zero Contour) mediante interpolación Spline 2D
        zero_puntos = []
        try:
            from scipy.interpolate import RectBivariateSpline
            import numpy as np
            
            p_vals = np.sort(df_clean['Variacion_Precio'].unique())
            c_vals = np.sort(df_clean['Variacion_Costo'].unique())
            
            # Crear matriz Z (Costo filas, Precio columnas)
            Z = df_clean.pivot(index='Variacion_Costo', columns='Variacion_Precio', values=metric).sort_index().sort_index(axis=1).values
            
            if Z.shape == (len(c_vals), len(p_vals)) and len(c_vals) >= 3 and len(p_vals) >= 3:
                k_degree = min(3, len(c_vals)-1, len(p_vals)-1)
                spline = RectBivariateSpline(c_vals, p_vals, Z, kx=k_degree, ky=k_degree)
                
                p_dense = np.linspace(p_vals.min(), p_vals.max(), 100)
                c_dense = np.linspace(c_vals.min(), c_vals.max(), 100)
                Z_dense = spline(c_dense, p_dense)
                
                for i, p in enumerate(p_dense):
                    col_vals = Z_dense[:, i]
                    # Encontrar los cruces por cero
                    crossings = np.where(np.diff(np.sign(col_vals)))[0]
                    if len(crossings) > 0:
                        j = crossings[0]
                        diff = col_vals[j+1] - col_vals[j]
                        if diff != 0:
                            pct = (0 - col_vals[j]) / diff
                            c_zero = c_dense[j] + pct * (c_dense[j+1] - c_dense[j])
                            zero_puntos.append({'Variacion_Precio': float(p), 'Variacion_Costo': float(c_zero)})
                            
            df_zero = pd.DataFrame(zero_puntos)
        except Exception:
            df_zero = pd.DataFrame(columns=['Variacion_Precio', 'Variacion_Costo'])
        
        if len(df_zero) > 0:
            # Sombra oscura de bajo contraste para que la linea destaque sobre burbujas
            zero_line_bg = alt.Chart(df_zero).mark_line(
                color='#1f2937', strokeWidth=5, opacity=0.4
            ).encode(
                x=alt.X('Variacion_Precio:Q'),
                y=alt.Y('Variacion_Costo:Q'),
                tooltip=[
                    alt.Tooltip('Variacion_Precio:Q', format='+.2%', title='Precio (Quiebre)'),
                    alt.Tooltip('Variacion_Costo:Q', format='+.2%', title='Costo (Quiebre)')
                ]
            )
            
            # Linea suave de los valores neutrales
            zero_line = alt.Chart(df_zero).mark_line(
                color='white', strokeWidth=2, opacity=1.0, strokeDash=[4, 4]
            ).encode(
                x=alt.X('Variacion_Precio:Q'),
                y=alt.Y('Variacion_Costo:Q'),
                tooltip=[
                    alt.Tooltip('Variacion_Precio:Q', format='+.2%', title='Precio (Quiebre)'),
                    alt.Tooltip('Variacion_Costo:Q', format='+.2%', title='Costo (Quiebre)')
                ]
            )
            capa = alt.layer(bubbles, zero_line_bg, zero_line)
        else:
            capa = bubbles
            
        return capa.properties(
            title=alt.TitleParams(title, fontSize=14, anchor='start'),
            width=350,
            height=350
        )
    
    chart_van = make_bubble_with_zero_line('VAN', 'abs_VAN', 'Sensibilidad VAN (Bubbles)')
    chart_tir = make_bubble_with_zero_line('TIR', 'abs_TIR', 'Sensibilidad TIR (Bubbles)')
    
    return chart_van, chart_tir

# =============================================================================
# GRÁFICOS MONTE CARLO
# =============================================================================

def _crear_histograma(df: pd.DataFrame, column: str, title: str, 
                      color: str, format_fn, subtitle: str = None) -> alt.Chart:
    """Helper para crear histogramas con percentiles."""
    data = df[column].dropna()
    if len(data) == 0:
        return alt.Chart(pd.DataFrame()).mark_text(text='Sin datos')
    
    p05 = data.quantile(0.05)
    p50 = data.quantile(0.5)
    p95 = data.quantile(0.95)
    
    # Histograma - Barras Azules por defecto (Estilo FT)
    hist = alt.Chart(df).mark_bar(color='#3B82F6', opacity=0.8).encode(
        x=alt.X(f'{column}:Q', bin=alt.Bin(maxbins=30), title=title,
               axis=alt.Axis(format='$,.2f' if 'VAN' in column or 'Venta' in column or 'Costo' in column else '.1%')),
        y=alt.Y('count()', title='Frecuencia')
    )
    
    # Líneas de percentiles
    df_lines = pd.DataFrame([
        {'x': p05, 'label': 'P05', 'pct': 'P05', 'color': '#EF4444'}, # Rojo (Pesimista)
        {'x': p50, 'label': 'Mediana', 'pct': 'P50', 'color': 'white'}, # Blanco (Central)
        {'x': p95, 'label': 'P95', 'pct': 'P95', 'color': '#3B82F6'}  # Azul (Optimista)
    ])
    
    rules = alt.Chart(df_lines).mark_rule(
        strokeDash=[3, 3],
        strokeWidth=2
    ).encode(
        x='x:Q',
        color=alt.Color('color:N', scale=None), # Usar color directo
        opacity=alt.value(0.9)
    )
    
    # Labels de percentiles
    labels = alt.Chart(df_lines).mark_text(
        align='center',
        dy=-10,
        fontSize=10,
        fontWeight='bold'
    ).encode(
        x='x:Q',
        y=alt.value(0),
        text=alt.Text('label:N'),
        color=alt.Color('color:N', scale=None)
    )
    
    chart_title = title
    chart_subtitle = subtitle or f"Mediana: {format_fn(p50)}"
    
    return alt.layer(hist, rules, labels).properties(
        title=alt.TitleParams(chart_title, subtitle=chart_subtitle, 
                             fontSize=14, anchor='start'),
        width=320,
        height=220
    )

def crear_graficos_montecarlo(df_mc: pd.DataFrame) -> Tuple[alt.Chart, alt.Chart]:
    """Histogramas de VAN y TIR."""
    from constants import format_currency, format_percent
    
    # Usar Azul consistente para métricas de valor
    chart_van = _crear_histograma(
        df_mc, 'VAN', 'Distribución VAN', 
        '#3B82F6', format_currency
    )
    
    chart_tir = _crear_histograma(
        df_mc.dropna(subset=['TIR']), 'TIR', 'Distribución TIR',
        '#3B82F6', format_percent
    )
    
    return chart_van, chart_tir


def crear_graficos_distribucion_montecarlo(df_mc: pd.DataFrame) -> Tuple[alt.Chart, alt.Chart]:
    """Histogramas de Ventas y Costos totales."""
    from constants import format_currency
    
    chart_ventas = _crear_histograma(
        df_mc, 'Total_Ventas', 'Ventas Totales',
        COLOR_INCOME, format_currency
    )
    
    chart_costos = _crear_histograma(
        df_mc, 'Total_Costo', 'Costos Totales',
        COLOR_EXPENSE, format_currency
    )
    
    return chart_ventas, chart_costos

