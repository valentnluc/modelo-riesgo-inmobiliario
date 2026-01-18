import os
from typing import Tuple, Optional
import pandas as pd
import numpy as np
import altair as alt

from constants import (
    COLORS, COLOR_INCOME, COLOR_EXPENSE, COLOR_NET, COLOR_ACCUM,
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

def _format_axis_k(field: str) -> alt.Axis:
    """Crea eje con formato K/M para valores."""
    return alt.Axis(format='~s', labelFontSize=10, titleFontSize=11, labelColor='#A1A1AA')


# --- Gráficos Unificados (Determinístico + Monte Carlo) ---

def get_unified_flow_chart(
    df_data: pd.DataFrame,
    is_montecarlo: bool = False,
    construction_end: int = None
) -> alt.Chart:
    """
    Gráfico unificado de flujos mensuales.
    - Determinístico: líneas sólidas.
    - Monte Carlo: medianas + bandas confianza (IC90%).
    """
    df = df_data.copy()
    max_month = int(df['Mes'].max())
    meses = np.arange(0, max_month + 1)
    
    def interpolar_a_meses(df_sim):
        """Interpola flujos acumulados a meses enteros y diferencia."""
        ventas_acum = np.cumsum(df_sim['Ventas'].values)
        obra_acum = np.cumsum(df_sim['Egresos_Obra'].values)
        tierra_acum = np.cumsum(df_sim['Egresos_Tierra'].values)
        
        ventas_interp = np.interp(meses, df_sim['Mes'].values, ventas_acum)
        obra_interp = np.interp(meses, df_sim['Mes'].values, obra_acum)
        tierra_interp = np.interp(meses, df_sim['Mes'].values, tierra_acum)
        
        return {
            'Mes_Int': meses,
            'Ventas': np.diff(ventas_interp, prepend=0),
            'Egresos_Obra': -np.diff(obra_interp, prepend=0),
            'Egresos_Tierra': -np.diff(tierra_interp, prepend=0)
        }
    
    if is_montecarlo and 'sim_id' in df.columns:
        # Interpolar cada simulación y agregar
        all_sims = []
        for sim_id in df['sim_id'].unique():
            df_sim = df[df['sim_id'] == sim_id].sort_values('Mes')
            interp = interpolar_a_meses(df_sim)
            interp['sim_id'] = sim_id
            all_sims.append(pd.DataFrame(interp))
        
        df_agg = pd.concat(all_sims)
        df_agg['Flujo_Neto'] = df_agg['Ventas'] + df_agg['Egresos_Obra'] + df_agg['Egresos_Tierra']
        
        # Calcular percentiles
        def calc_pcts(col):
            return df_agg.groupby('Mes_Int')[col].quantile([0.05, 0.5, 0.95]).unstack().reset_index()
        
        stats = {}
        for col in ['Ventas', 'Egresos_Obra', 'Flujo_Neto']:
            s = calc_pcts(col)
            s.columns = ['Mes_Int', 'P05', 'P50', 'P95']
            stats[col] = s
        
        # Tierra (sin variabilidad)
        stats_tierra = df_agg.groupby('Mes_Int')['Egresos_Tierra'].median().reset_index()
    else:
        # Modo determinístico
        interp = interpolar_a_meses(df.sort_values('Mes'))
        
        stats = {
            'Ventas': pd.DataFrame({'Mes_Int': meses, 'P50': interp['Ventas']}),
            'Egresos_Obra': pd.DataFrame({'Mes_Int': meses, 'P50': interp['Egresos_Obra']}),
            'Flujo_Neto': pd.DataFrame({'Mes_Int': meses, 'P50': interp['Ventas'] + interp['Egresos_Obra'] + interp['Egresos_Tierra']})
        }
        stats_tierra = pd.DataFrame({'Mes_Int': meses, 'Egresos_Tierra': interp['Egresos_Tierra']})
    
    layers = []
    
    # Preparar datos para líneas
    df_lines = []
    for tipo, color, label in [
        ('Ventas', COLOR_INCOME, 'Ingresos'),
        ('Egresos_Obra', COLOR_EXPENSE, 'Costos Obra')
    ]:
        s = stats[tipo].copy()
        s['Tipo'] = label
        s['Color'] = color
        df_lines.append(s)
    
    df_combined = pd.concat(df_lines)
    
    color_scale = alt.Scale(
        domain=['Ingresos', 'Costos Obra'],
        range=[COLOR_INCOME, COLOR_EXPENSE]
    )
    
    # Bandas de confianza (solo MC)
    if is_montecarlo and 'P05' in df_combined.columns:
        band = alt.Chart(df_combined).mark_area(opacity=0.25).encode(
            x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('P05:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
            y2='P95:Q',
            color=alt.Color('Tipo:N', scale=color_scale, legend=alt.Legend(orient='top', title=None))
        )
        layers.append(band)
    
    # Líneas medianas con puntos (puntos pequeños, líneas gruesas)
    line = alt.Chart(df_combined).mark_line(strokeWidth=3, point=alt.OverlayMarkDef(size=15)).encode(
        x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('P50:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
        color=alt.Color('Tipo:N', scale=color_scale, legend=alt.Legend(orient='top', title=None))
    )
    layers.append(line)
    
    # Barras de tierra
    tierra_bars = alt.Chart(stats_tierra).mark_bar(color='#ff8080', opacity=0.4).encode(
        x='Mes_Int:O',
        y=alt.Y('Egresos_Tierra:Q', axis=alt.Axis(format='~s'))
    )
    layers.insert(0, tierra_bars)
    
    # Línea de flujo neto (blanco punteado, puntos pequeños)
    line_neto = alt.Chart(stats['Flujo_Neto']).mark_line(
        color='white', strokeWidth=3, strokeDash=[4, 2], point=alt.OverlayMarkDef(size=12, color='white')
    ).encode(
        x='Mes_Int:O',
        y='P50:Q'
    )
    layers.append(line_neto)
    
    # Línea de fin de obra
    if construction_end is not None:
        max_m = stats['Ventas']['Mes_Int'].max()
        if construction_end <= max_m:
            df_const = pd.DataFrame([{'x': construction_end}])
            line_const = alt.Chart(df_const).mark_rule(color='#ffaa00', strokeWidth=2, strokeDash=[6, 4]).encode(x='x:O')
            label_const = alt.Chart(df_const).mark_text(
                align='center', dy=-10, fontSize=9, color='#ffaa00', fontWeight='bold'
            ).encode(x='x:O', y=alt.value(0), text=alt.value('Fin Obra'))
            layers.extend([line_const, label_const])
    
    title = 'Flujos Mensuales (IC 90%)' if is_montecarlo else 'Flujos Mensuales'
    return alt.layer(*layers).resolve_scale(y='shared').properties(
        title=alt.TitleParams(title, fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=CHART_HEIGHT_MAIN
    )


def get_unified_balance_chart(
    df_data: pd.DataFrame,
    is_montecarlo: bool = False,
    construction_end: int = None,
    break_even_month: float = None
) -> alt.Chart:
    """Gráfico unificado de saldo acumulado (Curva J)."""
    df = df_data.copy()
    max_month = int(df['Mes'].max())
    meses = np.arange(0, max_month + 1)
    
    # Función auxiliar para interpolar cash acumulado
    def interpolar_cash(df_sim):
        # Tomar último valor por mes si hay múltiples, luego interpolar
        return np.interp(meses, df_sim['Mes'].values, df_sim['Cash_Acumulado'].values)

    if is_montecarlo and 'sim_id' in df.columns:
        # Interpolar cada simulación
        all_sims = []
        for sim_id in df['sim_id'].unique():
            df_sim = df[df['sim_id'] == sim_id].sort_values('Mes')
            cash_interp = interpolar_cash(df_sim)
            all_sims.append(pd.DataFrame({'Mes_Int': meses, 'Cash_Acumulado': cash_interp}))
        
        df_agg = pd.concat(all_sims)
        stats = df_agg.groupby('Mes_Int')['Cash_Acumulado'].quantile([0.05, 0.5, 0.95]).unstack()
        stats.columns = ['P05', 'P50', 'P95']
        stats = stats.reset_index()
    else:
        # Modo determinístico
        cash_interp = interpolar_cash(df.sort_values('Mes'))
        stats = pd.DataFrame({'Mes_Int': meses, 'P50': cash_interp})
    
    layers = []
    
    # Banda de confianza (solo MC)
    if is_montecarlo and 'P05' in stats.columns:
        band = alt.Chart(stats).mark_area(opacity=0.2, color=COLOR_ACCUM).encode(
            x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('P05:Q', title='Saldo Acumulado', axis=alt.Axis(format='~s')),
            y2='P95:Q'
        )
        layers.append(band)
    
    # Área (solo determinístico)
    if not is_montecarlo:
        area = alt.Chart(stats).mark_area(color=COLOR_ACCUM, opacity=0.3).encode(
            x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('P50:Q', title='Saldo Acumulado', axis=alt.Axis(format='~s'))
        )
        layers.append(area)
    
    # Línea mediana con puntos (puntos pequeños, línea gruesa)
    line = alt.Chart(stats).mark_line(
        color=COLOR_ACCUM, strokeWidth=3, point=alt.OverlayMarkDef(size=15, color=COLOR_ACCUM)
    ).encode(
        x='Mes_Int:O',
        y='P50:Q'
    )
    layers.append(line)
    
    # Línea de cero
    zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
        color=COLORS['text_light'], strokeDash=[4, 4]
    ).encode(y='y:Q')
    layers.append(zero)
    
    # Punto de máximo déficit
    min_idx = stats['P50'].idxmin()
    min_row = stats.loc[min_idx]
    df_min = pd.DataFrame([{'Mes_Int': min_row['Mes_Int'], 'P50': min_row['P50']}])
    point_deficit = alt.Chart(df_min).mark_circle(size=80, color=COLOR_EXPENSE).encode(x='Mes_Int:O', y='P50:Q')
    label_deficit = alt.Chart(df_min).mark_text(
        align='left', dx=8, dy=-5, fontSize=10, fontWeight='bold', color=COLOR_EXPENSE
    ).encode(x='Mes_Int:O', y='P50:Q', text=alt.value('Max Déficit'))
    layers.extend([point_deficit, label_deficit])
    
    # Línea de fin de obra
    if construction_end is not None:
        df_const = pd.DataFrame([{'x': construction_end}])
        line_const = alt.Chart(df_const).mark_rule(color='#ffaa00', strokeWidth=2, strokeDash=[6, 4]).encode(x='x:O')
        label_const = alt.Chart(df_const).mark_text(
            align='center', dy=-10, fontSize=9, color='#ffaa00', fontWeight='bold'
        ).encode(x='x:O', y=alt.value(0), text=alt.value('Fin Obra'))
        layers.extend([line_const, label_const])
    
    # Punto de break-even
    if break_even_month is not None and break_even_month > 0:
        be_mes = int(round(break_even_month))
        if be_mes in stats['Mes_Int'].values:
            be_val = stats[stats['Mes_Int'] == be_mes]['P50'].iloc[0]
        else:
            be_val = 0
        df_be = pd.DataFrame([{'Mes_Int': be_mes, 'P50': be_val}])
        point_be = alt.Chart(df_be).mark_circle(size=80, color='#00ff88').encode(x='Mes_Int:O', y='P50:Q')
        label_be = alt.Chart(df_be).mark_text(
            align='left', dx=8, dy=5, fontSize=10, fontWeight='bold', color='#00ff88'
        ).encode(x='Mes_Int:O', y='P50:Q', text=alt.value('Break-Even'))
        layers.extend([point_be, label_be])
    
    title = 'Proyección de Saldo (IC 90%)' if is_montecarlo else 'Evolución del Saldo'
    return alt.layer(*layers).properties(
        title=alt.TitleParams(title, fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=CHART_HEIGHT_MAIN
    )


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
        y=alt.Y('Valor:Q', title='Inversión Acumulada', axis=alt.Axis(format='~s')),
        color=alt.Color('Preset:N')
    ).properties(title='Curvas de Costos', width=CHART_WIDTH, height=CHART_HEIGHT_MAIN)


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
    # Discretizar por mes
    df = df_flow.copy()
    df['Mes_Int'] = df['Mes'].round().astype(int)
    df_agg = df.groupby('Mes_Int').agg({
        'Ventas': 'sum',
        'Egresos_Obra': 'sum',
        'Egresos_Tierra': 'sum',
        'Flujo_Neto': 'sum',
        'Cash_Acumulado': 'last'
    }).reset_index()
    
    # Preparar datos para barras apiladas
    df_bars = pd.melt(
        df_agg,
        id_vars=['Mes_Int'],
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
        x=alt.X('Mes_Int:O', title=None, axis=alt.Axis(labelAngle=0, tickSize=0)),
        y=alt.Y('Monto:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
        color=alt.Color('Tipo:N',
            scale=alt.Scale(
                domain=['Ingresos', 'Costos Obra', 'Costos Tierra'],
                range=[COLOR_INCOME, COLOR_EXPENSE, COLORS['tertiary']]
            ),
            legend=alt.Legend(orient='top', title=None, labelFontSize=10)
        ),
        tooltip=[
            alt.Tooltip('Mes_Int:O', title='Mes'),
            alt.Tooltip('Tipo:N'),
            alt.Tooltip('Monto:Q', format=',.0f')
        ]
    )
    
    # Línea de flujo neto (blanco para mejor visibilidad)
    line_net = alt.Chart(df_agg).mark_line(
        color='white',
        strokeWidth=2.5,
        strokeDash=[4, 2]
    ).encode(
        x='Mes_Int:O',
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
        x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Cash_Acumulado:Q', 
                title='Cash Acumulado',
                axis=alt.Axis(format='~s'))
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
        'Mes_Int': min_row['Mes_Int'],
        'Cash_Acumulado': min_row['Cash_Acumulado'],
    }])
    
    point_min = alt.Chart(df_min).mark_circle(
        size=80,
        color=COLOR_EXPENSE
    ).encode(
        x='Mes_Int:O',
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
        x='Mes_Int:O',
        y='Cash_Acumulado:Q',
        text=alt.value('Max Inversión')
    )
    
    bottom_layers = [area, zero_line, point_min, label_min]
    
    # Línea de fin de obra
    if construction_end_month is not None:
        df_const = pd.DataFrame([{'Mes_Int': construction_end_month}])
        rule_const = alt.Chart(df_const).mark_rule(
            color=COLORS['text_light'],
            strokeDash=[2, 2]
        ).encode(x='Mes_Int:O')
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
    df_mc_curvas: Optional[pd.DataFrame] = None,
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
        y=alt.Y('Monto:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
        color=alt.Color('Tipo:N', scale=alt.Scale(domain=['Ingresos', 'Egresos'], range=['#3B82F6', '#EF4444']), legend=None),
        tooltip=['Mes_Int', 'Tipo', alt.Tooltip('Monto', format='~s')]
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
        tooltip=['Mes_Int', alt.Tooltip('Flujo_Neto', format='~s')]
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
        y=alt.Y('P50:Q', title='Balance Acumulado', axis=alt.Axis(format='~s')),
        tooltip=[alt.Tooltip('P50', title='Balance', format='~s')]
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
            x='Mes_Int:Q', y='P50:Q', tooltip=[alt.Tooltip('P50', title='Capital Trabajo', format='~s')]
        )
        # Etiqueta
        txt_min = alt.Chart(df_min).mark_text(align='center', dy=20, fontSize=11, color='#EF4444', fontStyle='italic').encode(
            x='Mes_Int:Q', y='P50:Q', text=alt.Text('P50', format='~s')
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
    Genera gráficos de burbujas (Bubble Matrix) para sensibilidad.
    X: Var Precio, Y: Var Costo, Size: Magnitud, Color: Signo.
    """
    # Reemplazar NaN para evitar errores de JSON
    df_clean = df_sens.copy()
    df_clean['TIR'] = df_clean['TIR'].fillna(0)
    df_clean['VAN'] = df_clean['VAN'].fillna(0)
    
    # Calcular absolutos para el tamaño de la burbuja
    df_clean['abs_VAN'] = df_clean['VAN'].abs()
    df_clean['abs_TIR'] = df_clean['TIR'].abs()
    
    def make_bubble_matrix(metric: str, abs_col: str, title: str):
        format_str = '~s' if metric == 'VAN' else '.1%'
        
        base = alt.Chart(df_clean).encode(
            x=alt.X('Variacion_Precio:O',
                    title='Var. Precio',
                    axis=alt.Axis(format='+.0%', labelAngle=0)),
            y=alt.Y('Variacion_Costo:O',
                    title='Var. Costo',
                    sort='descending',
                    axis=alt.Axis(format='+.0%'))
        )
        
        bubbles = base.mark_circle().encode(
            size=alt.Size(f'{abs_col}:Q', legend=None, scale=alt.Scale(range=[100, 1000])), # Rango de tamaños visuales
            color=alt.condition(
                alt.datum[metric] >= 0,
                alt.value('#3B82F6'), # Blue
                alt.value('#EF4444')  # Red
            ),
            tooltip=[
                alt.Tooltip('Variacion_Precio:Q', format='+.0%', title='Precio'),
                alt.Tooltip('Variacion_Costo:Q', format='+.0%', title='Costo'),
                alt.Tooltip(f'{metric}:Q', format=format_str)
            ]
        )
        
        return bubbles.properties(
            title=alt.TitleParams(title, fontSize=14, anchor='start'),
            width=350,
            height=400
        )
    
    chart_van = make_bubble_matrix('VAN', 'abs_VAN', 'Sensibilidad VAN (Bubbles)')
    chart_tir = make_bubble_matrix('TIR', 'abs_TIR', 'Sensibilidad TIR (Bubbles)')
    
    return chart_van, chart_tir


def get_sensitivity_heatmap(df_sens: pd.DataFrame, metric: str = 'VAN') -> alt.Chart:
    """Genera un solo mapa de calor (legacy)."""
    mid_val = 0 if metric == 'VAN' else df_sens['TIR'].median()
    
    base = alt.Chart(df_sens).encode(
        x=alt.X('Variacion_Precio:O', title='Var. Precio', axis=alt.Axis(format='.0%')),
        y=alt.Y('Variacion_Costo:O', title='Var. Costo', sort='descending', axis=alt.Axis(format='.0%'))
    )
    
    return base.mark_rect().encode(
        color=alt.Color(f'{metric}:Q', scale=alt.Scale(scheme='redblue', domainMid=mid_val))
    ).properties(width=300, height=260)


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
               axis=alt.Axis(format='~s' if 'VAN' in column or 'Venta' in column or 'Costo' in column else '.1%')),
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


def get_montecarlo_confidence_chart(df_curves: pd.DataFrame,
                                     construction_end: int = None,
                                     break_even_month: float = None) -> alt.Chart:
    """Bandas de confianza para cash acumulado - discretizado por mes."""
    if df_curves.empty:
        return alt.Chart(pd.DataFrame()).mark_text(text='Sin datos')
    
    # Discretizar por mes
    df = df_curves.copy()
    df['Mes_Int'] = df['Mes'].round().astype(int)
    
    # Agregar por sim_id y mes, tomando el ULTIMO valor de cash acumulado
    df_agg = df.groupby(['sim_id', 'Mes_Int']).agg({
        'Cash_Acumulado': 'last'
    }).reset_index()
    
    # Calcular percentiles sobre las simulaciones para cada mes
    stats = df_agg.groupby('Mes_Int')['Cash_Acumulado'].quantile([0.05, 0.5, 0.95]).unstack()
    stats.columns = ['P05', 'P50', 'P95']
    stats = stats.reset_index()
    
    base = alt.Chart(stats).encode(
        x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0))
    )
    
    band = base.mark_area(opacity=0.2, color=COLOR_ACCUM).encode(
        y=alt.Y('P05:Q', title='Cash Acumulado', axis=alt.Axis(format='~s')),
        y2='P95:Q'
    )
    
    line = base.mark_line(color=COLOR_ACCUM, strokeWidth=2).encode(
        y='P50:Q'
    )
    
    zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
        color=COLORS['text_light'], strokeDash=[4, 4]
    ).encode(y='y:Q')
    
    layers = [band, line, zero]
    
    # Punto de máximo déficit (mediana)
    min_idx = stats['P50'].idxmin()
    min_row = stats.loc[min_idx]
    df_min = pd.DataFrame([{'Mes_Int': min_row['Mes_Int'], 'P50': min_row['P50']}])
    point_deficit = alt.Chart(df_min).mark_circle(size=80, color=COLOR_EXPENSE).encode(
        x='Mes_Int:O', y='P50:Q'
    )
    label_deficit = alt.Chart(df_min).mark_text(
        align='left', dx=8, dy=-5, fontSize=10, fontWeight='bold', color=COLOR_EXPENSE
    ).encode(x='Mes_Int:O', y='P50:Q', text=alt.value('Max Déficit'))
    layers.extend([point_deficit, label_deficit])
    
    # Línea de fin de obra
    if construction_end is not None:
        df_const = pd.DataFrame([{'x': construction_end}])
        line_const = alt.Chart(df_const).mark_rule(
            color='#ffaa00', strokeWidth=2, strokeDash=[6, 4]
        ).encode(x='x:O')
        label_const = alt.Chart(df_const).mark_text(
            align='center', dy=-10, fontSize=9, color='#ffaa00', fontWeight='bold'
        ).encode(x='x:O', y=alt.value(0), text=alt.value('Fin Obra'))
        layers.extend([line_const, label_const])
    
    # Punto de break-even
    if break_even_month is not None and break_even_month > 0:
        be_mes = int(round(break_even_month))
        if be_mes in stats['Mes_Int'].values:
            be_val = stats[stats['Mes_Int'] == be_mes]['P50'].iloc[0]
        else:
            be_val = 0
        df_be = pd.DataFrame([{'Mes_Int': be_mes, 'P50': be_val}])
        point_be = alt.Chart(df_be).mark_circle(size=80, color='#00ff88').encode(
            x='Mes_Int:O', y='P50:Q'
        )
        label_be = alt.Chart(df_be).mark_text(
            align='left', dx=8, dy=5, fontSize=10, fontWeight='bold', color='#00ff88'
        ).encode(x='Mes_Int:O', y='P50:Q', text=alt.value('Break-Even'))
        layers.extend([point_be, label_be])
    
    return alt.layer(*layers).properties(
        title=alt.TitleParams('Proyeccion de Saldo (IC 90%)', fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=CHART_HEIGHT_MAIN
    )


def get_montecarlo_flow_confidence_chart(df_curves: pd.DataFrame,
                                          construction_end: int = None) -> alt.Chart:
    """Bandas de confianza para flujos - discretizado por mes."""
    if df_curves.empty or 'Ventas' not in df_curves.columns:
        return alt.Chart(pd.DataFrame()).mark_text(text='Sin datos')
    
    df = df_curves.copy()
    df['Mes_Int'] = df['Mes'].round().astype(int)
    
    # Agregar por sim_id y mes
    df_agg = df.groupby(['sim_id', 'Mes_Int']).agg({
        'Ventas': 'sum',
        'Egresos_Obra': 'sum',
        'Egresos_Tierra': 'sum'
    }).reset_index()
    
    # Hacer costos negativos (como en determinístico)
    df_agg['Egresos_Obra'] = -df_agg['Egresos_Obra']
    df_agg['Egresos_Tierra'] = -df_agg['Egresos_Tierra']
    
    # Calcular percentiles para Ingresos y Costos Obra (variables)
    def calc_stats(col, tipo):
        s = df_agg.groupby('Mes_Int')[col].quantile([0.05, 0.5, 0.95]).unstack()
        s.columns = ['P05', 'P50', 'P95']
        s['Tipo'] = tipo
        return s.reset_index()
    
    stats_inc = calc_stats('Ventas', 'Ingresos')
    stats_obra = calc_stats('Egresos_Obra', 'Costos Obra')
    df_stats = pd.concat([stats_inc, stats_obra])
    
    # Tierra no tiene variabilidad - usar solo mediana (ya negativa)
    stats_tierra = df_agg.groupby('Mes_Int')['Egresos_Tierra'].median().reset_index()
    stats_tierra.columns = ['Mes_Int', 'Monto']
    
    color_scale = alt.Scale(
        domain=['Ingresos', 'Costos Obra'],
        range=[COLOR_INCOME, COLOR_EXPENSE]
    )
    
    base = alt.Chart(df_stats).encode(
        x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0))
    )
    
    # Bandas de confianza para Ingresos y Costos Obra
    band = base.mark_area(opacity=0.35).encode(
        y=alt.Y('P05:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
        y2='P95:Q',
        color=alt.Color('Tipo:N', scale=color_scale, legend=alt.Legend(orient='top', title=None))
    )
    
    line = base.mark_line(strokeWidth=2).encode(
        y='P50:Q',
        color=alt.Color('Tipo:N', scale=color_scale, legend=None)
    )
    
    # Barras de tierra (sin variabilidad) - color diferenciado
    tierra_bars = alt.Chart(stats_tierra).mark_bar(
        color='#ff8080',  # Rojo claro para tierra
        opacity=0.4
    ).encode(
        x='Mes_Int:O',
        y=alt.Y('Monto:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
        tooltip=[alt.Tooltip('Mes_Int:O', title='Mes'), alt.Tooltip('Monto:Q', title='Tierra', format=',.0f')]
    )
    
    # Calcular flujo neto medio (ventas - costos obra - costos tierra)
    df_agg['Flujo_Neto'] = df_agg['Ventas'] + df_agg['Egresos_Obra'] + df_agg['Egresos_Tierra']
    flujo_neto_stats = df_agg.groupby('Mes_Int')['Flujo_Neto'].median().reset_index()
    flujo_neto_stats.columns = ['Mes_Int', 'Flujo_Neto']
    
    # Línea de flujo neto medio (blanco punteado)
    line_flujo = alt.Chart(flujo_neto_stats).mark_line(
        color='white',
        strokeWidth=2.5,
        strokeDash=[4, 2]
    ).encode(
        x='Mes_Int:O',
        y=alt.Y('Flujo_Neto:Q')
    )
    
    layers = [tierra_bars, band, line, line_flujo]
    
    # Línea de fin de obra
    if construction_end is not None:
        max_month = df['Mes_Int'].max()
        if construction_end <= max_month:
            df_const = pd.DataFrame([{'x': construction_end}])
            line_const = alt.Chart(df_const).mark_rule(
                color='#ffaa00', strokeWidth=2, strokeDash=[6, 4]
            ).encode(x='x:O')
            label_const = alt.Chart(df_const).mark_text(
                align='center', dy=-10, fontSize=9, color='#ffaa00', fontWeight='bold'
            ).encode(x='x:O', y=alt.value(0), text=alt.value('Fin Obra'))
            layers.extend([line_const, label_const])
    
    return alt.layer(*layers).resolve_scale(y='shared').properties(
        title=alt.TitleParams('Flujos Mensuales (IC 90%)', fontSize=14, anchor='start'),
        width=CHART_WIDTH,
        height=CHART_HEIGHT_MAIN
    )


# =============================================================================
# GRÁFICO INDIVIDUAL DE SALDO ACUMULADO
# =============================================================================

def get_accum_chart(df_flow: pd.DataFrame, 
                    construction_end: int = None,
                    break_even_month: float = None) -> alt.Chart:
    """Gráfico de área del saldo acumulado (standalone)."""
    df = df_flow.copy()
    df['Mes_Int'] = df['Mes'].round().astype(int)
    df_agg = df.groupby('Mes_Int').agg({'Cash_Acumulado': 'last'}).reset_index()
    
    # Área con línea
    area = alt.Chart(df_agg).mark_area(
        color=COLOR_ACCUM,
        opacity=0.3,
        line={'color': COLOR_ACCUM, 'strokeWidth': 2}
    ).encode(
        x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Cash_Acumulado:Q', title='Saldo Acumulado', axis=alt.Axis(format='~s'))
    )
    
    # Línea de cero
    zero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
        color=COLORS['text_light'], strokeDash=[4, 4]
    ).encode(y='y:Q')
    
    layers = [area, zero]
    
    # Punto de máximo déficit
    min_idx = df_agg['Cash_Acumulado'].idxmin()
    min_row = df_agg.loc[min_idx]
    df_min = pd.DataFrame([{'Mes_Int': min_row['Mes_Int'], 'Cash_Acumulado': min_row['Cash_Acumulado']}])
    
    point_deficit = alt.Chart(df_min).mark_circle(size=80, color=COLOR_EXPENSE).encode(
        x='Mes_Int:O', y='Cash_Acumulado:Q'
    )
    label_deficit = alt.Chart(df_min).mark_text(
        align='left', dx=8, dy=-5, fontSize=10, fontWeight='bold', color=COLOR_EXPENSE
    ).encode(x='Mes_Int:O', y='Cash_Acumulado:Q', text=alt.value('Max Déficit'))
    layers.extend([point_deficit, label_deficit])
    
    # Línea de fin de obra
    if construction_end is not None:
        df_const = pd.DataFrame([{'x': construction_end}])
        line_const = alt.Chart(df_const).mark_rule(
            color='#ffaa00', strokeWidth=2, strokeDash=[6, 4]
        ).encode(x='x:O')
        label_const = alt.Chart(df_const).mark_text(
            align='center', dy=-10, fontSize=9, color='#ffaa00', fontWeight='bold'
        ).encode(x='x:O', y=alt.value(0), text=alt.value('Fin Obra'))
        layers.extend([line_const, label_const])
    
    # Punto de break-even
    if break_even_month is not None and break_even_month > 0:
        be_mes = int(round(break_even_month))
        if be_mes in df_agg['Mes_Int'].values:
            be_val = df_agg[df_agg['Mes_Int'] == be_mes]['Cash_Acumulado'].iloc[0]
        else:
            be_val = 0
        df_be = pd.DataFrame([{'Mes_Int': be_mes, 'Cash_Acumulado': be_val}])
        point_be = alt.Chart(df_be).mark_circle(size=80, color='#00ff88').encode(
            x='Mes_Int:O', y='Cash_Acumulado:Q'
        )
        label_be = alt.Chart(df_be).mark_text(
            align='left', dx=8, dy=5, fontSize=10, fontWeight='bold', color='#00ff88'
        ).encode(x='Mes_Int:O', y='Cash_Acumulado:Q', text=alt.value('Break-Even'))
        layers.extend([point_be, label_be])
    
    return alt.layer(*layers).properties(
        title=alt.TitleParams('Evolucion del Saldo', fontSize=14, anchor='start'),
        width=CHART_WIDTH // 2,
        height=CHART_HEIGHT_MAIN
    )


def get_flow_bars_chart(df_flow: pd.DataFrame, construction_end: int = None) -> alt.Chart:
    """Gráfico de barras de flujos mensuales (standalone)."""
    import numpy as np
    
    df = df_flow.copy()
    
    # Mejor discretización: interpolar acumulados a meses enteros, luego diferenciar
    max_month = int(df['Mes'].max())
    meses = np.arange(0, max_month + 1)
    
    # Calcular acumulados
    ventas_acum = np.cumsum(df['Ventas'].values)
    obra_acum = np.cumsum(df['Egresos_Obra'].values)
    tierra_acum = np.cumsum(df['Egresos_Tierra'].values)
    
    # Interpolar acumulados a meses enteros
    ventas_interp = np.interp(meses, df['Mes'].values, ventas_acum)
    obra_interp = np.interp(meses, df['Mes'].values, obra_acum)
    tierra_interp = np.interp(meses, df['Mes'].values, tierra_acum)
    
    # Diferenciar para obtener valores mensuales
    ventas_mes = np.diff(ventas_interp, prepend=0)
    obra_mes = np.diff(obra_interp, prepend=0)
    tierra_mes = np.diff(tierra_interp, prepend=0)
    
    df_agg = pd.DataFrame({
        'Mes_Int': meses,
        'Ventas': ventas_mes,
        'Egresos_Obra': obra_mes,
        'Egresos_Tierra': tierra_mes
    })
    
    # Recalcular flujo neto para garantizar consistencia
    df_agg['Flujo_Neto'] = df_agg['Ventas'] - df_agg['Egresos_Obra'] - df_agg['Egresos_Tierra']
    
    # Preparar datos para barras
    df_bars = pd.melt(
        df_agg,
        id_vars=['Mes_Int'],
        value_vars=['Ventas', 'Egresos_Obra', 'Egresos_Tierra'],
        var_name='Tipo',
        value_name='Monto'
    )
    df_bars.loc[df_bars['Tipo'].str.contains('Egresos'), 'Monto'] *= -1
    df_bars['Tipo'] = df_bars['Tipo'].map({
        'Ventas': 'Ingresos',
        'Egresos_Obra': 'Costos Obra',
        'Egresos_Tierra': 'Costos Tierra'
    })
    
    bars = alt.Chart(df_bars).mark_bar(opacity=0.8).encode(
        x=alt.X('Mes_Int:O', title='Mes', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Monto:Q', title='Flujo Mensual', axis=alt.Axis(format='~s')),
        color=alt.Color('Tipo:N',
            scale=alt.Scale(
                domain=['Ingresos', 'Costos Obra', 'Costos Tierra'],
                range=[COLOR_INCOME, COLOR_EXPENSE, COLORS['tertiary']]
            ),
            legend=alt.Legend(orient='top', title=None, labelFontSize=9)
        ),
        tooltip=[alt.Tooltip('Mes_Int:O', title='Mes'), 'Tipo:N', alt.Tooltip('Monto:Q', format=',.0f')]
    )
    
    # Línea de flujo neto (blanco punteado)
    line = alt.Chart(df_agg).mark_line(
        color='white', 
        strokeWidth=2.5, 
        strokeDash=[4, 2],
        interpolate='monotone'
    ).encode(
        x='Mes_Int:O', 
        y='Flujo_Neto:Q'
    )
    
    layers = [bars, line]
    
    # Línea de fin de obra
    if construction_end is not None and construction_end <= max_month:
        df_const = pd.DataFrame([{'x': construction_end}])
        line_const = alt.Chart(df_const).mark_rule(
            color='#ffaa00', strokeWidth=2, strokeDash=[6, 4]
        ).encode(x='x:O')
        label_const = alt.Chart(df_const).mark_text(
            align='center', dy=-10, fontSize=9, color='#ffaa00', fontWeight='bold'
        ).encode(x='x:O', y=alt.value(0), text=alt.value('Fin Obra'))
        layers.extend([line_const, label_const])
    
    return alt.layer(*layers).properties(
        title=alt.TitleParams('Flujos Mensuales', fontSize=14, anchor='start'),
        width=CHART_WIDTH // 2,
        height=CHART_HEIGHT_MAIN
    )


# =============================================================================
# FUNCIONES DE EXPORTACIÓN
# =============================================================================

def generate_comparative_charts(output_dir: str, months: Tuple[int, int],
                                inversion_total: float, valor_tierra: float) -> None:
    get_sales_comparison_chart(months).save(
        os.path.join(output_dir, 'comparativa_ventas.html'))
    get_cost_comparison_chart(months, inversion_total).save(
        os.path.join(output_dir, 'comparativa_costos.html'))


def plot_cashflow_scenario(df_flow: pd.DataFrame, output_path: str,
                          title: str = "Flujo de Fondos") -> None:
    get_cashflow_chart(df_flow, title=title).save(output_path)


def plot_montecarlo_results(df_mc: pd.DataFrame, output_dir: str) -> None:
    chart_van, chart_tir = get_montecarlo_charts(df_mc)
    chart_van.save(os.path.join(output_dir, 'mc_van.html'))
    chart_tir.save(os.path.join(output_dir, 'mc_tir.html'))

