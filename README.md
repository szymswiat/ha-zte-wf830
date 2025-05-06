# ZTE WF830 Home Assistant Integration

This is a custom Home Assistant integration for the ZTE WF830 router. It provides various sensors, switches, and buttons to monitor and control your router directly from Home Assistant. This integration was created through reverse engineering of the router's web interface and is not officially supported by ZTE.

## Features

- Monitor router status and statistics
- Control router functions through switches
- Quick actions through buttons
- Real-time sensor data updates

## Installation

1. Download the latest release
2. Copy the `zte_wf830` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

1. In Home Assistant, go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "ZTE WF830"
4. Enter your router's IP address and credentials
5. Click "Submit"

## Requirements

- Home Assistant 2025.4.1 or later
- Python 3.x
- Required Python packages:
  - pydantic==1.10.2
  - requests==2.28.1
  - xmltodict==0.13.0

## Components

### Sensors
- Router status
- Connection statistics
- Network information

### Switches
- Various router control functions

### Buttons
- Quick action buttons for common router operations
