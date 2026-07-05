# Flower Care Assistant / 花卉养殖助手

A smart web-based flower care management application with climate-adjusted care schedules, plant photo upload, and AI plant identification.

## Features

- **20 Flower Types**: Complete care knowledge base covering seasonal watering, fertilizing, light, and temperature needs
- **Climate-Adjusted Care**: 7 climate zones with 150+ city mappings, auto-adjusting care schedules based on your location and current season
- **My Plants**: Add named plants, auto-generate watering plans with smart reminders
- **Custom Watering Cycle**: Adjust watering frequency per plant
- **Photo Upload & AI Identification**: Upload plant photos and get AI-powered variety identification and care advice
- **Smart Reminders**: Climate-adjusted care reminders that know your local weather patterns
- **Drag & Drop Reordering**: Customize your flower list order
- **User Accounts**: Registration, login, auto-login with session persistence

## Quick Start

### Prerequisites

- Python 3.x with Flask installed (`pip install flask`)

### Running

1. Clone this repository
2. Double-click `start.bat` (Windows) or run:
   ```
   python flower_server.py
   ```
3. The app will automatically open in your browser at `http://localhost:8765`

### Manual Start

```bash
pip install flask
python flower_server.py
```

Then open http://localhost:8765 in your browser.

## Tech Stack

- **Frontend**: Single-page HTML/CSS/JS (no build steps needed)
- **Backend**: Python Flask + SQLite
- **Storage**: Local SQLite database (no cloud dependencies)
- **Images**: All flower photos stored locally

## Project Structure

```
flower-care-assistant/
  flower-care.html       # Frontend (single HTML file with CSS + JS)
  flower_server.py       # Flask backend server
  start.bat              # Windows startup script
  images/                # Flower photos (20 types x 4 images each)
  plant_photos/          # User uploaded plant photos (created at runtime)
```

## License

MIT
