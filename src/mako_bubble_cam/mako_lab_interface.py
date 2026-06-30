# ============================
# PERFILES - Mako U-029B
# ============================
PROFILES = {
    "Velocidad 1": {
        "width": 640,
        "height": 480,
        "fps_limit": 30,
        "exposure": 10000
    },
    "Velocidad 2": {
        "width": 640,
        "height": 480,
        "fps_limit": 100,
        "exposure": 3000
    },
    "Velocidad 3": {
        "width": 640,
        "height": 480,
        "fps_limit": 200,
        "exposure": 1000
    },
    "ROI amplia": {
        "width": 480,
        "height": 360,
        "fps_limit": 400,
        "exposure": 500
    }
}

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from vmbpy import *
import cv2
import numpy as np
import threading
import time
import json
import os
import csv
import queue
from datetime import datetime

CONFIG_FILE = "camera_config.json"


class MakoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MAKO Lab Interface")

        self.running = True
        self.recording = False
        self.camera_initialized = False
        self.streaming_started = False

        self.vmb = None
        self.cam = None

        self.display_frame_gray = None
        self.display_frame_lock = threading.Lock()

        self.record_queue = queue.Queue(maxsize=5000)

        self.capture_fps = 0.0
        self.prev_time = time.time()

        self.record_start_time = None
        self.record_thread = None
        self.record_folder = None
        self.csv_file = None
        self.csv_writer = None
        self.frame_counter = 0
        self.first_saved_timestamp = None
        self.last_saved_timestamp = None

        self.load_config()

        # Líneas paralelas
        self.line1_y = self.config.get("line1_y", 200)
        self.line2_y = self.config.get("line2_y", 300)
        self.line1_active = self.config.get("line1_active", True)
        self.line2_active = self.config.get("line2_active", True)
        self.dragging_line = None

        # Calibración
        self.calibration_factor = self.config.get("calibration", None)
        self.calibration_mode = False
        self.calibration_line = None
        self.drawing_calibration = False

        # Círculo
        self.circle_mode = False
        self.circle_center = None
        self.circle_radius = 0
        self.drawing_circle = False

        self.setup_ui()
        self.connect_camera()

        self.root.after(0, self.display_loop)

    # =========================
    # UI
    # =========================
    def setup_ui(self):
        self.video_label = tk.Label(self.root)
        self.video_label.pack()

        self.video_label.bind("<ButtonPress-1>", self.mouse_press)
        self.video_label.bind("<B1-Motion>", self.mouse_drag)
        self.video_label.bind("<ButtonRelease-1>", self.mouse_release)

        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=6, pady=6)

        tk.Label(frame, text="Perfil de captura").pack(fill="x")

        self.profile_mode = ttk.Combobox(
            frame,
            values=list(PROFILES.keys()),
            state="readonly"
        )
        self.profile_mode.set(self.config.get("profile", "Velocidad 1"))
        self.profile_mode.pack(fill="x", pady=2)

        tk.Button(
            frame,
            text="Inicializar Cámara / Reaplicar Perfil",
            command=self.initialize_camera,
            bg="blue",
            fg="white"
        ).pack(fill="x", pady=2)

        tk.Button(
            frame,
            text="Calibrar",
            command=self.toggle_calibration
        ).pack(fill="x", pady=2)

        tk.Button(
            frame,
            text="Círculo",
            command=self.toggle_circle
        ).pack(fill="x", pady=2)

        self.line1_btn = tk.Button(
            frame,
            text=f"Línea 1 {'ON' if self.line1_active else 'OFF'}",
            command=self.toggle_line1
        )
        self.line1_btn.pack(fill="x", pady=2)

        self.line2_btn = tk.Button(
            frame,
            text=f"Línea 2 {'ON' if self.line2_active else 'OFF'}",
            command=self.toggle_line2
        )
        self.line2_btn.pack(fill="x", pady=2)

        self.rec_btn = tk.Button(
            frame,
            text="REC",
            bg="red",
            fg="white",
            command=self.toggle_recording
        )
        self.rec_btn.pack(fill="x", pady=2)

        self.status = tk.Label(frame, text="Estado: listo", anchor="w")
        self.status.pack(fill="x", pady=4)

    # =========================
    # CONFIG
    # =========================
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def save_config(self):
        self.config["profile"] = self.profile_mode.get()
        self.config["line1_y"] = int(self.line1_y)
        self.config["line2_y"] = int(self.line2_y)
        self.config["line1_active"] = self.line1_active
        self.config["line2_active"] = self.line2_active
        self.config["calibration"] = self.calibration_factor

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    # =========================
    # CAMERA
    # =========================
    def connect_camera(self):
        self.vmb = VmbSystem.get_instance()
        self.vmb.__enter__()

        cams = self.vmb.get_all_cameras()
        if not cams:
            raise RuntimeError("No se detectó ninguna cámara.")

        self.cam = cams[0]
        self.cam.__enter__()

        try:
            self.cam.get_feature_by_name("PixelFormat").set("Mono8")
        except Exception:
            pass

        try:
            self.cam.get_feature_by_name("ExposureMode").set("Timed")
        except Exception:
            pass

    def fit_feature_value(self, feature, value):
        value = int(value)
        min_v, max_v = feature.get_range()
        value = max(min_v, min(max_v, value))

        try:
            inc = feature.get_increment()
            if inc and inc > 1:
                value = min_v + ((value - min_v) // inc) * inc
        except Exception:
            pass

        return int(value)

    def initialize_camera(self):
        try:
            if self.recording:
                messagebox.showwarning(
                    "Error",
                    "No puedes reinicializar la cámara mientras estás grabando."
                )
                return

            if self.streaming_started:
                try:
                    self.cam.stop_streaming()
                except Exception:
                    pass
                self.streaming_started = False
                self.camera_initialized = False

            p = PROFILES[self.profile_mode.get()]

            width_feature = self.cam.get_feature_by_name("Width")
            height_feature = self.cam.get_feature_by_name("Height")
            offsetx_feature = self.cam.get_feature_by_name("OffsetX")
            offsety_feature = self.cam.get_feature_by_name("OffsetY")

            sensor_max_w = width_feature.get_range()[1]
            sensor_max_h = height_feature.get_range()[1]

            # Primero offsets a cero
            try:
                offsetx_feature.set(0)
            except Exception:
                pass

            try:
                offsety_feature.set(0)
            except Exception:
                pass

            w = self.fit_feature_value(width_feature, p["width"])
            h = self.fit_feature_value(height_feature, p["height"])

            width_feature.set(w)
            height_feature.set(h)

            # Centrar ROI si no es full frame
            desired_offset_x = max(0, (sensor_max_w - w) // 2)
            desired_offset_y = max(0, (sensor_max_h - h) // 2)

            try:
                ox = self.fit_feature_value(offsetx_feature, desired_offset_x)
                offsetx_feature.set(ox)
            except Exception:
                ox = 0

            try:
                oy = self.fit_feature_value(offsety_feature, desired_offset_y)
                offsety_feature.set(oy)
            except Exception:
                oy = 0

            # FPS límite nominal
            try:
                self.cam.get_feature_by_name("AcquisitionFrameRateEnable").set(True)
                self.cam.get_feature_by_name("AcquisitionFrameRate").set(float(p["fps_limit"]))
            except Exception as e:
                print("No se pudo aplicar FPS límite:", e)

            # Exposure
            try:
                self.cam.get_feature_by_name("ExposureTime").set(float(p["exposure"]))
            except Exception as e:
                print("No se pudo aplicar exposure:", e)

            self.cam.start_streaming(self.frame_handler)
            self.streaming_started = True
            self.camera_initialized = True

            self.status.config(
                text=f"Perfil aplicado: {self.profile_mode.get()} | {w}x{h} | Exp {p['exposure']} µs"
            )

            self.save_config()

        except Exception as e:
            messagebox.showerror("Error al inicializar cámara", str(e))

    # =========================
    # STREAM
    # =========================
    def frame_handler(self, cam, stream, frame):
        try:
            if frame.get_status() == FrameStatus.Complete:
                img = frame.as_numpy_ndarray().copy()
                t = time.time()

                dt = t - self.prev_time
                if dt > 0:
                    self.capture_fps = 1.0 / dt
                self.prev_time = t

                with self.display_frame_lock:
                    self.display_frame_gray = img

                if self.recording:
                    try:
                        self.record_queue.put_nowait((img, t))
                    except queue.Full:
                        pass
        finally:
            cam.queue_frame(frame)

    # =========================
    # DISPLAY
    # =========================
    def display_loop(self):
        frame = None
        with self.display_frame_lock:
            if self.display_frame_gray is not None:
                frame = self.display_frame_gray.copy()

        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            frame = self.draw_overlays(frame, rec_elapsed=None, recording_preview=True)

            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            imgtk = tk.PhotoImage(data=cv2.imencode(".png", img)[1].tobytes())

            self.video_label.config(image=imgtk)
            self.video_label.image = imgtk

        self.root.after(30, self.display_loop)

    # =========================
    # OVERLAYS
    # =========================
    def draw_overlays(self, img, rec_elapsed=None, recording_preview=False):
        h, w = img.shape[:2]

        if self.line1_active:
            cv2.line(img, (0, int(self.line1_y)), (w, int(self.line1_y)), (0, 255, 255), 2)

        if self.line2_active:
            cv2.line(img, (0, int(self.line2_y)), (w, int(self.line2_y)), (0, 255, 0), 2)

        if self.line1_active and self.line2_active:
            px = abs(self.line2_y - self.line1_y)
            if self.calibration_factor:
                text = f"{px * self.calibration_factor:.2f} µm"
            else:
                text = f"{px} px"

            cv2.putText(
                img,
                text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2
            )

        # Línea de calibración: visible solo mientras se dibuja
        if self.calibration_line is not None:
            (x1, y1), (x2, y2) = self.calibration_line
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 2)

            px_cal = abs(x2 - x1)
            cv2.putText(
                img,
                f"{px_cal} px",
                (min(x1, x2), max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 255),
                2
            )

        if self.circle_center is not None and self.circle_radius > 0:
            cv2.circle(img, self.circle_center, int(self.circle_radius), (255, 255, 0), 2)

            diameter_px = 2 * self.circle_radius
            if self.calibration_factor:
                circle_text = f"Ø {diameter_px * self.calibration_factor:.2f} µm"
            else:
                circle_text = f"Ø {diameter_px:.1f} px"

            tx = min(self.circle_center[0] + 10, max(w - 220, 10))
            ty = max(self.circle_center[1] - 10, 20)
            cv2.putText(
                img,
                circle_text,
                (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2
            )

        cv2.putText(
            img,
            f"FPS: {self.capture_fps:.1f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2
        )

        if recording_preview and self.recording and self.record_start_time is not None:
            elapsed = time.time() - self.record_start_time
            cv2.putText(
                img,
                f"t={elapsed:.4f}s",
                (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )
            cv2.putText(
                img,
                "● REC",
                (w - 120, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

        if rec_elapsed is not None:
            cv2.putText(
                img,
                f"t={rec_elapsed:.4f}s",
                (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        return img

    # =========================
    # MOUSE
    # =========================
    def mouse_press(self, event):
        if self.calibration_mode:
            self.calibration_line = [(event.x, event.y), (event.x, event.y)]
            self.drawing_calibration = True
            return

        if self.circle_mode:
            self.circle_center = (event.x, event.y)
            self.circle_radius = 0
            self.drawing_circle = True
            return

        if self.line1_active and abs(event.y - self.line1_y) < 10:
            self.dragging_line = "line1"
        elif self.line2_active and abs(event.y - self.line2_y) < 10:
            self.dragging_line = "line2"

    def mouse_drag(self, event):
        if self.drawing_calibration:
            x1, y1 = self.calibration_line[0]
            self.calibration_line[1] = (event.x, y1)
            return

        if self.drawing_circle and self.circle_center is not None:
            self.circle_radius = int(
                np.linalg.norm(np.array((event.x, event.y)) - np.array(self.circle_center))
            )
            return

        if self.dragging_line == "line1":
            self.line1_y = event.y
        elif self.dragging_line == "line2":
            self.line2_y = event.y

    def mouse_release(self, event):
        if self.drawing_calibration:
            self.drawing_calibration = False
            (x1, _), (x2, _) = self.calibration_line
            px = abs(x2 - x1)

            if px > 0:
                real = simpledialog.askfloat("Calibrar", "µm reales")
                if real:
                    self.calibration_factor = real / px
                    self.save_config()

            # borrar línea al terminar
            self.calibration_line = None
            self.calibration_mode = False

        self.drawing_circle = False
        self.dragging_line = None

    # =========================
    # CONTROLES
    # =========================
    def toggle_calibration(self):
        self.calibration_mode = not self.calibration_mode
        self.circle_mode = False

    def toggle_circle(self):
        self.circle_mode = not self.circle_mode
        self.calibration_mode = False

    def toggle_line1(self):
        self.line1_active = not self.line1_active
        self.line1_btn.config(text=f"Línea 1 {'ON' if self.line1_active else 'OFF'}")
        self.save_config()

    def toggle_line2(self):
        self.line2_active = not self.line2_active
        self.line2_btn.config(text=f"Línea 2 {'ON' if self.line2_active else 'OFF'}")
        self.save_config()

    # =========================
    # RECORD
    # =========================
    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if not self.camera_initialized:
            messagebox.showwarning("Error", "Inicializa cámara")
            return

        while not self.record_queue.empty():
            try:
                self.record_queue.get_nowait()
            except queue.Empty:
                break

        self.recording = True
        self.record_start_time = time.time()
        self.frame_counter = 0
        self.first_saved_timestamp = None
        self.last_saved_timestamp = None

        folder = "record_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(os.path.join(folder, "frames"), exist_ok=True)
        self.record_folder = folder

        self.csv_file = open(
            os.path.join(folder, "timestamps.csv"),
            "w",
            newline="",
            encoding="utf-8"
        )
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["frame", "filename", "timestamp_sec", "elapsed_sec"])

        self.rec_btn.config(text="STOP", bg="darkred")
        self.status.config(text=f"Grabando en: {folder}")

        self.record_thread = threading.Thread(target=self.record_worker, daemon=True)
        self.record_thread.start()

    def stop_recording(self):
        self.recording = False

        if self.record_thread is not None:
            self.record_thread.join()
            self.record_thread = None

        if self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None

        self.rec_btn.config(text="REC", bg="red")
        self.status.config(text=f"Grabación terminada: {self.record_folder}")

        try:
            self.generate_preview_video()
            self.status.config(text=f"Grabación y preview listos: {self.record_folder}")
        except Exception as e:
            self.status.config(text=f"Grabación lista, pero falló preview: {e}")

    def record_worker(self):
        while self.recording or not self.record_queue.empty():
            try:
                frame_gray, t = self.record_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if self.first_saved_timestamp is None:
                self.first_saved_timestamp = t
            self.last_saved_timestamp = t

            elapsed = t - self.record_start_time if self.record_start_time is not None else 0.0

            frame_bgr = cv2.cvtColor(frame_gray, cv2.COLOR_GRAY2BGR)
            frame_bgr = self.draw_overlays(frame_bgr, rec_elapsed=elapsed, recording_preview=False)

            filename = f"frame_{self.frame_counter:06d}.bmp"
            filepath = os.path.join(self.record_folder, "frames", filename)
            cv2.imwrite(filepath, frame_bgr)

            if self.csv_writer is not None:
                self.csv_writer.writerow([
                    self.frame_counter,
                    filename,
                    f"{t:.6f}",
                    f"{elapsed:.6f}"
                ])

            self.frame_counter += 1

    def generate_preview_video(self):
        if self.record_folder is None or self.frame_counter == 0:
            return

        frames_dir = os.path.join(self.record_folder, "frames")
        first_path = os.path.join(frames_dir, "frame_000000.bmp")
        first = cv2.imread(first_path)

        if first is None:
            return

        h, w = first.shape[:2]

        elapsed_total = 0.0
        if self.first_saved_timestamp is not None and self.last_saved_timestamp is not None:
            elapsed_total = self.last_saved_timestamp - self.first_saved_timestamp

        if elapsed_total > 0 and self.frame_counter > 1:
            preview_fps = (self.frame_counter - 1) / elapsed_total
        else:
            preview_fps = 30.0

        preview_fps = max(1.0, float(preview_fps))

        avi_path = os.path.join(self.record_folder, "preview.avi")
        writer = cv2.VideoWriter(
            avi_path,
            cv2.VideoWriter_fourcc(*"MJPG"),
            preview_fps,
            (w, h),
            True
        )

        for i in range(self.frame_counter):
            path = os.path.join(frames_dir, f"frame_{i:06d}.bmp")
            img = cv2.imread(path)
            if img is not None:
                writer.write(img)

        writer.release()

    # =========================
    # CLOSE
    # =========================
    def close(self):
        self.running = False

        try:
            if self.recording:
                self.stop_recording()
        except Exception:
            pass

        try:
            if self.streaming_started and self.cam is not None:
                self.cam.stop_streaming()
        except Exception:
            pass

        try:
            if self.cam is not None:
                self.cam.__exit__(None, None, None)
        except Exception:
            pass

        try:
            if self.vmb is not None:
                self.vmb.__exit__(None, None, None)
        except Exception:
            pass

        self.root.destroy()


root = tk.Tk()
app = MakoApp(root)
root.protocol("WM_DELETE_WINDOW", app.close)
root.mainloop()
