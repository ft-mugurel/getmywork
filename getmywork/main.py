#!/usr/bin/env python3
"""Main entry point for getmywork."""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    ListView,
    ListItem,
    Label,
    Input,
    DataTable,
)
from textual.containers import Container, VerticalScroll, Vertical, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen


# Default configuration paths
DEFAULT_CONFIG_DIR = Path("/root/.config/getmywork")
DEFAULT_CLONE_DIR = Path("/root")
PROJECTS_FILE = DEFAULT_CONFIG_DIR / "projects.json"


def ensure_config_dir():
    """Ensure the configuration directory exists."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_projects() -> list[dict]:
    """Load projects from the JSON file."""
    ensure_config_dir()
    if not PROJECTS_FILE.exists():
        return []
    with open(PROJECTS_FILE, "r") as f:
        return json.load(f)


def save_projects(projects: list[dict]):
    """Save projects to the JSON file."""
    ensure_config_dir()
    with open(PROJECTS_FILE, "w") as f:
        json.dump(projects, f, indent=2)


def add_project(name: str, url: str, description: str = ""):
    """Add a new project to the list."""
    projects = load_projects()
    projects.append({
        "name": name,
        "url": url,
        "description": description,
        "cloned": False,
    })
    save_projects(projects)


def delete_project(index: int):
    """Delete a project by index."""
    projects = load_projects()
    if 0 <= index < len(projects):
        projects.pop(index)
        save_projects(projects)


def clone_project(url: str, name: str) -> bool:
    """Clone a git repository to the default clone directory."""
    target_dir = DEFAULT_CLONE_DIR / name
    if target_dir.exists():
        return False  # Already exists
    
    try:
        subprocess.run(
            ["git", "clone", url, str(target_dir)],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


class AddProjectScreen(ModalScreen):
    """Screen for adding a new project."""
    
    CSS = """
    AddProjectScreen {
        align: center middle;
    }
    
    #add-project-container {
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #add-project-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    
    Input {
        margin: 1 0;
    }
    
    #button-container {
        height: auto;
        margin-top: 1;
    }
    
    Button {
        width: 1fr;
        margin: 0 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Vertical(id="add-project-container"):
            yield Label("Add New Project", id="add-project-title")
            yield Input(placeholder="Project name", id="name-input")
            yield Input(placeholder="Git repository URL", id="url-input")
            yield Input(placeholder="Description (optional)", id="desc-input")
            with Horizontal(id="button-container"):
                yield Button("Add", variant="primary", id="add-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss()
        elif event.button.id == "add-btn":
            name = self.query_one("#name-input", Input).value.strip()
            url = self.query_one("#url-input", Input).value.strip()
            desc = self.query_one("#desc-input", Input).value.strip()
            
            if name and url:
                add_project(name, url, desc)
                self.dismiss(True)
            else:
                self.notify("Name and URL are required!", severity="error")


class ConfirmScreen(ModalScreen):
    """Screen for confirming an action."""
    
    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    
    #confirm-container {
        width: 50;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #confirm-message {
        text-align: center;
        margin-bottom: 1;
    }
    
    #button-container {
        height: auto;
    }
    
    Button {
        width: 1fr;
        margin: 0 1;
    }
    """
    
    def __init__(self, message: str, **kwargs):
        self.message = message
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Label(self.message, id="confirm-message")
            with Horizontal(id="button-container"):
                yield Button("Yes", variant="primary", id="yes-btn")
                yield Button("No", variant="error", id="no-btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)


def update_clone_status(projects: list[dict]) -> bool:
    """Check if projects are actually cloned and update status."""
    changed = False
    for project in projects:
        target_dir = DEFAULT_CLONE_DIR / project["name"]
        is_cloned = target_dir.exists() and (target_dir / ".git").exists()
        if project.get("cloned") != is_cloned:
            project["cloned"] = is_cloned
            changed = True
    return changed


def get_git_status(name: str) -> str:
    """Check if there are uncommitted changes in the repository."""
    target_dir = DEFAULT_CLONE_DIR / name
    if not (target_dir.exists() and (target_dir / ".git").exists()):
        return ""
    
    try:
        # Check for uncommitted changes (including untracked files)
        result = subprocess.run(
            ["git", "-C", str(target_dir), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout.strip():
            return "⚠️ Uncommitted"
        return "✨ Clean"
    except Exception:
        return "❓ Error"


def get_git_remote(target_dir: Path) -> str | None:
    """Get the origin remote URL of a git repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(target_dir), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def discover_untracked_repos(base_dir: Path, tracked_names: set[str]) -> list[dict]:
    """Discover git repositories in base_dir that are not in the tracked list."""
    untracked = []
    
    try:
        for item in base_dir.iterdir():
            if item.is_dir() and item.name not in tracked_names:
                git_dir = item / ".git"
                if git_dir.exists():
                    remote = get_git_remote(item)
                    untracked.append({
                        "name": item.name,
                        "path": str(item),
                        "url": remote or "",
                        "has_remote": remote is not None,
                        "is_tracked": False,
                    })
    except Exception:
        pass
    
    return untracked


class AddUntrackedProjectScreen(ModalScreen):
    """Screen for adding an untracked project to the list."""
    
    CSS = """
    AddUntrackedProjectScreen {
        align: center middle;
    }
    
    #container {
        width: 70;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    
    #info {
        margin: 1 0;
    }
    
    Input {
        margin: 1 0;
    }
    
    #button-container {
        height: auto;
        margin-top: 1;
    }
    
    Button {
        width: 1fr;
        margin: 0 1;
    }
    """
    
    def __init__(self, project: dict, **kwargs):
        self.project = project
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        with Vertical(id="container"):
            yield Label("Add Local Repository", id="title")
            yield Label(f"Name: {self.project['name']}", id="info")
            yield Label(f"Path: {self.project['path']}", id="info")
            
            if self.project["has_remote"]:
                yield Label(f"Remote: {self.project['url']}", id="info")
                yield Label("This repo has a remote URL.", id="info")
            else:
                yield Label("⚠️ No remote URL configured", id="info")
            
            yield Input(placeholder="Description (optional)", id="desc-input")
            
            with Horizontal(id="button-container"):
                yield Button("Add to Projects", variant="primary", id="add-btn")
                yield Button("Just Open Folder", variant="default", id="open-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss()
        elif event.button.id == "open-btn":
            # Just open the folder without adding
            self.dismiss({"action": "open", "path": self.project["path"]})
        elif event.button.id == "add-btn":
            desc = self.query_one("#desc-input", Input).value.strip()
            self.dismiss({
                "action": "add",
                "name": self.project["name"],
                "url": self.project["url"] or "",
                "description": desc,
                "path": self.project["path"]
            })


class GetMyWorkApp(App):
    """Main application for managing GitHub repositories."""
    
    search_query = reactive("")
    exit_target_dir = None
    show_untracked = reactive(False)

    CSS = """
    Screen {
        align: center middle;
    }
    
    #main-container {
        width: 90;
        height: 90%;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 0;
    }
    
    #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #search-input {
        margin: 0 0 1 0;
    }
    
    #projects-table {
        height: 1fr;
        margin: 1 0;
    }
    
    #button-row {
        height: auto;
        margin-top: 1;
    }
    
    #button-row Button {
        margin: 0 1;
    }
    
    #status-bar {
        height: auto;
        margin-top: 1;
        text-align: center;
        color: $text-muted;
    }
    
    .cloned {
        color: $success;
    }
    
    .not-cloned {
        color: $warning;
    }
    
    .untracked {
        color: $text-muted;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("a", "add_project", "Add Project"),
        ("r", "refresh", "Refresh"),
        ("/", "focus_search", "Search"),
        ("enter", "select_project", "Open Project"),
        ("u", "toggle_untracked", "Show Untracked"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield Label("📦 GetMyWork", id="title")
            yield Label("Manage your GitHub repositories", id="subtitle")
            
            yield Input(placeholder="Search projects...", id="search-input")

            table = DataTable(id="projects-table")
            table.add_columns("Name", "URL", "Description", "Status", "Git Status")
            table.cursor_type = "row"
            yield table
            
            with Horizontal(id="button-row"):
                yield Button("➕ Add Project", variant="primary", id="add-btn")
                yield Button("🗑️ Delete", variant="error", id="delete-btn")
                yield Button("📥 Clone", variant="success", id="clone-btn")
                yield Button("🔄 Refresh", variant="default", id="refresh-btn")
                yield Button("📂 Local Repos", variant="warning", id="untracked-btn")
            
            yield Label("Press 'Enter' to open, 'u' for local repos, '/' to search, 'a' to add, 'r' to refresh, 'q' to quit", id="status-bar")
        yield Footer()
    
    def on_mount(self) -> None:
        # Don't call refresh_projects here as watch_search_query will be triggered on initialization
        pass
    
    def watch_search_query(self, value: str) -> None:
        """Watch for search query changes and refresh the table."""
        self.refresh_projects()

    def watch_show_untracked(self, value: bool) -> None:
        """Watch for show_untracked changes and refresh the table."""
        self.refresh_projects()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_query = event.value.lower()

    def refresh_projects(self) -> None:
        """Refresh the projects table and verify clone status."""
        try:
            table = self.query_one("#projects-table", DataTable)
        except Exception:
            return  # Table not ready yet
            
        table.clear()
        
        projects = load_projects()
        
        # Verify clone status on disk
        if update_clone_status(projects):
            save_projects(projects)

        # Get tracked project names
        tracked_names = {p["name"] for p in projects}
        
        # Discover untracked repos if enabled
        untracked_repos = []
        if self.show_untracked:
            untracked_repos = discover_untracked_repos(DEFAULT_CLONE_DIR, tracked_names)

        # Filter and combine projects
        filtered_projects = []
        
        # Add tracked projects
        for project in projects:
            name = project["name"].lower()
            url = project["url"].lower()
            desc = project.get("description", "").lower()
            
            if not self.search_query or (self.search_query in name or \
               self.search_query in url or self.search_query in desc):
                filtered_projects.append({
                    **project,
                    "is_tracked": True,
                    "has_remote": True,
                })

        # Add untracked repos
        for repo in untracked_repos:
            name = repo["name"].lower()
            url = repo["url"].lower()
            
            if not self.search_query or (self.search_query in name or \
               self.search_query in url):
                filtered_projects.append({
                    "name": repo["name"],
                    "url": repo["url"] or "(local - no remote)",
                    "description": "",
                    "cloned": True,
                    "is_tracked": False,
                    "has_remote": repo["has_remote"],
                    "path": repo["path"],
                })

        for project in filtered_projects:
            is_cloned = project.get("cloned")
            is_tracked = project.get("is_tracked", True)
            
            if is_tracked:
                status = "✓ Cloned" if is_cloned else "○ Not Cloned"
                git_status = get_git_status(project["name"]) if is_cloned else ""
                row_key = f"tracked_{project['name']}"
            else:
                status = "📂 Local (untracked)"
                git_status = get_git_status(project["name"])
                row_key = f"untracked_{project['name']}"
            
            table.add_row(
                project["name"],
                project["url"],
                project.get("description", ""),
                status,
                git_status,
                key=row_key
            )
    
    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input").focus()

    def action_toggle_untracked(self) -> None:
        """Toggle showing untracked local repositories."""
        self.show_untracked = not self.show_untracked
        status = "showing" if self.show_untracked else "hidden"
        self.notify(f"Local untracked repos: {status}", severity="information")

    def action_select_project(self) -> None:
        """Handle selection of a project (Enter key)."""
        table = self.query_one("#projects-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= table.row_count:
            return
        
        # Get the row key (which now has tracked_ or untracked_ prefix)
        row_key_obj = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        row_key = row_key_obj.value if row_key_obj else ""
        
        projects = load_projects()
        
        if row_key.startswith("tracked_"):
            project_name = row_key[len("tracked_"):]
            project = next((p for p in projects if p["name"] == project_name), None)
            
            if project:
                target_dir = DEFAULT_CLONE_DIR / project["name"]
                
                if project.get("cloned") and target_dir.exists():
                    self.exit_target_dir = str(target_dir)
                    self.exit()
                else:
                    # Ask to clone
                    def on_confirm(result) -> None:
                        if result:
                            if clone_project(project["url"], project["name"]):
                                project["cloned"] = True
                                save_projects(projects)
                                self.exit_target_dir = str(target_dir)
                                self.exit()
                            else:
                                self.notify(f"Failed to clone '{project['name']}'", severity="error")
                    
                    self.push_screen(
                        ConfirmScreen(f"Project not cloned. Clone to {DEFAULT_CLONE_DIR} and open?"),
                        on_confirm
                    )
        elif row_key.startswith("untracked_"):
            project_name = row_key[len("untracked_"):]
            tracked_names = {p["name"] for p in projects}
            untracked = discover_untracked_repos(DEFAULT_CLONE_DIR, tracked_names)
            untracked_project = next((r for r in untracked if r["name"] == project_name), None)
            
            if untracked_project:
                def on_untracked_action(result) -> None:
                    if not result:
                        return
                    
                    if result["action"] == "open":
                        self.exit_target_dir = result["path"]
                        self.exit()
                    elif result["action"] == "add":
                        # Add to projects list
                        add_project(result["name"], result["url"], result["description"])
                        self.notify(f"Added '{result['name']}' to projects", severity="information")
                        self.refresh_projects()
                
                self.push_screen(
                    AddUntrackedProjectScreen(untracked_project),
                    on_untracked_action
                )
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle double click or enter on a row."""
        self.action_select_project()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self.action_add_project()
        elif event.button.id == "delete-btn":
            self.action_delete_project()
        elif event.button.id == "clone-btn":
            self.action_clone_project()
        elif event.button.id == "refresh-btn":
            self.action_refresh()
        elif event.button.id == "untracked-btn":
            self.action_toggle_untracked()
    
    def action_add_project(self) -> None:
        """Open the add project screen."""
        def on_dismiss(result) -> None:
            if result:
                self.refresh_projects()
                self.notify("Project added successfully!", severity="information")
        
        self.push_screen(AddProjectScreen(), on_dismiss)
    
    def action_delete_project(self) -> None:
        """Delete the selected project."""
        table = self.query_one("#projects-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= table.row_count:
            self.notify("Please select a project to delete", severity="warning")
            return
        
        row_index = table.cursor_row
        projects = load_projects()
        if row_index >= len(projects):
            return
        
        project_name = projects[row_index]["name"]
        
        def on_confirm(result) -> None:
            if result:
                delete_project(row_index)
                self.refresh_projects()
                self.notify(f"Deleted '{project_name}'", severity="information")
        
        self.push_screen(
            ConfirmScreen(f"Delete '{project_name}'?"),
            on_confirm
        )
    
    def action_clone_project(self) -> None:
        """Clone the selected project."""
        table = self.query_one("#projects-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= table.row_count:
            self.notify("Please select a project to clone", severity="warning")
            return
        
        row_index = table.cursor_row
        projects = load_projects()
        if row_index >= len(projects):
            return
        
        project = projects[row_index]
        project_name = project["name"]
        project_url = project["url"]
        
        def do_clone():
            if clone_project(project_url, project_name):
                project["cloned"] = True
                save_projects(projects)
                self.refresh_projects()
                self.notify(f"Successfully cloned '{project_name}'", severity="information")
            else:
                self.notify(f"Failed to clone '{project_name}'. Directory may already exist.", severity="error")
        
        self.push_screen(
            ConfirmScreen(f"Clone '{project_name}' to {DEFAULT_CLONE_DIR}?"),
            lambda result: do_clone() if result else None
        )
    
    def action_refresh(self) -> None:
        """Refresh the projects list."""
        self.refresh_projects()
        self.notify("Projects refreshed", severity="information")


def main():
    """Entry point for the CLI."""
    app = GetMyWorkApp()
    app.run()
    
    # Use a specific file to communicate the target directory
    if app.exit_target_dir:
        goto_file = Path("/tmp/getmywork_goto")
        goto_file.write_text(app.exit_target_dir)


if __name__ == "__main__":
    main()
