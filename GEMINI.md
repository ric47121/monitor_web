# Monitor de Sitios Web Pro v5.1

## Project Overview
This is a desktop application written in Python using `tkinter` for the GUI. It monitors the status of multiple websites, checking for availability and latency. It features real-time charts (using `matplotlib`), Telegram notifications, customizable MP3 audio alarms, and a **Web Dashboard** for remote monitoring.

### Main Technologies
- **Python 3.14+**
- **Tkinter**: Main GUI framework.
- **Matplotlib**: Real-time charts for the desktop app with Zoom and Pan support.
- **Flask**: Integrated web server for remote dashboarding.
- **Chart.js**: Interactive web charts (Latency and Availability) in the dashboard.
- **Pygame-ce**: Audio engine for alarms.
- **Requests**: For web monitoring and Telegram API integration.
- **Pystray & Pillow**: System tray support.

## Architecture
The application follows a multi-threaded structure centered around the `MonitorApp` class.
- **Persistence**: 
  - `config.json`: Stores Telegram tokens, check intervals, audio settings, and Web Server configuration.
  - `sitios.txt`: Simple list of URLs to monitor.
  - `historial.json`: Stores up to 500 samples of historical data per site.
- **Monitoring**: Background thread for website polling.
- **Web Dashboard**: Secondary thread running a Flask service for remote data access.
- **Notifications**: Integrated with Telegram Bot API for remote alerts and local audio triggers for immediate attention.

## Building and Running
### Prerequisites
Ensure you have Python installed. The project uses `pygame-ce` for better compatibility with newer Python versions.

### Installation
```powershell
pip install -r requirements.txt
```

### Running the App
```powershell
python monitor.py
```

## Development Conventions
- **Naming**: Methods and variables follow `snake_case` (Spanish names used in the current implementation).
- **Styling**: The UI uses `ttk` with the `clam` theme and custom font configurations for a modern look.
- **Error Handling**: Uses a dedicated logger (`elsitio.log`) for recording events and errors.
- **Threading**: Web checks and audio playback are executed in separate threads to keep the UI responsive.

## File Structure
- `monitor.py`: Main application logic.
- `alarmas/`: Directory for storing custom MP3 alarm sounds.
- `requirements.txt`: Project dependencies.
- `*.json` / `*.txt`: Data persistence files.
