import yt_dlp
import sys
import os
import threading
import queue
import re
import subprocess
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.properties import StringProperty, ListProperty, DictProperty, BooleanProperty, NumericProperty
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.metrics import dp # Import the dp function
from kivy.uix.label import Label # Import the Label widget

# --- Kivy UI Layout (KV Language) ---
KV = '''
#:import Factory kivy.factory.Factory

<DownloadItem>:
    canvas.before:
        Color:
            rgba: app.colors['bg_light'] if self.index % 2 == 0 else app.colors['bg_lighter']
        Rectangle:
            pos: self.pos
            size: self.size
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(40)
    padding: [dp(10), 0]
    Label:
        text: root.title
        color: app.colors['fg']
        size_hint_x: 0.7
        halign: 'left'
        valign: 'middle'
        text_size: self.width, None
        shorten: True
        shorten_from: 'right'
    Label:
        text: root.status
        color: app.colors['fg']
        size_hint_x: 0.3

<RV>:
    viewclass: 'DownloadItem'
    RecycleBoxLayout:
        default_size: None, dp(40)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'

<SettingsPopup>:
    title: 'Settings'
    size_hint: 0.8, 0.8
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(20)
        
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                text: 'Theme:'
            Spinner:
                id: theme_spinner
                text: app.theme_name
                values: ['Dark', 'Light']
                on_text: app.change_theme(self.text)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                text: 'Speed Limit (e.g., 500K, 2M):'
            TextInput:
                id: rate_limit_input
                multiline: False
        
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                text: 'Concurrent Downloads:'
            Spinner:
                id: workers_spinner
                text: str(app.max_concurrent_downloads)
                values: [str(i) for i in range(1, 11)]
                on_text: app.max_concurrent_downloads = int(self.text)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                text: 'After Queue Finishes:'
            Spinner:
                id: post_dl_spinner
                text: app.post_dl_action
                values: ['Do Nothing', 'Shutdown', 'Sleep']
                on_text: app.post_dl_action = self.text

        Button:
            text: 'Update Download Engine (yt-dlp)'
            on_press: app.update_ytdlp()
        Label: # Spacer

<AboutPopup>:
    title: 'About'
    size_hint: 0.8, 0.8
    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(10)
        Label:
            text: 'About This Application'
            font_size: '20sp'
            bold: True
            size_hint_y: None
            height: dp(40)
        Label:
            text: "This Universal Video Converter is a versatile tool for downloading video and audio from a wide range of websites. Simply paste the URL of the content you want, choose your desired format and quality, and add it to the queue."
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
        Label:
            text: 'Developed By: Gemini & the user'
            size_hint_y: None
            height: dp(30)
        Label: # Spacer

<LogPopup>:
    title: 'Log'
    size_hint: 0.9, 0.9
    TextInput:
        id: log_text
        readonly: True
        background_color: app.colors['bg_light']
        foreground_color: app.colors['fg']

# --- Main App Layout ---
BoxLayout:
    orientation: 'vertical'
    padding: dp(10)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: app.colors['bg']
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(40)
        canvas.before:
            Color:
                rgba: app.colors['bg_light']
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(10),]
        padding: dp(5)
        Button:
            text: 'Settings'
            on_press: Factory.SettingsPopup().open()
            background_color: 0,0,0,0
        Button:
            text: 'Log'
            on_press: app.open_log_popup()
            background_color: 0,0,0,0
        Button:
            text: 'About'
            on_press: Factory.AboutPopup().open()
            background_color: 0,0,0,0

    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: app.colors['bg_light']
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(10),]

        TextInput:
            id: url_input
            hint_text: 'Paste URLs from any site (one per line)'
            multiline: True
            size_hint_y: 0.5
        
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(10)
            Label:
                text: 'Format:'
            CheckBox:
                group: 'format'
                active: True
                on_active: app.is_mp3 = self.active
            Label:
                text: 'MP3'
            CheckBox:
                group: 'format'
                on_active: app.is_mp3 = not self.active
            Label:
                text: 'MP4'

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(10)
            BoxLayout:
                opacity: 1 if app.is_mp3 else 0
                disabled: not app.is_mp3
                Label:
                    text: 'Bitrate:'
                Spinner:
                    id: bitrate_spinner
                    text: '192kbps'
                    values: ['128kbps', '192kbps', '256kbps', '320kbps']
            BoxLayout:
                opacity: 0 if app.is_mp3 else 1
                disabled: app.is_mp3
                Label:
                    text: 'Resolution:'
                Spinner:
                    id: resolution_spinner
                    text: '720p'
                    values: ['Best', '1080p', '720p', '480p']

        Button:
            text: 'Add to Queue'
            size_hint_y: None
            height: dp(50)
            on_press: app.add_links_to_queue()
                        
    RV:
        id: rv
        scroll_type: ['bars', 'content']
        bar_width: dp(10)

    BoxLayout:
        size_hint_y: None
        height: dp(40)
        spacing: dp(10)
        Button:
            id: pause_button
            text: 'Pause'
            on_press: app.toggle_pause()
        Button:
            text: 'Cancel Selected'
            on_press: app.cancel_selected_download()
        Button:
            text: 'Clear Finished'
            on_press: app.clear_finished()
        Button:
            text: 'Open Folder'
            on_press: app.open_download_folder()
'''

# --- Helper Functions ---
def get_output_path():
    """Creates and returns the output path."""
    home = os.path.expanduser("~")
    output_folder = os.path.join(home, 'Downloads', 'YTConverter')
    os.makedirs(output_folder, exist_ok=True)
    return output_folder

# --- Kivy Widgets ---
class DownloadItem(RecycleDataViewBehavior, BoxLayout):
    """A widget representing a single download item in the list."""
    title = StringProperty('')
    status = StringProperty('')
    index = NumericProperty(0)

    def refresh_view_attrs(self, rv, index, data):
        """Catch and handle the view changes."""
        self.index = index
        return super(DownloadItem, self).refresh_view_attrs(rv, index, data)

class RV(RecycleView):
    """The RecycleView that holds all the download items."""
    def __init__(self, **kwargs):
        super(RV, self).__init__(**kwargs)
        self.data = []

class SettingsPopup(Popup):
    pass

class AboutPopup(Popup):
    pass

class LogPopup(Popup):
    pass

# --- Main Kivy Application ---
class UniversalConverterApp(App):
    # --- Theme Properties ---
    themes = {
        "Dark": {
            "bg": [0.129, 0.145, 0.161, 1], "bg_light": [0.204, 0.227, 0.251, 1], 
            "bg_lighter": [0.286, 0.314, 0.341, 1], "fg": [0.973, 0.976, 0.98, 1], 
            "accent": [0.09, 0.635, 0.722, 1], "accent_light": [0.125, 0.788, 0.592, 1]
        },
        "Light": {
            "bg": [0.973, 0.976, 0.98, 1], "bg_light": [0.914, 0.925, 0.937, 1], 
            "bg_lighter": [0.871, 0.886, 0.902, 1], "fg": [0.129, 0.145, 0.161, 1], 
            "accent": [0, 0.482, 1, 1], "accent_light": [0, 0.337, 0.702, 1]
        }
    }
    colors = DictProperty(themes["Dark"])
    is_mp3 = BooleanProperty(True)
    theme_name = StringProperty("Dark")
    post_dl_action = StringProperty("Do Nothing")

    def build(self):
        self.download_queue = queue.Queue()
        self.active_downloads = 0
        self.max_concurrent_downloads = 3
        self.item_map = {}
        self.log_buffer = ""
        self.is_paused = False
        
        for _ in range(20): # Create a pool of worker threads
            thread = threading.Thread(target=self.worker, daemon=True)
            thread.start()

        return Builder.load_string(KV)

    def add_links_to_queue(self):
        """Adds links from the main input box to the queue."""
        urls = self.root.ids.url_input.text.strip().splitlines()
        self.root.ids.url_input.text = ""
        
        download_format = 'mp3' if self.is_mp3 else 'mp4'
        quality = self.root.ids.bitrate_spinner.text if self.is_mp3 else self.root.ids.resolution_spinner.text

        urls = [url for url in urls if url.strip()]
        if not urls:
            return

        for url in urls:
            item_id = len(self.root.ids.rv.data)
            self.root.ids.rv.data.append({'title': 'Fetching title...', 'status': 'Queued', 'index': item_id})
            self.item_map[item_id] = {'url': url, 'cancelled': False}
            self.download_queue.put((item_id, url, download_format, quality))
        
        self.start_next_download()

    def worker(self):
        """Worker thread to process downloads."""
        while True:
            item_id, url, download_format, quality = self.download_queue.get()
            if self.item_map.get(item_id, {}).get('cancelled'):
                self.download_queue.task_done()
                self.active_downloads -= 1
                self.start_next_download()
                continue
            self.run_download(url, download_format, quality, item_id)

    def start_next_download(self):
        """Starts the next download if a worker is free."""
        if self.is_paused:
            return
        while self.active_downloads < self.max_concurrent_downloads and not self.download_queue.empty():
            self.active_downloads += 1

    def run_download(self, url, download_format, quality, item_id):
        """The core download logic."""
        try:
            output_path = get_output_path()

            def update_ui(text, status):
                Clock.schedule_once(lambda dt: self._update_rv_item(item_id, text, status))

            update_ui("Fetching...", "Fetching...")

            with yt_dlp.YoutubeDL({'noplaylist': True, 'quiet': True}) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_title = info_dict.get('title', 'Unknown Title')
                video_id = info_dict.get('id', 'unknown_id')
                update_ui(video_title, "Fetching...")

            safe_title = re.sub(r'[\\/*?:"<>|]', "", video_title)
            safe_title = safe_title.encode('ascii', 'ignore').decode('ascii').strip()
            if len(safe_title) > 80:
                safe_title = safe_title[:80].strip()
            if not safe_title:
                safe_title = video_id
            
            output_template = os.path.join(output_path, f'{safe_title}.%(ext)s')

            ydl_opts = {
                'noplaylist': True,
                'progress_hooks': [lambda d: self.progress_hook(d, item_id, video_title)],
                'outtmpl': output_template,
            }
            
            # rate_limit = self.root.ids.rate_limit_input.text.strip()
            # if rate_limit:
            #     ydl_opts['ratelimit'] = rate_limit

            if download_format == 'mp3':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': quality.replace('kbps', '')}],
                })
            else: # MP4
                if quality == 'Best':
                    format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    height = quality.replace('p', '')
                    format_string = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4][height<={height}]'
                ydl_opts['format'] = format_string
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            update_ui(video_title, "✅ Complete")

        except Exception as e:
            update_ui(video_title, "❌ Error")
            error_message = f"Error downloading {url}: {e}\n"
            self.log_buffer += error_message
            print(error_message, file=sys.stderr)
        finally:
            self.download_queue.task_done()
            self.active_downloads -= 1
            self.check_queue_finished()
            self.start_next_download()

    def progress_hook(self, d, item_id, title):
        """Updates the UI with download progress."""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                percent = (d['downloaded_bytes'] / total_bytes) * 100
                status = f"Downloading {percent:.1f}%"
                Clock.schedule_once(lambda dt: self._update_rv_item(item_id, title, status))
        elif d['status'] == 'finished':
            Clock.schedule_once(lambda dt: self._update_rv_item(item_id, title, "Processing..."))

    def _update_rv_item(self, item_id, title, status):
        """Helper to safely update the RecycleView from a thread."""
        if item_id < len(self.root.ids.rv.data):
            self.root.ids.rv.data[item_id]['title'] = title
            self.root.ids.rv.data[item_id]['status'] = status
            self.root.ids.rv.refresh_from_data()

    def change_theme(self, theme_name):
        """Changes the color palette of the app."""
        self.theme_name = theme_name
        self.colors = self.themes[theme_name]

    def open_log_popup(self):
        """Opens the log popup and populates it with the buffered log."""
        popup = LogPopup()
        popup.ids.log_text.text = self.log_buffer
        popup.open()

    def update_ytdlp(self):
        """Updates the yt-dlp library in a separate thread."""
        def do_update():
            try:
                command = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
                subprocess.run(command, check=True, capture_output=True, text=True)
                print("Update Successful: yt-dlp has been updated.")
            except Exception as e:
                print(f"Update Failed: {e}", file=sys.stderr)
        
        threading.Thread(target=do_update, daemon=True).start()
    
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.root.ids.pause_button.text = "Resume"
        else:
            self.root.ids.pause_button.text = "Pause"
            self.start_next_download()

    def cancel_selected_download(self):
        # This requires selection in RecycleView, which is more complex.
        # For now, we'll cancel the first non-finished item as a placeholder.
        for i, item in enumerate(self.root.ids.rv.data):
            if item['status'] not in ["✅ Complete", "❌ Error", "Cancelled"]:
                self.item_map[i]['cancelled'] = True
                self._update_rv_item(i, item['title'], "Cancelling...")
                break

    def clear_finished(self):
        new_data = []
        new_item_map = {}
        for i, item in enumerate(self.root.ids.rv.data):
            if item['status'] not in ["✅ Complete", "❌ Error", "Cancelled"]:
                new_data.append(item)
                new_item_map[len(new_data)-1] = self.item_map[i]
        
        self.root.ids.rv.data = new_data
        self.item_map = new_item_map

    def open_download_folder(self):
        path = get_output_path()
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    
    def check_queue_finished(self):
        if self.active_downloads == 0 and self.download_queue.empty():
            action = self.post_dl_action
            if action == "Shutdown":
                os.system("shutdown /s /t 1")
            elif action == "Sleep":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


if __name__ == '__main__':
    UniversalConverterApp().run()
