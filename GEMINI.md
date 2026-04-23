# Monitor de Sitios Web Pro v5.0

## Project Overview
This is a desktop application written in Python using `tkinter` for the GUI. It monitors the status of multiple websites, checking for availability and latency. It features real-time charts (using `matplotlib`), Telegram notifications, and customizable MP3 audio alarms (using `pygame-ce`).

### Main Technologies
- **Python 3.14+**
- **Tkinter**: Main GUI framework.
- **Matplotlib**: Real-time health and latency charts.
- **Pygame-ce**: Audio engine for alarms.
- **Requests**: For web monitoring and Telegram API integration.
- **Pystray & Pillow**: System tray support.

## Architecture
The application follows a monolithic structure centered around the `MonitorApp` class in `monitor.py`.
- **Persistence**: 
  - `config.json`: Stores Telegram tokens, check intervals, and audio settings.
  - `sitios.txt`: Simple list of URLs to monitor.
  - `historial.json`: Stores historical data (uptime, checks, fails) for each site.
- **Monitoring**: Uses a background thread to poll websites at a configurable interval.
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
