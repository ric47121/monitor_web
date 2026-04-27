import json
import os
import time
import requests
import threading
import logging
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.text import Text
from rich.align import Align
import pygame

# --- CONFIGURACIÓN COMPARTIDA ---
ARCHIVO_SITIOS = "sitios.txt"
ARCHIVO_CONFIG = "config.json"
ARCHIVO_HISTORIAL = "historial.json"
CARPETA_ALARMAS = "alarmas"

# Configuración de Logging básica para errores internos
logging.basicConfig(filename='elsitio.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

pygame.mixer.init()
console = Console()

class MonitorTUI:
    def __init__(self):
        self.sitios = {}
        self.config = {
            "intervalo": 60,
            "sonido": True,
            "archivo_alarma": "Ninguno",
            "token": "",
            "id": "",
            "web_activo": False,
            "web_puerto": 5000
        }
        self.logs = []
        self.historial_global = []
        self.corriendo = True
        self.cargar_config()
        self.cargar_sitios()
        self.cargar_historial()

    def cargar_config(self):
        if os.path.exists(ARCHIVO_CONFIG):
            try:
                with open(ARCHIVO_CONFIG, "r") as f:
                    self.config.update(json.load(f))
            except Exception as e:
                logging.error(f"Error cargando config: {e}")

    def cargar_sitios(self):
        if os.path.exists(ARCHIVO_SITIOS):
            try:
                with open(ARCHIVO_SITIOS, "r") as f:
                    for linea in f:
                        linea = linea.strip()
                        if not linea: continue
                        if "\t" in linea:
                            url, desc = linea.split("\t", 1)
                        else:
                            url, desc = linea, ""
                        if url:
                            self.sitios[url] = {
                                "desc": desc,
                                "estado": "PENDIENTE",
                                "latencia": 0,
                                "checks": 0,
                                "fails": 0,
                                "ultimo": "-",
                                "historial": []
                            }
            except Exception as e:
                logging.error(f"Error cargando sitios: {e}")

    def cargar_historial(self):
        if os.path.exists(ARCHIVO_HISTORIAL):
            try:
                with open(ARCHIVO_HISTORIAL, "r") as f:
                    data = json.load(f)
                    for url, info in data.items():
                        if url in self.sitios:
                            self.sitios[url]["checks"] = info.get("checks", 0)
                            self.sitios[url]["fails"] = info.get("fails", 0)
                            self.sitios[url]["historial"] = info.get("historial", [])[-500:]
            except Exception as e:
                logging.error(f"Error cargando historial: {e}")

    def guardar_historial(self):
        try:
            data = {}
            for url, info in self.sitios.items():
                data[url] = {
                    "checks": info["checks"],
                    "fails": info["fails"],
                    "historial": info["historial"][-500:]
                }
            with open(ARCHIVO_HISTORIAL, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logging.error(f"Error guardando historial: {e}")

    def registrar_log(self, mensaje, estilo="white"):
        hora = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{estilo}][{hora}] {mensaje}[/]")
        if len(self.logs) > 15:
            self.logs.pop(0)

    def reproducir_alarma(self):
        if not self.config.get("sonido", True):
            return
        archivo = self.config.get("archivo_alarma", "Ninguno")
        ruta = os.path.join(CARPETA_ALARMAS, archivo)
        if archivo != "Ninguno" and os.path.exists(ruta):
            try:
                pygame.mixer.music.load(ruta)
                pygame.mixer.music.play()
            except Exception as e:
                logging.error(f"Error reproduciendo alarma: {e}")

    def enviar_telegram(self, mensaje):
        token = self.config.get("token")
        chat_id = self.config.get("id")
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            try:
                requests.post(url, json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"}, timeout=5)
            except Exception as e:
                logging.error(f"Error enviando Telegram: {e}")

    def verificar_sitio(self, url):
        try:
            inicio = time.time()
            r = requests.get(url, timeout=10, headers={"User-Agent": "MonitorProTUI/5.1"})
            latencia = int((time.time() - inicio) * 1000)
            return r.status_code == 200, latencia, f"HTTP {r.status_code}"
        except Exception as e:
            return False, 0, str(e)

    def ciclo_monitoreo(self):
        while self.corriendo:
            sitios_online = 0
            for url in self.sitios:
                online, lat, status_desc = self.verificar_sitio(url)
                self.sitios[url]["checks"] += 1
                
                estado_anterior = self.sitios[url]["estado"]
                nuevo_estado = "UP" if online else "DOWN"
                
                if online:
                    sitios_online += 1
                    self.sitios[url]["latencia"] = lat
                else:
                    self.sitios[url]["fails"] += 1
                
                self.sitios[url]["estado"] = nuevo_estado
                self.sitios[url]["ultimo"] = datetime.now().strftime("%H:%M:%S")
                
                # Guardar en historial local
                self.sitios[url]["historial"].append({
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "latencia": lat if online else 0,
                    "estado": nuevo_estado
                })
                if len(self.sitios[url]["historial"]) > 500:
                    self.sitios[url]["historial"].pop(0)

                # Alertas
                if nuevo_estado == "DOWN" and estado_anterior != "DOWN":
                    self.registrar_log(f"FALLO: {url} ({status_desc})", "bold red")
                    self.reproducir_alarma()
                    self.enviar_telegram(f"🚨 <b>CAÍDO:</b> {url}\nDetalle: {status_desc}")
                elif nuevo_estado == "UP" and estado_anterior == "DOWN":
                    self.registrar_log(f"RECUPERADO: {url}", "bold green")
                    self.enviar_telegram(f"✅ <b>RECUPERADO:</b> {url}")

            total = len(self.sitios)
            salud = (sitios_online / total * 100) if total > 0 else 0
            self.historial_global.append(salud)
            if len(self.historial_global) > 100: self.historial_global.pop(0)
            
            self.guardar_historial()
            time.sleep(self.config.get("intervalo", 60))

    def run_flask(self):
        app = Flask(__name__)
        
        @app.route("/")
        def index():
            return render_template_string("""
                <html>
                <head>
                    <title>Dashboard TUI</title>
                    <meta http-equiv="refresh" content="30">
                    <style>
                        body { font-family: sans-serif; background: #1a1a1a; color: white; padding: 20px; }
                        table { width: 100%; border-collapse: collapse; }
                        th, td { padding: 10px; border: 1px solid #444; text-align: left; }
                        th { background: #333; }
                        .UP { color: #4caf50; font-weight: bold; }
                        .DOWN { color: #f44336; font-weight: bold; }
                    </style>
                </head>
                <body>
                    <h1>Monitor de Sitios Web Pro - Dashboard</h1>
                    <table>
                        <tr><th>URL</th><th>Estado</th><th>Latencia</th><th>Último Check</th></tr>
                        {% for url, data in sitios.items() %}
                        <tr>
                            <td>{{ url }}</td>
                            <td class="{{ data.estado }}">{{ data.estado }}</td>
                            <td>{{ data.latencia }}ms</td>
                            <td>{{ data.ultimo }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                </body>
                </html>
            """, sitios=self.sitios)

        @app.route("/api/status")
        def api_status():
            return jsonify(self.sitios)

        try:
            app.run(host="0.0.0.0", port=self.config.get("web_puerto", 5000), debug=False, use_reloader=False)
        except Exception as e:
            logging.error(f"Error en servidor Flask: {e}")

    def generar_tabla(self):
        tabla = Table(expand=True, border_style="blue", show_header=True, header_style="bold magenta")
        tabla.add_column("Sitio Web", style="cyan", no_wrap=True)
        tabla.add_column("Estado", justify="center")
        tabla.add_column("Latencia", justify="right")
        tabla.add_column("Uptime %", justify="right")
        tabla.add_column("Fallas", justify="right", style="red")
        tabla.add_column("Último Check", style="dim")

        for url, data in self.sitios.items():
            uptime = ((data["checks"] - data["fails"]) / data["checks"] * 100) if data["checks"] > 0 else 100
            status_text = "[bold green]ONLINE[/]" if data["estado"] == "UP" else "[bold red]OFFLINE[/]"
            tabla.add_row(
                url,
                status_text,
                f"{data['latencia']}ms",
                f"{uptime:.1f}%",
                str(data["fails"]),
                data["ultimo"]
            )
        return tabla

    def main(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=18)
        )
        layout["main"].split_row(
            Layout(name="tabla", ratio=3),
            Layout(name="stats", ratio=1)
        )

        threading.Thread(target=self.ciclo_monitoreo, daemon=True).start()
        
        if self.config.get("web_activo", False):
            threading.Thread(target=self.run_flask, daemon=True).start()
            self.registrar_log(f"Servidor Web activo en puerto {self.config.get('web_puerto', 5000)}", "bold cyan")

        with Live(layout, refresh_per_second=1, screen=True):
            while self.corriendo:
                # Header
                hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                layout["header"].update(Panel(
                    Align.center(
                        Text(f"🌐 MONITOR DE SITIOS WEB PRO (TUI) | {hora_actual}", style="bold white on blue")
                    )
                ))
                
                # Tabla
                layout["tabla"].update(Panel(self.generar_tabla(), title="[bold]Estatus de Sitios[/]"))
                
                # Stats & Salud
                total = len(self.sitios)
                online = sum(1 for s in self.sitios.values() if s["estado"] == "UP")
                salud = (online / total * 100) if total > 0 else 0
                
                progreso = Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(bar_width=None),
                    TextColumn("[bold]{task.percentage:>3.0f}%"),
                )
                progreso.add_task("Salud Ecosistema", completed=salud)
                
                stats_panel = [
                    f"Total: {total}",
                    f"Online: [green]{online}[/]",
                    f"Offline: [red]{total - online}[/]",
                    "",
                    "Intervalo: {}s".format(self.config.get("intervalo")),
                    "Sonido: {}".format("[green]ON[/]" if self.config.get("sonido") else "[red]OFF[/]")
                ]
                
                layout["stats"].update(Panel(
                    Align.center(
                        Group(
                            Text.from_markup("\n".join(stats_panel) + "\n\n"),
                            progreso
                        )
                    ),
                    title="[bold]Estadísticas[/]"
                ))
                
                # Logs
                log_text = Text.from_markup("\n".join(self.logs))
                layout["footer"].update(Panel(log_text, title="[bold]Registro de Actividad[/]", subtitle="Presione Ctrl+C para salir"))
                
                time.sleep(1)

if __name__ == "__main__":
    try:
        app = MonitorTUI()
        app.main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Saliendo del monitor...[/]")
