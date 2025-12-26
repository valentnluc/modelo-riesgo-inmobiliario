# Modelo de Riesgo Inmobiliario (CLI v1)

Aplicación de consola para la simulación financiera de proyectos inmobiliarios. Permite modelar flujos de caja, calcular métricas de rentabilidad (VAN, TIR) y evaluar riesgos mediante simulaciones Monte Carlo.

## Características

*   **Simulación Determinística**: Proyecta un único escenario basado en parámetros fijos.
*   **Simulación Estocástica (Monte Carlo)**: Ejecuta miles de escenarios variando precios, ritmos de venta y costos para estimar probabilidades de éxito.
*   **Presets Inteligentes**:
    *   **Ventas**: Curvas de absorción tradicionales, preventa agresiva o ventas post-obra.
    *   **Costos (CAPEX)**: Curvas 'S' estándar, inicios pesados o colas largas.
    *   **Tierra**: Compra al contado, cuotas o canje por m².
*   **Reportes**:
    *   Gráficos interactivos HTML (Flujo de Caja, Distribuciones de Riesgo).
    *   Exportación de datos a CSV.

## Instalación

Requiere Python 3.8+ y las librerías listadas en `requirements.txt`.

```bash
pip install -r requirements.txt
```

## Uso

Ejecutar la aplicación desde la terminal:

```bash
python app.py
```

Siga las instrucciones en pantalla para definir:
1.  **Parámetros Generales**: Duración del proyecto y tasa de descuento esperada.
2.  **Estrategia de Ventas**: Elija un preset o defina su propia curva de ventas.
3.  **Estructura de Costos**: Defina cómo se ejecutará la obra.
4.  **Negociación de Tierra**: Establezca valor y forma de pago.
5.  **Tipo de Análisis**: Determinístico o Monte Carlo.

## Estructura del Código

*   `app.py`: Punto de entrada e interfaz de usuario (CLI).
*   `model.py`: Motor de cálculo financiero.
*   `presets.py`: Definiciones matemáticas de las curvas de distribución.
*   `viz.py`: Generación de gráficos y reportes visuales.

Para un análisis detallado de la lógica y arquitectura, consulte [DOCUMENTATION.md](DOCUMENTATION.md).

## Métricas Clave

*   **VAN (Valor Actual Neto)**: Ganancia total descontada a hoy. Valor > 0 indica rentabilidad superior a la tasa exigida.
*   **TIR (Tasa Interna de Retorno)**: Rentabilidad anual intrínseca del proyecto.
*   **Máxima Necesidad Financiera (Max Drawdown)**: Capital propio máximo ("Equity") que el desarrollador deberá inyectar antes de que el proyecto se autofinancie.
