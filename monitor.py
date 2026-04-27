import json
import logging
import os
import sys
import threading
import time
import tkinter as tk
import winsound  # Para alertas sonoras de respaldo
from datetime import datetime
from tkinter import messagebox, scrolledtext, simpledialog, ttk

import matplotlib.pyplot as plt
import pygame  # Para reproducir MP3
import requests
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

try:
    from flask import Flask, jsonify, render_template_string
    FLASK_SUPPORT = True
except ImportError:
    FLASK_SUPPORT = False

# --- PLANTILLAS DASHBOARD WEB ---
WEB_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Monitor Pro - Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f4f7f6; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1000px; margin: auto; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 15px; border-bottom: 2px solid #f0f0f0; color: #666; font-weight: 600; }
        td { padding: 15px; border-bottom: 1px solid #f0f0f0; }
        .status-badge { padding: 6px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
        .online { background: #e6fffa; color: #234e52; border: 1px solid #b2f5ea; }
        .offline { background: #fff5f5; color: #742a2a; border: 1px solid #feb2b2; }
        a { color: #007bff; text-decoration: none; font-weight: 500; }
        a:hover { text-decoration: underline; }
        .chart-container { height: 300px; width: 100%; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 Monitor de Sitios Web</h1>
            <div style="text-align: right">
                <div style="font-size: 0.9em; color: #718096">Salud Global: <strong>{{ global_health }}%</strong></div>
                <div style="font-size: 0.8em; color: #a0aec0">Última actualización: {{ ahora }}</div>
            </div>
        </header>

        <div class="card">
            <h3>📈 Salud Global del Ecosistema</h3>
            <div class="chart-container">
                <canvas id="globalChart"></canvas>
            </div>
        </div>

        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>SITIO WEB</th>
                        <th>ESTADO</th>
                        <th>LATENCIA</th>
                        <th>UPTIME</th>
                    </tr>
                </thead>
                <tbody>
                    {% for url, data in sitios.items() %}
                    <tr>
                        <td><a href="/site/{{ url }}">{{ url }}</a></td>
                        <td>
                            {% if data.estado == "UP" %}
                                <span class="status-badge online">● ONLINE</span>
                            {% else %}
                                <span class="status-badge offline">● DOWN</span>
                            {% endif %}
                        </td>
                        <td style="font-family: monospace;">{{ data.historial[-1].latencia if data.historial else '-' }} ms</td>
                        <td style="font-weight: bold; color: #2b6cb0;">{{ "%.2f"|format(((data.checks - data.fails) / data.checks * 100) if data.checks > 0 else 100) }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('globalChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ global_labels|safe }},
                datasets: [{
                    label: '% Online',
                    data: {{ global_values|safe }},
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { min: 0, max: 100 } }
            }
        });
    </script>
</body>
</html>
"""

DETALLE_WEB_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Detalle - {{ url }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f4f7f6; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: auto; }
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .back-link { margin-bottom: 20px; display: block; color: #007bff; text-decoration: none; }
        .chart-container { height: 350px; width: 100%; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .stat-box { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-val { font-size: 1.5em; font-weight: bold; color: #2d3748; }
        .stat-label { font-size: 0.8em; color: #718096; text-transform: uppercase; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Volver al Dashboard</a>
        <div class="card">
            <h1>📊 Análisis Detallado: {{ url }}</h1>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-val">{{ "%.2f"|format(uptime) }}%</div>
                    <div class="stat-label">Uptime Total</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val">{{ data.checks }}</div>
                    <div class="stat-label">Chequeos Totales</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val">{{ data.fails }}</div>
                    <div class="stat-label">Fallos Detectados</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>⏱ Historial de Latencia (ms)</h3>
            <div class="chart-container">
                <canvas id="latenciaChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h3>⚡ Estado de Disponibilidad (UP/DOWN)</h3>
            <div class="chart-container">
                <canvas id="statusChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        const labels = {{ labels|safe }};
        
        // Chart Latencia
        new Chart(document.getElementById('latenciaChart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Latencia (ms)',
                    data: {{ latencias|safe }},
                    borderColor: '#ff7f0e',
                    backgroundColor: 'rgba(255, 127, 14, 0.1)',
                    fill: true
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Chart Estado
        new Chart(document.getElementById('statusChart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Estado (1=UP, 0=DOWN)',
                    data: {{ estados|safe }},
                    borderColor: '#2ca02c',
                    stepped: true,
                    backgroundColor: 'rgba(44, 160, 44, 0.1)',
                    fill: true
                }]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false,
                scales: { y: { min: -0.5, max: 1.5, ticks: { stepSize: 1 } } }
            }
        });
    </script>
</body>
</html>
"""

# Para inicio automático en Windows
try:
    import winreg
    WINDOWS_REGISTRY = True
except ImportError:
    WINDOWS_REGISTRY = False

# ... (rest of imports unchanged)

# Intentar importar librerías para la bandeja del sistema
try:
    import pystray
    from PIL import Image, ImageDraw

    TRAY_SUPPORT = True
except ImportError:
    TRAY_SUPPORT = False

# --- ARCHIVOS DE PERSISTENCIA ---
ARCHIVO_SITIOS = "sitios.txt"
ARCHIVO_CONFIG = "config.json"
ARCHIVO_HISTORIAL = "historial.json"
CARPETA_ALARMAS = "alarmas"

# Inicializar mezclador de audio de pygame
pygame.mixer.init()

logging.basicConfig(
    filename="elsitio.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Sitios Web Pro v5.0")
        self.root.geometry("1000x850")
        self.root.configure(bg="#f8f9fa")

        self.monitoreando = False
        self.sitios = {}  # {url: {comentario, estado, checks, fails, historial: []}}

        # Variables de configuración (Persistentes)
        self.token_tg = tk.StringVar()
        self.id_tg = tk.StringVar()
        self.intervalo = tk.IntVar(value=60)
        self.sonido_activado = tk.BooleanVar(value=True)
        self.inicio_automatico = tk.BooleanVar(value=False)
        self.modo_oscuro = tk.BooleanVar(value=False)
        self.archivo_alarma = tk.StringVar(value="Ninguno")
        self.web_activo = tk.BooleanVar(value=False)
        self.web_puerto = tk.IntVar(value=5000)

        self.datos_tiempo = []
        self.datos_porcentaje = []

        # Asegurar que existe la carpeta de alarmas
        if not os.path.exists(CARPETA_ALARMAS):
            os.makedirs(CARPETA_ALARMAS)

        self.setup_ui()
        self.cargar_configuracion()
        self.cargar_sitios_desde_archivo()
        self.cargar_historial_persistente()

        if TRAY_SUPPORT:
            self.setup_tray()
            self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.iniciar_servidor_web()

    def setup_ui(self):
        # --- ESTILOS ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=28)

        # --- BARRA SUPERIOR ---
        top_bar = tk.Frame(
            self.root, bg="#ffffff", pady=10, padx=20, bd=1, relief="groove"
        )
        top_bar.pack(fill="x")

        tk.Label(top_bar, text="URL:", bg="#ffffff", font=("Segoe UI", 10)).pack(
            side="left"
        )
        self.entry_url = tk.Entry(top_bar, font=("Segoe UI", 10), width=35)
        self.entry_url.pack(side="left", padx=10)
        self.entry_url.insert(0, "https://")
        tk.Label(
            top_bar, text="Comentario:", bg="#ffffff", font=("Segoe UI", 10)
        ).pack(side="left")
        self.entry_comentario = tk.Entry(top_bar, font=("Segoe UI", 10), width=24)
        self.entry_comentario.pack(side="left", padx=8)

        tk.Button(
            top_bar,
            text="✚ Añadir",
            command=self.agregar_sitio,
            bg="#007bff",
            fg="white",
            padx=15,
            relief="flat",
        ).pack(side="left", padx=2)
        tk.Button(
            top_bar,
            text="✖ Eliminar",
            command=self.eliminar_sitio,
            bg="#6c757d",
            fg="white",
            padx=15,
            relief="flat",
        ).pack(side="left", padx=2)
        tk.Button(
            top_bar,
            text="Editar comentario",
            command=self.editar_comentario_sitio,
            bg="#17a2b8",
            fg="white",
            padx=15,
            relief="flat",
        ).pack(side="left", padx=2)

        tk.Button(
            top_bar, text="❓ Ayuda", command=self.mostrar_manual, bg="#f8f9fa", padx=10
        ).pack(side="right", padx=5)
        
        self.btn_tema = tk.Button(
            top_bar,
            text="🌙 Modo Oscuro",
            command=self.toggle_tema,
            bg="#f8f9fa",
            padx=10,
        )
        self.btn_tema.pack(side="right", padx=5)

        tk.Button(
            top_bar,
            text="⚙ Configuración",
            command=self.abrir_configuracion,
            bg="#f8f9fa",
            padx=10,
        ).pack(side="right")

        # --- CUERPO PRINCIPAL ---
        body = tk.Frame(self.root, bg="#f8f9fa", padx=20, pady=10)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="💡 Tip: Doble clic en un sitio para ver su historial detallado persistente",
            font=("Segoe UI", 8, "italic"),
            bg="#f8f9fa",
            fg="#6c757d",
        ).pack(anchor="w")

        # Tabla de sitios
        columns = ("url", "comment", "status", "latency", "uptime", "last_check")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", height=8)
        self.tree.heading("url", text="URL del Sitio")
        self.tree.heading("comment", text="Comentario")
        self.tree.heading("status", text="Estado")
        self.tree.heading("latency", text="Latencia")
        self.tree.heading("uptime", text="Uptime %")
        self.tree.heading("last_check", text="Visto")

        self.tree.column("url", width=290)
        self.tree.column("comment", width=220)
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("latency", width=100, anchor="center")
        self.tree.pack(fill="x", pady=5)

        # Evento de doble clic
        self.tree.bind("<Double-1>", self.mostrar_detalle_sitio)

        # Botón de Control
        self.btn_start = tk.Button(
            body,
            text="▶ INICIAR MONITOREO",
            command=self.toggle_monitor,
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 12, "bold"),
            pady=12,
        )
        self.btn_start.pack(fill="x", pady=5)

        # Gráfica Global
        self.fig, self.ax = plt.subplots(figsize=(6, 3), dpi=90)
        self.fig.set_facecolor("#f8f9fa")
        
        # Contenedor para la gráfica y el toolbar
        self.canvas = FigureCanvasTkAgg(self.fig, master=body)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.toolbar = NavigationToolbar2Tk(self.canvas, body)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.aplicar_tema()

    def obtener_lista_alarmas(self):
        """Lista archivos MP3 en la carpeta de alarmas."""
        try:
            archivos = [f for f in os.listdir(CARPETA_ALARMAS) if f.endswith(".mp3")]
            return archivos if archivos else ["Sin archivos MP3"]
        except:
            return ["Error al leer carpeta"]

    def reproducir_alarma(self):
        """Reproduce el MP3 seleccionado o un sonido de respaldo."""
        if not self.sonido_activado.get():
            return

        def sonar():
            archivo = self.archivo_alarma.get()
            ruta_completa = os.path.join(CARPETA_ALARMAS, archivo)

            # Intentar reproducir MP3
            if archivo != "Ninguno" and os.path.exists(ruta_completa):
                try:
                    pygame.mixer.music.load(ruta_completa)
                    pygame.mixer.music.play()
                    return
                except Exception as e:
                    logging.error(f"Error reproduciendo MP3: {e}")

            # Sonido de respaldo (Beep) si falla el MP3 o no hay uno seleccionado
            try:
                for _ in range(3):
                    winsound.Beep(2500, 150)
                    winsound.Beep(1800, 150)
            except:
                pass

        threading.Thread(target=sonar, daemon=True).start()

    def mostrar_detalle_sitio(self, event):
        """Abre una ventana con el historial específico del sitio seleccionado."""
        item = self.tree.selection()
        if not item:
            return
        url = item[0]
        data = self.sitios.get(url)
        if not data:
            return

        oscuro = self.modo_oscuro.get()
        bg_color = "#1e1e1e" if oscuro else "white"
        fg_color = "white" if oscuro else "black"
        ax_bg = "#2d2d2d" if oscuro else "white"

        det_win = tk.Toplevel(self.root)
        det_win.title(f"Detalle: {url}")
        det_win.geometry("700x650")
        det_win.configure(bg=bg_color)

        tk.Label(
            det_win,
            text=f"Análisis de {url}",
            font=("Segoe UI", 14, "bold"),
            bg=bg_color,
            fg=fg_color,
            pady=10,
        ).pack()

        # Frame para gráficas
        graph_frame = tk.Frame(det_win, bg=bg_color)
        graph_frame.pack(fill="both", expand=True, padx=10, pady=10)

        fig_det, (ax_lat, ax_status) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
        fig_det.subplots_adjust(hspace=0.4)
        fig_det.set_facecolor(bg_color)

        historia = data.get("historial", [])
        if not historia:
            tk.Label(
                graph_frame, text="No hay datos suficientes para graficar.", bg=bg_color, fg=fg_color
            ).pack()
            return

        tiempos = []
        for h in historia:
            if isinstance(h["hora"], str):
                tiempos.append(datetime.fromisoformat(h["hora"]))
            else:
                tiempos.append(h["hora"])

        latencias = [h["latencia"] for h in historia]
        estados = [1 if h["online"] else 0 for h in historia]

        ax_lat.plot(
            tiempos,
            latencias,
            color="#ff7f0e",
            marker="o",
            markersize=3,
            label="Latencia",
        )
        ax_lat.set_title("Latencia de Respuesta (ms)", color=fg_color)
        ax_lat.grid(True, alpha=0.3)
        ax_lat.set_ylabel("ms", color=fg_color)
        ax_lat.set_facecolor(ax_bg)
        ax_lat.tick_params(colors=fg_color)
        for spine in ax_lat.spines.values():
            spine.set_color(fg_color)

        ax_status.step(tiempos, estados, where="post", color="#2ca02c", label="Estado")
        ax_status.set_title("Disponibilidad (1=Online, 0=Offline)", color=fg_color)
        ax_status.set_ylim(-0.2, 1.2)
        ax_status.set_yticks([0, 1])
        ax_status.set_yticklabels(["CAÍDO", "OK"])
        ax_status.grid(True, alpha=0.3)
        ax_status.set_facecolor(ax_bg)
        ax_status.tick_params(colors=fg_color)
        for spine in ax_status.spines.values():
            spine.set_color(fg_color)

        fig_det.autofmt_xdate()
        canvas_det = FigureCanvasTkAgg(fig_det, master=graph_frame)
        canvas_det.get_tk_widget().pack(fill="both", expand=True)

        toolbar_det = NavigationToolbar2Tk(canvas_det, graph_frame)
        toolbar_det.update()
        toolbar_det.pack(side=tk.BOTTOM, fill=tk.X)

        total_checks = data["checks"]
        fails = data["fails"]
        uptime_val = (
            ((total_checks - fails) / total_checks * 100) if total_checks > 0 else 100
        )

        bg_stats = "#2d2d2d" if oscuro else "#f8f9fa"
        stats_frame = tk.Frame(det_win, bg=bg_stats, pady=10)
        stats_frame.pack(fill="x")

        info_str = f"Muestras: {len(historia)} | Fallos Totales: {fails} | Uptime Global: {uptime_val:.2f}%"
        tk.Label(
            stats_frame, text=info_str, font=("Segoe UI", 10, "bold"), bg=bg_stats, fg=fg_color
        ).pack()

    def abrir_configuracion(self):
        oscuro = self.modo_oscuro.get()
        bg_color = "#1e1e1e" if oscuro else "white"
        fg_color = "white" if oscuro else "black"
        bg_stats = "#2d2d2d" if oscuro else "#f8f9fa"

        config_win = tk.Toplevel(self.root)
        config_win.title("Ajustes del Monitor")
        config_win.geometry("480x700")
        config_win.configure(bg=bg_color)
        config_win.resizable(False, True)  # Permitir redimensionar verticalmente
        config_win.transient(self.root)
        config_win.grab_set()

        # Añadir un scrollbar si el contenido excede el alto
        main_canvas = tk.Canvas(config_win, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(config_win, orient="vertical", command=main_canvas.yview)
        container = tk.Frame(main_canvas, padx=20, pady=20, bg=bg_color)

        container.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=container, anchor="nw", width=440)
        main_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)

        # --- CONTENIDO ---
        # Telegram
        tk.Label(
            container, text="TOKEN DE TELEGRAM", font=("Segoe UI", 9, "bold"), bg=bg_color, fg=fg_color
        ).pack(anchor="w")
        tk.Entry(container, textvariable=self.token_tg, width=40, show="*", bg=bg_stats, fg=fg_color, insertbackground=fg_color).pack(
            pady=(0, 15)
        )

        tk.Label(container, text="CHAT ID", font=("Segoe UI", 9, "bold"), bg=bg_color, fg=fg_color).pack(
            anchor="w"
        )
        tk.Entry(container, textvariable=self.id_tg, width=40, bg=bg_stats, fg=fg_color, insertbackground=fg_color).pack(pady=(0, 15))

        # Intervalo
        tk.Label(
            container,
            text="INTERVALO DE CHEQUEO (Segundos)",
            font=("Segoe UI", 9, "bold"),
            bg=bg_color,
            fg=fg_color
        ).pack(anchor="w")
        tk.Scale(
            container, from_=10, to=300, orient="horizontal", variable=self.intervalo, bg=bg_color, fg=fg_color, highlightthickness=0
        ).pack(fill="x", pady=(0, 15))

        # Alarma Sonora
        tk.Label(container, text="ALARMA SONORA", font=("Segoe UI", 9, "bold"), bg=bg_color, fg=fg_color).pack(
            anchor="w"
        )
        tk.Checkbutton(
            container, text="Activar sonido en caídas", variable=self.sonido_activado, bg=bg_color, fg=fg_color, selectcolor=bg_stats, activebackground=bg_color
        ).pack(anchor="w")

        # Inicio Automático
        if WINDOWS_REGISTRY:
            tk.Checkbutton(
                container,
                text="Iniciar con el sistema (Windows)",
                variable=self.inicio_automatico,
                bg=bg_color,
                fg=fg_color,
                selectcolor=bg_stats,
                activebackground=bg_color
            ).pack(anchor="w")

        # Servidor Web
        tk.Label(container, text="SERVIDOR WEB DASHBOARD", font=("Segoe UI", 9, "bold"), bg=bg_color, fg=fg_color).pack(
            anchor="w", pady=(10, 0)
        )
        tk.Checkbutton(
            container, text="Activar servidor web", variable=self.web_activo, bg=bg_color, fg=fg_color, selectcolor=bg_stats, activebackground=bg_color
        ).pack(anchor="w")
        
        frame_puerto = tk.Frame(container, bg=bg_color)
        frame_puerto.pack(fill="x")
        tk.Label(frame_puerto, text="Puerto:", font=("Segoe UI", 9), bg=bg_color, fg=fg_color).pack(side="left")
        tk.Entry(frame_puerto, textvariable=self.web_puerto, width=10, bg=bg_stats, fg=fg_color, insertbackground=fg_color).pack(side="left", padx=5)

        # Selector de MP3
        tk.Label(
            container,
            text="Seleccionar archivo MP3 (Carpeta /alarmas):",
            font=("Segoe UI", 8),
            bg=bg_color,
            fg=fg_color
        ).pack(anchor="w", pady=(5, 0))
        alarmas_disponibles = self.obtener_lista_alarmas()
        combo_alarma = ttk.Combobox(
            container,
            textvariable=self.archivo_alarma,
            values=alarmas_disponibles,
            state="readonly",
        )
        combo_alarma.pack(fill="x", pady=(0, 10))

        tk.Button(
            container,
            text="🔊 Probar Sonido Seleccionado",
            command=self.probar_sonido,
            bg=bg_stats,
            fg=fg_color
        ).pack(fill="x", pady=5)
        tk.Button(
            container,
            text="⏹ Detener Sonido",
            command=self.detener_sonido,
            bg="#f8d7da" if not oscuro else "#4a1212",
            fg="black" if not oscuro else "white"
        ).pack(fill="x", pady=5)
        tk.Button(
            container,
            text="🔔 Enviar Mensaje de Prueba",
            command=self.probar_telegram,
            bg="#0088cc",
            fg="white",
        ).pack(fill="x", pady=5)

        tk.Button(
            container,
            text="GUARDAR CAMBIOS",
            command=lambda: [self.guardar_configuracion(), config_win.destroy()],
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            pady=8,
        ).pack(fill="x", pady=(20, 0))

    def mostrar_manual(self):
        manual_win = tk.Toplevel(self.root)
        manual_win.title("Manual de Uso - Monitor Web")
        manual_win.geometry("550x650")

        texto_manual = """
📖 MANUAL DE USO RÁPIDO v5.1

1. GESTIÓN DE SITIOS:
- Ingrese la URL completa y pulse 'Añadir'.

2. DASHBOARD WEB (¡Nuevo!):
- Active el servidor en 'Configuración'.
- Acceda desde su navegador a http://localhost:PUERTO (por defecto 5000).
- Permite monitoreo remoto con gráficas interactivas.
- Haga clic en el nombre de un sitio para ver su análisis detallado.

3. GRÁFICAS INTERACTIVAS (¡Nuevo!):
- Use la LUPA para hacer zoom en periodos específicos.
- Use la CRUZ (Pan) para desplazarse por el historial.
- El botón de la CASA vuelve a la vista original.

4. ALARMAS MP3:
- Guarde archivos .mp3 en la carpeta '/alarmas'.
- Seleccione su sonido favorito en 'Configuración'.

5. HISTORIAL PERSISTENTE:
- Doble clic en cualquier sitio de la tabla para ver su análisis detallado.
- Los datos se guardan automáticamente en 'historial.json'.

6. CONFIGURACIÓN (⚙️):
- Ajuste el intervalo de escaneo, alertas de Telegram y puerto web.
        """
        txt_area = scrolledtext.ScrolledText(
            manual_win, wrap=tk.WORD, font=("Segoe UI", 10), padx=10, pady=10
        )
        txt_area.insert(tk.INSERT, texto_manual)
        txt_area.config(state=tk.DISABLED)
        txt_area.pack(fill="both", expand=True)
        tk.Button(
            manual_win, text="Entendido", command=manual_win.destroy, pady=5
        ).pack(fill="x")

    def probar_sonido(self):
        self.reproducir_alarma()

    def detener_sonido(self):
        """Detiene la reproducción de música de pygame."""
        try:
            pygame.mixer.music.stop()
        except Exception as e:
            logging.error(f"Error al detener sonido: {e}")

    # --- LÓGICA DE PERSISTENCIA ---
    def cargar_configuracion(self):
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, "r") as f:
                    conf = json.load(f)
                    self.token_tg.set(conf.get("token", ""))
                    self.id_tg.set(conf.get("id", ""))
                    self.intervalo.set(conf.get("intervalo", 60))
                    self.sonido_activado.set(conf.get("sonido", True))
                    self.inicio_automatico.set(conf.get("inicio_automatico", False))
                    self.modo_oscuro.set(conf.get("modo_oscuro", False))
                    self.archivo_alarma.set(conf.get("archivo_alarma", "Ninguno"))
                    self.web_activo.set(conf.get("web_activo", False))
                    self.web_puerto.set(conf.get("web_puerto", 5000))
            except:
                pass

    def guardar_configuracion(self):
        # Guardar estado previo para ver si cambió el servidor web
        web_previo = False
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, "r") as f:
                    web_previo = json.load(f).get("web_activo", False)
            except: pass

        conf = {
            "token": self.token_tg.get(),
            "id": self.id_tg.get(),
            "intervalo": self.intervalo.get(),
            "sonido": self.sonido_activado.get(),
            "inicio_automatico": self.inicio_automatico.get(),
            "modo_oscuro": self.modo_oscuro.get(),
            "archivo_alarma": self.archivo_alarma.get(),
            "web_activo": self.web_activo.get(),
            "web_puerto": self.web_puerto.get(),
        }
        with open(ARCHIVO_CONFIG, "w") as f:
            json.dump(conf, f)

        if WINDOWS_REGISTRY:
            self.actualizar_inicio_automatico()
            
        # Si se activó el web server y antes estaba apagado, iniciarlo
        if self.web_activo.get() and not web_previo:
            self.iniciar_servidor_web()
        elif not self.web_activo.get() and web_previo:
            messagebox.showinfo("Aviso", "El servidor web se desactivará al reiniciar la aplicación.")

    def actualizar_inicio_automatico(self):
        """Gestiona la entrada del registro para el inicio con Windows."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "MonitorWebPro"
        # Usar pythonw.exe si está disponible para evitar la ventana de consola
        script_path = os.path.abspath(sys.argv[0])
        executable = sys.executable.lower().replace("python.exe", "pythonw.exe")
        command = f'"{executable}" "{script_path}"'

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            )
            if self.inicio_automatico.get():
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
                logging.info("Inicio automático activado en el registro.")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logging.info("Inicio automático desactivado del registro.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logging.error(f"Error al configurar inicio automático: {e}")

    def cargar_sitios_desde_archivo(self):
        if os.path.exists(ARCHIVO_SITIOS):
            with open(ARCHIVO_SITIOS, "r") as f:
                for linea in f.read().splitlines():
                    linea = linea.strip()
                    if not linea:
                        continue

                    if "	" in linea:
                        url, comentario = linea.split("	", 1)
                    else:
                        url, comentario = linea, ""

                    url = url.strip()
                    comentario = comentario.strip()
                    if url:
                        self.sitios[url] = {
                            "comentario": comentario,
                            "estado": "UP",
                            "checks": 0,
                            "fails": 0,
                            "historial": [],
                        }
                        self.tree.insert(
                            "",
                            "end",
                            iid=url,
                            values=(url, comentario, "PENDIENTE", "-", "100%", "-"),
                        )

    def cargar_historial_persistente(self):
        if os.path.exists(ARCHIVO_HISTORIAL):
            try:
                with open(ARCHIVO_HISTORIAL, "r") as f:
                    data_hist = json.load(f)
                    for url, info in data_hist.items():
                        if url in self.sitios:
                            self.sitios[url]["historial"] = info.get("historial", [])
                            self.sitios[url]["checks"] = info.get("checks", 0)
                            self.sitios[url]["fails"] = info.get("fails", 0)
                logging.info("Historial persistente cargado.")
            except Exception as e:
                logging.error(f"Error cargando historial: {e}")

    def guardar_historial_persistente(self):
        try:
            data_to_save = {}
            for url, info in self.sitios.items():
                hist_serializable = []
                for h in info["historial"]:
                    item = h.copy()
                    if isinstance(item["hora"], datetime):
                        item["hora"] = item["hora"].isoformat()
                    hist_serializable.append(item)

                data_to_save[url] = {
                    "checks": info["checks"],
                    "fails": info["fails"],
                    "historial": hist_serializable,
                }

            with open(ARCHIVO_HISTORIAL, "w") as f:
                json.dump(data_to_save, f)
        except Exception as e:
            logging.error(f"Error guardando historial: {e}")

    def guardar_sitios_en_archivo(self):
        with open(ARCHIVO_SITIOS, "w") as f:
            for url, info in self.sitios.items():
                comentario = info.get("comentario", "").replace("\n", " ").strip()
                f.write(f"{url}	{comentario}\n")

    def agregar_sitio(self):
        url = self.entry_url.get().strip()
        comentario = self.entry_comentario.get().strip()
        if url and url not in self.sitios:
            self.sitios[url] = {
                "comentario": comentario,
                "estado": "UP",
                "checks": 0,
                "fails": 0,
                "historial": [],
            }
            self.tree.insert(
                "", "end", iid=url, values=(url, comentario, "PENDIENTE", "-", "100%", "-")
            )
            self.guardar_sitios_en_archivo()
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, "https://")
            self.entry_comentario.delete(0, tk.END)

    def eliminar_sitio(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Eliminar sitio", "Selecciona al menos una URL para eliminar.")
            return
        cantidad = len(selected)
        mensaje = f"Vas a eliminar {cantidad} URL(s). Esta accion no se puede deshacer.\n\nDeseas continuar?"
        if not messagebox.askyesno("Confirmar eliminacion", mensaje):
            return

        for item in selected:
            del self.sitios[item]
            self.tree.delete(item)
        self.guardar_sitios_en_archivo()
        self.guardar_historial_persistente()

    def editar_comentario_sitio(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(
                "Editar comentario", "Seleccion? una URL para editar su comentario."
            )
            return
        if len(selected) > 1:
            messagebox.showwarning(
                "Editar comentario", "Seleccion? solo una URL a la vez."
            )
            return

        url = selected[0]
        if url not in self.sitios:
            return

        comentario_actual = self.sitios[url].get("comentario", "")
        nuevo_comentario = simpledialog.askstring(
            "Editar comentario",
            f"Comentario para:\n{url}",
            initialvalue=comentario_actual,
            parent=self.root,
        )
        if nuevo_comentario is None:
            return

        nuevo_comentario = nuevo_comentario.strip()
        self.sitios[url]["comentario"] = nuevo_comentario

        valores = list(self.tree.item(url, "values"))
        if len(valores) == 6:
            valores[1] = nuevo_comentario
            self.tree.item(url, values=tuple(valores))

        self.guardar_sitios_en_archivo()

    def enviar_telegram(self, mensaje):
        token = self.token_tg.get()
        chat_id = self.id_tg.get()
        if not token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            r = requests.post(
                url,
                json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
                timeout=5,
            )
            return r.status_code == 200
        except:
            return False

    def probar_telegram(self):
        if self.enviar_telegram("🔔 Prueba de conexión OK."):
            messagebox.showinfo("OK", "Mensaje enviado.")
        else:
            messagebox.showerror("Error", "Error al enviar mensaje.")

    def verificar_web(self, url):
        try:
            inicio = time.time()
            r = requests.get(url, timeout=10, headers={"User-Agent": "MonitorPro/5.0"})
            latencia = int((time.time() - inicio) * 1000)
            return (
                r.status_code == 200,
                latencia,
                "ONLINE" if r.status_code == 200 else f"Error {r.status_code}",
            )
        except:
            return False, 0, "Error"

    def ciclo_monitoreo(self):
        while self.monitoreando:
            if not self.sitios:
                time.sleep(1)
                continue

            sitios_online = 0
            ahora = datetime.now()
            ahora_str = ahora.strftime("%H:%M:%S")

            for url in list(self.sitios.keys()):
                online, latencia, status_desc = self.verificar_web(url)

                self.sitios[url]["checks"] += 1
                if not online:
                    self.sitios[url]["fails"] += 1
                else:
                    sitios_online += 1

                self.sitios[url]["historial"].append(
                    {"hora": ahora, "latencia": latencia, "online": online}
                )
                if len(self.sitios[url]["historial"]) > 500:
                    self.sitios[url]["historial"].pop(0)

                uptime = (
                    (self.sitios[url]["checks"] - self.sitios[url]["fails"])
                    / self.sitios[url]["checks"]
                ) * 100

                estado_previo = self.sitios[url]["estado"]
                if online and estado_previo == "DOWN":
                    self.enviar_telegram(f"✅ <b>RECUPERADO:</b> {url}")
                    self.sitios[url]["estado"] = "UP"
                elif not online and estado_previo == "UP":
                    self.reproducir_alarma()
                    self.enviar_telegram(
                        f"🚨 <b>CAÍDO:</b> {url}\nMotivo: {status_desc}"
                    )
                    self.sitios[url]["estado"] = "DOWN"

                self.root.after(
                    0,
                    self.update_table_row,
                    url,
                    status_desc,
                    latencia,
                    f"{uptime:.1f}%",
                    ahora_str,
                )

            self.guardar_historial_persistente()

            total = len(self.sitios)
            porcentaje = (sitios_online / total * 100) if total > 0 else 0
            self.root.after(0, self.actualizar_grafica, porcentaje)

            try:
                t_wait = self.intervalo.get()
            except:
                t_wait = 60
            for _ in range(t_wait):
                if not self.monitoreando:
                    break
                time.sleep(1)

    def update_table_row(self, url, status, lat, uptime, time_str):
        if url in self.sitios:
            lat_s = f"{lat}ms" if lat > 0 else "-"
            comentario = self.sitios[url].get("comentario", "")
            self.tree.item(url, values=(url, comentario, status, lat_s, uptime, time_str))

    def actualizar_grafica(self, porcentaje):
        self.datos_tiempo.append(datetime.now())
        self.datos_porcentaje.append(porcentaje)
        if len(self.datos_tiempo) > 500:
            self.datos_tiempo.pop(0)
            self.datos_porcentaje.pop(0)
        
        oscuro = self.modo_oscuro.get()
        color_linea = "#007bff"
        color_texto = "white" if oscuro else "black"
        color_bg = "#1e1e1e" if oscuro else "#f8f9fa"
        color_ax = "#2d2d2d" if oscuro else "white"

        self.ax.clear()
        self.ax.set_title("Salud Global del Ecosistema (% Online)", color=color_texto)
        self.ax.set_ylim(-5, 105)
        self.ax.plot(
            self.datos_tiempo,
            self.datos_porcentaje,
            color=color_linea,
            linewidth=2,
            marker="o",
            markersize=3,
        )
        self.ax.fill_between(
            self.datos_tiempo, self.datos_porcentaje, color=color_linea, alpha=0.1
        )
        
        self.ax.set_facecolor(color_ax)
        self.fig.set_facecolor(color_bg)
        self.ax.tick_params(colors=color_texto)
        for spine in self.ax.spines.values():
            spine.set_color(color_texto)

        self.fig.autofmt_xdate()
        self.canvas.draw()

    def toggle_tema(self):
        self.modo_oscuro.set(not self.modo_oscuro.get())
        self.aplicar_tema()
        self.guardar_configuracion()

    def aplicar_tema(self):
        oscuro = self.modo_oscuro.get()
        
        # Colores
        bg_main = "#1e1e1e" if oscuro else "#f8f9fa"
        fg_main = "#ffffff" if oscuro else "#000000"
        bg_card = "#2d2d2d" if oscuro else "#ffffff"
        bg_top = "#252526" if oscuro else "#ffffff"
        fg_secundario = "#cccccc" if oscuro else "#6c757d"
        
        self.root.configure(bg=bg_main)
        
        # Actualizar botón de tema
        self.btn_tema.config(
            text="☀️ Modo Claro" if oscuro else "🌙 Modo Oscuro",
            bg=bg_top,
            fg=fg_main
        )

        # Buscar y actualizar Frames, Labels y otros widgets estándar recursivamente
        def actualizar_recursivo(widget):
            name = widget.winfo_class()
            if name == "Frame":
                # Si el frame es la barra superior o el cuerpo
                if widget.master == self.root:
                    widget.configure(bg=bg_top if "!padx20" not in str(widget) else bg_main)
                else:
                    widget.configure(bg=bg_top if widget.cget("bg") == "#ffffff" else bg_main)
            elif name == "Label":
                # No cambiar color si es un badge o tiene colores específicos
                curr_bg = widget.cget("bg")
                if curr_bg in ["#ffffff", "#f8f9fa"]:
                    widget.configure(bg=bg_top if curr_bg == "#ffffff" else bg_main, fg=fg_main)
                elif curr_bg == "#f8f9fa" or widget.cget("fg") == "#6c757d":
                    widget.configure(bg=bg_main, fg=fg_secundario)
            
            for child in widget.winfo_children():
                actualizar_recursivo(child)

        # Estilo para Treeview (ttk)
        style = ttk.Style()
        if oscuro:
            style.configure("Treeview", background="#2d2d2d", foreground="white", fieldbackground="#2d2d2d")
            style.configure("Treeview.Heading", background="#333333", foreground="white")
            # Forzar colores en Treeview es complejo en clam, a veces es mejor cambiar el tema o configurar mas a fondo
        else:
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
            style.configure("Treeview.Heading", background="#e1e1e1", foreground="black")

        # Intentar aplicar a widgets principales directamente para mayor seguridad
        for child in self.root.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=bg_top if child.cget("bg") in ["#ffffff", "#f8f9fa"] else bg_main)
                for sub in child.winfo_children():
                    if isinstance(sub, tk.Label):
                        if sub.cget("bg") in ["#ffffff", "#f8f9fa"]:
                            sub.configure(bg=child.cget("bg"), fg=fg_main)
                        elif sub.cget("fg") == "#6c757d":
                            sub.configure(bg=child.cget("bg"), fg=fg_secundario)
                    elif isinstance(sub, tk.Entry):
                        sub.configure(bg="#3d3d3d" if oscuro else "white", fg=fg_main, insertbackground=fg_main)

        # Actualizar gráfica si hay datos
        if self.datos_porcentaje:
            self.actualizar_grafica(self.datos_porcentaje[-1])
        else:
            # Si no hay datos, solo limpiar con colores correctos
            color_bg = "#1e1e1e" if oscuro else "#f8f9fa"
            color_ax = "#2d2d2d" if oscuro else "white"
            color_texto = "white" if oscuro else "black"
            self.ax.set_facecolor(color_ax)
            self.fig.set_facecolor(color_bg)
            self.ax.tick_params(colors=color_texto)
            for spine in self.ax.spines.values():
                spine.set_color(color_texto)
            self.canvas.draw()

    def toggle_monitor(self):
        if not self.monitoreando:
            if not self.sitios:
                return
            self.monitoreando = True
            self.btn_start.config(text="⏹ DETENER MONITOREO", bg="#dc3545")
            threading.Thread(target=self.ciclo_monitoreo, daemon=True).start()
        else:
            self.monitoreando = False
            self.btn_start.config(text="▶ INICIAR MONITOREO", bg="#28a745")

    def create_tray_icon(self):
        image = Image.new("RGB", (64, 64), (40, 167, 69))
        dc = ImageDraw.Draw(image)
        dc.ellipse((10, 10, 54, 54), fill=(255, 255, 255))
        return image

    def setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar", self.show_window),
            pystray.MenuItem("Salir", self.quit_app),
        )
        self.icon = pystray.Icon(
            "monitor", self.create_tray_icon(), "Monitor Web", menu
        )
        threading.Thread(target=self.icon.run, daemon=True).start()

    def hide_window(self):
        if self.monitoreando:
            self.root.withdraw()
        else:
            self.quit_app()

    def show_window(self):
        self.root.after(0, self.root.deiconify)

    def quit_app(self):
        self.monitoreando = False
        self.guardar_historial_persistente()
        if TRAY_SUPPORT:
            self.icon.stop()
        self.root.quit()

    # --- SERVIDOR WEB ---
    def iniciar_servidor_web(self):
        """Inicia el servidor Flask en un hilo separado si está activado."""
        if not FLASK_SUPPORT or not self.web_activo.get():
            return

        threading.Thread(target=self.run_flask, daemon=True).start()
        logging.info(f"Servidor web iniciado en puerto {self.web_puerto.get()}")

    def run_flask(self):
        app = Flask(__name__)

        @app.route("/")
        def index():
            total = len(self.sitios)
            online = sum(1 for s in self.sitios.values() if s["estado"] == "UP")
            salud = (online / total * 100) if total > 0 else 0
            
            # Preparar datos para la gráfica global
            labels = [t.strftime("%H:%M:%S") for t in self.datos_tiempo]
            values = self.datos_porcentaje

            return render_template_string(
                WEB_TEMPLATE,
                sitios=self.sitios,
                global_health=f"{salud:.1f}",
                global_labels=json.dumps(labels),
                global_values=json.dumps(values),
                ahora=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        @app.route("/site/<path:url>")
        def site_detail(url):
            data = self.sitios.get(url)
            if not data:
                return "Sitio no encontrado", 404
            
            # Preparar datos del historial
            labels = []
            latencias = []
            estados = []
            
            for h in data["historial"]:
                hora = h["hora"]
                if isinstance(hora, str):
                    hora_obj = datetime.fromisoformat(hora)
                else:
                    hora_obj = hora
                
                labels.append(hora_obj.strftime("%H:%M:%S"))
                latencias.append(h["latencia"])
                estados.append(1 if h["online"] else 0)
            
            uptime = ((data["checks"] - data["fails"]) / data["checks"] * 100) if data["checks"] > 0 else 100
            
            return render_template_string(
                DETALLE_WEB_TEMPLATE,
                url=url,
                data=data,
                uptime=uptime,
                labels=json.dumps(labels),
                latencias=json.dumps(latencias),
                estados=json.dumps(estados)
            )

        @app.route("/api/data")
        def get_data():
            # Limpiar datos para JSON (quitar objetos datetime)
            data_clean = {}
            for url, info in self.sitios.items():
                data_clean[url] = info.copy()
                hist_clean = []
                for h in info["historial"]:
                    item = h.copy()
                    if isinstance(item["hora"], datetime):
                        item["hora"] = item["hora"].isoformat()
                    hist_clean.append(item)
                data_clean[url]["historial"] = hist_clean
            return jsonify(data_clean)

        try:
            app.run(host="0.0.0.0", port=self.web_puerto.get(), debug=False, use_reloader=False)
        except Exception as e:
            logging.error(f"Error en servidor web: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MonitorApp(root)
    root.mainloop()

