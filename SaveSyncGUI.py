import os
import sys
import shutil
import ftplib
import io
import zipfile
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Auto-install dependencies
import platform
try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
except ImportError:
    print("Installing pycryptodome...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "pycryptodome"]
    if platform.system() != "Windows":
        pip_cmd.append("--break-system-packages")
    subprocess.check_call(pip_cmd)
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes

# Portable Directories
if getattr(sys, 'frozen', False):
    CULT_SYNC_DIR = os.path.dirname(sys.executable)
else:
    CULT_SYNC_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(CULT_SYNC_DIR, "config.json")
if platform.system() == "Windows":
    PC_SAVE_DIR = os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Massive Monster\Cult Of The Lamb\saves")
else:
    _home = os.path.expanduser("~")
    _proton_path = os.path.join(_home, ".local/share/Steam/steamapps/compatdata/1313140/pfx/drive_c/users/steamuser/AppData/LocalLow/Massive Monster/Cult Of The Lamb/saves")
    _native_path = os.path.join(_home, ".config/unity3d/Massive Monster/Cult Of The Lamb/saves")
    if os.path.exists(_proton_path):
        PC_SAVE_DIR = _proton_path
    elif os.path.exists(_native_path):
        PC_SAVE_DIR = _native_path
    else:
        PC_SAVE_DIR = _proton_path
BACKUPS_DIR = os.path.join(CULT_SYNC_DIR, "backups")

class SaveSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cult of the Lamb Save Sync & Backup Utility")
        self.root.geometry("850x650")
        self.root.configure(bg="#181825")
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Color palette (Catppuccin Mocha)
        self.bg_color = "#181825"
        self.card_color = "#1e1e2e"
        self.text_color = "#cdd6f4"
        self.green = "#a6e3a1"
        self.blue = "#89b4fa"
        self.red = "#f38ba8"
        self.accent = "#b4befe"
        
        # Ttk styling
        self.style.configure('.', background=self.card_color, foreground=self.text_color)
        self.style.configure('TLabel', background=self.card_color, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure('Header.TLabel', font=("Segoe UI", 12, "bold"), foreground=self.accent)
        self.style.configure('TEntry', fieldbackground="#313244", foreground=self.text_color, insertcolor=self.text_color)
        
        # Load config
        self.config = self.load_config()
        
        self.setup_ui()
        self.refresh_backups_list()
        self.log("Utility started successfully. Ready to sync.")

    def load_config(self):
        import json
        default_config = {
            "switch_ip": "192.168.1.183",
            "ftp_port": 5000,
            "profile_name": "sanchos",
            "jksv_folder": "/JKSV/Cult of the Lamb"
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    default_config.update(json.load(f))
            except Exception as e:
                self.log(f"Error loading config.json: {e}")
        return default_config

    def save_config(self):
        import json
        self.config["switch_ip"] = self.ip_entry.get().strip()
        try:
            self.config["ftp_port"] = int(self.port_entry.get().strip())
        except ValueError:
            pass
        self.config["profile_name"] = self.profile_entry.get().strip()
        self.config["jksv_folder"] = self.jksv_entry.get().strip()
        
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.log("Settings saved to config.json.")
        except Exception as e:
            self.log(f"Failed to save settings: {e}")

    def setup_ui(self):
        # Main Layout split
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Left Panel (Switch Sync)
        left_panel = tk.Frame(main_frame, bg=self.card_color, bd=1, relief=tk.SOLID, highlightbackground="#313244")
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.48, relheight=0.6)
        
        # Left Panel Header
        lbl = ttk.Label(left_panel, text="Switch FTP Sync Settings", style="Header.TLabel")
        lbl.pack(anchor=tk.W, padx=15, pady=10)
        
        # Form Fields
        fields_frame = tk.Frame(left_panel, bg=self.card_color)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=15)
        
        ttk.Label(fields_frame, text="Switch IP-Address:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ip_entry = ttk.Entry(fields_frame)
        self.ip_entry.insert(0, self.config["switch_ip"])
        self.ip_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(fields_frame, text="FTP Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.port_entry = ttk.Entry(fields_frame)
        self.port_entry.insert(0, str(self.config["ftp_port"]))
        self.port_entry.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(fields_frame, text="JKSV Profile Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.profile_entry = ttk.Entry(fields_frame)
        self.profile_entry.insert(0, self.config["profile_name"])
        self.profile_entry.grid(row=2, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(fields_frame, text="JKSV SD Path:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.jksv_entry = ttk.Entry(fields_frame)
        self.jksv_entry.insert(0, self.config["jksv_folder"])
        self.jksv_entry.grid(row=3, column=1, sticky=tk.EW, pady=5, padx=5)
        
        fields_frame.columnconfigure(1, weight=1)
        
        # Action Buttons Layout (Side by Side)
        left_btn_frame = tk.Frame(left_panel, bg=self.card_color)
        left_btn_frame.pack(fill=tk.X, padx=15, pady=15)
        
        self.sync_btn = tk.Button(left_btn_frame, text="📥 Switch ➔ PC Sync", font=("Segoe UI", 10, "bold"),
                                  bg=self.green, fg="#11111b", activebackground="#a6e3a1", bd=0, cursor="hand2",
                                  command=self.run_switch_sync)
        self.sync_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.export_btn = tk.Button(left_btn_frame, text="📤 PC ➔ Switch Sync", font=("Segoe UI", 10, "bold"),
                                    bg=self.accent, fg="#11111b", activebackground="#b4befe", bd=0, cursor="hand2",
                                    command=self.run_pc_to_switch_sync)
        self.export_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Right Panel (PC Backups)
        right_panel = tk.Frame(main_frame, bg=self.card_color, bd=1, relief=tk.SOLID, highlightbackground="#313244")
        right_panel.place(relx=0.52, rely=0.0, relwidth=0.48, relheight=0.6)
        
        # Right Panel Header
        lbl2 = ttk.Label(right_panel, text="PC Save Backups Manager", style="Header.TLabel")
        lbl2.pack(anchor=tk.W, padx=15, pady=10)
        
        # List of Backups
        list_frame = tk.Frame(right_panel, bg=self.card_color)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15)
        
        self.backups_listbox = tk.Listbox(list_frame, bg="#313244", fg=self.text_color, bd=0,
                                          selectbackground=self.accent, selectforeground="#11111b",
                                          font=("Segoe UI", 10))
        self.backups_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.backups_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.backups_listbox.config(yscrollcommand=scrollbar.set)
        
        # Backup actions
        btn_frame = tk.Frame(right_panel, bg=self.card_color)
        btn_frame.pack(fill=tk.X, padx=15, pady=15)
        
        self.backup_btn = tk.Button(btn_frame, text="💾 Backup PC Saves", font=("Segoe UI", 10, "bold"),
                                    bg=self.blue, fg="#11111b", activebackground="#89b4fa", bd=0, cursor="hand2",
                                    command=self.create_pc_backup)
        self.backup_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.restore_btn = tk.Button(btn_frame, text="🔄 Restore Selected", font=("Segoe UI", 10, "bold"),
                                     bg=self.accent, fg="#11111b", activebackground="#b4befe", bd=0, cursor="hand2",
                                     command=self.restore_pc_backup)
        self.restore_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Log Console (Bottom)
        console_frame = tk.Frame(main_frame, bg=self.card_color, bd=1, relief=tk.SOLID, highlightbackground="#313244")
        console_frame.place(relx=0.0, rely=0.65, relwidth=1.0, relheight=0.35)
        
        console_header_frame = tk.Frame(console_frame, bg=self.card_color)
        console_header_frame.pack(fill=tk.X, padx=15, pady=5)
        
        lbl3 = ttk.Label(console_header_frame, text="Console Log Output", style="Header.TLabel")
        lbl3.pack(side=tk.LEFT)
        
        lbl_author = ttk.Label(console_header_frame, text="Made by Sanchos from sanchos.su", font=("Segoe UI", 9, "italic"), foreground="#a6adc8")
        lbl_author.pack(side=tk.RIGHT)
        
        self.log_area = scrolledtext.ScrolledText(console_frame, bg="#11111b", fg=self.text_color, bd=0,
                                                  insertbackground=self.text_color, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def run_switch_sync(self):
        self.save_config()
        self.sync_btn.config(state=tk.DISABLED, text="Syncing...")
        self.log("Starting Switch Synchronization workflow...")
        
        # Clean up any existing patched files to prevent stale deployment
        if os.path.exists(CULT_SYNC_DIR):
            for f in os.listdir(CULT_SYNC_DIR):
                if f.endswith("_patched.bin"):
                    try:
                        os.remove(os.path.join(CULT_SYNC_DIR, f))
                    except Exception:
                        pass
        
        try:
            # 1. Connect to FTP
            ip = self.config["switch_ip"]
            port = self.config["ftp_port"]
            self.log(f"Connecting to Switch FTP at {ip}:{port}...")
            ftp = ftplib.FTP()
            ftp.connect(ip, port, timeout=10)
            ftp.login()
            
            # 2. Locate backup
            self.log("Searching JKSV backups folder...")
            jksv_folder = self.config["jksv_folder"]
            try:
                ftp.cwd(jksv_folder)
            except Exception:
                self.log(f"JKSV folder '{jksv_folder}' not found! Trying common roots...")
                found = False
                for r in ["/JKSV", "/JKSV/Cult Of The Lamb", "/JKSV/Cult of the Lamb"]:
                    try:
                        ftp.cwd(r)
                        jksv_folder = r
                        found = True
                        break
                    except Exception:
                        pass
                if not found:
                    raise Exception("Could not find Cult of the Lamb saves under /JKSV/ on SD card.")
            
            files = ftp.nlst()
            prefix = f"{self.config['profile_name']} - "
            zips = [f for f in files if os.path.basename(f).startswith(prefix) and f.endswith(".zip")]
            
            if not zips:
                raise Exception(f"No zip archives found matching '{prefix}*.zip' in {jksv_folder}")
            
            zips.sort()
            latest_zip = zips[-1]
            self.log(f"Found latest backup: {latest_zip}")
            
            # 3. Download
            self.log("Downloading backup archive...")
            zip_buffer = io.BytesIO()
            ftp.retrbinary(f"RETR {latest_zip}", zip_buffer.write)
            ftp.quit()
            self.log("Download completed successfully.")
            
            # Save a local zip copy for security
            os.makedirs(CULT_SYNC_DIR, exist_ok=True)
            local_zip = os.path.join(CULT_SYNC_DIR, os.path.basename(latest_zip))
            with open(local_zip, "wb") as f:
                f.write(zip_buffer.getvalue())
            self.log(f"Backup zip saved locally to: {local_zip}")
            
            # 4. Extract
            self.log("Extracting Switch save files...")
            temp_dir = os.path.join(CULT_SYNC_DIR, "temp_extracted")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            
            zip_buffer.seek(0)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                zf.extractall(temp_dir)
            self.log("Save files extracted to temp directory.")
            
            # 5. Run Patcher (Node.js)
            self.log("Executing Node.js patcher script (patch_switch_binary.js)...")
            patcher_script = os.path.join(CULT_SYNC_DIR, "patch_switch_binary.js")
            if not os.path.exists(patcher_script):
                raise Exception("patch_switch_binary.js not found in sync folder!")
                
            result = subprocess.run(["node", "patch_switch_binary.js", "s2p"], cwd=CULT_SYNC_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise Exception(f"Node.js patcher failed: {result.stderr}")
                
            self.log("Save files successfully patched and re-compressed.")
            self.log(result.stdout.strip())
            
            # 6. Encrypt and Deploy
            self.log("Encrypting files and deploying to active PC saves folder...")
            self.encrypt_and_deploy_saves()
            self.log("[Success] Saves synced and deployed natively!")
            messagebox.showinfo("Sync Success", "Saves successfully imported from Switch, patched, and deployed natively!\nMake sure Steam Cloud is off before starting.")
            
            # Clean up temp
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            self.log(f"Error during synchronization: {e}")
            messagebox.showerror("Sync Error", f"Failed to sync saves:\n{e}")
            
        finally:
            self.sync_btn.config(state=tk.NORMAL, text="📥 Switch ➔ PC Sync")
            self.refresh_backups_list()

    def encrypt_file_payload(self, raw_data):
        # Strip MP platform header if present
        if raw_data.startswith(b'MP'):
            raw_data = raw_data[2:]
            
        # PKCS7 Padding
        pad_len = 16 - (len(raw_data) % 16)
        padded_data = raw_data + bytes([pad_len] * pad_len)
        
        key = get_random_bytes(16)
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(padded_data)
        
        return b'E' + key + iv + ciphertext

    def encrypt_and_deploy_saves(self):
        # Dynamically scan CULT_SYNC_DIR for patched save files
        files_to_process = {}
        if os.path.exists(CULT_SYNC_DIR):
            for file_name in os.listdir(CULT_SYNC_DIR):
                if file_name.endswith("_patched.bin"):
                    src_path = os.path.join(CULT_SYNC_DIR, file_name)
                    base_name = file_name.replace("_patched.bin", "")
                    if base_name.startswith("slot_"):
                        num = base_name.replace("slot_", "").replace("MP", "")
                        files_to_process[src_path] = f"slot_{num}.mp"
                    elif base_name.startswith("meta_"):
                        num = base_name.replace("meta_", "").replace("MP", "")
                        files_to_process[src_path] = f"meta_{num}.mp"
        
        # Check for persistence in temp_extracted
        persistence_src = os.path.join(CULT_SYNC_DIR, "temp_extracted", "persistence")
        if os.path.exists(persistence_src):
            files_to_process[persistence_src] = "persistence"
        
        # Backup settings.json first
        settings_path = os.path.join(PC_SAVE_DIR, "settings.json")
        settings_data = None
        if os.path.exists(settings_path):
            with open(settings_path, "rb") as f:
                settings_data = f.read()
                
        # Backup existing saves as PC backup before overwriting
        self.create_pc_backup(silent=True)
        
        # Clear PC saves folder
        if os.path.exists(PC_SAVE_DIR):
            for f in os.listdir(PC_SAVE_DIR):
                fp = os.path.join(PC_SAVE_DIR, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                elif os.path.isdir(fp):
                    shutil.rmtree(fp)
        else:
            os.makedirs(PC_SAVE_DIR, exist_ok=True)
            
        # Process and deploy files
        for src, target in files_to_process.items():
            if not os.path.exists(src):
                self.log(f"  [Warning] Missing {os.path.basename(src)}, skipping.")
                continue
            with open(src, "rb") as f:
                raw_data = f.read()
                
            enc_data = self.encrypt_file_payload(raw_data)
            dst_path = os.path.join(PC_SAVE_DIR, target)
            with open(dst_path, "wb") as f:
                f.write(enc_data)
            self.log(f"  Deployed encrypted {target} ({len(enc_data)} bytes)")
            
        # Restore settings.json
        if settings_data:
            with open(settings_path, "wb") as f:
                f.write(settings_data)
            self.log("  Restored settings.json.")

    def create_pc_backup(self, silent=False):
        if not os.path.exists(PC_SAVE_DIR) or len(os.listdir(PC_SAVE_DIR)) == 0:
            if not silent:
                messagebox.showwarning("Backup Cancelled", "PC saves directory is empty! Nothing to backup.")
            return
            
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = os.path.join(BACKUPS_DIR, f"PC_Backup_{timestamp}")
        
        try:
            shutil.copytree(PC_SAVE_DIR, backup_path)
            self.log(f"Created PC saves backup: PC_Backup_{timestamp}")
            if not silent:
                messagebox.showinfo("Backup Created", f"PC saves backed up successfully to:\n{backup_path}")
        except Exception as e:
            self.log(f"Error creating PC saves backup: {e}")
            if not silent:
                messagebox.showerror("Backup Error", f"Failed to backup PC saves:\n{e}")
                
        self.refresh_backups_list()

    def restore_pc_backup(self):
        selection = self.backups_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup from the list to restore.")
            return
            
        backup_name = self.backups_listbox.get(selection[0])
        if backup_name == "FINAL_WORKING_BACKUP":
            backup_path = os.path.join(CULT_SYNC_DIR, "FINAL_WORKING_BACKUP")
        else:
            backup_path = os.path.join(BACKUPS_DIR, backup_name)
        
        confirm = messagebox.askyesno("Restore Save", f"Are you sure you want to restore backup:\n{backup_name}?\n\nThis will overwrite your current active saves!")
        if not confirm:
            return
            
        self.log(f"Restoring save backup: {backup_name}...")
        try:
            # Clear current saves folder
            if os.path.exists(PC_SAVE_DIR):
                for f in os.listdir(PC_SAVE_DIR):
                    fp = os.path.join(PC_SAVE_DIR, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                    elif os.path.isdir(fp):
                        shutil.rmtree(fp)
            else:
                os.makedirs(PC_SAVE_DIR, exist_ok=True)
                
            # Copy backup files
            for item in os.listdir(backup_path):
                s = os.path.join(backup_path, item)
                d = os.path.join(PC_SAVE_DIR, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
                    
            self.log(f"Backup restored successfully: {backup_name}")
            messagebox.showinfo("Restore Success", f"Save backup restored successfully:\n{backup_name}")
        except Exception as e:
            self.log(f"Failed to restore backup: {e}")
            messagebox.showerror("Restore Error", f"Failed to restore backup:\n{e}")

    def run_pc_to_switch_sync(self):
        self.save_config()
        self.export_btn.config(state=tk.DISABLED, text="Exporting...")
        self.sync_btn.config(state=tk.DISABLED)
        self.log("Starting PC to Switch Export workflow...")
        
        try:
            # 1. Run Node.js patcher in PC to Switch mode (p2s)
            self.log("Executing Node.js patcher in PC to Switch mode...")
            result = subprocess.run(
                ["node", "patch_switch_binary.js", "p2s"],
                cwd=CULT_SYNC_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                raise Exception(f"Node.js patcher failed: {result.stderr}")
                
            self.log("PC saves patched, LZ4 compressed, and packed.")
            self.log(result.stdout.strip())
            
            # Find the ZIP path from stdout
            zip_path = None
            for line in result.stdout.split('\n'):
                if line.startswith("ZIP_PATH:"):
                    zip_path = line.split("ZIP_PATH:")[1].strip()
                    break
                    
            if not zip_path or not os.path.exists(zip_path):
                raise Exception("Could not find generated Switch backup ZIP path in patcher output.")
                
            # 2. Connect to FTP
            ip = self.config["switch_ip"]
            port = self.config["ftp_port"]
            self.log(f"Connecting to Switch FTP at {ip}:{port}...")
            ftp = ftplib.FTP()
            ftp.connect(ip, port, timeout=10)
            ftp.login()
            
            # 3. Locate / create JKSV directory
            self.log("Searching JKSV backups folder on SD card...")
            jksv_folder = self.config["jksv_folder"]
            try:
                ftp.cwd(jksv_folder)
            except Exception:
                self.log(f"JKSV folder '{jksv_folder}' not found! Trying common roots...")
                found = False
                for r in ["/JKSV/Cult of the Lamb", "/JKSV/Cult Of The Lamb", "/JKSV"]:
                    try:
                        ftp.cwd(r)
                        jksv_folder = r
                        found = True
                        break
                    except Exception:
                        pass
                if not found:
                    raise Exception("Could not find JKSV folder on SD card. Please make a JKSV backup first.")
            
            # 4. Upload zip file
            zip_name = os.path.basename(zip_path)
            self.log(f"Uploading {zip_name} to Switch FTP...")
            with open(zip_path, "rb") as f:
                ftp.storbinary(f"STOR {zip_name}", f)
            ftp.quit()
            
            self.log(f"[Success] Save backup uploaded to Switch: {zip_name}")
            messagebox.showinfo("Export Success", f"Saves successfully exported and uploaded to Switch!\n\nArchive name: {zip_name}\n\nNow, open JKSV on your Switch and RESTORE this backup to import it into your game.")
            
        except Exception as e:
            self.log(f"Error during export: {e}")
            messagebox.showerror("Export Error", f"Failed to export saves to Switch:\n{e}")
            
        finally:
            self.export_btn.config(state=tk.NORMAL, text="📤 PC ➔ Switch Sync")
            self.sync_btn.config(state=tk.NORMAL)

    def refresh_backups_list(self):
        self.backups_listbox.delete(0, tk.END)
        
        # Include FINAL_WORKING_BACKUP if it exists
        safe_dir = os.path.join(CULT_SYNC_DIR, "FINAL_WORKING_BACKUP")
        if os.path.exists(safe_dir):
            self.backups_listbox.insert(tk.END, "FINAL_WORKING_BACKUP")
            
        if os.path.exists(BACKUPS_DIR):
            dirs = [d for d in os.listdir(BACKUPS_DIR) if os.path.isdir(os.path.join(BACKUPS_DIR, d))]
            dirs.sort(reverse=True)
            for d in dirs:
                if d != "FINAL_WORKING_BACKUP": # prevent duplicate entry
                    self.backups_listbox.insert(tk.END, d)

if __name__ == "__main__":
    root = tk.Tk()
    app = SaveSyncApp(root)
    root.mainloop()
