# SmartPlayground

An interactive playground control system developed by the Tufts University Center for Engineering Education and Outreach (CEEO) FET Lab.

## Overview

We combine the novel smart tools developed at the center and the physical playground equipment to create engaging, interactive play experiences. The system uses ESP-based controllers and wireless communication to enable remote control and monitoring of playground elements.

## Features

- **Web-based Control Interface**: Browser-based application for managing playground equipment
- **Plushie Modules**: Interactive soft toys with embedded electronics
- **Real-time Communication**: Wireless connectivity between control hub and playground elements
- **Modular Design**: Extensible architecture for adding new playground components

## Repository Structure

```
SmartPlayground/
├── App_Hub/                    # Central hub application
├── App_Web/                    # Web-based control interface
├── Plushie_Module/            # Interactive plushie toy modules
└── old_stuff/                 # Archived legacy code
```

## Getting Started

### Prerequisites

- Playground modules (Buttons, Plushies, etc.) and a controller module developed at the center.
- A computer with Chrome browser installed to run the web app.

### Preparing the Playground Modules (one-time setup)
- Download the codes from Plushie_Module onto the your computer 
- Upload the following folders onto the Playground Modules
    1. games
    2. utilities
- Upload the following files onto the Playground Modules
    1. config.py
    2. main.py
- Modify the contents of config.py based on the type/name of your hardware

### using the App
- Connect the controller module to your computer using a USB-C cable
- Open the following link on Chrome browser https://tuftsceeo.github.io/SmartPlayground/
- If you are setting up the controller module for the first time, click Set up as a New Hub. Otherwise, click Connect to an Existing Hub. Select your device from the list.
- If you are setting up for the first time, click Start Upload and finish the setup process.
- Once you are all set, click on the message box to select the game you want to send to the playground modules. (Don't forget to hit send)



## Project Status

Active development. Check the [Issues](https://github.com/tuftsceeo/SmartPlayground/issues) tab for known bugs and planned features.


## Contact

For questions or collaboration inquiries, please contact the Tufts CEEO team.

## Acknowledgments

Developed by the Future Education Technology (FET) Lab at Tufts University Center for Engineering Education and Outreach.
