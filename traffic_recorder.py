"""
Browser Traffic Recorder using Playwright
Dieses Skript erfasst alle HTTP-Requests und Responses während einer Browser-Session.
"""

import asyncio
import json
import os
import sys
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Request, Response

class TrafficRecorder:
    def __init__(self, output_dir="traffic_logs", download_blobs=True, browser_name="unknown"):
        self.session_start = datetime.now()
        self.browser_name = browser_name

        # Erstelle Unterordner mit Browser und Timestamp
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        session_folder = f"{browser_name}_{timestamp}"

        self.base_output_dir = Path(output_dir)
        self.base_output_dir.mkdir(exist_ok=True)

        self.output_dir = self.base_output_dir / session_folder
        self.output_dir.mkdir(exist_ok=True)

        self.blobs_dir = self.output_dir / "blobs"
        self.blobs_dir.mkdir(exist_ok=True)

        self.requests = []
        self.responses = []
        self.download_blobs = download_blobs
        self.blob_urls = set()
        self.page = None
        self.downloaded_blobs = []

        print(f"Session-Ordner erstellt: {self.output_dir}")

    def _format_headers(self, headers):
        """Formatiert Header-Dictionary für bessere Lesbarkeit"""
        return dict(headers)

    async def download_blob(self, blob_url, content_type=""):
        """Lädt eine Blob-URL herunter und speichert sie lokal"""
        if not self.page:
            print(f"[BLOB] Fehler: Keine Page-Referenz verfügbar")
            return None

        try:
            # JavaScript ausführen, um Blob-Daten zu extrahieren (optimiert für große Dateien)
            blob_data = await self.page.evaluate("""
                async (blobUrl) => {
                    try {
                        const response = await fetch(blobUrl);
                        const blob = await response.blob();
                        const arrayBuffer = await blob.arrayBuffer();

                        // Für große Dateien: Verarbeite in Chunks
                        const uint8Array = new Uint8Array(arrayBuffer);
                        const chunkSize = 65536; // 64KB chunks
                        let base64 = '';

                        for (let i = 0; i < uint8Array.length; i += chunkSize) {
                            const chunk = uint8Array.subarray(i, Math.min(i + chunkSize, uint8Array.length));
                            base64 += btoa(String.fromCharCode.apply(null, chunk));
                        }

                        return {
                            success: true,
                            data: base64,
                            type: blob.type,
                            size: blob.size
                        };
                    } catch (e) {
                        return {
                            success: false,
                            error: e.message
                        };
                    }
                }
            """, blob_url)

            if not blob_data.get('success'):
                print(f"[BLOB] Fehler beim Abrufen von {blob_url}: {blob_data.get('error')}")
                return None

            # Dateiendung basierend auf Content-Type bestimmen
            content_type = blob_data.get('type', content_type)
            ext = self._get_file_extension(content_type)

            # Base64-Daten dekodieren
            file_data = base64.b64decode(blob_data['data'])

            # Validiere, ob Blob vollständig ist
            is_valid, validation_msg = self._validate_blob_data(file_data, content_type)

            if not is_valid:
                print(f"[BLOB] Validierung fehlgeschlagen: {validation_msg}")
                return {"error": validation_msg, "blob_url": blob_url}

            # Hash des Dateiinhalts berechnen (SHA256 für Deduplizierung)
            file_hash = hashlib.sha256(file_data).hexdigest()

            # Dateiname mit Hash (verhindert Duplikate)
            filename = f"{file_hash}{ext}"
            filepath = self.blobs_dir / filename

            # Prüfe, ob Datei bereits existiert (für Statistik)
            is_duplicate = filepath.exists()

            # Speichere Datei (überschreibt bei Duplikaten)
            with open(filepath, 'wb') as f:
                f.write(file_data)

            blob_info = {
                "blob_url": blob_url,
                "filename": filename,
                "filepath": str(filepath),
                "content_type": content_type,
                "size": blob_data['size'],
                "hash": file_hash,
                "duplicate": is_duplicate,
                "timestamp": datetime.now().isoformat()
            }

            self.downloaded_blobs.append(blob_info)

            if is_duplicate:
                print(f"[BLOB] OK Aktualisiert (Duplikat): {filename} ({blob_data['size']} bytes, {content_type})")
            else:
                print(f"[BLOB] OK Heruntergeladen: {filename} ({blob_data['size']} bytes, {content_type})")

            return blob_info

        except Exception as e:
            print(f"[BLOB] Fehler beim Herunterladen von {blob_url}: {e}")
            return None

    def _validate_blob_data(self, file_data, content_type):
        """Validiert, ob Blob-Daten vollständig sind"""
        # Minimale Größenprüfung
        if len(file_data) < 100:  # Zu klein für valide Medien
            return False, "Datei zu klein (< 100 bytes)"

        content_type_base = content_type.split(';')[0].strip()

        # JPEG Validierung (Start UND Ende prüfen!)
        if content_type_base == 'image/jpeg':
            # Start: FF D8 FF
            if not file_data.startswith(b'\xFF\xD8\xFF'):
                return False, "JPEG: Ungültiger Start (FF D8 FF fehlt)"

            # Ende: FF D9 (End of Image marker)
            if not file_data.endswith(b'\xFF\xD9'):
                return False, "JPEG: Unvollständig (FF D9 End-Marker fehlt)"

        # PNG Validierung (Start UND Ende prüfen!)
        elif content_type_base == 'image/png':
            # Start: 89 50 4E 47 0D 0A 1A 0A
            if not file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                return False, "PNG: Ungültiger Start"

            # Ende: IEND chunk (49 45 4E 44 AE 42 60 82)
            if b'IEND' not in file_data[-12:]:
                return False, "PNG: Unvollständig (IEND chunk fehlt)"

        # GIF Validierung
        elif content_type_base == 'image/gif':
            if not (file_data.startswith(b'GIF87a') or file_data.startswith(b'GIF89a')):
                return False, "GIF: Ungültiger Start"

            # Ende: 3B (semicolon trailer)
            if not file_data.endswith(b'\x3B'):
                return False, "GIF: Unvollständig (Trailer fehlt)"

        # WebP Validierung
        elif content_type_base == 'image/webp':
            if not file_data.startswith(b'RIFF'):
                return False, "WebP: Ungültiger Start (RIFF fehlt)"

            if b'WEBP' not in file_data[:20]:
                return False, "WebP: Ungültige Struktur"

        # MP4/Video Validierung (vollständig)
        elif content_type_base == 'video/mp4':
            # Start: ftyp box muss vorhanden sein
            if b'ftyp' not in file_data[:20]:
                return False, "MP4: Ungültiger Start (ftyp fehlt)"

            # Prüfe auf wichtige MP4 boxes/atoms
            required_boxes = [b'moov']  # Movie header - essentiell
            for box in required_boxes:
                if box not in file_data:
                    return False, f"MP4: Unvollständig ({box.decode()} box fehlt)"

            # Datei sollte groß genug für echtes Video sein
            if len(file_data) < 1000:  # Videos sind normalerweise größer
                return False, "MP4: Datei zu klein für Video"

        # WebM Validierung
        elif content_type_base == 'video/webm':
            # WebM ist EBML-basiert, prüfe Header
            if not file_data.startswith(b'\x1a\x45\xdf\xa3'):
                return False, "WebM: Ungültiger EBML Header"

            if len(file_data) < 1000:
                return False, "WebM: Datei zu klein für Video"

        return True, "OK"

    def _get_file_extension(self, content_type):
        """Bestimmt Dateiendung basierend auf Content-Type"""
        extensions = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg',
            'video/mp4': '.mp4',
            'video/webm': '.webm',
            'video/ogg': '.ogg',
            'audio/mpeg': '.mp3',
            'audio/ogg': '.ogg',
            'audio/wav': '.wav',
            'application/javascript': '.js',
            'application/json': '.json',
            'text/html': '.html',
            'text/css': '.css',
            'text/plain': '.txt'
        }
        return extensions.get(content_type.split(';')[0].strip(), '.bin')

    async def on_request(self, request: Request):
        """Callback für ausgehende Requests"""
        # POST-Daten sicher extrahieren
        post_data = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                post_data = request.post_data
            except (UnicodeDecodeError, Exception):
                post_data = "<binary data>"

        request_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": request.url,
            "headers": self._format_headers(request.headers),
            "post_data": post_data,
            "resource_type": request.resource_type
        }
        self.requests.append(request_data)

        # Live-Ausgabe
        print(f"[REQUEST] {request.method} {request.url}")

    async def on_response(self, response: Response):
        """Callback für eingehende Responses"""
        response_data = {
            "timestamp": datetime.now().isoformat(),
            "url": response.url,
            "status": response.status,
            "status_text": response.status_text,
            "headers": self._format_headers(response.headers),
            "content_type": response.headers.get("content-type", "")
        }

        # Versuche Body zu erfassen (nur für bestimmte Content-Types)
        try:
            if "application/json" in response_data["content_type"]:
                response_data["body"] = await response.text()
            elif "text/" in response_data["content_type"]:
                response_data["body"] = await response.text()
        except Exception as e:
            response_data["body_error"] = str(e)

        self.responses.append(response_data)

        # Live-Ausgabe
        status_color = "OK" if 200 <= response.status < 300 else "ERROR"
        print(f"[RESPONSE] {response.status} {response.url} [{status_color}]")

        # Blob-URL erkennen und herunterladen
        if self.download_blobs and response.url.startswith('blob:'):
            if response.url not in self.blob_urls:
                self.blob_urls.add(response.url)
                # Verzögere Download, damit Blob vollständig geladen ist
                asyncio.create_task(self._download_blob_delayed(response.url, response_data["content_type"]))

    async def _download_blob_delayed(self, blob_url, content_type):
        """Verzögerter Blob-Download mit content-type-basierter Verzögerung und Retry-Logik"""
        # ERHÖHTE Verzögerungen für bessere Vollständigkeit
        if 'video' in content_type.lower():
            initial_delay = 3.0  # 3 Sekunden für Videos (erhöht von 2.0)
        elif 'image' in content_type.lower():
            initial_delay = 2.0  # 2 Sekunden für Bilder (erhöht von 1.0)
        else:
            initial_delay = 1.0  # 1 Sekunde für andere (erhöht von 0.5)

        await asyncio.sleep(initial_delay)

        # Unendliche Retry-Logik mit exponential backoff (max 10s cap)
        attempt = 0
        while True:
            result = await self.download_blob(blob_url, content_type)

            if result:
                # Prüfe ob Download erfolgreich war und Datei valide ist
                if not result.get('error'):
                    break  # Erfolgreich - fertig!

            # Exponential backoff: 1s, 2s, 4s, 8s, 10s, 10s, 10s...
            # Cap bei 10 Sekunden für praktikable Wartezeiten
            wait_time = min(2 ** attempt, 10)
            attempt += 1

            print(f"[BLOB] Retry #{attempt} in {wait_time}s (unvollständig - warte auf vollständigen Download)...")
            await asyncio.sleep(wait_time)

    def save_logs(self):
        """Speichert alle erfassten Requests und Responses"""
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")

        # Speichere Requests
        requests_file = self.output_dir / f"requests_{timestamp}.json"
        with open(requests_file, 'w', encoding='utf-8') as f:
            json.dump(self.requests, f, indent=2, ensure_ascii=False)
        print(f"\nRequests gespeichert: {requests_file}")

        # Speichere Responses
        responses_file = self.output_dir / f"responses_{timestamp}.json"
        with open(responses_file, 'w', encoding='utf-8') as f:
            json.dump(self.responses, f, indent=2, ensure_ascii=False)
        print(f"Responses gespeichert: {responses_file}")

        # Speichere heruntergeladene Blobs
        if self.downloaded_blobs:
            blobs_file = self.output_dir / f"downloaded_blobs_{timestamp}.json"
            with open(blobs_file, 'w', encoding='utf-8') as f:
                json.dump(self.downloaded_blobs, f, indent=2, ensure_ascii=False)
            print(f"Heruntergeladene Blobs: {blobs_file}")

            # Statistiken über Duplikate
            unique_blobs = [b for b in self.downloaded_blobs if not b.get('duplicate', False)]
            duplicate_count = len(self.downloaded_blobs) - len(unique_blobs)

            print(f"  - {len(unique_blobs)} einzigartige Blob(s) gespeichert")
            if duplicate_count > 0:
                print(f"  - {duplicate_count} Duplikat(e) übersprungen")
            print(f"  - Speicherort: {self.blobs_dir}")

        # Zusammenfassung
        unique_blobs_count = len([b for b in self.downloaded_blobs if not b.get('duplicate', False)])
        duplicate_blobs_count = len(self.downloaded_blobs) - unique_blobs_count

        summary = {
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "total_requests": len(self.requests),
            "total_responses": len(self.responses),
            "total_blobs_processed": len(self.downloaded_blobs),
            "unique_blobs_saved": unique_blobs_count,
            "duplicate_blobs_skipped": duplicate_blobs_count,
            "unique_domains": list(set([r["url"].split("/")[2] if len(r["url"].split("/")) > 2 else "" for r in self.requests]))
        }

        summary_file = self.output_dir / f"summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Zusammenfassung gespeichert: {summary_file}")

        return requests_file, responses_file, summary_file

async def record_browser_session(url="https://www.snapchat.com/web", headless=False, har_path=None, browser_type="chromium", channel=None):
    """
    Startet eine Browser-Session und zeichnet den Traffic auf.

    Args:
        url: Start-URL
        headless: Browser im Headless-Modus starten
        har_path: Optional - Pfad für HAR-Datei (HTTP Archive)
        browser_type: "chromium", "firefox", "webkit", "chrome", "msedge"
        channel: Optional - "chrome", "msedge", "chrome-beta", "msedge-beta", "msedge-dev"
    """
    recorder = TrafficRecorder(browser_name=browser_type)

    async with async_playwright() as p:
        # Browser auswählen
        brave_path = None
        executable_path = None

        if browser_type == "firefox":
            browser_launcher = p.firefox
            print(f"Starte Firefox (headless={headless})...")
        elif browser_type == "webkit":
            browser_launcher = p.webkit
            print(f"Starte WebKit (headless={headless})...")
        elif browser_type == "brave":
            browser_launcher = p.chromium
            # Suche nach Brave Installation
            brave_paths = [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe")
            ]
            for path in brave_paths:
                if os.path.exists(path):
                    brave_path = path
                    executable_path = path
                    break

            if not brave_path:
                print("WARNUNG: Brave Browser nicht gefunden! Versuche Standard-Pfad...")
                print("Wenn Brave nicht startet, gib den Pfad manuell im Script an.")
                executable_path = brave_paths[0]  # Versuche trotzdem

            print(f"Starte Brave Browser (headless={headless})...")
            print(f"Pfad: {executable_path}")
        elif browser_type == "chrome" or channel == "chrome":
            browser_launcher = p.chromium
            channel = "chrome"
            print(f"Starte Chrome (lokal installiert, headless={headless})...")
        elif browser_type == "msedge" or channel == "msedge":
            browser_launcher = p.chromium
            channel = "msedge"
            print(f"Starte Edge (lokal installiert, headless={headless})...")
        else:
            browser_launcher = p.chromium
            print(f"Starte Chromium (headless={headless})...")

        # Browser-Context mit optionalem HAR-Recording
        context_options = {
            "viewport": {"width": 1080, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        # HAR-Datei im Session-Ordner speichern
        if har_path:
            # Verwende den Session-Ordner für die HAR-Datei
            har_filename = f"session.har"
            har_full_path = recorder.output_dir / har_filename
            context_options["record_har_path"] = str(har_full_path)
            print(f"HAR-Recording aktiviert: {har_full_path}")

        # Browser starten (mit verschiedenen Launch-Optionen)
        launch_options = {"headless": headless}

        if executable_path:
            # Für Brave mit executable_path
            launch_options["executable_path"] = executable_path
            browser = await browser_launcher.launch(**launch_options)
        elif channel:
            # Für Chrome/Edge mit channel
            launch_options["channel"] = channel
            browser = await browser_launcher.launch(**launch_options)
        else:
            # Standard für Chromium/Firefox/WebKit
            browser = await browser_launcher.launch(**launch_options)

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        # Page-Referenz im Recorder setzen für Blob-Downloads
        recorder.page = page

        # Event-Listener registrieren
        page.on("request", recorder.on_request)
        page.on("response", recorder.on_response)

        print(f"\nNavigiere zu {url}...")
        print("=" * 80)

        try:
            await page.goto(url, wait_until="networkidle")

            print("\n" + "=" * 80)
            print("Browser ist bereit. Du kannst jetzt manuell navigieren.")
            print("Drücke Ctrl+C zum Beenden und Speichern der Logs...")
            print("=" * 80 + "\n")

            # Warte auf Benutzerinteraktion (kann mit Ctrl+C beendet werden)
            await page.wait_for_timeout(300000)  # 5 Minuten Max-Timeout

        except KeyboardInterrupt:
            print("\n\nSession wird beendet...")
        except Exception as e:
            print(f"\nFehler: {e}")
        finally:
            # Logs speichern
            print("\nSpeichere Traffic-Logs...")
            recorder.save_logs()

            # Browser schließen
            await context.close()
            await browser.close()

            print("\nBrowser geschlossen. Aufzeichnung abgeschlossen.")

if __name__ == "__main__":
    # Konfiguration
    START_URL = "https://www.snapchat.com/web"  # Standard-URL
    HEADLESS = False  # True = Browser unsichtbar, False = Browser sichtbar
    HAR_FILE = True  # HAR-Recording aktivieren (wird automatisch im Session-Ordner gespeichert)

    # Browser aus Command-Line-Argument oder Standard
    if len(sys.argv) > 1:
        BROWSER = sys.argv[1].lower()
    else:
        # Standard-Browser wenn kein Argument übergeben wurde
        BROWSER = "chrome"

    # URL aus Command-Line-Argument (optional als zweites Argument)
    if len(sys.argv) > 2:
        START_URL = sys.argv[2]

    # Browser-Auswahl:
    # "chromium"  = Playwright's Chromium (Version 143.0.7499.4)
    # "firefox"   = Playwright's Firefox (Version 144.0.2)
    # "chrome"    = Dein lokal installierter Chrome Browser (neueste Version)
    # "msedge"    = Dein lokal installierter Edge Browser (neueste Version)
    # "brave"     = Dein lokal installierter Brave Browser (neueste Version)
    # "webkit"    = Playwright's WebKit

    print("=" * 80)
    print("Browser Traffic Recorder + Blob Downloader")
    print("=" * 80)
    print(f"Browser: {BROWSER.upper()}")
    print(f"Start-URL: {START_URL}")
    print("=" * 80)
    print("BLOB-DOWNLOAD AKTIVIERT: Alle Blob-URLs werden automatisch heruntergeladen!")
    print("=" * 80)

    # Starte Recording
    asyncio.run(record_browser_session(
        url=START_URL,
        headless=HEADLESS,
        har_path=HAR_FILE,
        browser_type=BROWSER
    ))
