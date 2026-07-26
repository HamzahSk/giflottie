import os
import sys
import tempfile
import json
import numpy as np
import cv2
import vtracer
from PIL import Image
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def frames_are_identical(frame1, frame2, threshold=0.98):
    """Deteksi apakah dua frame identik menggunakan OpenCV"""
    if frame1.shape != frame2.shape:
        return False
    
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGBA2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGBA2GRAY)
    score = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)[0][0]
    return score >= threshold

def detect_static_elements(frames):
    """Deteksi elemen statis menggunakan background subtraction"""
    gray_frames = [cv2.cvtColor(f, cv2.COLOR_RGBA2GRAY) for f in frames]
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=len(frames))
    
    static_mask = np.ones_like(gray_frames[0], dtype=np.uint8) * 255
    for gray in gray_frames:
        mask = bg_subtractor.apply(gray)
        static_mask = cv2.bitwise_and(static_mask, cv2.bitwise_not(mask))
    
    return static_mask

def optimize_shapes(shapes):
    """Hapus shape duplikat berdasarkan hash"""
    seen = set()
    optimized = []
    for shape in shapes:
        h = str(shape.to_dict())
        if h not in seen:
            seen.add(h)
            optimized.append(shape)
    return optimized

def gif_to_optimized_vector_lottie(gif_path, output_path, target_fps=12, quality='medium'):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print(f"Membaca file GIF dengan OpenCV...")
    cap = cv2.VideoCapture(gif_path)
    all_frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        all_frames.append(frame_rgba)
    cap.release()

    # Baca durasi frame dengan PIL
    gif_pil = Image.open(gif_path)
    frame_durations = []
    for i in range(len(all_frames)):
        gif_pil.seek(i)
        frame_durations.append(gif_pil.info.get('duration', 100))

    total_frames = len(all_frames)
    print(f"Total frame asli: {total_frames}")

    # Deteksi frame unik
    print("Mendeteksi frame identik...")
    unique_frames = []
    frame_mapping = []  # indeks frame asli -> indeks di unique_frames

    for frame in all_frames:
        found = False
        for j, uf in enumerate(unique_frames):
            if frames_are_identical(frame, uf):
                frame_mapping.append(j)
                found = True
                break
        if not found:
            unique_frames.append(frame)
            frame_mapping.append(len(unique_frames) - 1)

    print(f"Frame unik: {len(unique_frames)} (hemat {total_frames - len(unique_frames)} frame)")

    # Deteksi elemen statis
    print("Mendeteksi elemen statis...")
    static_mask = detect_static_elements(unique_frames)

    # Konfigurasi vtracer berdasarkan quality (tanpa parameter yang tidak didukung)
    quality_configs = {
        'low': {'filter_speckle': 8, 'mode': 'polygon'},
        'medium': {'filter_speckle': 4, 'mode': 'spline'},
        'high': {'filter_speckle': 2, 'mode': 'spline'}
    }
    config = quality_configs.get(quality, quality_configs['medium'])

    # Inisialisasi animasi Lottie
    animation = objects.Animation(0, target_fps)
    animation.width = all_frames[0].shape[1]
    animation.height = all_frames[0].shape[0]
    animation.name = "Optimized Vector Lottie"

    lottie_frames = []
    frame_timing = []

    frame_interval_ms = 1000.0 / target_fps
    current_time_ms = 0
    next_target_time_ms = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        print("Memproses vector frames...")
        for idx, frame in enumerate(unique_frames):
            # Ekstrak area bergerak
            if static_mask is not None:
                moving_parts = cv2.bitwise_and(frame, frame, mask=static_mask)
            else:
                moving_parts = frame

            png_path = os.path.join(temp_dir, f"frame_{idx}.png")
            svg_path = os.path.join(temp_dir, f"frame_{idx}.svg")

            Image.fromarray(moving_parts).save(png_path, format="PNG", optimize=True)

            # Panggil vtracer hanya dengan parameter yang didukung
            vtracer.convert_image_to_svg_py(
                png_path,
                svg_path,
                colormode="color",
                mode=config['mode'],
                hierarchical="stacked",
                filter_speckle=config['filter_speckle']
            )

            svg_anim = import_svg(svg_path)
            shapes = []
            for svg_layer in svg_anim.layers:
                if isinstance(svg_layer, objects.ShapeLayer):
                    shapes.extend(svg_layer.shapes)

            lottie_frames.append(optimize_shapes(shapes))
            print(f"Frame {idx+1}/{len(unique_frames)} diproses")

        # Bangun timeline Lottie
        print("Membangun timeline animasi...")
        prev_mapped_idx = -1
        for i in range(total_frames):
            current_time_ms += frame_durations[i]
            if current_time_ms >= next_target_time_ms:
                mapped_idx = frame_mapping[i]
                if mapped_idx != prev_mapped_idx:
                    frame_layer = animation.add_layer(objects.ShapeLayer())
                    frame_layer.name = f"Frame {len(animation.layers)}"
                    for shape in lottie_frames[mapped_idx]:
                        frame_layer.add_shape(shape.clone())
                    prev_mapped_idx = mapped_idx

                frame_layer.in_point = len(frame_timing)
                frame_layer.out_point = len(frame_timing) + 1
                frame_timing.append(len(frame_timing))
                next_target_time_ms += frame_interval_ms

    animation.out_point = len(frame_timing)

    # Simpan
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    export_lottie(animation, output_path)

    # Kompresi JSON output
    with open(output_path, 'r') as f:
        data = json.load(f)
    with open(output_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n--- Statistik Optimasi ---")
    print(f"Frame asli: {total_frames}")
    print(f"Frame unik: {len(unique_frames)}")
    print(f"Frame Lottie: {len(frame_timing)}")
    print(f"Ukuran file: {size_kb:.1f} KB")
    print(f"Tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    quality = sys.argv[4] if len(sys.argv) > 4 else 'medium'
    gif_to_optimized_vector_lottie(input_file, output_file, target_fps=fps, quality=quality)