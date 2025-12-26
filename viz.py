
import os
from typing import Tuple, Dict, Any
import pandas as pd
import altair as alt
from presets import VENTAS_PRESETS, COSTOS_PRESETS, TIERRA_PRESETS, generate_sales_curve, generate_investment_curve

def generate_comparative_charts(output_dir: str, months: Tuple[int, int], inversion_total: float, valor_tierra: float) -> None:
    
    rows_v = []
    for name, params in VENTAS_PRESETS.items():
        p = {**params, 'area_n': 5000}
        x, y = generate_sales_curve(p, months)
        for xi, yi in zip(x, y):
            rows_v.append({'Mes': xi, 'Valor': yi, 'Preset': name})
    
    df_v = pd.DataFrame(rows_v)
    chart_v = alt.Chart(df_v).mark_line().encode(
        x=alt.X('Mes:Q', title='Mes'),
        y=alt.Y('Valor:Q', title='Ritmo de Ventas (u.m/mes)'),
        color=alt.Color('Preset:N')
    ).properties(title='Comparativa Presets de Ventas', width=600, height=400)
    chart_v.save(os.path.join(output_dir, 'comparativa_ventas_presets.html'))

    rows_c = []
    for name, params in COSTOS_PRESETS.items():
        p = {**params, 'limite_n': inversion_total}
        x, y = generate_investment_curve(p, months)
        for xi, yi in zip(x, y):
            rows_c.append({'Mes': xi, 'Valor': yi, 'Preset': name})
    
    df_c = pd.DataFrame(rows_c)
    chart_c = alt.Chart(df_c).mark_line().encode(
        x=alt.X('Mes:Q', title='Mes'),
        y=alt.Y('Valor:Q', title='Inversión Acumulada ($)'),
        color=alt.Color('Preset:N')
    ).properties(title='Comparativa Presets de Costos', width=600, height=400)
    chart_c.save(os.path.join(output_dir, 'comparativa_costos_presets.html'))

    rows_t = []
    base_100 = 100.0
    for name, params in TIERRA_PRESETS.items():
        if params.get('tipo') == 'pago':
            for pago in params.get('pagos', []):
                mes = pago['mes']
                monto = base_100 * pago['pct']
                rows_t.append({'Mes': mes, 'Monto': monto, 'Preset': name, 'Tipo': 'Pago'})
        elif params.get('tipo') == 'canje':
            pct = params.get('canje_pct_m2', 0.0)
            monto = base_100 * pct 
            rows_t.append({'Mes': 0, 'Monto': monto, 'Preset': name, 'Tipo': 'Canje (Referencia Equivalente)'})
            
    df_t = pd.DataFrame(rows_t)
    chart_t = alt.Chart(df_t).mark_bar().encode(
        x=alt.X('Mes:O', title='Mes'),
        y=alt.Y('Monto:Q', title='% del Valor de Tierra'),
        color=alt.Color('Preset:N'),
        column=alt.Column('Preset:N', header=alt.Header(titleOrient="bottom", labelOrient="bottom"))
    ).properties(title='Comparativa Estructura: Tierra', width=200, height=300)
    chart_t.save(os.path.join(output_dir, 'comparativa_tierra_presets.html'))


def plot_cashflow_scenario(df_flow: pd.DataFrame, output_path: str, title: str = "Detalle de Flujo de Fondos"):
    
    df_inc = df_flow[['Mes', 'Ventas']].copy()
    df_inc['Tipo'] = 'Ingresos (Ventas)'
    df_inc['Monto'] = df_inc['Ventas']
    
    df_obra = df_flow[['Mes', 'Egresos_Obra']].copy()
    df_obra['Tipo'] = 'Egresos (Obra)'
    df_obra['Monto'] = -df_obra['Egresos_Obra']
    
    df_tierra = df_flow[['Mes', 'Egresos_Tierra']].copy()
    df_tierra['Tipo'] = 'Egresos (Tierra)'
    df_tierra['Monto'] = -df_tierra['Egresos_Tierra']

    df_viz = pd.concat([df_inc, df_obra, df_tierra])

    base_bars = alt.Chart(df_viz).encode(
        x=alt.X('Mes:Q', title='')
    )
    
    bars = base_bars.mark_bar().encode(
        y=alt.Y('Monto:Q', title='Flujo Mensual ($)'),
        color=alt.Color('Tipo:N', scale=alt.Scale(
            domain=['Ingresos (Ventas)', 'Egresos (Obra)', 'Egresos (Tierra)'],
            range=['#4c78a8', '#f58518', '#e45756'] 
        )),
        tooltip=['Mes', 'Tipo', alt.Tooltip('Monto:Q', format=',.2f')]
    )
    
    line_neto = alt.Chart(df_flow).mark_line(color='black', strokeWidth=2).encode(
        x='Mes:Q',
        y='Flujo_Neto:Q',
        tooltip=[alt.Tooltip('Mes'), alt.Tooltip('Flujo_Neto', format=',.2f', title="Flujo Neto Total")]
    )
    
    top_chart = alt.layer(bars, line_neto).properties(
        title='Composición de Ingresos y Egresos Mensuales',
        width=800, 
        height=300
    )

    base_acum = alt.Chart(df_flow).encode(x=alt.X('Mes:Q', title='Mes del Proyecto'))
    
    area_acum = base_acum.mark_area(
        line={'color':'darkgreen'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(offset=0, color='white'), alt.GradientStop(offset=1, color='darkgreen')],
            x1=1, x2=1, y1=1, y2=0
        ),
        opacity=0.3
    ).encode(
        y=alt.Y('Cash_Acumulado:Q', title='Cash Acumulado ($)')
    )
    
    line_acum = base_acum.mark_line(color='darkgreen').encode(
        y='Cash_Acumulado:Q',
        tooltip=[alt.Tooltip('Mes'), alt.Tooltip('Cash_Acumulado', format=',.2f', title="Saldo Acumulado")]
    )
    
    rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray', strokeDash=[3,3]).encode(y='y')
    
    bottom_chart = alt.layer(area_acum, line_acum, rule).properties(
        title='Evolución Financiera (Saldo de Caja Acumulado)',
        width=800, 
        height=250
    )

    dashboard = alt.vconcat(top_chart, bottom_chart).resolve_scale(
        x='shared'
    ).properties(
        title=f"{title} - Vista Detallada"
    ).configure_axis(
        grid=True,
        gridOpacity=0.3
    )
    
    dashboard.save(output_path)


def plot_montecarlo_results(df_mc: pd.DataFrame, output_dir: str):
    
    chart_van = alt.Chart(df_mc).mark_bar().encode(
        x=alt.X('VAN:Q', bin=alt.Bin(maxbins=40), title='VAN (Valor Actual Neto)'),
        y=alt.Y('count()', title='Frecuencia'),
        tooltip=['count()']
    ).properties(title='Distribución de Resultados: VAN', width=600, height=400)
    
    chart_van.save(os.path.join(output_dir, 'montecarlo_distribucion_van.html'))

    df_tir = df_mc.dropna(subset=['TIR'])
    
    chart_tir = alt.Chart(df_tir).mark_bar().encode(
        x=alt.X('TIR:Q', bin=alt.Bin(maxbins=40), title='TIR Anual'),
        y=alt.Y('count()', title='Frecuencia'),
        tooltip=['count()']
    ).properties(title='Distribución de Resultados: TIR', width=600, height=400)
    
    chart_tir.save(os.path.join(output_dir, 'montecarlo_distribucion_tir.html'))
