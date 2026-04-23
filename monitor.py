import json
import logging
import os
import sys
import threading
import time
import tkinter as tk
import winsound  # Para alertas sonoras de respaldo
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

import matplotlib.pyplot as plt
import pygame  # Para reproducir MP3
import requests
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
        self.sitios = {}  # {url: {estado, checks, fails, historial: []}}

        # Variables de configuración (Persistentes)
        self.token_tg = tk.StringVar()
        self.id_tg = tk.StringVar()
        self.intervalo = tk.IntVar(value=60)
        self.sonido_activado = tk.BooleanVar(value=True)
        self.inicio_automatico = tk.BooleanVar(value=False)
        self.archivo_alarma = tk.StringVar(value="Ninguno")

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
            top_bar, text="❓ Ayuda", command=self.mostrar_manual, bg="#f8f9fa", padx=10
        ).pack(side="right", padx=5)
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
        columns = ("url", "status", "latency", "uptime", "last_check")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", height=8)
        self.tree.heading("url", text="URL del Sitio")
        self.tree.heading("status", text="Estado")
        self.tree.heading("latency", text="Latencia")
        self.tree.heading("uptime", text="Uptime %")
        self.tree.heading("last_check", text="Visto")

        self.tree.column("url", width=350)
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
        self.canvas = FigureCanvasTkAgg(self.fig, master=body)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)

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

        det_win = tk.Toplevel(self.root)
        det_win.title(f"Detalle: {url}")
        det_win.geometry("700x650")
        det_win.configure(bg="white")

        tk.Label(
            det_win,
            text=f"Análisis de {url}",
            font=("Segoe UI", 14, "bold"),
            bg="white",
            pady=10,
        ).pack()

        # Frame para gráficas
        graph_frame = tk.Frame(det_win, bg="white")
        graph_frame.pack(fill="both", expand=True, padx=10, pady=10)

        fig_det, (ax_lat, ax_status) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
        fig_det.subplots_adjust(hspace=0.4)

        historia = data.get("historial", [])
        if not historia:
            tk.Label(
                graph_frame, text="No hay datos suficientes para graficar.", bg="white"
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
        ax_lat.set_title("Latencia de Respuesta (ms)")
        ax_lat.grid(True, alpha=0.3)
        ax_lat.set_ylabel("ms")

        ax_status.step(tiempos, estados, where="post", color="#2ca02c", label="Estado")
        ax_status.set_title("Disponibilidad (1=Online, 0=Offline)")
        ax_status.set_ylim(-0.2, 1.2)
        ax_status.set_yticks([0, 1])
        ax_status.set_yticklabels(["CAÍDO", "OK"])
        ax_status.grid(True, alpha=0.3)

        fig_det.autofmt_xdate()
        canvas_det = FigureCanvasTkAgg(fig_det, master=graph_frame)
        canvas_det.get_tk_widget().pack(fill="both", expand=True)

        total_checks = data["checks"]
        fails = data["fails"]
        uptime_val = (
            ((total_checks - fails) / total_checks * 100) if total_checks > 0 else 100
        )

        stats_frame = tk.Frame(det_win, bg="#f8f9fa", pady=10)
        stats_frame.pack(fill="x")

        info_str = f"Muestras: {len(historia)} | Fallos Totales: {fails} | Uptime Global: {uptime_val:.2f}%"
        tk.Label(
            stats_frame, text=info_str, font=("Segoe UI", 10, "bold"), bg="#f8f9fa"
        ).pack()

    def abrir_configuracion(self):
        config_win = tk.Toplevel(self.root)
        config_win.title("Ajustes del Monitor")
        config_win.geometry("450x550")
        config_win.resizable(False, False)
        config_win.transient(self.root)
        config_win.grab_set()

        container = tk.Frame(config_win, padx=20, pady=20)
        container.pack(fill="both", expand=True)

        # Telegram
        tk.Label(
            container, text="TOKEN DE TELEGRAM", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")
        tk.Entry(container, textvariable=self.token_tg, width=40, show="*").pack(
            pady=(0, 15)
        )

        tk.Label(container, text="CHAT ID", font=("Segoe UI", 9, "bold")).pack(
            anchor="w"
        )
        tk.Entry(container, textvariable=self.id_tg, width=40).pack(pady=(0, 15))

        # Intervalo
        tk.Label(
            container,
            text="INTERVALO DE CHEQUEO (Segundos)",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Scale(
            container, from_=10, to=300, orient="horizontal", variable=self.intervalo
        ).pack(fill="x", pady=(0, 15))

        # Alarma Sonora
        tk.Label(container, text="ALARMA SONORA", font=("Segoe UI", 9, "bold")).pack(
            anchor="w"
        )
        tk.Checkbutton(
            container, text="Activar sonido en caídas", variable=self.sonido_activado
        ).pack(anchor="w")

        # Inicio Automático
        if WINDOWS_REGISTRY:
            tk.Checkbutton(
                container,
                text="Iniciar con el sistema (Windows)",
                variable=self.inicio_automatico,
            ).pack(anchor="w")


        # Selector de MP3
        tk.Label(
            container,
            text="Seleccionar archivo MP3 (Carpeta /alarmas):",
            font=("Segoe UI", 8),
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
            bg="#e9ecef",
        ).pack(fill="x", pady=5)
        tk.Button(
            container,
            text="⏹ Detener Sonido",
            command=self.detener_sonido,
            bg="#f8d7da",
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
📖 MANUAL DE USO RÁPIDO v5.0

1. GESTIÓN DE SITIOS:
- Ingrese la URL completa y pulse 'Añadir'.

2. ALARMAS MP3 (¡Nuevo!):
- Cree una carpeta llamada 'alarmas' en el mismo directorio del script.
- Guarde sus archivos .mp3 allí.
- En 'Configuración', elija su sonido favorito.
- Si no hay archivos MP3, el programa usará un pitido de alerta por defecto.

3. HISTORIAL PERSISTENTE:
- Los datos de las gráficas se guardan en 'historial.json'.
- Doble clic en la tabla para ver el detalle de un sitio.

4. CONFIGURACIÓN (⚙️):
- Configure Telegram para alertas remotas.
- Ajuste el intervalo de escaneo.

5. ARCHIVOS:
- 'elsitio.log': Registros de eventos.
- 'config.json': Sus ajustes y tokens.
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
                    self.archivo_alarma.set(conf.get("archivo_alarma", "Ninguno"))
            except:
                pass

    def guardar_configuracion(self):
        conf = {
            "token": self.token_tg.get(),
            "id": self.id_tg.get(),
            "intervalo": self.intervalo.get(),
            "sonido": self.sonido_activado.get(),
            "inicio_automatico": self.inicio_automatico.get(),
            "archivo_alarma": self.archivo_alarma.get(),
        }
        with open(ARCHIVO_CONFIG, "w") as f:
            json.dump(conf, f)

        if WINDOWS_REGISTRY:
            self.actualizar_inicio_automatico()

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
                for url in f.read().splitlines():
                    url = url.strip()
                    if url:
                        self.sitios[url] = {
                            "estado": "UP",
                            "checks": 0,
                            "fails": 0,
                            "historial": [],
                        }
                        self.tree.insert(
                            "",
                            "end",
                            iid=url,
                            values=(url, "PENDIENTE", "-", "100%", "-"),
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
            for url in self.sitios.keys():
                f.write(f"{url}\n")

    def agregar_sitio(self):
        url = self.entry_url.get().strip()
        if url and url not in self.sitios:
            self.sitios[url] = {
                "estado": "UP",
                "checks": 0,
                "fails": 0,
                "historial": [],
            }
            self.tree.insert(
                "", "end", iid=url, values=(url, "PENDIENTE", "-", "100%", "-")
            )
            self.guardar_sitios_en_archivo()
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, "https://")

    def eliminar_sitio(self):
        selected = self.tree.selection()
        if selected:
            for item in selected:
                del self.sitios[item]
                self.tree.delete(item)
            self.guardar_sitios_en_archivo()
            self.guardar_historial_persistente()

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
                if len(self.sitios[url]["historial"]) > 100:
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
            self.tree.item(url, values=(url, status, lat_s, uptime, time_str))

    def actualizar_grafica(self, porcentaje):
        self.datos_tiempo.append(datetime.now())
        self.datos_porcentaje.append(porcentaje)
        if len(self.datos_tiempo) > 30:
            self.datos_tiempo.pop(0)
            self.datos_porcentaje.pop(0)
        self.ax.clear()
        self.ax.set_title("Salud Global del Ecosistema (% Online)")
        self.ax.set_ylim(-5, 105)
        self.ax.plot(
            self.datos_tiempo,
            self.datos_porcentaje,
            color="#007bff",
            linewidth=2,
            marker="o",
            markersize=3,
        )
        self.ax.fill_between(
            self.datos_tiempo, self.datos_porcentaje, color="#007bff", alpha=0.1
        )
        self.fig.autofmt_xdate()
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


if __name__ == "__main__":
    root = tk.Tk()
    app = MonitorApp(root)
    root.mainloop()
