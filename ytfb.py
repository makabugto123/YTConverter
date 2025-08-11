import yt_dlp
import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, font
import queue
import re
import subprocess

def get_output_path():
    """Creates and returns the output path: 'Downloads/YTConverter'."""
    try:
        downloads_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Downloads')
        output_folder = os.path.join(downloads_path, 'YTConverter')
        os.makedirs(output_folder, exist_ok=True)
        return output_folder
    except Exception:
        fallback_folder = "YTConverter_Downloads"
        os.makedirs(fallback_folder, exist_ok=True)
        return fallback_folder

class TextRedirector:
    """A class to redirect stdout/stderr to a tkinter Text widget."""
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str_val):
        self.widget.configure(state='normal')
        self.widget.insert('end', str_val, (self.tag,))
        self.widget.configure(state='disabled')
        self.widget.see('end')

    def flush(self):
        pass

class PlaylistWindow(tk.Toplevel):
    """A Toplevel window to display and select videos from a playlist."""
    def __init__(self, master, entries, download_format, quality):
        super().__init__(master)
        self.master_app = master
        self.download_format = download_format
        self.quality = quality
        
        self.title("Select Videos from Playlist")
        self.geometry("600x400")
        self.configure(bg=self.master_app.colors["bg"])

        # --- Treeview for playlist items ---
        list_frame = ttk.Frame(self, style="Main.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tree = ttk.Treeview(list_frame, columns=('Title',), show='headings', style="Custom.Treeview", selectmode="extended")
        self.tree.heading('Title', text='Video Title')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview, style="Custom.Vertical.TScrollbar")
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.video_entries = entries
        for entry in self.video_entries:
            self.tree.insert('', 'end', values=(entry.get('title', 'N/A'),), iid=entry.get('url'))

        # --- Bottom control buttons ---
        button_frame = ttk.Frame(self, style="Main.TFrame")
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        add_button = ttk.Button(button_frame, text="Add Selected to Queue", command=self.add_selected, style="Accent.TButton")
        add_button.pack(side=tk.RIGHT)

        select_all_button = ttk.Button(button_frame, text="Select All", command=self.select_all, style="Secondary.TButton")
        select_all_button.pack(side=tk.LEFT)
        
        deselect_all_button = ttk.Button(button_frame, text="Deselect All", command=self.deselect_all, style="Secondary.TButton")
        deselect_all_button.pack(side=tk.LEFT, padx=10)

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def deselect_all(self):
        self.tree.selection_set()

    def add_selected(self):
        selected_urls = self.tree.selection()
        if not selected_urls:
            messagebox.showwarning("No Selection", "Please select at least one video to add.", parent=self)
            return
        
        self.master_app.add_multiple_links_to_queue(selected_urls, self.download_format, self.quality)
        self.destroy()


class YouTubeConverterApp:
    """A graphical user interface for the downloader with a modern, tabbed design."""
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Video Converter")
        try:
            self.root.iconbitmap("icon.ico")
        except tk.TclError:
            print("Icon file 'icon.ico' not found. Using default icon.")
        self.root.geometry("800x760")
        self.root.resizable(True, True)

        self.download_queue = queue.Queue()
        self.active_downloads = 0
        self.is_paused = False
        self.item_map = {}
        
        self.font_main = font.Font(family="Roboto", size=10)
        self.font_bold = font.Font(family="Roboto", size=10, weight="bold")
        self.font_title = font.Font(family="Roboto", size=11, weight="bold")
        self.themes = {
            "Dark": {
                "bg": "#212529", "bg_light": "#343A40", "bg_lighter": "#495057",
                "fg": "#F8F9FA", "accent": "#17A2B8", "accent_light": "#20C997",
                "success": "#28A745", "error": "#DC3545", "warning": "#FFC107"
            },
            "Light": {
                "bg": "#F8F9FA", "bg_light": "#E9ECEF", "bg_lighter": "#DEE2E6",
                "fg": "#212529", "accent": "#007BFF", "accent_light": "#0056b3",
                "success": "#28A745", "error": "#DC3545", "warning": "#FFC107"
            }
        }
        self.colors = self.themes["Dark"]

        self.setup_styles()
        self.root.configure(bg=self.colors["bg"])
        
        main_frame = ttk.Frame(self.root, padding="15 20 20 20", style="Main.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(main_frame, style='Custom.TNotebook')
        self.notebook.pack(fill='x', pady=(0, 20))

        self.yt_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")
        self.fb_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")
        self.ig_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")
        self.other_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")
        self.settings_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")
        self.log_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")
        self.about_tab = ttk.Frame(self.notebook, style='Main.TFrame', padding="15")

        self.notebook.add(self.yt_tab, text='  YouTube  ')
        self.notebook.add(self.fb_tab, text='  Facebook  ')
        self.notebook.add(self.ig_tab, text='  Instagram  ')
        self.notebook.add(self.other_tab, text='  Other  ')
        self.notebook.add(self.settings_tab, text='  Settings  ')
        self.notebook.add(self.log_tab, text='  Log  ')
        self.notebook.add(self.about_tab, text='  About  ')
        
        self.create_youtube_tab_widgets(self.yt_tab)
        self.create_facebook_tab_widgets(self.fb_tab)
        self.create_instagram_tab_widgets(self.ig_tab)
        self.create_other_tab_widgets(self.other_tab)
        self.create_settings_tab_widgets(self.settings_tab)
        self.create_log_tab_widgets(self.log_tab)
        self.create_about_tab_widgets(self.about_tab)

        list_frame = ttk.Frame(main_frame, style="Main.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(list_frame, columns=('Title', 'Status'), show='headings', style="Custom.Treeview")
        self.tree.heading('Title', text='Title')
        self.tree.heading('Status', text='Download Status')
        self.tree.column('Title', width=560, anchor='w')
        self.tree.column('Status', width=150, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview, style="Custom.Vertical.TScrollbar")
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree.tag_configure('oddrow', background=self.colors['bg_light'])
        self.tree.tag_configure('evenrow', background=self.colors['bg_lighter'])
        
        bottom_controls_frame = ttk.Frame(main_frame, style="Main.TFrame")
        bottom_controls_frame.pack(fill='x', pady=(10, 0))

        self.pause_button = ttk.Button(bottom_controls_frame, text="❚❚ Pause", command=self.toggle_pause, style="Warning.TButton")
        self.pause_button.pack(side=tk.LEFT)

        cancel_button = ttk.Button(bottom_controls_frame, text="Cancel Selected", command=self.cancel_selected_download, style="Error.TButton")
        cancel_button.pack(side=tk.LEFT, padx=10)

        clear_button = ttk.Button(bottom_controls_frame, text="Clear Finished", command=self.clear_finished, style="Secondary.TButton")
        clear_button.pack(side=tk.LEFT)

        open_folder_button = ttk.Button(bottom_controls_frame, text="Open Folder", command=self.open_download_folder, style="Secondary.TButton")
        open_folder_button.pack(side=tk.LEFT, padx=10)

        post_dl_frame = ttk.Frame(bottom_controls_frame, style="Main.TFrame")
        post_dl_frame.pack(side=tk.RIGHT, padx=(10,0))
        ttk.Label(post_dl_frame, text="After Queue:", style="White.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.post_dl_action_var = tk.StringVar(value="Do Nothing")
        post_dl_menu = ttk.Combobox(post_dl_frame, textvariable=self.post_dl_action_var, values=["Do Nothing", "Shutdown", "Sleep"], width=10, state='readonly', style="Custom.TCombobox")
        post_dl_menu.pack(side=tk.LEFT)


    def create_youtube_tab_widgets(self, parent_frame):
        """Creates all the widgets for the YouTube downloader tab."""
        ttk.Label(parent_frame, text="Paste YouTube URLs (one per line):", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        
        text_frame = ttk.Frame(parent_frame, style="Text.TFrame", padding=2)
        text_frame.pack(fill=tk.X, expand=True, pady=(5, 15))
        self.yt_url_text = tk.Text(
            text_frame, height=5, width=60, font=self.font_main, 
            bg=self.colors["bg_light"], fg=self.colors["fg"],
            relief=tk.FLAT, insertbackground=self.colors["fg"],
            selectbackground=self.colors["accent"],
            borderwidth=0, highlightthickness=0
        )
        self.yt_url_text.pack(fill=tk.X, expand=True)
        
        settings_frame = ttk.Frame(parent_frame, style="Main.TFrame")
        settings_frame.pack(fill=tk.X, pady=(10, 0))

        add_yt_button = ttk.Button(settings_frame, text="✚  Add to Queue", command=self.add_links_to_queue, style="Accent.TButton", padding=(20, 10))
        add_yt_button.pack(side=tk.RIGHT, anchor='s', padx=(20, 0))

        format_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        format_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(format_frame, text="Format", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        self.yt_format_var = tk.StringVar(value="mp3")
        self.yt_format_var.trace_add("write", self.toggle_quality_options)
        mp3_button = ttk.Radiobutton(format_frame, text="MP3", variable=self.yt_format_var, value="mp3", style="White.TRadiobutton")
        mp3_button.pack(side=tk.LEFT, padx=(0, 10))
        mp4_button = ttk.Radiobutton(format_frame, text="MP4", variable=self.yt_format_var, value="mp4", style="White.TRadiobutton")
        mp4_button.pack(side=tk.LEFT)

        self.yt_quality_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        self.yt_quality_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        self.yt_bitrate_frame = ttk.Frame(self.yt_quality_frame, style="Main.TFrame")
        ttk.Label(self.yt_bitrate_frame, text="Bitrate", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        self.yt_bitrate_var = tk.StringVar(value='192kbps')
        self.yt_bitrate_menu = ttk.Combobox(self.yt_bitrate_frame, textvariable=self.yt_bitrate_var, values=['128kbps', '192kbps', '256kbps', '320kbps'], width=10, state='readonly', style="Custom.TCombobox")
        self.yt_bitrate_menu.pack(side=tk.LEFT)

        self.yt_resolution_frame = ttk.Frame(self.yt_quality_frame, style="Main.TFrame")
        ttk.Label(self.yt_resolution_frame, text="Resolution", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        self.yt_resolution_var = tk.StringVar(value='720p')
        self.yt_resolution_menu = ttk.Combobox(self.yt_resolution_frame, textvariable=self.yt_resolution_var, values=['Best', '1080p', '720p', '480p'], width=10, state='readonly', style="Custom.TCombobox")
        self.yt_resolution_menu.pack(side=tk.LEFT)
        
        self.yt_playlist_var = tk.BooleanVar()
        playlist_check = ttk.Checkbutton(settings_frame, text="Download Playlist", variable=self.yt_playlist_var, style="White.TCheckbutton")
        playlist_check.pack(side=tk.LEFT, padx=(20, 0), anchor='s', pady=(0, 5))
        
        self.toggle_quality_options()

    def create_facebook_tab_widgets(self, parent_frame):
        """Creates widgets for the Facebook downloader tab."""
        ttk.Label(parent_frame, text="Paste Facebook Video/Reel URLs (one per line):", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        
        text_frame = ttk.Frame(parent_frame, style="Text.TFrame", padding=2)
        text_frame.pack(fill=tk.X, expand=True, pady=(5, 15))
        self.fb_url_text = tk.Text(
            text_frame, height=5, width=60, font=self.font_main, 
            bg=self.colors["bg_light"], fg=self.colors["fg"],
            relief=tk.FLAT, insertbackground=self.colors["fg"],
            selectbackground=self.colors["accent"],
            borderwidth=0, highlightthickness=0
        )
        self.fb_url_text.pack(fill=tk.X, expand=True)

        settings_frame = ttk.Frame(parent_frame, style="Main.TFrame")
        settings_frame.pack(fill=tk.X, pady=(10, 0), anchor='e')
        
        add_fb_button = ttk.Button(settings_frame, text="✚  Add to Queue", command=self.add_links_to_queue, style="Accent.TButton", padding=(20, 10))
        add_fb_button.pack(side=tk.RIGHT)
        
        ttk.Label(settings_frame, text="Format: MP4 (Best Available)", style="White.TLabel").pack(side=tk.RIGHT, padx=20)

    def create_instagram_tab_widgets(self, parent_frame):
        """Creates widgets for the Instagram downloader tab."""
        ttk.Label(parent_frame, text="Paste Instagram Video/Reel URLs (one per line):", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        
        text_frame = ttk.Frame(parent_frame, style="Text.TFrame", padding=2)
        text_frame.pack(fill=tk.X, expand=True, pady=(5, 15))
        self.ig_url_text = tk.Text(
            text_frame, height=5, width=60, font=self.font_main, 
            bg=self.colors["bg_light"], fg=self.colors["fg"],
            relief=tk.FLAT, insertbackground=self.colors["fg"],
            selectbackground=self.colors["accent"],
            borderwidth=0, highlightthickness=0
        )
        self.ig_url_text.pack(fill=tk.X, expand=True)

        settings_frame = ttk.Frame(parent_frame, style="Main.TFrame")
        settings_frame.pack(fill=tk.X, pady=(10, 0), anchor='e')
        
        add_ig_button = ttk.Button(settings_frame, text="✚  Add to Queue", command=self.add_links_to_queue, style="Accent.TButton", padding=(20, 10))
        add_ig_button.pack(side=tk.RIGHT)
        
        ttk.Label(settings_frame, text="Format: MP4 (Best Available)", style="White.TLabel").pack(side=tk.RIGHT, padx=20)

    def create_other_tab_widgets(self, parent_frame):
        """Creates widgets for the generic 'Other' downloader tab."""
        ttk.Label(parent_frame, text="Paste URL from any other supported site (one per line):", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        
        text_frame = ttk.Frame(parent_frame, style="Text.TFrame", padding=2)
        text_frame.pack(fill=tk.X, expand=True, pady=(5, 15))
        self.other_url_text = tk.Text(
            text_frame, height=5, width=60, font=self.font_main, 
            bg=self.colors["bg_light"], fg=self.colors["fg"],
            relief=tk.FLAT, insertbackground=self.colors["fg"],
            selectbackground=self.colors["accent"],
            borderwidth=0, highlightthickness=0
        )
        self.other_url_text.pack(fill=tk.X, expand=True)

        settings_frame = ttk.Frame(parent_frame, style="Main.TFrame")
        settings_frame.pack(fill=tk.X, pady=(10, 0))
        
        add_other_button = ttk.Button(settings_frame, text="✚  Add to Queue", command=self.add_links_to_queue, style="Accent.TButton", padding=(20, 10))
        add_other_button.pack(side=tk.RIGHT)
        
        format_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        format_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(format_frame, text="Format", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        self.other_format_var = tk.StringVar(value="mp4")
        mp3_button = ttk.Radiobutton(format_frame, text="MP3 (Audio)", variable=self.other_format_var, value="mp3", style="White.TRadiobutton")
        mp3_button.pack(side=tk.LEFT, padx=(0, 10))
        mp4_button = ttk.Radiobutton(format_frame, text="MP4 (Video)", variable=self.other_format_var, value="mp4", style="White.TRadiobutton")
        mp4_button.pack(side=tk.LEFT)
        
        self.other_playlist_var = tk.BooleanVar()
        playlist_check = ttk.Checkbutton(settings_frame, text="Download Playlist", variable=self.other_playlist_var, style="White.TCheckbutton")
        playlist_check.pack(side=tk.LEFT, padx=(20, 0), anchor='s', pady=(0, 5))

    def create_settings_tab_widgets(self, parent_frame):
        """Creates widgets for the Settings tab."""
        settings_frame = ttk.Frame(parent_frame, style="Main.TFrame")
        settings_frame.pack(fill='x', anchor='n')

        # Theme Selection
        theme_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        theme_frame.pack(anchor='w', pady=(0, 20))
        ttk.Label(theme_frame, text="Theme:", style="Title.TLabel").pack(side=tk.LEFT, padx=(0, 10))
        self.theme_var = tk.StringVar(value="Dark")
        theme_menu = ttk.Combobox(theme_frame, textvariable=self.theme_var, values=["Dark", "Light"], width=10, state='readonly', style="Custom.TCombobox")
        theme_menu.pack(side=tk.LEFT)
        theme_menu.bind("<<ComboboxSelected>>", self.change_theme)

        # Speed Limiter
        rate_limit_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        rate_limit_frame.pack(anchor='w', pady=(0, 20))
        ttk.Label(rate_limit_frame, text="Global Speed Limit (e.g., 500K, 2M):", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        self.rate_limit_var = tk.StringVar(value="")
        rate_limit_entry = ttk.Entry(rate_limit_frame, textvariable=self.rate_limit_var, width=20, font=self.font_main)
        rate_limit_entry.pack(side=tk.LEFT, anchor='w')
        
        set_limit_button = ttk.Button(rate_limit_frame, text="Set Limit", command=self.confirm_rate_limit, style="Secondary.TButton")
        set_limit_button.pack(side=tk.LEFT, padx=10)
        
        # Concurrency
        concurrency_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        concurrency_frame.pack(anchor='w', pady=(0, 20))
        ttk.Label(concurrency_frame, text="Concurrent Downloads (Workers):", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        self.max_concurrent_var = tk.IntVar(value=3)
        self.max_concurrent_spinbox = ttk.Spinbox(
            concurrency_frame, from_=1, to=20, 
            textvariable=self.max_concurrent_var, width=5,
            font=self.font_main, style="Custom.TSpinbox"
        )
        self.max_concurrent_spinbox.pack(anchor='w')
        
        # Update yt-dlp
        update_frame = ttk.Frame(settings_frame, style="Main.TFrame")
        update_frame.pack(anchor='w')
        ttk.Label(update_frame, text="Download Engine:", style="Title.TLabel").pack(anchor="w", pady=(0,5))
        update_button = ttk.Button(update_frame, text="Update yt-dlp", command=self.update_ytdlp, style="Secondary.TButton")
        update_button.pack(side=tk.LEFT)


    def create_log_tab_widgets(self, parent_frame):
        """Creates widgets for the Log tab."""
        log_frame = ttk.Frame(parent_frame, style="Main.TFrame")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state='disabled', font=self.font_main, bg=self.colors['bg_light'], fg=self.colors['fg'])
        self.log_text.pack(fill=tk.BOTH, expand=True)

        sys.stderr = TextRedirector(self.log_text, "stderr")

    def create_about_tab_widgets(self, parent_frame):
        """Creates widgets for the About tab."""
        ttk.Label(parent_frame, text="About This Application", style="Title.TLabel", font=font.Font(family="Roboto", size=14, weight="bold")).pack(anchor="w", pady=(0, 15))
        description_text = "This Universal Video Converter is a versatile tool for downloading video and audio from a wide range of websites. Simply paste the URL of the content you want, choose your desired format and quality, and add it to the queue."
        ttk.Label(parent_frame, text=description_text, style="White.TLabel", wraplength=650, justify=tk.LEFT).pack(anchor="w", pady=(0, 20))

        ttk.Label(parent_frame, text="Supported Websites", style="Title.TLabel", font=font.Font(family="Roboto", size=12, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        supported_sites_text = (
            "This application supports hundreds of websites, including but not limited to:\n\n"
            "• YouTube (Videos, Shorts, Music)\n"
            "• Facebook (Videos, Reels)\n"
            "• Instagram (Videos, Reels)\n"
            "• TikTok\n"
            "• X (formerly Twitter)\n"
            "• Vimeo\n"
            "• Dailymotion\n"
            "• Twitch (VODs, Clips)\n"
            "• SoundCloud\n"
            "• Bandcamp\n"
            "• And many more news, social, and educational sites."
        )
        ttk.Label(parent_frame, text=supported_sites_text, style="White.TLabel", wraplength=650, justify=tk.LEFT).pack(anchor="w", pady=(0, 25))

        ttk.Label(parent_frame, text="Developed By", style="Title.TLabel", font=font.Font(family="Roboto", size=12, weight="bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(parent_frame, text="PHC-Cathy", style="White.TLabel").pack(anchor="w")


    def setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        self.style.configure("Main.TFrame", background=self.colors["bg"])
        self.style.configure("Text.TFrame", background=self.colors["accent"])
        self.style.configure("White.TLabel", background=self.colors["bg"], foreground=self.colors["fg"], font=self.font_main)
        self.style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["fg"], font=self.font_title)
        
        self.style.configure("Accent.TButton", background=self.colors["accent"], foreground=self.colors["fg"], font=self.font_bold, borderwidth=0, relief=tk.FLAT, focuscolor=self.colors['fg'])
        self.style.map("Accent.TButton", background=[('active', self.colors["accent_light"]), ('pressed', self.colors["accent_light"])])
        
        self.style.configure("Secondary.TButton", background=self.colors["bg_lighter"], foreground=self.colors["fg"], font=self.font_main, borderwidth=0, relief=tk.FLAT, focuscolor=self.colors['fg'])
        self.style.map("Secondary.TButton", background=[('active', self.colors["bg_light"])])
        
        self.style.configure("Warning.TButton", background=self.colors["warning"], foreground=self.colors["bg"], font=self.font_bold, borderwidth=0, relief=tk.FLAT, focuscolor=self.colors['fg'])
        self.style.map("Warning.TButton", background=[('active', '#ffca2c')])

        self.style.configure("Error.TButton", background=self.colors["error"], foreground=self.colors["fg"], font=self.font_main, borderwidth=0, relief=tk.FLAT, focuscolor=self.colors['fg'])
        self.style.map("Error.TButton", background=[('active', '#e06c75')])

        self.style.configure("White.TRadiobutton", background=self.colors["bg"], foreground=self.colors["fg"], font=self.font_main, indicatorcolor=self.colors['bg'], borderwidth=0)
        self.style.map("White.TRadiobutton",
            background=[('active', self.colors["bg"])],
            indicatorbackground=[('selected', self.colors['accent']), ('!selected', self.colors['bg_lighter'])],
            indicatorcolor=[('selected', self.colors['accent'])]
        )
        
        self.style.configure("White.TCheckbutton", background=self.colors['bg'], foreground=self.colors['fg'], font=self.font_main, indicatorcolor=self.colors['bg'])
        self.style.map("White.TCheckbutton",
            indicatorbackground=[('selected', self.colors['accent']), ('!selected', self.colors['bg_lighter'])]
        )

        self.style.configure("Custom.Treeview", background=self.colors["bg_light"], foreground=self.colors["fg"], fieldbackground=self.colors["bg_light"], rowheight=28, font=self.font_main, borderwidth=0)
        self.style.configure("Custom.Treeview.Heading", background=self.colors["bg"], foreground=self.colors["fg"], font=self.font_bold, relief=tk.FLAT)
        self.style.map("Custom.Treeview.Heading", background=[('active', self.colors["bg"])])
        self.style.map("Custom.Treeview", background=[('selected', self.colors["accent"])], foreground=[('selected', self.colors['fg'])])

        self.style.configure("Custom.Vertical.TScrollbar", background=self.colors["bg_light"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["fg"])
        self.style.map("Custom.Vertical.TScrollbar", background=[('active', self.colors['bg_lighter'])])

        self.style.configure('Custom.TCombobox', 
            fieldbackground=self.colors['bg_light'], background=self.colors['bg_light'], foreground=self.colors['fg'],
            arrowcolor=self.colors['fg'], selectbackground=self.colors['bg_light'], selectforeground=self.colors['fg'],
            bordercolor=self.colors['bg_lighter'], lightcolor=self.colors['bg_light'], darkcolor=self.colors['bg_light']
        )
        self.root.option_add('*TCombobox*Listbox*background', self.colors["bg_lighter"])
        self.root.option_add('*TCombobox*Listbox*foreground', self.colors["fg"])
        self.root.option_add('*TCombobox*Listbox*selectBackground', self.colors["accent"])
        
        self.style.configure('Custom.TSpinbox',
            fieldbackground=self.colors['bg_light'], background=self.colors['bg_light'], foreground=self.colors['fg'],
            bordercolor=self.colors['bg_light'], arrowcolor=self.colors['fg'], relief=tk.FLAT
        )
        self.style.map('Custom.TSpinbox', background=[('readonly', self.colors['bg_light'])])

        self.style.configure('Custom.TNotebook', background=self.colors['bg'], borderwidth=0)
        self.style.configure('Custom.TNotebook.Tab', background=self.colors['bg_light'], foreground=self.colors['fg'], font=self.font_main, padding=[10, 5], borderwidth=0)
        self.style.map('Custom.TNotebook.Tab',
            background=[('selected', self.colors['accent']), ('active', self.colors['bg_lighter'])],
            foreground=[('selected', self.colors['fg'])]
        )


    def toggle_quality_options(self, *args):
        self.yt_bitrate_frame.pack_forget()
        self.yt_resolution_frame.pack_forget()

        if self.yt_format_var.get() == "mp3":
            self.yt_bitrate_frame.pack()
        else:
            self.yt_resolution_frame.pack()

    def progress_hook(self, d, item_id):
        if self.item_map.get(item_id, {}).get('cancelled'):
            raise yt_dlp.utils.DownloadError("Download cancelled by user.")

        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                percent = (d['downloaded_bytes'] / total_bytes) * 100
                self.tree.set(item_id, 'Status', f"Downloading {percent:.1f}%")
        elif d['status'] == 'finished':
            self.tree.set(item_id, 'Status', "Processing...")
        elif d['status'] == 'error':
             self.tree.set(item_id, 'Status', "Error")

    def run_download(self, url, download_format, quality, item_id):
        try:
            if self.item_map.get(item_id, {}).get('cancelled'):
                self.tree.set(item_id, 'Status', "Cancelled")
                return

            output_path = get_output_path()
            
            self.tree.set(item_id, 'Status', "Fetching...")
            
            with yt_dlp.YoutubeDL({'noplaylist': True, 'quiet': True}) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_title = info_dict.get('title', 'Unknown Title')
                video_id = info_dict.get('id', 'unknown_id')
                self.tree.set(item_id, 'Title', f"  {video_title}")

            safe_title = re.sub(r'[\\/*?:"<>|]', "", video_title)
            safe_title = safe_title.encode('ascii', 'ignore').decode('ascii').strip()
            if len(safe_title) > 80:
                safe_title = safe_title[:80].strip()
            if not safe_title:
                safe_title = video_id
            
            output_template = os.path.join(output_path, f'{safe_title}.%(ext)s')

            ydl_opts = {
                'noplaylist': True,
                'progress_hooks': [lambda d: self.progress_hook(d, item_id)],
                'outtmpl': output_template,
            }

            rate_limit = self.rate_limit_var.get().strip()
            if rate_limit:
                ydl_opts['ratelimit'] = rate_limit

            if download_format == 'mp3':
                if getattr(sys, 'frozen', False):
                    ffmpeg_location = os.path.join(sys._MEIPASS, 'ffmpeg.exe')
                else:
                    ffmpeg_location = 'ffmpeg.exe'
                if not os.path.exists(ffmpeg_location):
                    raise FileNotFoundError("ffmpeg.exe not found!")
                
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': quality.replace('kbps', '')}],
                    'ffmpeg_location': ffmpeg_location,
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
            
            self.tree.set(item_id, 'Status', "✅ Complete")
            self.tree.item(item_id, tags=(self.tree.item(item_id, 'tags')[0], 'success'))
            self.tree.tag_configure('success', foreground=self.colors['success'])

        except Exception as e:
            if "cancelled by user" in str(e).lower():
                self.tree.set(item_id, 'Status', "Cancelled")
            else:
                self.tree.set(item_id, 'Status', "❌ Error")
                self.tree.item(item_id, tags=(self.tree.item(item_id, 'tags')[0], 'error'))
                self.tree.tag_configure('error', foreground=self.colors['error'])
                print(f"Error downloading {url}: {e}", file=sys.stderr)
        finally:
            self.download_queue.task_done()
            self.active_downloads -= 1
            self.check_queue_finished()
            self.start_next_download()

    def worker(self):
        while True:
            item_id, url, download_format, quality = self.download_queue.get()
            if self.item_map.get(item_id, {}).get('cancelled'):
                self.download_queue.task_done()
                self.active_downloads -= 1
                self.start_next_download()
                continue
            self.run_download(url, download_format, quality, item_id)

    def start_next_download(self):
        if self.is_paused:
            return
        while self.active_downloads < self.max_concurrent_var.get() and not self.download_queue.empty():
            self.active_downloads += 1
            # A worker will automatically pick up the next item

    def add_links_to_queue(self):
        active_tab_index = self.notebook.index(self.notebook.select())
        
        if active_tab_index == 0: # YouTube
            urls = self.yt_url_text.get("1.0", tk.END).strip().splitlines()
            url_text_widget = self.yt_url_text
            download_format = self.yt_format_var.get()
            quality = self.yt_bitrate_var.get() if download_format == 'mp3' else self.yt_resolution_var.get()
            is_playlist = self.yt_playlist_var.get()
        elif active_tab_index == 1: # Facebook
            urls = self.fb_url_text.get("1.0", tk.END).strip().splitlines()
            url_text_widget = self.fb_url_text
            download_format = 'mp4'
            quality = 'Best'
            is_playlist = False
        elif active_tab_index == 2: # Instagram
            urls = self.ig_url_text.get("1.0", tk.END).strip().splitlines()
            url_text_widget = self.ig_url_text
            download_format = 'mp4'
            quality = 'Best'
            is_playlist = False
        elif active_tab_index == 3: # Other
            urls = self.other_url_text.get("1.0", tk.END).strip().splitlines()
            url_text_widget = self.other_url_text
            download_format = self.other_format_var.get()
            quality = '192kbps' if download_format == 'mp3' else 'Best'
            is_playlist = self.other_playlist_var.get()
        else:
            return

        urls = [url for url in urls if url.strip()]
        if not urls:
            messagebox.showwarning("Input Required", "Please paste at least one URL.")
            return

        if is_playlist:
            if len(urls) > 1:
                messagebox.showwarning("Playlist Mode", "Please enter only one playlist URL at a time.")
                return
            self.fetch_playlist(urls[0], download_format, quality)
        else:
            self.add_multiple_links_to_queue(urls, download_format, quality)
        
        url_text_widget.delete("1.0", tk.END)

    def add_multiple_links_to_queue(self, urls, download_format, quality):
        """Adds a list of URLs to the main download queue."""
        for i, url in enumerate(urls):
            tag = 'evenrow' if (len(self.tree.get_children()) % 2 == 0) else 'oddrow'
            item_id = self.tree.insert('', 'end', values=('  Fetching title...', 'Queued'), tags=(tag,))
            self.item_map[item_id] = {'url': url, 'cancelled': False}
            self.download_queue.put((item_id, url, download_format, quality))
        self.start_next_download()

    def fetch_playlist(self, url, download_format, quality):
        """Fetches playlist contents in a new thread."""
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Fetching Playlist")
        progress_window.geometry("300x100")
        progress_window.configure(bg=self.colors['bg'])
        
        ttk.Label(progress_window, text="Fetching playlist contents...", style="White.TLabel").pack(pady=10)
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
        progress_bar.pack(pady=10, padx=20, fill='x')
        progress_bar.start(10)

        def do_fetch():
            try:
                ydl_opts = {'extract_flat': True, 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                
                progress_window.destroy()
                if 'entries' in info:
                    self.root.after(0, lambda: PlaylistWindow(self, info['entries'], download_format, quality))
                else:
                    messagebox.showerror("Error", "Could not find any videos in the playlist.", parent=self.root)
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror("Error", f"Failed to fetch playlist:\n{e}", parent=self.root)

        threading.Thread(target=do_fetch, daemon=True).start()

    def cancel_selected_download(self):
        """Cancels the currently selected download in the treeview."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select a download to cancel.")
            return
        
        for item_id in selected_items:
            if item_id in self.item_map:
                self.item_map[item_id]['cancelled'] = True
                self.tree.set(item_id, 'Status', "Cancelling...")

    def clear_finished(self):
        """Removes all completed or errored items from the list."""
        for item_id in list(self.tree.get_children()):
            status = self.tree.set(item_id, 'Status')
            if "Complete" in status or "Error" in status or "Cancelled" in status:
                self.tree.delete(item_id)
                if item_id in self.item_map:
                    del self.item_map[item_id]

    def open_download_folder(self):
        """Opens the output folder in the default file explorer."""
        path = get_output_path()
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin": # macOS
                subprocess.Popen(["open", path])
            else: # linux
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def toggle_pause(self):
        """Pauses or resumes the download queue."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.config(text="▶ Resume")
            self.pause_button.config(style="Accent.TButton")
        else:
            self.pause_button.config(text="❚❚ Pause")
            self.pause_button.config(style="Warning.TButton")
            for _ in range(self.max_concurrent_var.get()):
                self.start_next_download()

    def check_queue_finished(self):
        """Checks if the queue is empty and performs post-download actions."""
        if self.active_downloads == 0 and self.download_queue.empty():
            action = self.post_dl_action_var.get()
            if action == "Do Nothing":
                return

            if messagebox.askyesno("Queue Finished", f"The download queue is complete. Do you want to {action.lower()} the computer now?"):
                try:
                    if action == "Shutdown":
                        if sys.platform == "win32":
                            os.system("shutdown /s /t 1")
                        else:
                            os.system("shutdown now")
                    elif action == "Sleep":
                        if sys.platform == "win32":
                            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                        else: # Sleep is more complex on Linux/macOS
                            messagebox.showinfo("Info", "Sleep is not automatically supported on this OS.")
                except Exception as e:
                    messagebox.showerror("Error", f"Could not perform action: {e}")


    def change_theme(self, event=None):
        """Switches the application's color theme."""
        selected_theme = self.theme_var.get()
        self.colors = self.themes[selected_theme]
        self.root.configure(bg=self.colors["bg"])
        self.setup_styles()
        for i, item_id in enumerate(self.tree.get_children()):
            tag = 'evenrow' if (i % 2 == 0) else 'oddrow'
            current_tags = list(self.tree.item(item_id, 'tags'))
            if 'evenrow' in current_tags: current_tags.remove('evenrow')
            if 'oddrow' in current_tags: current_tags.remove('oddrow')
            current_tags.insert(0, tag)
            self.tree.item(item_id, tags=tuple(current_tags))

    def confirm_rate_limit(self):
        """Shows a confirmation message for the rate limit."""
        limit = self.rate_limit_var.get().strip()
        if limit:
            messagebox.showinfo("Speed Limit Set", f"The speed limit has been set to {limit}.\nThis will apply to all new downloads.")
        else:
            messagebox.showinfo("Speed Limit Removed", "The speed limit has been removed.")

    def update_ytdlp(self):
        """Updates the yt-dlp library using pip."""
        def do_update():
            try:
                command = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()

                if process.returncode == 0:
                    messagebox.showinfo("Update Successful", "yt-dlp has been updated successfully!")
                else:
                    messagebox.showerror("Update Failed", f"An error occurred:\n\n{stderr}")
            except Exception as e:
                messagebox.showerror("Update Error", f"An unexpected error occurred:\n\n{e}")

        threading.Thread(target=do_update, daemon=True).start()


    def start_app(self):
        num_threads = 20
        for _ in range(num_threads):
            thread = threading.Thread(target=self.worker, daemon=True)
            thread.start()
        
        self.root.mainloop()

if __name__ == '__main__':
    root = tk.Tk()
    app = YouTubeConverterApp(root)
    app.start_app()
