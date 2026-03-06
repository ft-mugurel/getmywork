# GetMyWork

A TUI (Terminal User Interface) tool for managing your GitHub repositories. Keep track of all your projects and easily clone them when you need to work on them.

## Features

- 📦 Store repository URLs with project names and descriptions
- 📋 View all your projects in a nice table interface
- 📥 Clone repositories to your home directory with one click
- 🗑️ Delete projects from the list
- 💾 Persistent storage in JSON format

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd getmywork
```

2. Install the package:
```bash
pip install -e .
```

Or install directly:
```bash
pip install textual
python -m getmywork.main
```

## Usage

Run the tool from anywhere:
```bash
getmywork
```

Or run as a Python module:
```bash
python -m getmywork
```

## Keyboard Shortcuts

- `a` - Add a new project
- `r` - Refresh the project list
- `q` - Quit the application
- `↑/↓` - Navigate the project list
- `Enter` - Select a project

## Configuration

- **Config file location**: `/root/.config/getmywork/projects.json`
- **Clone directory**: `/root/`

## How It Works

1. **Add a project**: Press `a` or click "Add Project" to add a new repository. Enter the project name, Git URL, and an optional description.

2. **View projects**: All your projects are displayed in a table showing name, URL, description, and clone status.

3. **Clone a project**: Select a project and click "Clone" (or press Enter) to clone it to your home directory.

4. **Delete a project**: Select a project and click "Delete" to remove it from the list (does not delete cloned files).

## Requirements

- Python 3.9+
- textual >= 0.47.0
- git (for cloning repositories)

## License

MIT
