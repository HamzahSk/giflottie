import os
import sys
import tempfile
import json
import cv2
import numpy as np
from PIL import Image
import vtracer
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def frames_are_similar(f1, f2, threshold=0.98):
    """Cek kesamaan frame menggunakan template matching (grayscale)."""
    if f1.shape != f2.shape:
        return False
    g1 = cv2.cvtColor(f1, cv2.COLOR_RGBA2GRAY)
    g2 = cv2.cvtColor(f2, cv2.COLOR_RGBA2GRAY)
    return cv2.matchTemplate(g1, g2, cv2.TM_CCOEFF_NORMED)[0][0] >= threshold

def simplify_shapes(shapes):
    """Buang shape yang sama persis dalam satu frame."""
    seen = set()
    uniq = []
    for s in shapes:
        h = str(s.to_dict())
        if h not in seen:
            seen.add(h)
            uniq.append(s)
    return uniq

def gif_to_optimized_vector_lottie(gif_path, output_path, target_fps=15, quality='low'):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print("Membaca GIF...")
    cap = cv2.VideoCapture(gif_path)
    frames_raw = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames_raw.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA))
    cap.release()

    # Durasi tiap frame (ms)
    pil_gif = Image.open(gif_path)
    durations = []
    for i in range(len(frames_raw)):
        pil_gif.seek(i)
        durations.append(pil_gif.info.get('duration', 100))

    total = len(frames_raw)
    print(f"Total frame asli: {total}")

    # --- Deteksi frame unik ---
    unique_frames = []
    frame_map = []  # indeks asli -> indeks unik
    for f in frames_raw:
        found = False
        for j, uf in enumerate(unique_frames):
            if frames_are_similar(f, uf):
                frame_map.append(j)
                found = True
                break
        if not found:
            unique_frames.append(f)
            frame_map.append(len(unique_frames) - 1)
    print(f"Frame unik: {len(unique_frames)} (hemat {total - len(unique_frames)})")

    # --- Konfigurasi vtracer ---
    vt_config = {
        'low':    {'filter_speckle': 10, 'mode': 'polygon'},
        'medium': {'filter_speckle': 5,  'mode': 'spline'},
        'high':   {'filter_speckle': 2,  'mode': 'spline'}
    }.get(quality, {'filter_speckle': 5, 'mode': 'spline'})

    # --- Proses tracing hanya untuk frame unik ---
    lottie_shapes_per_unique = []  # list of list of shapes
    with tempfile.TemporaryDirectory() as tmp:
        for idx, frame in enumerate(unique_frames):
            png_path = os.path.join(tmp, f"u{idx}.png")
            svg_path = os.path.join(tmp, f"u{idx}.svg")
            Image.fromarray(frame).save(png_path, "PNG", optimize=True)

            vtracer.convert_image_to_svg_py(
                png_path, svg_path,
                colormode="color",
                mode=vt_config['mode'],
                hierarchical="stacked",
                filter_speckle=vt_config['filter_speckle']
            )

            anim = import_svg(svg_path)
            shapes = []
            for lay in anim.layers:
                if isinstance(lay, objects.ShapeLayer):
                    shapes.extend(lay.shapes)
            lottie_shapes_per_unique.append(simplify_shapes(shapes))
            print(f"Tracing frame unik {idx+1}/{len(unique_frames)} selesai")

    # --- Bangun animasi Lottie ---
    anim = objects.Animation(0, target_fps)
    anim.width, anim.height = frames_raw[0].shape[1], frames_raw[0].shape[0]
    anim.name = "Optimized Lottie"

    # Timeline dengan frame skipping sesuai FPS
    frame_interval = 1000.0 / target_fps
    time_cursor = 0.0
    next_trigger = 0.0

    current_layer = None        # layer yang sedang "dibuka"
    current_unique_idx = None   # indeks unik dari layer tsb
    lottie_time = 0             # frame Lottie saat ini

    for i in range(total):
        time_cursor += durations[i]
        if time_cursor >= next_trigger:
            uid = frame_map[i]
            # Jika frame unik sama dengan sebelumnya, cukup perpanjang durasi layer
            if uid == current_unique_idx and current_layer is not None:
                current_layer.out_point = lottie_time + 1
            else:
                # Buat layer baru
                layer = objects.ShapeLayer()
                layer.name = f"F{len(anim.layers)}"
                layer.in_point = lottie_time
                layer.out_point = lottie_time + 1
                # isi shapes (clone)
                for s in lottie_shapes_per_unique[uid]:
                    layer.add_shape(s.clone())
                anim.add_layer(layer)
                current_layer = layer
                current_unique_idx = uid

            lottie_time += 1
            next_trigger += frame_interval

    anim.out_point = lottie_time

    # Simpan
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    export_lottie(anim, output_path)

    # Kompresi JSON (hapus spasi)
    with open(output_path, 'r') as f:
        data = json.load(f)
    with open(output_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n--- Hasil ---")
    print(f"Frame Lottie: {lottie_time}")
    print(f"Ukuran file : {size_kb:.1f} KB")
    print(f"Tersimpan   : {output_path}")

if __name__ == "__main__":
    in_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    qual = sys.argv[4] if len(sys.argv) > 4 else 'low'
    gif_to_optimized_vector_lottie(in_file, out_file, fps, qual)