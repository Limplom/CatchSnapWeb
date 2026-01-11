"""
Terminal-UI mit Rich-Library für Progress-Anzeige und Live-Status
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.text import Text

console = Console()


class RecorderUI:
    """Terminal-UI for Traffic Recorder with Live-Updates"""

    def __init__(self, browser_name: str, url: str):
        self.browser_name = browser_name
        self.url = url
        self.session_start = datetime.now()

        self.stats = {
            'requests': 0,
            'responses': 0,
            'blobs_downloaded': 0,
            'blobs_queued': 0,
            'blob_errors': 0
        }

    def print_header(self) -> None:
        """Show Session-Header"""
        console.print("\n" + "="*80, style="bold blue")
        console.print("🌐 CatchSnapWeb - Browser Traffic Recorder", style="bold cyan", justify="center")
        console.print("="*80 + "\n", style="bold blue")

        info_table = Table(show_header=False, box=None, padding=(0, 2))
        info_table.add_column(style="bold yellow")
        info_table.add_column(style="white")

        info_table.add_row("Browser:", self.browser_name.upper())
        info_table.add_row("Start-URL:", self.url)
        info_table.add_row("Session Start:", self.session_start.strftime("%Y-%m-%d %H:%M:%S"))

        console.print(Panel(info_table, title="[bold]Session Info[/bold]", border_style="blue"))
        console.print()

    def print_ready_message(self) -> None:
        """Displays ready message"""
        console.print("="*80, style="bold green")
        console.print("✓ Browser is ready!", style="bold green", justify="center")
        console.print("="*80 + "\n", style="bold green")

        console.print("[yellow]You can now navigate manually in the browser.[/yellow]")
        console.print("[yellow]Press Ctrl+C to exit and save the logs...[/yellow]\n")

    def create_live_table(self, stats: Dict[str, Any]) -> Table:
        """Create Live-Statistik-Tabelle"""
        # Session-Dauer berechnen
        duration = datetime.now() - self.session_start
        duration_str = str(duration).split('.')[0]  # Ohne Mikrosekunden

        # Statistik-Tabelle
        table = Table(title=f"📊 Live-Statistiken (duration: {duration_str})", show_header=True, header_style="bold cyan")

        table.add_column("Category", style="yellow", width=25)
        table.add_column("Count", justify="right", style="green", width=15)

        # Network-Statistiken
        table.add_row("HTTP Requests", str(stats.get('requests', 0)))
        table.add_row("HTTP Responses", str(stats.get('responses', 0)))
        table.add_section()

        # Blob-Statistiken
        blob_stats = stats.get('blob_stats', {})
        table.add_row("🎯 Blobs download", str(blob_stats.get('successful', 0)))
        table.add_row("⏳ Blobs in Queue", str(blob_stats.get('queue_size', 0)))
        table.add_row("🔄 Active Downloads", str(blob_stats.get('active_downloads', 0)))

        if blob_stats.get('failed', 0) > 0:
            table.add_row("❌ Error", str(blob_stats.get('failed', 0)), style="red")

        if blob_stats.get('duplicates', 0) > 0:
            table.add_row("📋 Duplicate", str(blob_stats.get('duplicates', 0)), style="dim")

        return table

    def print_statistics(self, stats: Dict[str, Any]) -> None:
        """Displays final statistics"""
        console.print("\n" + "="*80, style="bold blue")
        console.print("📈 Session-Statistiken", style="bold cyan", justify="center")
        console.print("="*80 + "\n", style="bold blue")

        table = self.create_live_table(stats)
        console.print(table)
        console.print()

    def print_shutdown_message(self) -> None:
        """Displays shutdown message"""
        console.print("\n" + "="*80, style="bold yellow")
        console.print("⚠️  Session is terminated...", style="bold yellow", justify="center")
        console.print("="*80 + "\n", style="bold yellow")

    def print_save_message(self) -> None:
        """Displays memory message"""
        console.print("[cyan]💾 Save Traffic-Logs...[/cyan]")

    def print_completion_message(self, output_dir: str) -> None:
        """Displays completion message"""
        console.print("\n" + "="*80, style="bold green")
        console.print("✓  Recording completed!", style="bold green", justify="center")
        console.print("="*80 + "\n", style="bold green")

        console.print(f"[green]📁 Alle Daten gespeichert in:[/green] [cyan]{output_dir}[/cyan]\n")

    def print_error(self, error: str) -> None:
        """Displays Erros"""
        console.print(f"\n[bold red]❌ Error:[/bold red] {error}\n")

    def print_warning(self, warning: str) -> None:
        """Displays warning"""
        console.print(f"[bold yellow]⚠️  warning:[/bold yellow] {warning}")


class DownloadProgressUI:
    """Progress-Bar for Blob-Downloads"""

    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        )
        self.task_id: Optional[int] = None

    def start(self, total: int) -> None:
        """Start Progress-Bar"""
        self.progress.start()
        self.task_id = self.progress.add_task(
            "[cyan]Downloading Blobs...",
            total=total
        )

    def update(self, advance: int = 1) -> None:
        """Updated Progress"""
        if self.task_id is not None:
            self.progress.update(self.task_id, advance=advance)

    def stop(self) -> None:
        """Stopped Progress-Bar"""
        self.progress.stop()


def print_banner() -> None:
    """Displays CatchSnapWeb banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║   ██████╗ █████╗ ████████╗ ██████╗██╗  ██╗███████╗███╗   ██╗ █████╗   ║
    ║  ██╔════╝██╔══██╗╚══██╔══╝██╔════╝██║  ██║██╔════╝████╗  ██║██╔══██╗  ║
    ║  ██║     ███████║   ██║   ██║     ███████║███████╗██╔██╗ ██║███████║  ║
    ║  ██║     ██╔══██║   ██║   ██║     ██╔══██║╚════██║██║╚██╗██║██╔══██║  ║
    ║  ╚██████╗██║  ██║   ██║   ╚██████╗██║  ██║███████║██║ ╚████║██║  ██║  ║
    ║   ╚═════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝  ║
    ║                                                                       ║
    ║           Browser Traffic Recorder + Blob Downloader v2.0             ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")
