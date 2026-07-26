import os
import sys
import tempfile
import numpy as np
import cv2
import vtracer
from PIL import Image
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie
from collections import defaultdict

def frames_are_identical(frame1, frame2, threshold=0.98):
    """Deteksi apakah dua frame identik menggunakan OpenCV"""
    if frame1.shape != frame2.shape:
        return False
    
    # Konversi ke grayscale untuk perbandingan lebih cepat
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGBA2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGBA2GRAY)
    
    # Hitung similarity score
    score = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)[0][0]
    return score >= threshold

def detect_static_elements(frames, min_static_frames=3):
    """Deteksi elemen statis yang muncul di sebagian besar frame"""
    static_regions = []
    
    # Konversi frame ke grayscale
    gray_frames = [cv2.cvtColor(f, cv2.COLOR_RGBA2GRAY) for f in frames]
    
    # Deteksi background statis dengan background subtraction
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=len(frames))
    
    static_mask = None
    for gray in gray_frames:
        mask = bg_subtractor.apply(gray)
        if static_mask is None:
            static_mask = np.ones_like(mask) * 255
        
        # Area yang jarang berubah dianggap statis
        static_mask = cv2.bitwise_and(static_mask, cv2.bitwise_not(mask))
    
    return static_mask

def optimize_shapes(shapes):
    """Hapus shape duplikat dan optimasi path"""
    seen_shapes = set()
    optimized = []
    
    for shape in shapes:
        # Buat hash sederhana dari shape properties
        shape_hash = str(shape.to_dict())
        
        if shape_hash not in seen_shapes:
            seen_shapes.add(shape_hash)
            optimized.append(shape)
    
    return optimized

def gif_to_optimized_vector_lottie(gif_path, output_path, target_fps=12, quality='medium'):
    """
    quality: 'low', 'medium', 'high' - mempengaruhi vtracer settings
    """
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print(f"Membaca file GIF dengan OpenCV...")
    
    # Baca semua frame menggunakan OpenCV (lebih cepat)
    cap = cv2.VideoCapture(gif_path)
    all_frames = []
    frame_durations = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Konversi BGR ke RGBA
        frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        all_frames.append(frame_rgba)
    
    cap.release()
    
    # Baca durasi frame dengan PIL
    gif_pil = Image.open(gif_path)
    for i in range(len(all_frames)):
        gif_pil.seek(i)
        frame_durations.append(gif_pil.info.get('duration', 100))
    
    total_frames = len(all_frames)
    print(f"Total frame asli: {total_frames}")
    
    # Deteksi frame duplikat
    print("Mendeteksi frame identik...")
    unique_frames = []
    frame_mapping = []  # Map frame Lottie ke frame asli
    
    for i, frame in enumerate(all_frames):
        is_duplicate = False
        for j, unique_frame in enumerate(unique_frames):
            if frames_are_identical(frame, unique_frame):
                frame_mapping.append(j)
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_frames.append(frame)
            frame_mapping.append(len(unique_frames) - 1)
    
    print(f"Frame unik ditemukan: {len(unique_frames)} (penghematan: {total_frames - len(unique_frames)} frame)")
    
    # Deteksi elemen statis
    print("Mendeteksi elemen statis...")
    static_mask = detect_static_elements(unique_frames)
    
    # Konfigurasi vtracer berdasarkan quality
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
    
    # Logika timing
    frame_interval_ms = 1000.0 / target_fps
    current_time_ms = 0
    next_target_time_ms = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print("Membuat vector frames...")
        
        # Proses hanya frame unik
        for idx, frame in enumerate(unique_frames):
            # Ekstrak region non-statis
            if static_mask is not None:
                # Apply mask untuk mengambil hanya bagian yang bergerak
                moving_parts = cv2.bitwise_and(frame, frame, mask=static_mask)
            else:
                moving_parts = frame
            
            # Simpan sebagai PNG
            png_path = os.path.join(temp_dir, f"frame_{idx}.png")
            svg_path = os.path.join(temp_dir, f"frame_{idx}.svg")
            
            Image.fromarray(moving_parts).save(png_path, format="PNG", optimize=True)
            
            # Auto-tracing dengan konfigurasi optimal
            vtracer.convert_image_to_svg_py(
                png_path,
                svg_path,
                colormode="color",
                mode=config['mode'],
                hierarchical="stacked",
                filter_speckle=config['filter_speckle'],
                corner_threshold=0.5,  # Kurangi detail
                segment_length=5.0     # Sederhanakan path
            )
            
            # Import dan optimasi SVG
            svg_anim = import_svg(svg_path)
            
            # Ekstrak dan optimasi shapes
            shapes = []
            for svg_layer in svg_anim.layers:
                if isinstance(svg_layer, objects.ShapeLayer):
                    for shape in svg_layer.shapes:
                        shapes.append(shape)
            
            lottie_frames.append(optimize_shapes(shapes))
            
            print(f"Frame {idx + 1}/{len(unique_frames)} diproses")
        
        # Bangun timeline dengan referensi ke frame yang sama
        print("Membangun animasi Lottie...")
        prev_frame_idx = -1
        
        for i in range(total_frames):
            current_time_ms += frame_durations[i]
            
            if current_time_ms >= next_target_time_ms:
                mapped_idx = frame_mapping[i]
                
                # Hanya buat layer baru jika frame berbeda dari sebelumnya
                if mapped_idx != prev_frame_idx:
                    frame_layer = animation.add_layer(objects.ShapeLayer())
                    frame_layer.name = f"Frame {len(animation.layers)}"
                    
                    # Tambahkan shapes yang sudah dioptimasi
                    for shape in lottie_frames[mapped_idx]:
                        frame_layer.add_shape(shape.clone())
                    
                    prev_frame_idx = mapped_idx
                
                # Atur timing
                frame_layer.in_point = len(frame_timing)
                frame_layer.out_point = len(frame_timing) + 1
                frame_timing.append(len(frame_timing))
                
                next_target_time_ms += frame_interval_ms
    
    # Finalisasi
    animation.out_point = len(frame_timing)
    
    # Kompresi output
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    # Export dengan kompresi
    export_lottie(animation, output_path)
    
    # Optimasi JSON output
    import json
    with open(output_path, 'r') as f:
        data = json.load(f)
    
    # Hapus whitespace berlebih
    with open(output_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    
    original_size = os.path.getsize(output_path)
    print(f"\n--- Statistik Optimasi ---")
    print(f"Frame asli: {total_frames}")
    print(f"Frame unik: {len(unique_frames)}")
    print(f"Frame Lottie: {len(frame_timing)}")
    print(f"Ukuran file: {original_size / 1024:.1f} KB")
    print(f"Tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    quality = sys.argv[4] if len(sys.argv) > 4 else 'medium'
    
    gif_to_optimized_vector_lottie(input_file, output_file, target_fps=fps, quality=quality)