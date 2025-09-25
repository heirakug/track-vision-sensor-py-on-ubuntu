# MultiModal Tracker - Sensor Module

MediaPipe-based multi-modal tracking sensor optimized for Ubuntu/Raspberry Pi with CSI cameras.

## Features
- **Multi-modal Detection**: Hands, Face, Pose (individually configurable)
- **Raspberry Pi Optimized**: rpicam-apps/libcamera integration with V4L2 fallback
- **Real-time Processing**: 30fps with lightweight MediaPipe settings
- **OSC Integration**: Dual transmission to osc-router and visual-app
- **Gesture Recognition**: Advanced hand gesture detection system
- **Threaded Processing**: Non-blocking frame reading for stable performance

## Platform Support
- **OS**: Ubuntu 20.04+ / Raspberry Pi OS
- **Hardware**: Raspberry Pi 4/5 + CSI Camera (IMX219, etc.)
- **Camera**: rpicam-vid (priority) → libcamera → V4L2 fallback

## Quick Start
```bash
# Install dependencies
poetry install

# Basic usage (hands only)
poetry run python main.py

# Enable multiple features
poetry run python main.py --all                    # All features
poetry run python main.py --face                   # Hands + Face
poetry run python main.py --pose --no-hands        # Pose only

# Headless mode (no GUI)
poetry run python main.py --headless
```

## Configuration
Environment variables in `.env`:
```bash
# Camera settings
CAMERA_WIDTH=160        # Ultra-lightweight: 160x120
CAMERA_HEIGHT=120       # Standard: 640x480

# OSC targets
OSC_ROUTER_IP=127.0.0.1
OSC_ROUTER_PORT=8000
VISUAL_APP_IP=127.0.0.1
VISUAL_APP_PORT=8003
```

## Controls (Interactive Mode)
- **Q**: Quit application
- **H**: Toggle hand tracking
- **F**: Toggle face tracking
- **P**: Toggle pose tracking
- **G**: Toggle gesture recognition
- **R**: Rotate display (0°→90°→180°→270°)

## Dependencies
- mediapipe: Multi-modal tracking
- opencv-python: Camera and image processing
- python-osc: OSC communication
- python-dotenv: Environment configuration

## Troubleshooting
- **Camera issues**: Run `rpicam-hello --list-cameras`
- **Performance**: Use 160x120 resolution for Raspberry Pi
- **Color problems**: Automatic rpicam→V4L2 fallback