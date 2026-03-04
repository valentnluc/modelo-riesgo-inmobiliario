# Visual Identity & Theme - Core Infra

Esta guía documenta los estilos visuales, paleta de colores y tipografía utilizados en el proyecto para asegurar consistencia en futuras implementaciones.

## 1. Tipografía

**Fuente Principal:** [Inter](https://fonts.google.com/specimen/Inter)
- **400 (Regular):** Texto general, cuerpo.
- **500 (Medium):** Botones, UI inputs.
- **700 (Bold):** Encabezados de sección, Títulos de gráficos.
- **900 (Black):** Título principal de la aplicación.
- **300 (Light):** Valores numéricos grandes (KPIs).

## 2. Paleta de Colores (Dark Mode)

El diseño utiliza un tema oscuro de alto contraste ("Core Infra"), optimizado para visualización de datos.

### Infraestructura UI
| Variable CSS | Hex | Uso |
|--------------|-----|-----|
| `--bg-base` | `#000000` | Fondo principal de la aplicación y gráficos. |
| `--surface-n1` | `#0A0A0A` | Fondo de sidebar, tarjetas de métricas, expanders. |
| `--surface-n2` | `#121212` | Fondo de inputs, elementos secundarios. |
| `--border-subtle` | `#1F1F1F` | Líneas de grilla en gráficos, separadores suaves. |
| `--border-strong` | `#333333` | Bordes al hacer hover, delimitadores claros. |

### Texto
| Variable CSS | Hex | Uso |
|--------------|-----|-----|
| `--text-primary` | `#FFFFFF` | Títulos, valores de métricas, etiquetas importantes. |
| `--text-secondary` | `#A1A1AA` | Etiquetas de ejes, subtítulos, texto en sidebar. |
| `--text-muted` | `#52525B` | Captions, texto deshabilitado, placeholders. |

### Semántica y Datos
| Token | Hex | Referencia Visual | Uso Principal |
|-------|-----|-------------------|---------------|
| **Ingresos / Positivo** | `#3B82F6` | 🔵 Azul | Barras de ventas, escenarios optimistas. |
| **Egresos / Negativo** | `#EF4444` | 🔴 Rojo | Barras de costos, escenarios pesimistas, déficit. |
| **Saldo / Acumulado** | `#29B09D` | 🟢 Teal | Curva de caja acumulada, métricas de stock. |
| **Estable / Éxito** | `#10B981` | 🟢 Verde | Break-even point, validaciones correctas. |
| **Advertencia** | `#F59E0B` | 🟠 Ámbar | Alertas, líneas de referencia secundarias. |
| **Marca (UI)** | `#3B82F6` | 🔵 Azul | Botones, estados de foco (interacción UI), sintonizado con ingresos. |

## 3. Especificaciones para Gráficos (Altair/Vega-Lite)

Para mantener la estética "Financial Times" en modo oscuro:

### Configuración General
- **Fondo:** `#000000`
- **Títulos:** Fuente `Inter`, tamaño `14px`, color `#FFFFFF`.
- **Leyendas:** Posición `top` (generalmente), sin título de leyenda si el contexto es claro.

### Ejes y Grillas
- **Líneas de Eje (Domain):** Ocultas o `#333333`.
- **Grilla (Grid):** `#1F1F1F` (muy sutil).
- **Etiquetas (Labels):** `#A1A1AA`, tamaño `10px`, fuente `Inter`.
- **Títulos de Eje:** `#A1A1AA`, tamaño `11px`.

### Elementos Específicos
- **Líneas de Flujo Neto:** Blanco (`#FFFFFF`), punteadas (`strokeDash=[4, 2]`), `strokeWidth=2.5`.
- **Líneas de Intervalo de Confianza (Whiskers):**
  - Ingresos: `#172554` (Azul oscuro, baja opacidad).
  - Egresos: `#7F1D1D` (Rojo oscuro, baja opacidad).
- **Annotaciones:** Fuente `Inter`, generalmente `#A1A1AA` o el color de la serie correspondiente.

## 4. Componentes CSS (Snippets)

### Métricas (KPI Cards)
```css
background-color: #0A0A0A;
border: 1px solid #1F1F1F;
border-radius: 4px;
padding: 16px;
```

### Botones Primarios
```css
background-color: #3B82F6; /* Brand UI */
color: #FFFFFF;
font-weight: 500;
border-radius: 4px;
```

### Inputs
```css
background-color: #121212;
border: 1px solid #1F1F1F;
color: #FFFFFF;
border-radius: 4px;
```
