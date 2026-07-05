import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import re
import time

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Touch Pad Settings")
        self.geometry("800x300")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.serial_conn = None

        # Layout configuration
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.rects = []
        self.labels = []
        self.entries = []
        self.buttons = []

        # Optimization: Cache state to avoid redundant UI updates
        self.last_values = [""] * 4
        self.last_triggers = [False] * 4

        # Row 0: P1, P2, P3, P4 (Rectangles showing current values)
        for i in range(4):
            frame = ctk.CTkFrame(self, corner_radius=10, height=100)
            frame.grid(row=0, column=i, padx=10, pady=(20, 10), sticky="nsew")
            frame.grid_propagate(False)
            
            label_title = ctk.CTkLabel(frame, text=f"P{i+1}", font=("Arial", 16, "bold"))
            label_title.pack(pady=5)
            
            label_val = ctk.CTkLabel(frame, text="0", font=("Arial", 20))
            label_val.pack(pady=5)
            
            self.rects.append(frame)
            self.labels.append(label_val)

        # Row 1: T1, T2, T3, T4 (Threshold entry boxes)
        for i in range(4):
            entry = ctk.CTkEntry(self, placeholder_text=f"T{i+1} Threshold")
            entry.grid(row=1, column=i, padx=10, pady=10, sticky="ew")
            entry.insert(0, "10000")
            self.entries.append(entry)

        # Row 2: B1, B2, B3, B4 (Set buttons)
        for i in range(4):
            btn = ctk.CTkButton(self, text=f"Set B{i+1}", command=lambda idx=i: self.send_threshold(idx))
            btn.grid(row=2, column=i, padx=10, pady=10, sticky="ew")
            self.buttons.append(btn)

        # Row 3: Serial Port Connection Settings
        serial_frame = ctk.CTkFrame(self)
        serial_frame.grid(row=3, column=0, columnspan=4, padx=10, pady=20, sticky="nsew")
        
        self.port_selector = ctk.CTkOptionMenu(serial_frame, values=["Scanning..."])
        self.port_selector.pack(side="left", padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(serial_frame, text="Refresh", command=self.refresh_ports, width=80)
        self.refresh_btn.pack(side="left", padx=5, pady=10)
        
        self.connect_btn = ctk.CTkButton(serial_frame, text="Connect", command=self.toggle_connection, width=100)
        self.connect_btn.pack(side="left", padx=10, pady=10)
        
        self.status_label = ctk.CTkLabel(serial_frame, text="Disconnected", text_color="red")
        self.status_label.pack(side="left", padx=10, pady=10)

        # Defer port scanning and thread start to improve startup speed
        self.after(100, self.initial_load)

    def initial_load(self):
        self.refresh_ports()
        self.running = True
        self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.read_thread.start()

    def get_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        return ports if ports else ["No Ports Found"]

    def refresh_ports(self):
        ports = self.get_ports()
        self.port_selector.configure(values=ports)
        if ports:
            self.port_selector.set(ports[0])

    def toggle_connection(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        port = self.port_selector.get()
        if port == "No Ports Found" or port == "Scanning...":
            return
            
        try:
            self.serial_conn = serial.Serial(port, 115200, timeout=0.1)
            self.status_label.configure(text=f"Connected to {port}", text_color="green")
            self.connect_btn.configure(text="Disconnect", fg_color="red", hover_color="#8B0000")
        except Exception:
            self.status_label.configure(text="Error Connecting", text_color="red")

    def disconnect_serial(self):
        if self.serial_conn:
            try:
                # Cancel any pending read to unlock the background thread instantly
                self.serial_conn.cancel_read()
                self.serial_conn.close()
            except:
                pass
            self.serial_conn = None
        self.status_label.configure(text="Disconnected", text_color="red")
        self.connect_btn.configure(text="Connect", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])

    def on_closing(self):
        self.running = False
        self.disconnect_serial()
        self.destroy()

    def send_threshold(self, idx):
        if not self.serial_conn or not self.serial_conn.is_open:
            return
        
        try:
            value = int(self.entries[idx].get())
            cmd = f"THR {idx} {value}\n"
            self.serial_conn.write(cmd.encode())
        except ValueError:
            pass

    def read_serial(self):
        while self.running:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    line = self.serial_conn.readline().decode('utf-8').rstrip('\r\n')
                    if line:
                        # Batch updates per line for better performance
                        updates = []

                        # Parse format like "P1:19501  *P2:18414  *P3:40046   P4:45307"
                        matches = re.findall(r"P(\d):(\d+)\s{2}([\* ])", line)
                        for pad_num, val, trigger in matches:
                            idx = int(pad_num) - 1
                            if 0 <= idx < 4:
                                is_triggered = (trigger == '*')
                                # Only add to update list if state changed
                                if val != self.last_values[idx] or is_triggered != self.last_triggers[idx]:
                                    updates.append((idx, val, is_triggered))
                                    self.last_values[idx] = val
                                    self.last_triggers[idx] = is_triggered
                        
                        if updates:
                            self.after(0, self.apply_updates, updates)
                        
                        # Handle confirmation like "Threshold[3] set to 15000 and saved"
                        conf_match = re.search(r"Threshold\[(\d)\] set to (\d+) and saved", line)
                        if conf_match:
                            idx, val = conf_match.groups()
                            self.after(0, lambda i=idx, v=val: self.status_label.configure(
                                text=f"P{int(i)+1} Threshold saved: {v}", text_color="green"))
                except Exception:
                    pass
            else:
                time.sleep(0.1) # Reduce CPU usage when disconnected

    def apply_updates(self, updates):
        for idx, value, is_triggered in updates:
            self.labels[idx].configure(text=value)
            color = "green" if is_triggered else ["#3B3B3B", "#242424"]
            self.rects[idx].configure(fg_color=color)

    def update_ui(self, idx, value, is_triggered):
        pass # Deprecated in favor of apply_updates

if __name__ == "__main__":
    app = App()
    app.mainloop()
