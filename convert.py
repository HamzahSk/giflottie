import os
import sys
import tempfile
import json
import cv2
import numpy as np
import vtracer
from PIL import Image
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def minify_lottie_json(file_path):
    """Minify JSON Lottie untuk memangkas ukuran byte."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'))

def gif_to_optimized_lottie_cv(gif_path, output_path, target_fps=12, max_colors=16):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print("Menggunakan OpenCV untuk ekstraksi dan optimasi Frame Difference...")
    
    # OpenCV jauh lebih andal dalam mengekstrak GIF tanpa bug transparansi
    cap = cv2.VideoCapture(gif_path)
    if not cap.isOpened():
        print("Error: OpenCV gagal membaca GIF.")
        sys.exit(1)
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    animation = objects.Animation(0, target_fps)
    animation.width = width
    animation.height = height
    animation.name = "OpenCV Optimized Lottie"
    
    lottie_frame_count = 0
    last_added_layer = None
    prev_gray = None
    
    with tempfile.TemporaryDirectory() as temp_dir:
        while True:
            ret, frame = cap.read()
            if not ret:
                break # Frame habis
                
            # Konversi ke Grayscale khusus untuk mencari perbedaan frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            is_identical = False
            
            # FRAME DIFFERENCE (OpenCV)
            if prev_gray is not None:
                # Cari selisih absolut antar frame
                diff = cv2.absdiff(gray, prev_gray)
                # Filter noise kecil (Thresholding)
                _, thresh = cv2.threshold(diff, 10, 255, cv2.THRESH_BINARY)
                
                # Hitung persentase piksel yang berubah
                changed_pixels = cv2.countNonZero(thresh)
                total_pixels = width * height
                
                # Jika perubahan kurang dari 1% (0.01), anggap frame sama (Skip!)
                if (changed_pixels / total_pixels) < 0.01:
                    is_identical = True

            if is_identical and last_added_layer:
                print(f"Frame {lottie_frame_count} mirip dengan sebelumnya. Durasi diperpanjang!")
                last_added_layer.out_point = lottie_frame_count + 1
            else:
                print(f"Merender Vektor Frame {lottie_frame_count}...")
                
                # COLOR QUANTIZATION (Konversi kembali BGR ke RGB untuk PIL)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                
                # Batasi warna untuk meringankan beban VTracer
                quantized = pil_img.quantize(colors=max_colors)
                frame_rgba = quantized.convert("RGBA")
                
                png_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.png")
                svg_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.svg")
                frame_rgba.save(png_path, format="PNG")
                
                # VTRACER & PATH SIMPLIFICATION
                vtracer.convert_image_to_svg_py(
                    png_path, svg_path,
                    colormode="color", mode="spline", hierarchical="stacked",
                    filter_speckle=8, color_precision=6, path_precision=3
                )
                
                # EXPORT KE LOTTIE
                svg_anim = import_svg(svg_path)
                frame_layer = animation.add_layer(objects.ShapeLayer())
                frame_layer.name = f"Frame {lottie_frame_count}"
                frame_layer.in_point = lottie_frame_count
                frame_layer.out_point = lottie_frame_count + 1
                
                for svg_layer in svg_anim.layers:
                    if isinstance(svg_layer, objects.ShapeLayer):
                        for shape in svg_layer.shapes:
                            frame_layer.add_shape(shape)
                            
                last_added_layer = frame_layer
                
                # Update prev_gray HANYA jika frame ini dirender
                # Agar tidak terjadi pergeseran warna/bentuk perlahan yang ter-skip
                prev_gray = gray 
                
            lottie_frame_count += 1
            
    animation.out_point = lottie_frame_count
    
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    export_lottie(animation, output_path)
    
    # JSON MINIFY
    minify_lottie_json(output_path)
    
    print("---")
    print(f"Sukses! Total durasi timeline Lottie: {lottie_frame_count} frame.")
    print(f"Tersimpan dan di-minify di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    gif_to_optimized_lottie_cv(input_file, output_file, target_fps=12, max_colors=16)
