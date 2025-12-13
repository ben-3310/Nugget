#!/bin/bash
#
# Nugget macOS Build Script
#
# This script automates the process of building Nugget for macOS.
# It checks dependencies, compiles UI files, and runs PyInstaller.
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}       Nugget macOS Build Script       ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script is for macOS only${NC}"
    exit 1
fi

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 8 ]]; then
    echo -e "${RED}Error: Python 3.8 or newer is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}Python $PYTHON_VERSION found${NC}"

# Check if virtual environment exists
if [[ -d ".env" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .env/bin/activate
else
    echo -e "${YELLOW}No virtual environment found. Using system Python.${NC}"
fi

# Check required packages
echo -e "${YELLOW}Checking required packages...${NC}"

check_package() {
    python3 -c "import $1" 2>/dev/null
    if [[ $? -ne 0 ]]; then
        echo -e "${RED}Missing package: $1${NC}"
        echo -e "${YELLOW}Installing dependencies...${NC}"
        pip3 install -r requirements.txt
        return 1
    fi
    return 0
}

check_package "PySide6" || true
check_package "pymobiledevice3" || true
check_package "PyInstaller" || true

# Compile UI files
echo -e "${YELLOW}Compiling UI files...${NC}"
if command -v pyside6-uic &> /dev/null; then
    pyside6-uic qt/mainwindow.ui -o qt/mainwindow_ui.py
    echo -e "${GREEN}mainwindow_ui.py compiled${NC}"
else
    echo -e "${YELLOW}pyside6-uic not found, skipping UI compilation${NC}"
fi

# Compile resources
echo -e "${YELLOW}Compiling resources...${NC}"
if command -v pyside6-rcc &> /dev/null; then
    pyside6-rcc resources.qrc -o resources_rc.py
    echo -e "${GREEN}resources_rc.py compiled${NC}"
else
    echo -e "${YELLOW}pyside6-rcc not found, skipping resource compilation${NC}"
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf build/ dist/ *.spec 2>/dev/null || true

# Run PyInstaller
echo -e "${YELLOW}Running PyInstaller...${NC}"
python3 compile.py

# Check if build succeeded
if [[ -d "dist/Nugget.app" ]]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}        Build completed successfully!   ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Output: ${YELLOW}dist/Nugget.app${NC}"
    echo ""

    # Show app size
    APP_SIZE=$(du -sh dist/Nugget.app | cut -f1)
    echo -e "App size: ${YELLOW}$APP_SIZE${NC}"

    # Optional: Open Finder at dist folder
    # open dist/
else
    echo -e "${RED}Build failed! Check the output above for errors.${NC}"
    exit 1
fi
