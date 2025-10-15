#!/usr/bin/env python
# src/interfaz_grafica.py

import os
import sys
import json
import logging
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import pg8000
import pandas as pd
from tkcalendar import DateEntry
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from sklearn.decomposition import PCA
import threading
import socket
import json
import os


class ToolTip:
    """
    Crea una ayuda emergente (tooltip) para un widget dado.
    """

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwin = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event):
        if self.tipwin or not self.text:
            return
        try:
            if hasattr(self.widget, "bbox"):
                # Solo usar bbox("insert") en widgets de texto
                if self.widget.winfo_class() in ("Text", "Entry"):
                    x, y, cx, cy = self.widget.bbox("insert")
                else:
                    # Para Treeview, Combobox u otros: valores seguros
                    x, y, cx, cy = (0, 0, 0, 0)
            else:
                x, y, cx, cy = (0, 0, 0, 0)
        except Exception:
            # Si bbox falla, devolvemos valores seguros
            x, y, cx, cy = (0, 0, 0, 0)

        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20
        self.tipwin = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("Arial", "8", "normal"),
        )
        label.pack(ipadx=1)

    def hide(self, _event):
        if self.tipwin:
            self.tipwin.destroy()
            self.tipwin = None
# ————————————— Bloque: Configuración global —————————————
# Variables de configuración de la BD, colores gráficos, archivo de settings y configuración por defecto
DB_CONFIG = {
    "host": "ep-lucky-morning-adafnn5y-pooler.c-2.us-east-1.aws.neon.tech",
    "user": "neondb_owner",
    "password": "npg_pgxVl1e3BMqH",
    "database": "neondb",  # asegúrate que el nombre de la base sea correcto
    "port": 5432
}

COLOR_BG = "#2c3e50"  # Color de fondo
COLOR_BT = "#3498db"  # Color de botones
COLOR_FG = "#ffffff"  # Color de fuente

SETTINGS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "settings.json"))

# Configuración por defecto corregida: ahora solo se usa el tercer ciclo
DEFAULT_SETTINGS = {
    "selected_cycle": 3,   # Solo tercer ciclo
    "ppm_factor": 1.0,
    "alert_threshold": 0.5
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger()

class Aplicacion(tk.Tk):
    """
    Clase principal que representa la interfaz gráfica del Sistema de Monitoreo Electroquímico.
    Integra módulos para cargar datos, realizar consultas, visualizar y exportar gráficos y reportes.
    """

    # ————— Bloque: Inicialización y carga de ajustes —————
    def __init__(self):
        """
        Inicializa la ventana principal, carga ajustes, configura estilo, menú y pestañas.
        También carga las sesiones iniciales.
        """
        super().__init__()
        self.title("Sistema de Monitoreo Electroquímico")
        self.geometry("1400x900")
        self.configure(bg=COLOR_BG)

        self.current_data = None  # DataFrame con datos de la sesión actual
        self.session_info = {}  # Diccionario con metadatos de la sesión
        self.ppm_df = None  # DataFrame para la tabla de estimaciones ppm
        self.settings = self.load_settings()  # Carga o crea el archivo settings.json

        # Configurar estilo de la interfaz, crear menú y pestañas
        self.setup_style()
        self.create_menu()
        self.create_tabs()
        self.load_sessions()

    def load_file(self):
        """
        Llama al método de selección de archivo para cargar .pssession.
        """
        return self.seleccionar_archivo()

    def load_settings(self):
        """
        Carga los ajustes del archivo settings.json.
        Si no existe o hay error, utiliza los ajustes por defecto.

        Returns:
            dict: Diccionario de ajustes.
        """
        if not os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "w") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2)
            return DEFAULT_SETTINGS.copy()
        try:
            return json.load(open(SETTINGS_FILE))
        except:
            log.warning("No se pudo leer settings.json; usando valores por defecto")
            return DEFAULT_SETTINGS.copy()

    def save_settings(self):
        """
        Guarda los ajustes actuales en el archivo settings.json.
        """
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f, indent=2)
        log.info("Settings guardados: %s", self.settings)

    # ————— Bloque: Estilos —————
    def setup_style(self):
        """
        Configura el estilo visual de la aplicación (colores, fuentes, temas) utilizando ttk.Style.
        """
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=COLOR_BG)
        s.configure("TButton", background=COLOR_BT, foreground=COLOR_FG, font=("Arial", 12, "bold"))
        s.map("TButton", background=[("active", "#2980b9")])
        s.configure("TLabel", background=COLOR_BG, foreground=COLOR_FG, font=("Arial", 11))
        s.configure("Treeview", background="#34495e", fieldbackground="#34495e", foreground=COLOR_FG)
        s.configure("TNotebook", background=COLOR_BG)
        s.configure("TNotebook.Tab", background="#7f8c8d", foreground=COLOR_FG, font=("Arial", 10, "bold"))

    # ————— Bloque: Menú principal —————
    def create_menu(self):
        """
        Crea el menú principal de la aplicación con opciones de archivo y ayuda.
        """
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_separator()
        f.add_command(label="Salir", command=self.quit)
        m.add_cascade(label="Archivo", menu=f)
        h = tk.Menu(m, tearoff=0)
        h.add_command(
            label="Acerca de", command=lambda: messagebox.showinfo("Acerca de", "Sistema Monitoreo Electroquímico v2.0")
        )
        m.add_cascade(label="Ayuda", menu=h)
        self.config(menu=m)

    # ————— Bloque: Creación de pestañas —————
    def create_tabs(self):
        """
        Crea las pestañas principales de la interfaz para diferentes módulos:
        Cargar Datos, Consultas, Detalle, Curvas, PCA y ppm.
        """
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.build_load_tab(nb)
        self.build_query_tab(nb)
        self.build_detail_tab(nb)
        self.build_curve_tab(nb)
        self.build_pca_tab(nb)
        self.build_ppm_tab(nb)
        self.build_iot_tab(nb)
        

    # ————— Bloque: Pestaña “Cargar Datos” —————
    def build_load_tab(self, parent):
        """
        Configura la pestaña de carga de datos (.pssession).

        Args:
            parent (ttk.Notebook): Notebook padre donde se añade la pestaña.
        """
        f = ttk.Frame(parent)
        parent.add(f, text="📤 Cargar Datos")
        ttk.Button(f, text="Seleccionar Archivo .pssession", command=self.load_file).pack(pady=20)
        self.log_text = tk.Text(f, height=8, bg="#34495e", fg="white", font=("Courier", 10))
        self.log_text.pack(fill="x", padx=10, pady=10)

    # ---------------------- BLOQUE 2 REFACTORIZADO CON DEBUGS: MENÚ Y CONSULTAS ----------------------

    # ——— Bloque 2.1 ———
    def show_settings_alternative(self):
        """
        Ventana de Configuraciones Alternativas.
        Permite al usuario ajustar el umbral de alerta (ppm).
        Debug: imprime entrada y errores.
        """
        print("[DEBUG] show_settings_alternative() invoked")
        settings_window = tk.Toplevel(self)
        settings_window.title("Configuraciones")
        settings_window.geometry("400x300")
        settings_window.transient(self)
        settings_window.grab_set()

        main_frame = ttk.Frame(settings_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Configuraciones", font=("Arial", 14, "bold")).pack(pady=(0, 20))

        threshold_frame = ttk.Frame(main_frame)
        threshold_frame.pack(fill="x", pady=5)
        ttk.Label(threshold_frame, text="Umbral de Alerta (ppm):").pack(side="left")
        threshold_var = tk.StringVar(value=str(self.settings.get("alert_threshold", 100)))
        threshold_entry = ttk.Entry(threshold_frame, textvariable=threshold_var, width=10)
        threshold_entry.pack(side="right")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side="bottom", fill="x", pady=(20, 0))

        def save_settings():
            print("[DEBUG] save_settings() invoked with value:", threshold_var.get())
            try:
                new_thr = float(threshold_var.get())
                self.settings["alert_threshold"] = new_thr
                if hasattr(self, "threshold_entry"):
                    self.threshold_entry.delete(0, "end")
                    self.threshold_entry.insert(0, str(new_thr))
                messagebox.showinfo("Éxito", "Umbral guardado correctamente")
                settings_window.destroy()
            except ValueError:
                print("[DEBUG] save_settings() ValueError: invalid float")
                messagebox.showerror("Error", "El umbral debe ser un número válido")

        ttk.Button(button_frame, text="Guardar", command=save_settings).pack(side="right", padx=(5, 0))
        ttk.Button(button_frame, text="Cancelar", command=settings_window.destroy).pack(side="right")

    # ——— Bloque 2.2 ———
    def build_query_tab(self, parent):
        """
        Armado de la pestaña 'Consultas', llamando a los sub-bloques:
          2.2.1 Vista general
          2.2.2 Filtros básicos
          2.2.3 Tabla de resultados
          2.2.4 Detalles técnicos
        """
        print("[DEBUG] build_query_tab() invoked")
        tab = ttk.Frame(parent)
        parent.add(tab, text="🔍 Consultas")

        self._create_overview_panel(tab)  # 2.2.1
        self._create_filters_panel(tab)  # 2.2.2
        self._create_results_table(tab)  # 2.2.3
        self._create_meta_panel(tab)  # 2.2.4

        self.load_devices()
        self.update_overview()
        self.set_default_date_range()
        self.query_sessions()


    # ——— Bloque 2.2.1 ———

    def _create_overview_panel(self, parent):
        """
        Panel superior de estadísticas generales.
        """
        print("[DEBUG] _create_overview_panel() invoked")

        frame = ttk.LabelFrame(parent, text="Vista General de Datos")
        frame.pack(fill="x", padx=10, pady=5)
        container = ttk.Frame(frame)
        container.pack(fill="x", padx=10, pady=10)

        # Campos a mostrar en la vista general
        fields = [
            ("total_sessions", "Total de Sesiones: --"),
            ("total_measurements", "Total de Mediciones: --"),
            ("avg_ppm", "PPM Promedio: --"),
            ("max_ppm", "PPM Máximo: --"),
            ("min_ppm", "PPM Mínimo: --"),   # 🔧 añadido para evitar error y mostrar mínimo
            ("alert_count", "Alertas Activas: --"),
            ("last_update", "Última Actualización: --"),
        ]

        self.overview_labels = {}
        for i, (key, text) in enumerate(fields):
            r, c = divmod(i, 3)
            lbl = ttk.Label(container, text=text, font=("Arial", 10))
            lbl.grid(row=r, column=c, sticky="w", padx=20, pady=5)
            self.overview_labels[key] = lbl
            print(f"[DEBUG] _create_overview_panel: label creado -> {key}")

        # Botón de actualización manual
        ttk.Button(
            container,
            text="🔄 Actualizar",
            command=lambda: (
                print("[DEBUG] Click: actualizar vista general"),
                self.update_overview()
            ),
        ).grid(row=3, column=0, columnspan=3, pady=10)

        print("[DEBUG] _create_overview_panel configurado correctamente con min_ppm incluido")


    # ——— Bloque 2.2.2 ———

    def _create_filters_panel(self, parent):
        """
        Panel de filtros básicos por ID, rango de fechas y dispositivo.
        """
        print("[DEBUG] _create_filters_panel() invoked")
        frame = ttk.LabelFrame(parent, text="Filtros de Búsqueda")
        frame.pack(fill="x", padx=10, pady=5)
        container = ttk.Frame(frame)
        container.pack(fill="x", padx=10, pady=10)

        # ID Sesión
        ttk.Label(container, text="ID Sesión:").grid(row=0, column=0, sticky="e", padx=5)
        self.id_entry = ttk.Entry(container, width=10)
        self.id_entry.grid(row=0, column=1, padx=5)
        ToolTip(self.id_entry, "Introduce el ID de la sesión para filtrar los resultados")

        # Rango de fechas
        ttk.Label(container, text="Fecha Inicio:").grid(row=0, column=2, sticky="e", padx=5)
        self.date_start = DateEntry(container, date_pattern="yyyy-mm-dd")
        self.date_start.grid(row=0, column=3, padx=5)
        ToolTip(self.date_start, "Selecciona la fecha de inicio del rango de búsqueda")

        ttk.Label(container, text="Fecha Fin:").grid(row=0, column=4, sticky="e", padx=5)
        self.date_end = DateEntry(container, date_pattern="yyyy-mm-dd")
        self.date_end.grid(row=0, column=5, padx=5)
        ToolTip(self.date_end, "Selecciona la fecha de fin del rango de búsqueda")

        # Dispositivo (nuevo combobox)
        ttk.Label(container, text="Dispositivo:").grid(row=1, column=0, sticky="e", padx=5, pady=(10, 0))
        self.device_combobox = ttk.Combobox(container, state="readonly", width=12)
        self.device_combobox.grid(row=1, column=1, padx=5, pady=(10, 0))
        self.device_combobox["values"] = ["— Todos —"]
        self.device_combobox.current(0)
        ToolTip(self.device_combobox, "Filtra los resultados por el número de serie del dispositivo")

        # Botones de acción
        btns = ttk.Frame(container)
        btns.grid(row=2, column=0, columnspan=6, pady=(10, 0))

        btn_search = ttk.Button(
            btns, text="🔍 Buscar", command=lambda: (print("[DEBUG] Click: buscar sesiones"), self.query_sessions())
        )
        btn_search.pack(side="left", padx=5)
        ToolTip(btn_search, "Ejecuta la búsqueda con los filtros seleccionados")

        btn_clear = ttk.Button(
            btns, text="🗑️ Limpiar", command=lambda: (print("[DEBUG] Click: limpiar filtros"), self.clear_filters())
        )
        btn_clear.pack(side="left", padx=5)
        ToolTip(btn_clear, "Limpia todos los filtros y restablece valores por defecto")

        btn_last7 = ttk.Button(
            btns,
            text="📅 Últimos 7d",
            command=lambda: (print("[DEBUG] Click: últimos 7 días"), self.set_default_date_range()),
        )
        btn_last7.pack(side="left", padx=5)
        ToolTip(btn_last7, "Establece el rango de fechas a los últimos siete días")

    # ——— Bloque 2.2.3 EXTENDIDO con Tooltips ———
    def _create_results_table(self, parent):
        """
        Crea la tabla de resultados con la nueva columna 'Contaminantes'
        y enlaza el evento de selección.
        """
        print("[DEBUG] _create_results_table() invoked")
        frame = ttk.LabelFrame(parent, text="Resultados de Búsqueda")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("ID", "Archivo", "Fecha", "Dispositivo", "Curvas", "Estado", "Máx. ppm", "Contaminantes")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree.heading(col, text=col)
            width = 120 if col == "Contaminantes" else 100
            self.tree.column(col, width=width, anchor="center")

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        self.tree.pack(fill="both", expand=True)
        ToolTip(self.tree, "Tabla con las sesiones encontradas; selecciona una para ver detalles.")

        self.tree.tag_configure("alert", background="#ffebee", foreground="#c62828")
        self.tree.tag_configure("safe", background="#e8f5e9", foreground="#2e7d32")
        self.tree.bind("<<TreeviewSelect>>", lambda ev: self.on_session_select())
        ToolTip(self.tree, "Al hacer clic en una fila, se mostrarán los detalles técnicos abajo.")

    # ——— Bloque 2.2.4 con Tooltips ———
    def _create_meta_panel(self, parent):
        """
        Panel de detalles técnicos de la sesión seleccionada.
        """
        print("[DEBUG] _create_meta_panel() invoked")
        frame = ttk.LabelFrame(parent, text="Detalles Técnicos de la Sesión Seleccionada")
        frame.pack(fill="x", padx=10, pady=5)
        meta_content = ttk.Frame(frame)
        meta_content.pack(fill="x", padx=10, pady=10)

        # Campos disponibles según esquema de BD
        fields = [
            ("scan_rate", "Velocidad de Escaneo: --"),
            ("start_potential", "Potencial Inicial: --"),
            ("end_potential", "Potencial Final: --"),
            ("software_version", "Versión Software: --"),
        ]
        self.meta_labels = {}
        for i, (key, text) in enumerate(fields):
            r, c = divmod(i, 2)
            lbl = ttk.Label(meta_content, text=text, font=("Arial", 9))
            lbl.grid(row=r, column=c, sticky="w", padx=15, pady=2)
            self.meta_labels[key] = lbl
            ToolTip(lbl, f"Muestra el valor de '{key}' de la sesión seleccionada")


    # ===================================================================================
    # ——— Bloque 2.3 EXTENDIDO (metales contaminantes) ———
    # ===================================================================================

    def query_sessions(self):
        """
        Ejecuta consulta avanzada que integra límites regulatorios y 
        clasifica el estado de contaminación según normas oficiales.
        Ahora se usan directamente los campos clasificacion y ppm_estimations
        guardados en la BD, evitando recalcular en la GUI.
        """
        log.debug("🔄 Iniciando query_sessions() mejorado")

        # 1) Cargar límites regulatorios (para tooltips y validaciones)
        try:
            with open("limits_ppm.json", "r") as f:
                limites = json.load(f)
                log.debug(f"📚 Límites regulatorios cargados: {limites}")
        except Exception as e:
            log.error(f"❌ Error cargando limits_ppm.json: {e}")
            messagebox.showerror("Error", "No se pudieron cargar los límites regulatorios")
            return

        # 2) Procesar filtros
        sid_text = self.id_entry.get().strip()
        try:
            session_id = int(sid_text) if sid_text else None
        except ValueError:
            log.debug(f"⚠️ ID inválido ignorado: '{sid_text}'")
            session_id = None

        # 3) Fechas y dispositivo
        start_date = self.date_start.get_date().strftime("%Y-%m-%d")
        end_date = self.date_end.get_date().strftime("%Y-%m-%d")
        device = self.device_combobox.get()
        use_device_filter = device and device != "— Todos —"

        # 4) Parámetros para la consulta
        params = [start_date, end_date]
        if session_id is not None:
            params.append(session_id)
        if use_device_filter:
            params.append(device)

        # 5) Consulta SQL mejorada con campos nuevos
        sql = """
            SELECT 
                s.id,
                s.filename,
                s.loaded_at::date AS fecha,
                m.device_serial AS dispositivo,
                m.curve_count AS curvas,
                COALESCE(ROUND(m.contamination_level::numeric, 2), 0) AS nivel_ppm,
                m.clasificacion,
                m.ppm_estimations
            FROM sessions s
            JOIN measurements m ON s.id = m.session_id
            WHERE s.loaded_at::date BETWEEN %s AND %s
        """

        # 6) Agregar filtros adicionales
        if session_id is not None:
            sql += " AND s.id = %s"
        if use_device_filter:
            sql += " AND m.device_serial = %s"

        # 7) Completar consulta con ordenamiento
        sql += " ORDER BY fecha DESC, nivel_ppm DESC"

        # 8) Ejecutar consulta
        try:
            conn = pg8000.connect(**DB_CONFIG)
            cur = conn.cursor()
            log.debug(f"🔍 Ejecutando consulta con params: {params}")
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            conn.close()
            log.debug(f"✅ Consulta exitosa: {len(rows)} resultados")
        except Exception as e:
            log.error(f"❌ Error en consulta: {e}")
            messagebox.showerror("Error en consulta", f"No se pudo ejecutar la consulta:\n{e}")
            return

        # 9) Actualizar interfaz
        self.tree.delete(*self.tree.get_children())

        if not rows:
            self.tree.insert("", "end", values=("--", "Sin resultados", "--", "--", "--", "0.00", "--", "--"))
            return

        # 10) Poblar tabla usando clasificacion de BD
        for r in rows:
            nivel = float(r[5])          # contamination_level
            clasificacion = r[6] or "--" # clasificacion textual
            ppm_json = r[7] or {}        # ppm_estimations JSONB

            log.debug(f"📊 Fila BD -> nivel={nivel}, clasificacion={clasificacion}, ppm={ppm_json}")

            # Determinar estilo visual según clasificacion
            if clasificacion.startswith("⚠️"):
                tag = "alert"
                tooltip = f"{clasificacion} (nivel={nivel:.2f}%)"
            elif clasificacion.startswith("⚡"):
                tag = "warning"
                tooltip = f"{clasificacion} (nivel={nivel:.2f}%)"
            elif clasificacion.startswith("🟡"):
                tag = "attention"
                tooltip = f"{clasificacion} (nivel={nivel:.2f}%)"
            else:
                tag = "safe"
                tooltip = f"{clasificacion} (nivel={nivel:.2f}%)"

            # Insertar fila con valores reales de BD
            valores = (r[0], r[1], r[2], r[3], r[4], clasificacion, nivel, json.dumps(ppm_json))
            item_id = self.tree.insert("", "end", values=valores, tags=(tag,))
            ToolTip(self.tree, tooltip)

        # 11) Configurar estilos visuales
        self.tree.tag_configure("alert", background="#ffcdd2", foreground="#d32f2f")
        self.tree.tag_configure("warning", background="#ffe0b2", foreground="#f57c00")
        self.tree.tag_configure("attention", background="#fff9c4", foreground="#fbc02d")
        self.tree.tag_configure("safe", background="#c8e6c9", foreground="#2e7d32")

        log.info(f"📊 Tabla actualizada con {len(rows)} registros")

        # 12) Actualizar estadísticas
        self.update_overview()


# ===================================================================================
    # ——— Bloque 2.5: load_devices (mejorado) ———
# ===================================================================================
    def load_devices(self):
        """
        Consulta la base de datos para cargar los seriales de dispositivos
        y asignarlos al combobox, siempre incluyendo la opción “— Todos —”.
        Además, enlaza el evento de selección para actualizar la consulta.
        """
        print("[DEBUG] load_devices() invoked")
        if not hasattr(self, "device_combobox"):
            print("[DEBUG] load_devices: no existe device_combobox, skip.")
            return

        try:
            conn = pg8000.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT device_serial
                FROM measurements
                WHERE device_serial IS NOT NULL
                ORDER BY device_serial
            """
            )
            vals = [row[0] for row in cur.fetchall()]
            conn.close()

            # Siempre incluir “— Todos —” al inicio
            options = ["— Todos —"] + vals if vals else ["— Todos —"]
            print(f"[DEBUG] load_devices: valores obtenidos: {options}")
            self.device_combobox["values"] = options
            self.device_combobox.current(0)

            # Enlazar la selección para refrescar consultas
            self.device_combobox.bind(
                "<<ComboboxSelected>>",
                lambda ev: (
                    print(f"[DEBUG] Dispositivo seleccionado: {self.device_combobox.get()}"),
                    self.query_sessions(),
                ),
            )

        except Exception as e:
            print(f"[DEBUG] load_devices Error: {e}")
            messagebox.showerror("Error BD", f"Error cargando dispositivos:\n{e}")


# ===================================================================================
    # ——— Bloque 2.6: update_overview ———
# ===================================================================================

    def update_overview(self):
        """
        Actualiza la vista general mostrando estadísticas globales.
        Debug: imprime cada paso y captura excepciones.
        """
        print("[DEBUG] update_overview() invoked")
        # Si no hay overview_labels, salimos
        if not hasattr(self, "overview_labels"):
            print("[DEBUG] update_overview: no existe overview_labels, skip.")
            return

        try:
            conn = pg8000.connect(**DB_CONFIG)
            cur = conn.cursor()

            # Consultas basadas en contamination_level ya calculado contra JSON
            queries = {
                "total_sessions": "SELECT COUNT(*) FROM sessions",
                "total_measurements": "SELECT COUNT(*) FROM measurements",
                "avg_ppm": "SELECT ROUND(AVG(contamination_level)::numeric, 2) FROM measurements WHERE contamination_level IS NOT NULL",
                "max_ppm": "SELECT ROUND(MAX(contamination_level)::numeric, 2) FROM measurements WHERE contamination_level IS NOT NULL",
                "min_ppm": "SELECT ROUND(MIN(contamination_level)::numeric, 2) FROM measurements WHERE contamination_level IS NOT NULL",
                "alert_count": "SELECT COUNT(*) FROM measurements WHERE contamination_level >= %s",
                "last_update": "SELECT MAX(loaded_at) FROM sessions",
            }

            stats = {}
            for key, sql in queries.items():
                if key == "alert_count":
                    # Usar el umbral definido en settings (ej. 100% del límite)
                    cur.execute(sql, (self.settings["alert_threshold"],))
                else:
                    cur.execute(sql)
                stats[key] = cur.fetchone()[0]

            conn.close()
            print(f"[DEBUG] update_overview: stats fetched: {stats}")

            # Actualizar labels con valores reales
            self.overview_labels["total_sessions"].config(
                text=f"Total de Sesiones: {stats['total_sessions']}"
            )
            self.overview_labels["total_measurements"].config(
                text=f"Total de Mediciones: {stats['total_measurements']}"
            )
            self.overview_labels["avg_ppm"].config(
                text=f"PPM Promedio: {stats['avg_ppm'] if stats['avg_ppm'] is not None else '--'}"
            )
            self.overview_labels["max_ppm"].config(
                text=f"PPM Máximo: {stats['max_ppm'] if stats['max_ppm'] is not None else '--'}"
            )
            if "min_ppm" in stats:
                self.overview_labels["min_ppm"].config(
                    text=f"PPM Mínimo: {stats['min_ppm'] if stats['min_ppm'] is not None else '--'}"
                )
            self.overview_labels["alert_count"].config(
                text=f"Alertas Activas: {stats['alert_count']}"
            )

            last = stats["last_update"]
            if last:
                formatted = last.strftime("%Y-%m-%d %H:%M:%S") if hasattr(last, "strftime") else str(last)
                text = f"Última Actualización: {formatted}"
            else:
                text = "Última Actualización: --"
            self.overview_labels["last_update"].config(text=text)

        except Exception as e:
            print(f"[DEBUG] update_overview Error: {e}")
            messagebox.showerror("Error", f"Error actualizando vista general:\n{e}")
            # Reset labels en caso de fallo
            for lbl in getattr(self, "overview_labels", {}).values():
                lbl.config(text="--")

    # ——— Bloque 2.7: set_default_date_range ———
    def set_default_date_range(self):
        """
        Establece el rango de fechas a los últimos 7 días y dispara la consulta.
        Debug: imprime los valores de fecha establecidos.
        """
        print("[DEBUG] set_default_date_range() invoked")
        # Verificar que existan los datepickers
        if not hasattr(self, "date_start") or not hasattr(self, "date_end"):
            print("[DEBUG] set_default_date_range: no existen date_start/date_end, skip.")
            return

        try:
            today = datetime.date.today()
            last7 = today - datetime.timedelta(days=7)
            self.date_start.set_date(last7)
            self.date_end.set_date(today)
            print(f"[DEBUG] set_default_date_range: date_start={last7}, date_end={today}")
            # Ejecutar la consulta con el nuevo rango
            self.query_sessions()
        except Exception as e:
            print(f"[DEBUG] set_default_date_range Error: {e}")
            messagebox.showerror("Error", f"Error estableciendo rango de fechas:\n{e}")
# ===================================================================================
    # ——— Bloque: Pestaña “Detalle Sesión” ———
# ===================================================================================

    def build_detail_tab(self, parent):
        """
        Crea la pestaña 'Detalle Sesión' donde se muestra un área de texto
        para información detallada de la sesión.

        Args:
            parent (ttk.Notebook): Notebook donde se añade la pestaña.
        """
        f = ttk.Frame(parent)
        parent.add(f, text="📝 Detalle Sesión")
        self.txt_detail = tk.Text(f, wrap="word", bg="#34495e", fg="white", font=("Arial", 10))
        self.txt_detail.pack(fill="both", expand=True, padx=10, pady=10)
        ToolTip(self.txt_detail, "Aquí se muestra la información detallada (JSON) de la sesión seleccionada")



    # ——— Bloque: Pestaña “Curvas” ———
    def build_curve_tab(self, parent):
        """
        Configura la pestaña 'Curvas' para visualizar curvas individuales y promedio.

        Args:
            parent (ttk.Notebook): Notebook donde se añade la pestaña.
        """
        f = ttk.Frame(parent)
        parent.add(f, text="📊 Curvas")
        frm = ttk.Frame(f)
        frm.pack(fill="x", padx=10, pady=8)

        ttk.Label(frm, text="Índice medida:").pack(side="left", padx=5)
        ToolTip(frm.winfo_children()[-1], "Selecciona el índice de la medición para graficar la curva correspondiente")

        self.cmb_curve = ttk.Combobox(frm, state="readonly", width=8)
        self.cmb_curve.pack(side="left", padx=5)
        ToolTip(self.cmb_curve, "Desplegable para elegir cuál de las mediciones graficar")
        self.cmb_curve.bind("<<ComboboxSelected>>", lambda e: self.show_curve())

        self.fig_curve, self.ax_curve = plt.subplots(figsize=(9, 5), facecolor=COLOR_BG)
        self.ax_curve.set_facecolor(COLOR_BG)
        self.ax_curve.tick_params(colors="white")
        self.ax_curve.grid(True, color="#5d6d7e")
        self.canvas_curve = FigureCanvasTkAgg(self.fig_curve, master=f)
        self.canvas_curve.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        ToolTip(self.canvas_curve.get_tk_widget(), "Gráfica de corriente vs potencial para la curva seleccionada")

        btn_export_curve = ttk.Button(f, text="Exportar PNG", command=lambda: self.export_figure(self.fig_curve))
        btn_export_curve.pack(side="right", padx=10, pady=5)
        ToolTip(btn_export_curve, "Exporta la gráfica de curvas como imagen PNG")


    # ——— Bloque: Pestaña “ppm” (ahora “Clasificación”) ———
    def build_ppm_tab(self, parent):
        """
        Configura la pestaña 'ppm' (ahora 'Clasificación') para mostrar
        grupo y nivel de contaminación y permitir su exportación.
        Los valores que se mostrarán provienen del cálculo con el ciclo 3
        y se comparan directamente contra los límites oficiales definidos
        en el archivo JSON.
        """
        f = ttk.Frame(parent)
        parent.add(f, text="🗂 Clasificación")

        # Botón para refrescar la vista de clasificación
        btn_show_ppm = ttk.Button(
            f,
            text="Mostrar Clasificación",
            command=self.show_classification
        )
        btn_show_ppm.pack(pady=8)
        ToolTip(btn_show_ppm, "Muestra la clasificación global y el nivel de contaminación calculado contra los límites JSON")

        # Tabla de clasificación: Grupo (estado) y Nivel (%) de superación
        cols = ("Grupo", "Nivel (%)")
        self.tree_ppm = ttk.Treeview(
            f,
            columns=cols,
            show="headings",
            height=8
        )
        for c in cols:
            self.tree_ppm.heading(c, text=c)
            self.tree_ppm.column(c, anchor="center")
        self.tree_ppm.pack(fill="both", expand=True, padx=10, pady=10)
        ToolTip(self.tree_ppm, "Tabla con el estado de clasificación y el porcentaje de superación respecto al límite oficial")

        # Botón para exportar la tabla de clasificación
        btn_export_ppm = ttk.Button(
            f,
            text="Exportar Clasificación",
            command=self.export_classification
        )
        btn_export_ppm.pack(side="right", padx=10, pady=5)
        ToolTip(btn_export_ppm, "Exporta la tabla de clasificación como CSV con valores de ciclo 3 y comparación contra JSON")



    # ——— Bloque: Exportar Clasificación ———
    def export_classification(self):
        """
        Exporta la tabla de clasificación (ppm) a un archivo CSV.
        Usa self.ppm_df, que se construye en show_classification/show_ppm,
        garantizando que los datos exportados correspondan a la comparación
        contra los límites oficiales definidos en limits_ppm.json.

        Flujo:
        - Verifica que self.ppm_df exista y no esté vacío.
        - Abre un diálogo para seleccionar la ruta de guardado.
        - Exporta el DataFrame a CSV con codificación UTF-8.
        - Muestra un mensaje de confirmación o error.
        """
        if self.ppm_df is None or self.ppm_df.empty:
            messagebox.showwarning("Exportar", "No hay datos de clasificación para exportar.")
            print("[DEBUG] export_classification: self.ppm_df vacío o None")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Guardar clasificación como CSV"
        )
        if not path:
            print("[DEBUG] export_classification: guardado cancelado por el usuario")
            return

        try:
            self.ppm_df.to_csv(path, index=False, encoding="utf-8-sig")
            messagebox.showinfo("Exportar", f"Clasificación guardada en {path}")
            print(f"[DEBUG] export_classification: CSV guardado en {path}")
        except Exception as e:
            print(f"[ERROR] export_classification: {e}")
            messagebox.showerror("Error", f"No se pudo exportar la clasificación:\n{e}")


     # ——— Bloque: Pestaña “IoT / Comunicación” ———

    def build_iot_tab(self, parent):
        """
        Crea la pestaña para control del servidor IoT, conexión remota y envío de archivos.
        Permite iniciar/detener servidor, probar conexión y transferir archivos.
        """
        f = ttk.Frame(parent)
        parent.add(f, text="🌐 IoT / Comunicación")

        ttk.Label(f, text="Centro de Control IoT", font=("Arial", 14, "bold")).pack(pady=10)

        # ==============================
        # CONFIGURACIÓN
        # ==============================
        frame_conf = ttk.LabelFrame(f, text="Configuración del Servidor / Cliente")
        frame_conf.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame_conf, text="IP del servidor remoto:").grid(row=0, column=0, padx=5, sticky="e")
        self.iot_ip_var = tk.StringVar(value="")
        ttk.Entry(frame_conf, textvariable=self.iot_ip_var, width=18).grid(row=0, column=1, padx=5)

        ttk.Label(frame_conf, text="Puerto:").grid(row=0, column=2, padx=5, sticky="e")
        self.iot_port_var = tk.IntVar(value=5000)
        ttk.Entry(frame_conf, textvariable=self.iot_port_var, width=8).grid(row=0, column=3, padx=5)

        # ==============================
        # CONTROLES DE SERVIDOR LOCAL
        # ==============================
        frame_srv = ttk.LabelFrame(f, text="Servidor IoT Local")
        frame_srv.pack(fill="x", padx=10, pady=5)

        self.server_running = False
        self.server_thread = None

        ttk.Button(frame_srv, text="🚀 Iniciar Servidor", command=self.start_iot_server).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(frame_srv, text="🛑 Detener Servidor", command=self.stop_iot_server).grid(row=0, column=1, padx=5, pady=5)

        # ==============================
        # FUNCIONES DE CLIENTE
        # ==============================
        frame_cli = ttk.LabelFrame(f, text="Cliente IoT (modo remoto)")
        frame_cli.pack(fill="x", padx=10, pady=5)

        ttk.Button(frame_cli, text="🔌 Probar Conexión", command=self.test_iot_connection).grid(row=0, column=0, padx=5)
        ttk.Button(frame_cli, text="📤 Enviar Archivo", command=self.send_iot_file).grid(row=0, column=1, padx=5)

        # ==============================
        # PROGRESO + LOGS
        # ==============================
        ttk.Label(f, text="Progreso de envío:").pack(pady=(15, 5))
        self.iot_progress = ttk.Progressbar(f, length=500, mode="determinate")
        self.iot_progress.pack(pady=5)

        self.iot_log = tk.Text(f, height=12, bg="#1e272e", fg="white", font=("Courier", 10))
        self.iot_log.pack(fill="x", padx=10, pady=10)
        ToolTip(self.iot_log, "Registro detallado de eventos IoT")

        # ==============================
        # SECCIÓN DE AYUDA
        # ==============================
        ttk.Label(f, text="ℹ️ Ayuda rápida:", font=("Arial", 11, "bold")).pack(pady=(10, 2))
        help_text = (
            "1️⃣ Para recibir archivos, inicia el servidor en el dispositivo de destino.\n"
            "2️⃣ En el otro dispositivo, introduce la IP del servidor (ver más abajo).\n"
            "3️⃣ Usa 'Probar Conexión' para verificar.\n"
            "4️⃣ Si funciona, selecciona un archivo y presiona 'Enviar Archivo'.\n\n"
            "💡 Para obtener la IP en el dispositivo servidor (Linux/Mac):\n"
            "   👉 Ejecuta en la terminal: ip a | grep inet\n"
            "   Ejemplo: inet 192.168.0.45\n\n"
            "💡 En Windows:\n"
            "   👉 Abre CMD y escribe: ipconfig\n"
            "   Busca 'Dirección IPv4'.\n"
        )
        help_label = tk.Text(f, height=8, wrap="word", bg="#2c3e50", fg="#ecf0f1", font=("Arial", 9))
        help_label.insert("1.0", help_text)
        help_label.config(state="disabled")
        help_label.pack(fill="x", padx=15, pady=(0, 10))

    # ==============================
    # FUNCIONES AUXILIARES IoT
    # ==============================
    def log_iot(self, msg):
        """Agrega texto a la consola IoT."""
        self.iot_log.insert("end", msg + "\n")
        self.iot_log.see("end")
        log.info("[IoT] " + msg)

    def start_iot_server(self):
        """Inicia el servidor IoT en un hilo separado."""
        if self.server_running:
            self.log_iot("⚠️ El servidor ya está en ejecución.")
            return

        def server_loop():
            host = "0.0.0.0"
            port = self.iot_port_var.get()
            buffer_size = 4096
            dest_dir = os.path.join(os.path.dirname(__file__), "..", "archivos_recibidos")
            os.makedirs(dest_dir, exist_ok=True)

            self.log_iot(f"🌐 Servidor IoT escuchando en {host}:{port}")
            self.server_running = True

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.bind((host, port))
                server.listen(5)
                server.settimeout(1)

                while self.server_running:
                    try:
                        conn, addr = server.accept()
                        self.log_iot(f"📡 Conexión desde {addr}")
                        with conn:
                            header_data = b""
                            while not header_data.endswith(b"\n"):
                                chunk = conn.recv(1)
                                if not chunk:
                                    break
                                header_data += chunk
                            if not header_data:
                                self.log_iot("⚠️ Conexión vacía.")
                                continue

                            header = json.loads(header_data.decode().strip())
                            filename = header["filename"]
                            size = int(header["size"])
                            checksum = header["checksum"]

                            filepath = os.path.join(dest_dir, filename)
                            conn.sendall(b"ACK")
                            with open(filepath, "wb") as f:
                                total_received = 0
                                while total_received < size:
                                    data = conn.recv(buffer_size)
                                    if not data:
                                        break
                                    f.write(data)
                                    total_received += len(data)
                            self.log_iot(f"✅ Archivo recibido: {filename} ({total_received/1e6:.2f} MB)")
                            conn.sendall(b"EOF_OK")

                    except socket.timeout:
                        continue
                    except Exception as e:
                        self.log_iot(f"❌ Error en servidor: {e}")
                        continue

            self.server_running = False
            self.log_iot("🛑 Servidor IoT detenido.")

        # Lanzar el hilo
        self.server_thread = threading.Thread(target=server_loop, daemon=True)
        self.server_thread.start()

    def stop_iot_server(self):
        """Detiene el servidor IoT embebido."""
        if not self.server_running:
            self.log_iot("⚠️ El servidor no está activo.")
            return
        self.server_running = False
        self.log_iot("🛑 Solicitando apagado del servidor...")

    def test_iot_connection(self):
        """Prueba la conexión TCP simple con el servidor IoT."""
        host = self.iot_ip_var.get()
        port = self.iot_port_var.get()
        try:
            with socket.create_connection((host, port), timeout=3) as s:
                s.sendall(b"ping")
                self.log_iot(f"✅ Conectado con {host}:{port}")
                messagebox.showinfo("Conexión exitosa", f"Conectado con {host}:{port}")
        except Exception as e:
            self.log_iot(f"❌ Error al conectar: {e}")
            messagebox.showerror("Error de conexión", str(e))

    def send_iot_file(self):
        """Permite seleccionar un archivo y enviarlo al servidor IoT."""
        filepath = filedialog.askopenfilename(title="Seleccionar archivo para enviar")
        if not filepath:
            return

        host = self.iot_ip_var.get()
        port = self.iot_port_var.get()
        size = os.path.getsize(filepath)
        filename = os.path.basename(filepath)

        import hashlib
        checksum = hashlib.sha256(open(filepath, "rb").read()).hexdigest()

        header = json.dumps({
            "action": "send_file",
            "filename": filename,
            "size": size,
            "checksum": checksum
        }).encode() + b"\n"

        try:
            with socket.create_connection((host, port)) as s:
                s.sendall(header)
                ack = s.recv(8)
                if ack != b"ACK":
                    raise Exception("Servidor no aceptó la transferencia")

                self.iot_progress["value"] = 0
                self.iot_progress["maximum"] = size
                self.log_iot(f"📤 Enviando {filename} ({size/1e6:.2f} MB) a {host}:{port}")

                with open(filepath, "rb") as f:
                    sent = 0
                    for chunk in iter(lambda: f.read(4096), b""):
                        s.sendall(chunk)
                        sent += len(chunk)
                        self.iot_progress["value"] = sent
                        self.update_idletasks()

                self.log_iot("✅ Transferencia completada.")
                s.sendall(b"EOF")
                messagebox.showinfo("Éxito", f"Archivo {filename} enviado correctamente.")
        except Exception as e:
            self.log_iot(f"❌ Error de envío: {e}")
            messagebox.showerror("Error", str(e))





    # ————— Bloque: Registrar mensajes en ventana de logs —————
    def log_message(self, msg):
        """
        Registra mensajes en la ventana de log (área de texto) y a la vez en el logger.

        Args:
            msg (str): Mensaje a registrar.
        """
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        log.info(msg)


    # ————— Bloque: Exportación de figuras y tablas —————
    def export_figure(self, fig):
        """
        Exporta la figura gráfica actual a un archivo PNG.

        Args:
            fig (matplotlib.figure.Figure): Figura a exportar.
        """
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")]
        )
        if path:
            fig.savefig(path)
            messagebox.showinfo("Exportar", f"Guardado en {path}")


    def export_ppm(self):
        """
        Exporta la tabla de estimaciones ppm a un archivo CSV.
        """
        if self.ppm_df is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        if path:
            self.ppm_df.to_csv(path, index=False)
            messagebox.showinfo("Exportar", f"Guardado en {path}")


    # ————— Bloque: Mostrar estimación ppm en tabla —————
    def show_ppm(self):
        """
        Muestra las estimaciones de ppm en un Treeview:
        - Extrae los nombres de metales de limits_ppm.json
        - Construye un DataFrame con nombres reales de metales
        - Marca alertas usando umbrales específicos para cada metal
        - Añade porcentaje de superación y estado por metal
        """
        print("[DEBUG] show_ppm() invoked")
        if self.current_data is None:
            print("[DEBUG] show_ppm: sin datos")
            return

        # Cargar límites desde JSON la primera vez
        if not hasattr(self, "limites_ppm"):
            try:
                with open("limits_ppm.json", "r") as f:
                    self.limites_ppm = json.load(f)
                print(f"[DEBUG] Límites cargados: {self.limites_ppm}")
            except Exception as e:
                print(f"[ERROR] Error cargando límites: {e}")
                return  # No es posible continuar sin límites

        # Asegurarse de que existen estimaciones en memoria
        if "ppm_estimations" not in self.current_data.columns:
            print("[DEBUG] show_ppm: columna 'ppm_estimations' no existe en DataFrame")
            return

        # Construir dataframe con nombres de metales
        metales = list(self.limites_ppm.keys())
        df = (
            pd.DataFrame(
                self.current_data["ppm_estimations"].tolist(),
                columns=metales
            )
            .fillna(0)
        )

        # Añadir columnas de % superación y estado por metal
        for metal in metales:
            limite = float(self.limites_ppm.get(metal, 0))
            if limite > 0:
                df[f"{metal}_%"] = (df[metal] / limite) * 100
                df[f"{metal}_estado"] = df[metal].apply(
                    lambda v: "⚠️ EXCEDE" if v >= limite else "✅ SEGURO"
                )
            else:
                df[f"{metal}_%"] = 0
                df[f"{metal}_estado"] = "N/A"

        self.ppm_df = df  # guardar para exportar CSV

        # Configurar columnas del Treeview
        cols = []
        for metal in metales:
            cols.extend([metal, f"{metal}_%", f"{metal}_estado"])
        self.tree_ppm.config(columns=cols)

        for col in cols:
            self.tree_ppm.heading(col, text=col)

        self.tree_ppm.delete(*self.tree_ppm.get_children())

        # Poblar filas y resaltar alertas
        for _, row in df.iterrows():
            valores = []
            alerta = False
            for metal in metales:
                valores.append(row[metal])
                valores.append(f"{row[f'{metal}_%']:.1f}%")
                estado = row[f"{metal}_estado"]
                valores.append(estado)
                if "EXCEDE" in estado:
                    alerta = True

            tag = "alert" if alerta else "safe"
            self.tree_ppm.insert("", "end", values=valores, tags=(tag,))

        # Estilos
        self.tree_ppm.tag_configure("alert", background="#ffcdd2", foreground="#d32f2f")
        self.tree_ppm.tag_configure("safe", background="#c8e6c9", foreground="#2e7d32")

        ToolTip(
            self.tree_ppm,
            "Tabla de estimaciones ppm; se muestra valor, % de superación y estado por metal.\n"
            "En rojo los que exceden el límite oficial definido en limits_ppm.json"
        )

        print("[DEBUG] Tabla ppm actualizada correctamente")

    # ————— Bloque: Botón “Mostrar Clasificación” —————
    def show_classification(self):
        """
        Invocado por el botón "Mostrar Clasificación".
        Refresca la tabla de ppm comparando contra los límites oficiales del JSON.

        Flujo:
        - Carga los límites regulatorios desde limits_ppm.json.
        - Recorre las mediciones actuales (self.current_data).
        - Para cada metal, compara el valor medido contra su límite oficial.
        - Construye un DataFrame con columnas detalladas (Metal, Valor, Límite, Estado, Clasificación Global, Nivel).
        - Reconfigura la tabla tree_ppm para mostrar esas columnas.
        - Inserta filas con estilos según el estado (seguro o contaminado).
        - Guarda el DataFrame en self.ppm_df para exportación.
        """
        print("[DEBUG] show_classification() invoked")

        # 1) Cargar límites regulatorios
        try:
            with open("limits_ppm.json", "r") as f:
                limites = json.load(f)
            print(f"[DEBUG] Límites regulatorios cargados: {limites}")
        except Exception as e:
            print(f"[ERROR] No se pudieron cargar los límites: {e}")
            messagebox.showerror("Error", "No se pudieron cargar los límites regulatorios")
            return

        # 2) Validar que haya datos cargados
        if self.current_data is None or self.current_data.empty:
            print("[DEBUG] No hay datos en current_data")
            return

        # 3) Construir DataFrame con comparaciones
        rows = []
        for idx, m in self.current_data.iterrows():
            ppm_vals = m.get("ppm_estimations", {})
            clasificacion = m.get("clasificacion", "SIN CLASIFICAR")
            nivel = m.get("contamination_level", 0)

            # Debug detallado
            print(f"[DEBUG] Medición {idx}: ppm={ppm_vals}, clasificacion={clasificacion}, nivel={nivel}")

            # Comparar cada metal contra su límite
            for metal, limite in limites.items():
                valor = ppm_vals.get(metal, 0)
                estado = "✅ SEGURO" if valor < limite else "⚠️ CONTAMINADO"
                rows.append({
                    "Metal": metal,
                    "Valor (ppm)": valor,
                    "Límite (ppm)": limite,
                    "Estado": estado,
                    "Clasificación Global": clasificacion,
                    "Nivel (%)": nivel
                })

        # 4) Reconfigurar columnas de la tabla para que coincidan con los datos
        cols = ("Metal", "Valor (ppm)", "Límite (ppm)", "Estado", "Clasificación Global", "Nivel (%)")
        self.tree_ppm.config(columns=cols)
        for c in cols:
            self.tree_ppm.heading(c, text=c)
            self.tree_ppm.column(c, anchor="center")

        # 5) Poblar tabla en GUI
        self.tree_ppm.delete(*self.tree_ppm.get_children())
        self.ppm_df = pd.DataFrame(rows)  # para exportar CSV

        for _, row in self.ppm_df.iterrows():
            estado = row["Estado"]
            tag = "safe" if "SEGURO" in estado else "alert"
            vals = (
                row["Metal"],
                row["Valor (ppm)"],
                row["Límite (ppm)"],
                row["Estado"],
                row["Clasificación Global"],
                row["Nivel (%)"]
            )
            self.tree_ppm.insert("", "end", values=vals, tags=(tag,))

        # 6) Estilos
        self.tree_ppm.tag_configure("alert", background="#ffcdd2", foreground="#d32f2f")
        self.tree_ppm.tag_configure("safe", background="#c8e6c9", foreground="#2e7d32")

        print("[DEBUG] Tabla de clasificación actualizada correctamente")



    # ————— Bloque: Cargar archivo y guardar en BD (corregido) —————
    def load_file(self):
        """
        Abre un diálogo para seleccionar un archivo .pssession.
        Procesa la sesión internamente, guarda en BD y actualiza la interfaz.

        Flujo:
        - Carga límites regulatorios desde JSON.
        - Procesa la sesión y extrae mediciones.
        - Calcula ppm_estimations, contamination_level y clasificacion.
        - Determina classification_group en Python (0,1,2).
        - Inserta datos en la BD con tipos correctos.
        - Actualiza la interfaz gráfica.
        """
        print("[DEBUG] load_file() invoked")
        path = filedialog.askopenfilename(filetypes=[("PSSession", "*.pssession")])
        if not path:
            print("[DEBUG] Carga de archivo cancelada por el usuario")
            return
        try:
            print(f"[DEBUG] Procesando archivo: {path}")

            # 1) Importación corregida
            from pstrace_session import extract_session_dict, cargar_limites_ppm as cargar_limites
            print("[DEBUG] Módulo pstrace_session importado correctamente")

            limites = cargar_limites()
            print(f"[DEBUG] Límites PPM cargados: {list(limites.keys()) if limites else 'No disponibles'}")

            data = extract_session_dict(path)
            if not data:
                raise ValueError("No se extrajeron datos de la sesión")
            print("[DEBUG] Datos de sesión extraídos correctamente")

            # 2) Guardar en la base de datos
            conn = pg8000.connect(**DB_CONFIG)
            cur = conn.cursor()
            fname = os.path.basename(path)
            now = datetime.datetime.now()

            # Insertar session
            cur.execute(
                """
                INSERT INTO sessions
                  (filename, loaded_at, scan_rate, start_potential,
                   end_potential, software_version)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    fname,
                    now,
                    data["session_info"].get("scan_rate"),
                    data["session_info"].get("start_potential"),
                    data["session_info"].get("end_potential"),
                    data["session_info"].get("software_version"),
                ),
            )
            sid = cur.fetchone()[0]
            print(f"[DEBUG] Sesión insertada en BD. ID: {sid}")

            # Insertar mediciones usando la clave correcta (pca_data o pca_scores)
            for idx, m in enumerate(data["measurements"]):
                pca_key = "pca_scores" if "pca_scores" in m else "pca_data"

                ppm_estimations = m.get("ppm_estimations") or {}
                contamination_level = m.get("contamination_level", 0)
                clasificacion = m.get("clasificacion", "SIN CLASIFICAR")

                # Derivar valores si faltan
                if not ppm_estimations:
                    ppm_estimations = {}
                max_superacion = 0.0
                for metal, limite in limites.items():
                    valor = float(ppm_estimations.get(metal, 0) or 0)
                    superacion = (valor / float(limite)) * 100 if float(limite) > 0 else 0
                    if superacion > max_superacion:
                        max_superacion = superacion
                if contamination_level in (None, 0) and max_superacion > 0:
                    contamination_level = round(max_superacion, 2)

                if not clasificacion or clasificacion == "SIN CLASIFICAR":
                    if contamination_level >= 120:
                        clasificacion = "⚠️ CONTAMINACIÓN SEVERA"
                    elif contamination_level >= 100:
                        clasificacion = "⚡ CONTAMINACIÓN MODERADA"
                    elif contamination_level >= 80:
                        clasificacion = "🟡 REQUIERE ATENCIÓN"
                    else:
                        clasificacion = "✅ NIVEL SEGURO"

                # Calcular classification_group en Python
                if contamination_level >= 100:
                    classification_group = 1
                elif contamination_level >= 80:
                    classification_group = 2
                else:
                    classification_group = 0

                # Debug detallado antes de insertar
                print(
                    f"[DEBUG] Medición {idx+1} -> nivel={contamination_level}, clas={clasificacion}, grupo={classification_group}, ppm={ppm_estimations}"
                )

                cur.execute(
                    """
                    INSERT INTO measurements
                      (session_id, title, timestamp, device_serial, curve_count,
                       pca_scores, ppm_estimations, classification_group,
                       contamination_level, clasificacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sid,
                        m.get("title"),
                        m.get("timestamp"),
                        m.get("device_serial"),
                        m.get("curve_count"),
                        m.get(pca_key),
                        json.dumps(ppm_estimations),
                        classification_group,          # entero calculado en Python
                        float(contamination_level),    # double precision
                        clasificacion,
                    ),
                )
                print(f"[DEBUG] Medición {idx+1} insertada")

            conn.commit()
            conn.close()
            print("[DEBUG] Datos guardados en BD")

            # 3) Actualizar UI
            self.current_data = pd.DataFrame(data["measurements"])
            self.session_info = data["session_info"]
            self.session_info["session_id"] = sid

            self.log_message(f"Sesión {sid} cargada")
            self.txt_detail.delete("1.0", "end")
            self.txt_detail.insert("end", json.dumps(self.session_info, indent=2, ensure_ascii=False))

            indices = list(self.current_data.index)
            self.cmb_curve["values"] = indices
            if indices:
                self.cmb_curve.set(indices[0])

            self.show_curve()
            self.show_pca()
            self.show_classification()
            self.load_sessions()
            print("[DEBUG] UI actualizada")

        except Exception as e:
            print(f"[ERROR] Error en load_file: {str(e)}")
            import traceback
            traceback.print_exc()
            self.log_message(f"Error carga archivo: {e}")



    # ————— Bloque: (Segunda) Consultar sesiones —————
    def query_sessions_alternative(self):
        """
        Realiza una consulta alternativa de sesiones basado en el ID y fecha.
        Actualiza la tabla de resultados con los datos obtenidos.
        """
        sid_text = self.id_entry.get().strip()
        date_text = self.date_start.get_date().strftime("%Y-%m-%d")
        where_clauses = []
        params = []

        if sid_text:
            where_clauses.append("s.id = %s")
            params.append(int(sid_text))
        if date_text:
            where_clauses.append("s.loaded_at::date = %s")
            params.append(date_text)

        where_sql = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"""
            SELECT s.id, s.filename, s.loaded_at AS Fecha,
                   m.device_serial AS Sensor,
                   m.curve_count AS CurveCount,
                   CASE WHEN MAX(p.current) > %s THEN '⚠️ Contaminación' ELSE '✅ Limpio' END AS Estado
            FROM sessions s
            JOIN measurements m ON s.id = m.session_id
            LEFT JOIN curves c ON m.id = c.measurement_id
            LEFT JOIN points p ON c.id = p.curve_id
            WHERE 1=1
            {where_sql}
            GROUP BY s.id, s.filename, s.loaded_at, m.device_serial, m.curve_count
        """
        params.insert(0, self.settings["alert_threshold"])

        try:
            conn = pg8000.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            conn.close()

            self.tree.delete(*self.tree.get_children())
            for row in rows:
                self.tree.insert("", "end", values=row)
        except Exception as e:
            self.log_message(f"Error en consulta: {e}")


    # ————— Bloque: Mostrar curvas individuales y ciclo 3 —————
    def show_curve(self):
        """
        Dibuja la(s) curva(s) de voltametría para la medición seleccionada.
        Ahora se muestran todas las curvas para inspección, pero se resalta
        únicamente el ciclo 3, que es el usado para la clasificación según
        los objetivos del proyecto.
        """
        print("[DEBUG] show_curve() invoked")
        if self.current_data is None or self.cmb_curve.get() == "":
            print("[DEBUG] show_curve: sin datos o índice vacío")
            return

        # Índice de medición seleccionado
        idx = int(self.cmb_curve.get())
        arrs = self.current_data.at[idx, "pca_scores"] or []
        n = len(arrs) // len(self.settings["cycles"]) if arrs else 1
        curvas = [arrs[i * n : (i + 1) * n] for i in range(len(self.settings["cycles"]))]
        x = list(range(n))

        # Limpiar ejes
        self.ax_curve.clear()

        # Graficar todas las curvas individuales en gris claro
        for i, curve in enumerate(curvas, start=1):
            color = "#95a5a6"  # gris
            alpha = 0.3
            linewidth = 1
            if i == 3:  # ciclo 3
                color = "#e74c3c"  # rojo intenso
                alpha = 1.0
                linewidth = 2
            self.ax_curve.plot(x, curve, color=color, alpha=alpha, linewidth=linewidth)

        # Título y etiquetas
        si = self.session_info
        sensor = self.current_data.at[idx, "device_serial"] or "N/A"
        self.ax_curve.set_title(f"Sesión {si['session_id']} · Sensor {sensor}", color="white")
        self.ax_curve.set_xlabel("Índice de punto", color="white")
        self.ax_curve.set_ylabel("Corriente (A)", color="white")

        # Leyenda y cuadrícula
        self.ax_curve.legend(["Curvas individuales", "Ciclo 3 (referencia)"],
                             facecolor=COLOR_BG, labelcolor="white")
        self.ax_curve.grid(True, color="#5d6d7e")

        # Redibujar canvas
        self.canvas_curve.draw()
        ToolTip(self.canvas_curve.get_tk_widget(),
                "Aquí ves todas las curvas; el ciclo 3 en rojo es el usado para clasificación")
  
  
    # ————— Bloque: Mostrar PCA y varianza —————


    def show_pca(self):
        """
        Calcula y muestra el PCA de los vectores pca_scores de todas las mediciones.
        La varianza acumulada permite identificar cuántos componentes principales
        explican la mayor parte de la variabilidad en los datos.
        """
        print("[DEBUG] show_pca() invoked")
        if self.current_data is None or "pca_scores" not in self.current_data:
            print("[DEBUG] show_pca: sin datos en current_data o falta columna pca_scores")
            return

        try:
            # Matriz de datos
            df = pd.DataFrame(self.current_data["pca_scores"].tolist()).fillna(0)
            if df.empty:
                print("[DEBUG] show_pca: DataFrame vacío, no se puede calcular PCA")
                return

            # Ajuste PCA
            pca = PCA().fit(df)
            var = pca.explained_variance_ratio_.cumsum() * 100
            print(f"[DEBUG] show_pca: Varianza acumulada calculada, primeros valores: {var[:5]}")

            # Limpiar ejes
            self.ax_pca.clear()

            # Graficar varianza acumulada
            self.ax_pca.plot(range(1, len(var) + 1), var, marker="o", linewidth=2, color="#3498db")
            for i, v in enumerate(var[:3], start=1):
                self.ax_pca.annotate(
                    f"{v:.1f}%",
                    (i, v),
                    textcoords="offset points",
                    xytext=(0, 5),
                    ha="center",
                    color="white"
                )

            # Estética
            self.ax_pca.set_ylim(0, 100)
            self.ax_pca.set_title("Varianza Acumulada PCA", color="white")
            self.ax_pca.set_xlabel("Componentes", color="white")
            self.ax_pca.set_ylabel("Varianza (%)", color="white")
            self.ax_pca.grid(True, color="#5d6d7e")

            # Redibujar canvas
            self.canvas_pca.draw()
            ToolTip(
                self.canvas_pca.get_tk_widget(),
                "La curva muestra cuánta varianza explican los componentes principales.\n"
                "Ejemplo: si con 2 componentes llegas al 90%, significa que esos dos\n"
                "componentes explican el 90% de la variabilidad de los datos."
            )

        except Exception as e:
            print(f"[DEBUG] show_pca Error: {e}")
            messagebox.showerror("Error", f"Error calculando o mostrando PCA:\n{e}")

    # ——— Bloque: Pestaña “PCA” ———
    def build_pca_tab(self, parent):
        """
        Configura la pestaña 'PCA' para visualizar el análisis de componentes principales.

        Args:
            parent (ttk.Notebook): Notebook donde se añade la pestaña.
        """
        print("[DEBUG] build_pca_tab() invoked")

        f = ttk.Frame(parent)
        parent.add(f, text="📈 PCA")

        # Botón para mostrar PCA
        btn_show_pca = ttk.Button(f, text="Mostrar PCA", command=self.show_pca)
        btn_show_pca.pack(pady=8)
        ToolTip(
            btn_show_pca,
            "Calcula y muestra la gráfica de varianza acumulada del PCA.\n"
            "Esto permite ver cuántos componentes principales explican la mayor parte de la variabilidad."
        )

        # Figura y ejes para la gráfica PCA
        self.fig_pca, self.ax_pca = plt.subplots(figsize=(9, 5), facecolor=COLOR_BG)
        self.ax_pca.set_facecolor(COLOR_BG)
        self.ax_pca.tick_params(colors="white")
        self.ax_pca.grid(True, color="#5d6d7e")

        # Canvas para incrustar la figura en la GUI
        self.canvas_pca = FigureCanvasTkAgg(self.fig_pca, master=f)
        self.canvas_pca.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        ToolTip(
            self.canvas_pca.get_tk_widget(),
            "Gráfica de varianza acumulada resultante del PCA.\n"
            "Ejemplo: si con 2 componentes llegas al 90%, significa que esos dos\n"
            "componentes explican el 90% de la variabilidad de los datos."
        )

        # Botón para exportar la gráfica
        btn_export_pca = ttk.Button(
            f,
            text="Exportar PCA",
            command=lambda: self.export_figure(self.fig_pca)
        )
        btn_export_pca.pack(side="right", padx=10, pady=5)
        ToolTip(
            btn_export_pca,
            "Exporta la gráfica de PCA como imagen PNG.\n"
            "Útil para informes, documentación y trazabilidad científica."
        )

        print("[DEBUG] build_pca_tab: pestaña PCA configurada correctamente")



    # ————— Bloque: Cargar lista de sesiones (para futuras funciones) —————
    def load_sessions(self):
        """
        Carga en memoria la lista de IDs de sesiones registradas en la base de datos.
        """
        try:
            conn = pg8000.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("SELECT id FROM sessions")
            _ = [r[0] for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            self.log_message(f"Error cargando sesiones: {e}")

    # ————— Bloque: Ventana de ajustes (segunda definición) —————
    def show_settings_alternative(self):
        """
        Abre una ventana para editar los ciclos a promediar en base a la configuración actual.
        Guarda los cambios mediante la función save_settings().
        """
        w = tk.Toplevel(self)
        w.title("Ajustes")
        ttk.Label(w, text="Ciclos a promediar:").pack(pady=5)
        e = ttk.Entry(w)
        e.insert(0, ",".join(map(str, self.settings["cycles"])))
        e.pack(pady=5)

        def save():
            self.settings["cycles"] = [int(x) for x in e.get().split(",")]
            self.save_settings()
            w.destroy()

        ttk.Button(w, text="Guardar", command=save).pack(pady=10)

if __name__ == "__main__":
    app = Aplicacion()
    app.mainloop()