import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, glob, re, shutil, subprocess, winsound
import time
import struct
import json
import hashlib


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# Configuration
os.environ['LC_ALL'] = 'C'
os.environ['LANG'] = 'C'

# Constants
CONFIG_FILE = "NANDFix.config"
REQUIRED_DISK_SPACE_GB = 30  # Minimum free space needed
VERSION = "v1.0.3"
USER_PARTITION_FLASH_MB = 100  # Only flash first 100MB of USER partition (filesystem structures)


class CustomDialog:
    """Custom dialog that centers on parent window and follows it if moved."""

    def __init__(self, parent, title, message, dialog_type="info"):
        """
        dialog_type: "info", "warning", "error", "confirm"
        """
        self.parent = parent
        self.result = None
        self.dialog_type = dialog_type

        # Create dialog as transient (modal) to parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)

        # Make it modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Remove window decorations (make it look like a custom popup)
        # self.dialog.overrideredirect(True)  # Optional: removes title bar

        # Configure dialog
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#f0f0f0", highlightbackground="#cccccc",
                            highlightthickness=1)

        # Get message icon based on type
        icon_map = {
            "info": "\u2139\ufe0f",      # Information symbol
            "warning": "\u26a0\ufe0f",   # Warning symbol
            "error": "\u274c",           # Cross mark
            "confirm": "\u2753",         # Question mark
        }

        # Icon colors
        icon_color_map = {
            "info": "#0078d4",      # Blue
            "warning": "#ff8c00",   # Orange
            "error": "#dc3545",     # Red
            "confirm": "#6c757d",   # Gray
        }

        # Main frame
        main_frame = tk.Frame(self.dialog, bg="#f0f0f0", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Icon and message frame
        content_frame = tk.Frame(main_frame, bg="#f0f0f0")
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Icon label
        icon_label = tk.Label(content_frame, text=icon_map.get(dialog_type, ""),
                            font=("Segoe UI", 24),
                            fg=icon_color_map.get(dialog_type, "#000000"),
                            bg="#f0f0f0")
        icon_label.pack(side=tk.LEFT, padx=(0, 15))

        # Message label
        msg_label = tk.Label(content_frame, text=message, font=("Segoe UI", 10),
                           bg="#f0f0f0", fg="#000000", justify=tk.LEFT,
                           wraplength=300)
        msg_label.pack(side=tk.LEFT, padx=(0, 0))

        # Button frame
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(side=tk.BOTTOM, pady=(15, 0))

        # Add buttons based on dialog type
        if dialog_type == "confirm":
            btn_yes = tk.Button(button_frame, text="Yes", font=("Segoe UI", 9),
                              command=self.on_yes, width=10, bg="#0078d4", fg="white",
                              relief="flat", cursor="hand2")
            btn_yes.pack(side=tk.LEFT, padx=5)

            btn_no = tk.Button(button_frame, text="No", font=("Segoe UI", 9),
                             command=self.on_no, width=10, bg="#6c757d", fg="white",
                             relief="flat", cursor="hand2")
            btn_no.pack(side=tk.LEFT, padx=5)
        else:
            # Single OK button with color based on type
            btn_color = "#0078d4" if dialog_type == "info" else \
                       "#ff8c00" if dialog_type == "warning" else "#dc3545"

            btn_ok = tk.Button(button_frame, text="OK", font=("Segoe UI", 9),
                             command=self.on_ok, width=10, bg=btn_color, fg="white",
                             relief="flat", cursor="hand2")
            btn_ok.pack(side=tk.LEFT, padx=5)

        # Position dialog centered on parent
        self._center_on_parent()

        # Track parent movement to recenter
        self._track_parent_movement()

        # Handle close button
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Wait for dialog to close
        self.dialog.wait_window(self.dialog)

    def _center_on_parent(self):
        """Center the dialog on the parent window."""
        self.dialog.update_idletasks()

        # Get parent dimensions and position
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        # Get dialog dimensions
        dialog_width = self.dialog.winfo_reqwidth()
        dialog_height = self.dialog.winfo_reqheight()

        # Calculate centered position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.dialog.geometry(f"+{x}+{y}")

    def _track_parent_movement(self):
        """Track parent window movement and recenter the dialog."""
        if not self.dialog.winfo_exists():
            return

        # Get current parent position
        try:
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()

            # Check if we have a previous position stored
            if hasattr(self, '_last_parent_pos'):
                if (parent_x != self._last_parent_pos[0] or
                    parent_y != self._last_parent_pos[1]):
                    # Parent moved, recenter dialog
                    self._center_on_parent()

            # Store current position
            self._last_parent_pos = (parent_x, parent_y)

            # Continue tracking
            self.dialog.after(50, self._track_parent_movement)
        except tk.TclError:
            # Parent window was destroyed
            pass

    def on_ok(self):
        self.dialog.destroy()

    def on_yes(self):
        self.result = True
        self.dialog.destroy()

    def on_no(self):
        self.result = False
        self.dialog.destroy()

    def _on_close(self):
        """Handle dialog close button."""
        if self.dialog_type == "confirm":
            self.result = False
        self.dialog.destroy()


class NXUnbrickerGUI:

    def log(self, message):
        """Log message to console for debugging."""
        print(f"[NANDFIX] {message}")

    def check_disk_space(self, required_gb=REQUIRED_DISK_SPACE_GB):
        """Check if sufficient disk space is available."""
        try:
            stat = shutil.disk_usage(self.base_path)
            free_gb = stat.free / (1024**3)
            if free_gb < required_gb:
                self.log(f"Disk space check failed: {free_gb:.1f}GB free, {required_gb}GB needed")
                return False, f"Insufficient disk space: {free_gb:.1f}GB free, {required_gb}GB required."
            self.log(f"Disk space check passed: {free_gb:.1f}GB available")
            return True, f"{free_gb:.1f}GB available"
        except Exception as e:
            self.log(f"Disk space check error: {e}")
            # Allow proceeding if check fails (graceful degradation)
            return True, "Disk space check unavailable"

    def load_config(self):
        """Load saved configuration file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.log("Configuration loaded successfully")
                return config
        except Exception as e:
            self.log(f"Failed to load config: {e}")
        return {}

    def save_config(self):
        """Save current configuration."""
        try:
            config = {}
            for key, entry in self.entries.items():
                path = entry.get()
                if path:
                    config[key] = path
            # Save console type
            config['console_type'] = self.console_type.get()
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            self.log("Configuration saved")
        except Exception as e:
            self.log(f"Failed to save config: {e}")

    def validate_prodinfo(self, prodinfo_path):
        """Validate PRODINFO file integrity."""
        try:
            if not os.path.exists(prodinfo_path):
                return False, "File not found"

            with open(prodinfo_path, 'rb') as f:
                magic = f.read(4)

            if magic != b'CAL0':
                return False, "Invalid PRODINFO: File is encrypted or corrupt (missing CAL0 magic)"

            # Check file size (PRODINFO is typically around 8KB-128KB)
            file_size = os.path.getsize(prodinfo_path)
            if file_size < 0x200 or file_size > 0x200000:
                return False, f"Suspicious file size: {file_size} bytes"

            return True, "Valid PRODINFO file"

        except Exception as e:
            return False, f"Validation error: {e}"

    def locate_enc_files(self):
        """Locate all .enc files in the current directory."""
        # <<< IMPROVED: Use self.base_path for consistency
        enc_files_dir = self.base_path
        enc_files = {
            "prodinfof": os.path.join(enc_files_dir, "prodinfof.enc"),
            "prodinfo": os.path.join(enc_files_dir, "prodinfo.enc"),
            "safe": os.path.join(enc_files_dir, "safe.enc"),
            "system": os.path.join(enc_files_dir, "system.enc"),
            "user": os.path.join(enc_files_dir, "user.enc"),
        }

        # Check if all required .enc files exist
        for key, path in enc_files.items():
            if not os.path.exists(path):
                self.create_popup("Build Error", f"Missing {key}.enc file. Ensure all encryption steps completed successfully.", "error")
                return None
        return enc_files

    def __init__(self, root):
        self.root = root
        self.root.title("NANDFIX - The Nintendo Switch Unbricker")
        self.root.geometry("400x480")
        self.root.resizable(False, False)

        # Elapsed time variables
        self.start_time = None

        # <<< IMPROVED: Standardized way to get the base path for all operations
        # Determine the path of the executable or script
        if hasattr(sys, '_MEIPASS'):
            # If the script is running from a PyInstaller bundle, use _MEIPASS
            self.base_path = sys._MEIPASS
        else:
            # Otherwise, use the directory of the current script
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        # Paths for nxnandmanager and EmmcHaccGen.exe
        self.nxnandmanager_path = os.path.join(self.base_path, 'bin', 'nxnandmanager', 'nxnandmanager.exe')
        self.emmc_hacc_gen_path = os.path.join(self.base_path, 'bin', 'emmchaccgen', 'EmmcHaccGen.exe')

        self.log(f"Base path set to: {self.base_path}")
        self.log(f"Full path to nxnandmanager: {self.nxnandmanager_path}")
        self.log(f"Full path to EmmcHaccGen.exe: {self.emmc_hacc_gen_path}")

        self.entries = {}
        # Track operation buttons separately for safer enable/disable
        self.operation_buttons = []

        self.create_widgets()
        self.check_and_delete_files_at_startup()
        self.root.after(100, self.delete_existing_version_folders)

        # Load saved configuration
        self._load_saved_config()

        # Save config on exit
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # GUI Elements
    def create_widgets(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure('.', font="TkDefaultFont")
        if sys.platform == "win32":
            style.theme_use('winnative')

        ttk.Separator(self.root).place(relx=0.025, rely=0.658, relwidth=0.95)

        buttons_info = [
            ("Select Prod.Keys", 0.132),
            ("Select Firmware Folder", 0.236),
            ("Select Donor_Rawnand.bin", 0.342),
            ("Select Donor.Keys", 0.448),
            ("Select Prodinfo", 0.552)
        ]

        for text, rely in buttons_info:
            self.create_button_entry(text, rely)

        operations = ["GENERATE", "DECRYPT", "ENCRYPT", "BUILD"]
        for i, operation in enumerate(operations):
            btn = ttk.Button(self.root, text=operation, width=10, command=lambda op=operation: self.handle_operation(op))
            btn.place(relx=0.025 + (i * 0.25), rely=0.868, height=26, width=80)
            self.operation_buttons.append(btn)

        self.status_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.status_var, maximum=100)
        self.progress_bar.place(relx=0.025, rely=0.708, relwidth=0.95, height=28)

        status_frame = tk.Frame(self.root)
        status_frame.place(relx=0.025, rely=0.768, relwidth=0.95, height=39)

        self.status_label = tk.Label(status_frame, text="", font=("Helvetica", 10))
        self.status_label.pack(side=tk.TOP, anchor="center", expand=True)

        self.elapsed_time_label = tk.Label(status_frame, text="", font=("Helvetica", 10))
        self.elapsed_time_label.pack(side=tk.TOP, anchor="center", expand=True)

        ttk.Label(self.root, text="Select Console Type:", background=self.root["background"]).place(relx=0.05, rely=0.033, height=32, width=124)
        self.console_types = ['Patched & Unpatched V1 (Erista)', 'V2, Lite, OLED (Mariko)']
        self.console_type = ttk.Combobox(self.root, values=self.console_types, font="-family {Segoe UI} -size 9")
        self.console_type.place(relx=0.45, rely=0.033, relheight=0.061, relwidth=0.525)
        self.console_type.current(0)

        self.footer_label = tk.Label(self.root, text=f"{VERSION} sthetix", font=("Helvetica", 10), bg=self.root["background"])
        self.footer_label.pack(side="bottom", pady=5)

    def _load_saved_config(self):
        """Load saved configuration and populate entries."""
        config = self.load_config()
        if config:
            for key, entry in self.entries.items():
                if key in config and config[key]:
                    entry.delete(0, tk.END)
                    entry.insert(0, config[key])
            # Restore console type
            if 'console_type' in config and config['console_type'] in self.console_types:
                self.console_type.set(config['console_type'])

    def _on_closing(self):
        """Handle window closing - save config and cleanup."""
        self.save_config()
        self.root.destroy()

    def create_button_entry(self, text, rely):
        ttk.Button(self.root, text=text, width=20, command=lambda: self.select_file(text)).place(relx=0.025, rely=rely, height=26, width=155)
        entry = tk.Entry(self.root)
        entry.place(relx=0.45, rely=rely, height=26, relwidth=0.525)
        self.entries[text.lower().replace(' ', '_')] = entry

    # File Selection Handling
    def select_file(self, label):
        if 'prod.keys' in label.lower():
            self.select_specific_file(["prod.keys"], "*.keys", self.entries['select_prod.keys'])
        elif 'donor_rawnand.bin' in label.lower():
            self.select_specific_file(["donor_rawnand.bin"], "*.bin", self.entries['select_donor_rawnand.bin'])
        elif 'donor.keys' in label.lower():
            self.select_specific_file(["donor.keys"], "*.keys", self.entries['select_donor.keys'])
        elif 'prodinfo' in label.lower():
            self.select_specific_file(["prodinfo", "prodinfo.bin", "prodinfo.dec"], "*.bin;*.dec;*prodinfo", self.entries['select_prodinfo'])
        elif 'firmware folder' in label.lower():
            path = filedialog.askdirectory()
            if path:
                entry = self.entries[label.lower().replace(' ', '_')]
                entry.delete(0, tk.END)
                entry.insert(0, path)
        else:
            path = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
            if path:
                entry = self.entries[label.lower().replace(' ', '_')]
                entry.delete(0, tk.END)
                entry.insert(0, path)

    def select_specific_file(self, expected_names, file_types, entry):
        path = filedialog.askopenfilename(filetypes=[("Allowed files", file_types)])
        if not path:
            return

        file_name = os.path.basename(path).lower()
        
        is_prod_keys = 'prod.keys' in [name.lower() for name in expected_names]
        is_donor_keys = 'donor.keys' in [name.lower() for name in expected_names]
        is_donor_rawnand = 'donor_rawnand.bin' in [name.lower() for name in expected_names]
        is_prodinfo = 'prodinfo' in [name.lower() for name in expected_names]

        if is_prod_keys and file_name != 'prod.keys':
            self.create_popup("Error", "Please select the correct file named prod.keys", "error")
            return
        elif is_donor_keys and file_name != 'donor.keys':
            self.create_popup("Error", "Please select the correct file named donor.keys", "error")
            return
        elif is_donor_rawnand and file_name != 'donor_rawnand.bin':
            self.create_popup("Error", "Please select the correct file named donor_rawnand.bin", "error")
            return
        elif is_prodinfo:
            if file_name not in ['prodinfo', 'prodinfo.bin', 'prodinfo.dec']:
                self.create_popup("Error", "Please select a correct file named prodinfo, prodinfo.bin, or prodinfo.dec", "error")
                return
            try:
                with open(path, 'rb') as f:
                    if f.read(4) != b'CAL0':
                        self.create_popup("Prodinfo Encrypted", "The loaded prodinfo is ENCRYPTED. Please provide a decrypted prodinfo file.", "warning")
                        return
            except Exception as e:
                self.create_popup("Error", f"Failed to read the prodinfo file: {e}", "error")
                return

        entry.delete(0, tk.END)
        entry.insert(0, path)

    # Deletion of .dec and .enc files at startup
    def check_and_delete_files_at_startup(self):
        files_to_delete = glob.glob("*.dec") + glob.glob("*.enc")
        if files_to_delete:
            if self.create_popup("Delete Files", f"Found {len(files_to_delete)} temporary (.dec, .enc) files. Do you want to delete them?", "confirm"):
                for file in files_to_delete:
                    try:
                        os.remove(file)
                        print(f"Deleted {file}")
                    except Exception as e:
                        self.create_popup("Error", f"Failed to delete file {file}: {e}", "error")

    def delete_existing_version_folders(self):
        # <<< CORRECTED: Use self.base_path for consistent and reliable directory scanning
        script_dir = self.base_path
        pattern = re.compile(r'\d+\.\d+\.\d+.*exfat', re.IGNORECASE)
        print(f"Scanning for old firmware folders in: {script_dir}")
        for item_name in os.listdir(script_dir):
            item_path = os.path.join(script_dir, item_name)
            if os.path.isdir(item_path) and pattern.search(item_name):
                print(f"Deleting old firmware folder: {item_name}")
                try:
                    shutil.rmtree(item_path)
                except Exception as e:
                    self.create_popup("Cleanup Error", f"Failed to delete folder {item_name}: {e}", "error")

    # Operations Handling
    def handle_operation(self, operation):
        # Check disk space before starting any operation
        space_ok, space_msg = self.check_disk_space()
        if not space_ok:
            self.create_popup("Disk Space Warning", space_msg, "warning")
            return

        # Disable all operation buttons to prevent multiple operations
        for btn in self.operation_buttons:
            btn.state(['disabled'])

        op_map = {
            "GENERATE": self.start_generation_thread,
            "DECRYPT": self.start_decryption_thread,
            "ENCRYPT": self.start_encryption_thread,
            "BUILD": self.start_build_thread
        }

        # Run the operation in a thread so it doesn't block the GUI
        thread = threading.Thread(target=op_map[operation])
        thread.start()

        # Poll the thread to see when it's finished, then re-enable buttons
        self.root.after(100, self.check_thread, thread)

    def check_thread(self, thread):
        if thread.is_alive():
            self.root.after(100, self.check_thread, thread)
        else:
            # Re-enable all operation buttons
            for btn in self.operation_buttons:
                btn.state(['!disabled'])

    # Timer and Progress Bar Control
    def start_timer(self):
        self.start_time = time.time()
        self.update_timer()

    def stop_timer(self):
        self.start_time = None

    def update_timer(self):
        if self.start_time is not None:
            elapsed_time = time.time() - self.start_time
            hours, rem = divmod(elapsed_time, 3600)
            minutes, seconds = divmod(rem, 60)
            formatted_time = f"Elapsed time: {int(hours):02}:{int(minutes):02}:{int(seconds):02}"
            self.elapsed_time_label.config(text=formatted_time)
            self.root.after(1000, self.update_timer)

    # <<< IMPROVED: Made GUI updates from other threads thread-safe using self.root.after
    def update_progress(self, value, message=""):
        self.root.after(0, self.status_var.set, value)
        self.root.after(0, self.status_label.config, {'text': message})

    # NAND Generation
    def start_generation_thread(self):
        self.delete_existing_version_folders()
        prod_keys = self.entries['select_prod.keys'].get()
        firmware_folder = self.entries['select_firmware_folder'].get()
        if not prod_keys or not firmware_folder:
            self.create_popup("Input Required", "Please select both prod.keys file and firmware folder.", "error")
            return
        self.run_generation(prod_keys, firmware_folder, self.console_type.get())

    def run_generation(self, prod_keys, firmware_folder, console_type):
        # Validate inputs exist
        if not os.path.exists(prod_keys):
            self.create_popup("Error", f"prod.keys file not found:\n{prod_keys}", "error")
            return
        if not os.path.exists(firmware_folder):
            self.create_popup("Error", f"Firmware folder not found:\n{firmware_folder}", "error")
            return
        if not os.path.exists(self.emmc_hacc_gen_path):
            self.create_popup("Error", f"EmmcHaccGen.exe not found at {self.emmc_hacc_gen_path}", "error")
            return

        self.start_timer()
        self.update_progress(0, "Starting NAND files generation...")

        try:
            self.generate_nand(prod_keys, firmware_folder, self.emmc_hacc_gen_path, console_type)
            self.update_progress(100, "NAND files generation complete.")
            self.create_popup("Generation Complete", "NAND files generation process completed successfully.", "info")
        except Exception as e:
            self.update_progress(0, "Generation failed.")
            self.create_popup("Generation Error", f"An error occurred during NAND files generation:\n{e}", "error")
            self.log(f"Generation error: {e}")
        finally:
            self.stop_timer()

    def generate_nand(self, prod_keys, firmware_folder, emmc_hacc_gen_path, console_type):
        # <<< IMPROVED: Switched to a list of args instead of shell=True for better security and reliability
        base_command = [emmc_hacc_gen_path, "--keys", prod_keys, "--fw", firmware_folder]
        if console_type == "Patched & Unpatched V1 (Erista)":
            command_list = base_command + ["--no-autorcm"]
        elif console_type == "V2, Lite, OLED (Mariko)":
            command_list = base_command + ["--mariko"]
        else: # Should not happen with a combobox, but good to have a fallback
            command_list = base_command

        self.log(f"Executing command: {' '.join(command_list)}")
        process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)

        last_progress = 0
        for line in iter(process.stdout.readline, ''):
            line_stripped = line.strip()
            if line_stripped:
                self.log(line_stripped)
            if "Progress:" in line:
                try:
                    progress = int(line.split("Progress:")[1].split("%")[0].strip())
                    self.update_progress(progress, "Generating NAND...")
                    last_progress = progress
                except (ValueError, IndexError):
                    self.log(f"Could not parse progress from line: {line_stripped}")

        process.wait()
        process.stdout.close()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command_list)

    # NAND Decryption, Encryption, and Build methods remain largely the same logically,
    # but they will benefit from the thread-safe `update_progress` and robust button handling.
    # The structure below is kept for completeness.

    def start_decryption_thread(self):
        donor_rawnand = self.entries['select_donor_rawnand.bin'].get()
        donor_prod_keys = self.entries['select_donor.keys'].get()
        if not donor_rawnand or not donor_prod_keys:
            self.create_popup("Error", "Donor rawnand.bin or donor.keys not provided.", "error")
            return

        # Validate inputs exist
        if not os.path.exists(donor_rawnand):
            self.create_popup("Error", f"Donor rawnand.bin not found:\n{donor_rawnand}", "error")
            return
        if not os.path.exists(donor_prod_keys):
            self.create_popup("Error", f"donor.keys not found:\n{donor_prod_keys}", "error")
            return
        if not os.path.exists(self.nxnandmanager_path):
            self.create_popup("Error", f"nxnandmanager.exe not found:\n{self.nxnandmanager_path}", "error")
            return

        self.run_decryption()

    def run_decryption(self):
        self.start_timer()
        self.update_progress(0, "Starting decryption...")
        try:
            self.decrypt_nand(self.entries, self.update_progress)
            self.update_progress(100, "Decryption complete.")
            self.create_popup("Decryption Complete", "Decryption process completed successfully.\nYou can now proceed with the encryption.", "info")
        except Exception as e:
            self.update_progress(0, "Decryption failed.")
            self.create_popup("Decryption Error", f"An error occurred during decryption:\n{e}", "error")
            self.log(f"Decryption error: {e}")
        finally:
            self.stop_timer()

    def decrypt_nand(self, entries, update_progress):
        donor_rawnand = entries['select_donor_rawnand.bin'].get()
        donor_prod_keys = entries['select_donor.keys'].get()

        # All subprocess calls in decrypt, encrypt, and build are already using the safer list-based format.
        decryption_commands = [
            ["-i", donor_rawnand, "-o", "prodinfof.dec", "-d", "-keyset", donor_prod_keys, "-part=prodinfof"],
            ["-i", donor_rawnand, "-o", "safe.dec", "-d", "-keyset", donor_prod_keys, "-part=safe"],
            ["-i", donor_rawnand, "-o", "system.dec", "-d", "-keyset", donor_prod_keys, "-part=system"],
            ["-i", donor_rawnand, "-o", "user.dec", "-d", "-keyset", donor_prod_keys, "-part=user"]
        ]

        expected_outputs = ["prodinfof.dec", "safe.dec", "system.dec", "user.dec"]

        for i, command_args in enumerate(decryption_commands):
            command = [self.nxnandmanager_path] + command_args
            self.log(f"Running command: {' '.join(command)}")
            result = subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
            if result.stderr:
                self.log(f"Warning/Error from nxnandmanager: {result.stderr}")

            # Verify output file was created
            partition_name = command_args[7].split('=')[1]
            expected_file = expected_outputs[i]
            if not os.path.exists(os.path.join(self.base_path, expected_file)):
                raise FileNotFoundError(f"Expected output file '{expected_file}' was not created")

            update_progress((i + 1) / len(decryption_commands) * 100, f"Decrypting {partition_name}...")

        self.log("Decryption completed successfully.")
        
    def start_encryption_thread(self):
        prod_keys = self.entries['select_prod.keys'].get()
        prodinfo = self.entries['select_prodinfo'].get()
        if not prod_keys or not prodinfo:
            self.create_popup("Error", "prod.keys or prodinfo not provided.", "error")
            return

        # Validate inputs exist
        if not os.path.exists(prod_keys):
            self.create_popup("Error", f"prod.keys not found:\n{prod_keys}", "error")
            return
        if not os.path.exists(prodinfo):
            self.create_popup("Error", f"prodinfo not found:\n{prodinfo}", "error")
            return

        # Validate PRODINFO integrity
        valid, msg = self.validate_prodinfo(prodinfo)
        if not valid:
            self.create_popup("PRODINFO Error", msg, "error")
            return

        # Check required .dec files exist from previous step
        required_dec_files = ["prodinfof.dec", "safe.dec", "system.dec", "user.dec"]
        missing_files = []
        for dec_file in required_dec_files:
            if not os.path.exists(os.path.join(self.base_path, dec_file)):
                missing_files.append(dec_file)
        if missing_files:
            self.create_popup("Missing Files", f"Required decrypted files not found:\n{', '.join(missing_files)}\n\nPlease run DECRYPT first.", "error")
            return

        if not os.path.exists(self.nxnandmanager_path):
            self.create_popup("Error", f"nxnandmanager.exe not found:\n{self.nxnandmanager_path}", "error")
            return

        self.run_encryption()

    def run_encryption(self):
        self.start_timer()
        self.update_progress(0, "Starting encryption...")
        try:
            self.encrypt_nand(self.entries, self.update_progress)
            self.update_progress(100, "Encryption complete.")
            self.create_popup("Encryption Complete", "Encryption process completed successfully.\nYou can now proceed with the build.", "info")
        except Exception as e:
            self.update_progress(0, "Encryption failed.")
            self.create_popup("Encryption Error", f"An error occurred during encryption:\n{e}", "error")
            self.log(f"Encryption error: {e}")
        finally:
            self.stop_timer()

    def encrypt_nand(self, entries, update_progress):
        prod_keys = entries['select_prod.keys'].get()
        prodinfo_path = entries['select_prodinfo'].get()

        encryption_commands = [
            ["-i", prodinfo_path, "-o", "prodinfo.enc", "-e", "-keyset", prod_keys],
            ["-i", "prodinfof.dec", "-o", "prodinfof.enc", "-e", "-keyset", prod_keys],
            ["-i", "safe.dec", "-o", "safe.enc", "-e", "-keyset", prod_keys],
            ["-i", "system.dec", "-o", "system.enc", "-e", "-keyset", prod_keys],
            ["-i", "user.dec", "-o", "user.enc", "-e", "-keyset", prod_keys]
        ]

        expected_outputs = ["prodinfo.enc", "prodinfof.enc", "safe.enc", "system.enc", "user.enc"]

        for i, command_args in enumerate(encryption_commands):
            command = [self.nxnandmanager_path] + command_args
            self.log(f"Running command: {' '.join(command)}")
            subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)

            # Verify output file was created
            expected_file = expected_outputs[i]
            if not os.path.exists(os.path.join(self.base_path, expected_file)):
                raise FileNotFoundError(f"Expected output file '{expected_file}' was not created")

            update_progress((i + 1) / len(encryption_commands) * 100, f"Encrypting {os.path.basename(command_args[1])}...")

        self.log("Encryption completed successfully.")

    def start_build_thread(self):
        if not self.locate_enc_files():
            return

        # Validate donor rawnand exists
        donor_rawnand = self.entries['select_donor_rawnand.bin'].get()
        if not donor_rawnand or not os.path.exists(donor_rawnand):
            self.create_popup("Build Error", f"Donor rawnand.bin not found:\n{donor_rawnand}", "error")
            return

        # Validate nxnandmanager exists
        if not os.path.exists(self.nxnandmanager_path):
            self.create_popup("Error", f"nxnandmanager.exe not found:\n{self.nxnandmanager_path}", "error")
            return

        self.run_build_process()

    def run_build_process(self):
        self.start_timer()
        self.update_progress(0, "Starting build process...")
        try:
            build_successful = self.build_nand(self.entries, self.update_progress)
            if build_successful:
                self.update_progress(100, "Build complete.")
                self.create_popup("Build Complete", "Build process completed successfully.\nrawnand.bin has been created.", "info")
                self.cleanup_after_build()
        except Exception as e:
            self.update_progress(0, "Build failed.")
            self.create_popup("Build Error", f"An error occurred during the build process:\n{e}", "error")
            self.log(f"Build error: {e}")
        finally:
            self.stop_timer()

    def _run_and_interrupt_flash(self, command, partition_name, target_mb, update_progress):
        """
        Run a flash command and interrupt it after reaching target_mb.
        This is used for the USER partition since only the first ~100MB
        contains critical filesystem structures. This saves significant time.

        Args:
            command: List of command arguments
            partition_name: Name of partition for progress matching
            target_mb: MB threshold after which to terminate the process
            update_progress: Callback function for progress updates

        Returns:
            0 on success, -1 on error
        """
        self.log(f"--- Starting partial flash for {partition_name} with a {target_mb}MB target...")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Pattern to match progress output from nxnandmanager
            # It outputs progress like: "Building user... 45.23 MB"
            progress_regex = re.compile(rf'{partition_name}.*?(\d+\.?\d*)\s*MB', re.IGNORECASE)

            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                clean_line = line.strip()
                if clean_line:
                    self.log(clean_line)

                # Check for progress in the output
                match = progress_regex.search(clean_line)
                if match:
                    try:
                        mb_written = float(match.group(1))
                        # Update progress (scale to 100% at target_mb)
                        progress_pct = min((mb_written / target_mb) * 100, 100)
                        update_progress(progress_pct, f"Building {partition_name}... ({mb_write:.1f}/{target_mb}MB)")

                        # Check if we've reached the target
                        if mb_written >= target_mb:
                            self.log(f"--- SUCCESS: Reached {target_mb}MB target. Terminating flash early...")
                            process.terminate()
                            break
                    except ValueError:
                        pass

            # Wait for process to finish
            try:
                process.wait(timeout=5)
            except:
                process.kill()

            process.stdout.close()
            self.log(f"--- Partial flash for {partition_name} complete (first {target_mb}MB).")
            return 0

        except Exception as e:
            self.log(f"FATAL ERROR during interruptible flash: {e}")
            try:
                process.kill()
            except:
                pass
            return -1

    def build_nand(self, entries, update_progress):
        original_donor_rawnand_path = entries['select_donor_rawnand.bin'].get()
        if not original_donor_rawnand_path or not os.path.exists(original_donor_rawnand_path):
            self.create_popup("Build Error", "Original donor_rawnand.bin not provided or does not exist.", "error")
            return False

        # <<< CORRECTED: Use self.base_path for consistency
        enc_files_dir = self.base_path
        enc_files = self.locate_enc_files()
        if not enc_files: return False

        build_commands = [
            ["-i", enc_files['prodinfof'], "-o", original_donor_rawnand_path, "-part=PRODINFOF", "FORCE"],
            ["-i", enc_files['prodinfo'], "-o", original_donor_rawnand_path, "-part=PRODINFO", "FORCE"],
            ["-i", enc_files['safe'], "-o", original_donor_rawnand_path, "-part=safe", "FORCE"],
            ["-i", enc_files['system'], "-o", original_donor_rawnand_path, "-part=system", "FORCE"],
            ["-i", enc_files['user'], "-o", original_donor_rawnand_path, "-part=user", "FORCE"]
        ]

        total_commands = len(build_commands)

        for i, command_args in enumerate(build_commands):
            command = [self.nxnandmanager_path] + command_args
            partition_name = command_args[5].split('=')[1]
            self.log(f"Running command: {' '.join(command)}")

            # USER partition: Use interruptible flash (only first 100MB)
            # This saves significant time as USER partition is ~25GB but only
            # the first ~100MB contains critical filesystem structures
            if partition_name.lower() == "user":
                self.log(f"--- USER PARTITION: Using optimized flash (first {USER_PARTITION_FLASH_MB}MB only) ---")
                result_code = self._run_and_interrupt_flash(
                    command,
                    "user",
                    USER_PARTITION_FLASH_MB,
                    lambda p, msg: update_progress(((i + p/100) / total_commands) * 100, msg)
                )
                if result_code != 0:
                    raise subprocess.CalledProcessError(result_code, command)
            else:
                # Normal flash for other partitions
                result = subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
                if result.stderr:
                    self.log(f"Warning/Error from nxnandmanager: {result.stderr}")
                update_progress((i + 1) / total_commands * 100, f"Building {partition_name}...")

        donor_rawnand_dir = os.path.dirname(original_donor_rawnand_path)
        final_rawnand_path = os.path.join(donor_rawnand_dir, "rawnand.bin")

        # Delete existing rawnand.bin if it exists
        if os.path.exists(final_rawnand_path):
            self.log(f"Removing existing {final_rawnand_path}")
            try:
                os.remove(final_rawnand_path)
            except Exception as e:
                self.log(f"Warning: Could not remove existing rawnand.bin: {e}")

        self.log(f"Renaming {original_donor_rawnand_path} to {final_rawnand_path}")
        os.rename(original_donor_rawnand_path, final_rawnand_path)

        # Verify final file was created
        if not os.path.exists(final_rawnand_path):
            raise FileNotFoundError(f"Final rawnand.bin was not created at {final_rawnand_path}")

        # Clear the entry field so the old path isn't reused by mistake
        entries['select_donor_rawnand.bin'].delete(0, tk.END)

        self.log("Build process completed successfully.")
        return True

    def cleanup_after_build(self):
        self.log("Cleaning up temporary files...")
        files_to_delete = glob.glob(os.path.join(self.base_path, "*.dec")) + glob.glob(os.path.join(self.base_path, "*.enc"))
        deleted_count = 0
        for file in files_to_delete:
            try:
                os.remove(file)
                self.log(f"Deleted {file}")
                deleted_count += 1
            except OSError as e:
                self.log(f"Error deleting file {file}: {e}")
        self.log(f"Cleanup complete: {deleted_count} files deleted")

    # monitor_file_size is no longer needed as we are processing user partition in a blocking way.
    # It was a workaround for a non-blocking process that is no longer used.

    # Popup and Confirmation Handling
    def create_popup(self, title, message, popup_type="info"):
        """
        Create a custom popup dialog centered on the main window.
        popup_type: "info", "warning", "error", "confirm"
        Returns: None for info/warning/error, True/False for confirm
        """
        self.log(f"[{title}] {message}")

        dialog = CustomDialog(self.root, title, message, popup_type)

        if popup_type == "confirm":
            return dialog.result
        return None

if __name__ == "__main__":
    root = tk.Tk()
    app = NXUnbrickerGUI(root)
    root.mainloop()