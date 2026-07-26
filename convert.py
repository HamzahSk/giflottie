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

def remove_gray_background(frame, lower_gray=np.array([180, 180, 180]), upper_gray=np.array([235, 235, 235])):
    """
    Menghapus background abu-abu dan menjadikannya transparan (BGRA).
    Sesuaikan rentang lower_gray dan upper_gray jika warna abu-abu di GIF sedikit berbeda.
    """
    # Pastikan frame berformat RGBA atau BGRA
    if frame.shape[2] == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
    elif frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGRA)

    # Deteksi piksel dalam rentang warna abu-abu
    # (Di BGR, warna abu-abu memiliki nilai B, G, R yang relatif seimbang/sama)
    mask = cv2.inRange(frame[:, :, :3], lower_gray, upper_gray)

    # Buat channel Alpha (transparansi) menjadi 0 untuk area background abu-abu
    frame[mask > 0, 3] = 0

    return frame

def frames_are_similar(f1, f2, threshold=0.98):
    """Cek kesamaan frame menggunakan template matching (grayscale)."""
    if f1.shape != f2.shape:
        return False
    g1 = cv2.cvtColor(f1, cv2.COLOR_BGRA2GRAY) if f1.shape[2] == 4 else cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(f2, cv2.COLOR_BGRA2GRAY) if f2.shape[2] == 4 else cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
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
        
        # --- PRE-PROCESSING: Hapus Background Abu-abu ---
        frame_no_bg = remove_gray_background(frame)
        frames_raw.append(frame_no_bg)
        
    cap.release()

    if not frames_raw:
        print("Error: Tidak ada frame yang terbaca dari GIF!")
        sys.exit(1)

    h, w, _ = frames_raw[0].shape
    print(f"Total frame awal: {len(frames_raw)}, Ukuran: {w}x{h}")

    # Deduplikasi frame yang mirip
    print("Menghapus frame duplikat...")
    unique_frames = [frames_raw[0]]
    for f in frames_raw[1:]:
        if not frames_are_similar(unique_frames[-1], f):
            unique_frames.append(f)

    print(f"Frame tersisa setelah deduplikasi: {len(unique_frames)}")

    # Parameter vtracer berdasarkan quality
    vtracer_opts = {
        'low': {'colormode': 'color', 'hierarchical': 'stacked', 'filter_speckle': 8, 'color_precision': 6, 'layer_difference': 16, 'corner_threshold': 60, 'length_threshold': 4.0, 'max_iterations': 10, 'splice_threshold': 45, 'path_precision': 3},
        'medium': {'colormode': 'color', 'hierarchical': 'stacked', 'filter_speckle': 4, 'color_precision': 7, 'layer_difference': 12, 'corner_threshold': 45, 'length_threshold': 3.0, 'max_iterations': 10, 'splice_threshold': 45, 'path_precision': 5},
        'high': {'colormode': 'color', 'hierarchical': 'stacked', 'filter_speckle': 2, 'color_precision': 8, 'layer_difference': 8, 'corner_threshold': 30, 'length_threshold': 2.0, 'max_iterations': 10, 'splice_threshold': 45, 'path_precision': 8}
    }
    opts = vtracer_opts.get(quality, vtracer_opts['low'])

    # Vektorisasi tiap frame unik ke Lottie shapes
    print("Mengonversi frame ke bentuk vektor (SVG -> Lottie)...")
    lottie_shapes_per_unique = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, uframe in enumerate(unique_frames):
            # Frame disimpen sebagai PNG transparan
            png_path = os.path.join(tmpdir, f"frame_{idx}.png")
            svg_path = os.path.join(tmpdir, f"frame_{idx}.svg")

            # Ubah BGRA ke RGBA untuk disimpan oleh PIL Image
            frame_rgba = cv2.cvtColor(uframe, cv2.COLOR_BGRA2RGBA)
            Image.fromarray(frame_rgba).save(png_path)

            # Konversi ke SVG
            vtracer.convert_image_to_svg_py(
                png_path,
                svg_path,
                colormode=opts['colormode'],
                hierarchical=opts['hierarchical'],
                filter_speckle=opts['filter_speckle'],
                color_precision=opts['color_precision'],
                layer_difference=opts['layer_difference'],
                corner_threshold=opts['corner_threshold'],
                length_threshold=opts['length_threshold'],
                max_iterations=opts['max_iterations'],
                splice_threshold=opts['splice_threshold'],
                path_precision=opts['path_precision']
            )

            # Import SVG ke Lottie Animation
            lottie_anim = import_svg(svg_path)
            shapes = []
            for layer in lottie_anim.layers:
                if hasattr(layer, 'shapes'):
                    shapes.extend(layer.shapes)

            # Simplifikasi shape
            shapes = simplify_shapes(shapes)
            lottie_shapes_per_unique.append(shapes)

    # Buat Struktur Animasi Lottie Utama
    print("Membangun struktur animasi Lottie...")
    anim = objects.Animation()
    anim.width = w
    anim.height = h
    anim.frame_rate = target_fps

    # Mapping frame raw ke index frame unik
    frame_to_unique_idx = []
    current_uid = 0
    frame_to_unique_idx.append(0)

    for i in range(1, len(frames_raw)):
        if not frames_are_similar(frames_raw[i-1], frames_raw[i]):
            current_uid += 1
        frame_to_unique_idx.append(current_uid)

    # Susun timeline Lottie
    src_fps = target_fps
    frame_interval = max(1, int(round(src_fps / target_fps)))

    lottie_time = 0
    next_trigger = 0

    current_layer = None
    current_unique_idx = -1

    for idx, raw_frame in enumerate(frames_raw):
        if idx >= next_trigger:
            uid = frame_to_unique_idx[idx]

            if uid == current_unique_idx and current_layer is not None:
                # Perpanjang durasi layer yang ada
                current_layer.out_point = lottie_time + 1
            else:
                # Buat layer baru
                layer = objects.ShapeLayer()
                layer.name = f"F{len(anim.layers)}"
                layer.in_point = lottie_time
                layer.out_point = lottie_time + 1
                
                # Isi shapes (clone)
                for s in lottie_shapes_per_unique[uid]:
                    layer.add_shape(s.clone())
                anim.add_layer(layer)
                current_layer = layer
                current_unique_idx = uid

            lottie_time += 1
            next_trigger += frame_interval

    anim.out_point = lottie_time

    # Simpan File Lottie JSON
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
    if len(sys.argv) < 2:
        print("Penggunaan: python convert.py <input_gif> [output_json]")
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else "output.json"
    gif_to_optimized_vector_lottie(in_file, out_file)
