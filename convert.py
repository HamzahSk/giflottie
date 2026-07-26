import os
import sys
import tempfile
import json
import vtracer
from PIL import Image, ImageChops
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def is_frame_identical(img1, img2):
    """Mengecek apakah dua frame sama persis menggunakan ImageChops."""
    if img1 is None or img2 is None:
        return False
    return ImageChops.difference(img1, img2).getbbox() is None

def minify_lottie_json(file_path):
    """Membaca file JSON Lottie dan menyimpannya kembali tanpa spasi (Minify)."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'))

def gif_to_optimized_vector_lottie(gif_path, output_path, target_fps=12, max_colors=16):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print(f"Membaca GIF, optimasi ke {target_fps}fps, dan kuantisasi {max_colors} warna...")
    gif = Image.open(gif_path)
    width, height = gif.size
    
    animation = objects.Animation(0, target_fps)
    animation.width = width
    animation.height = height
    animation.name = "Optimized Vector Lottie"
    
    lottie_frame_count = 0
    frame_interval_ms = 1000.0 / target_fps
    current_time_ms = 0
    next_target_time_ms = 0
    
    previous_frame_img = None
    last_added_layer = None
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            while True:
                frame_duration = gif.info.get('duration', 100)
                
                if current_time_ms >= next_target_time_ms:
                    # Color Quantization: Kurangi warna sebelum diconvert ke RGBA
                    quantized_img = gif.convert("P", palette=Image.ADAPTIVE, colors=max_colors)
                    frame_img = quantized_img.convert("RGBA")
                    
                    # Frame Difference: Cek apakah frame ini sama dengan frame sebelumnya
                    if is_frame_identical(frame_img, previous_frame_img) and last_added_layer:
                        print(f"Frame Lottie ke-{lottie_frame_count} sama dengan sebelumnya. Skip rendering...")
                        # Cukup perpanjang durasi layer terakhir (menghemat ukuran file secara drastis)
                        last_added_layer.out_point = lottie_frame_count + 1
                    else:
                        print(f"Memproses Vektor Frame Lottie ke-{lottie_frame_count}...")
                        
                        png_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.png")
                        svg_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.svg")
                        frame_img.save(png_path, format="PNG")
                        
                        # VTracer & Path Simplification Tweaks
                        # filter_speckle dinaikkan, color_precision diatur agar path lebih sedikit (polygon merge secara implisit)
                        vtracer.convert_image_to_svg_py(
                            png_path,
                            svg_path,
                            colormode="color",
                            mode="spline",
                            hierarchical="stacked",
                            filter_speckle=10,      # Mengabaikan bintik kecil (noise)
                            color_precision=8,      # Menggabungkan warna yang mirip
                            path_precision=3        # Menyederhanakan titik path (Path Simplification)
                        )
                        
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
                        previous_frame_img = frame_img
                    
                    next_target_time_ms += frame_interval_ms
                    lottie_frame_count += 1
                
                current_time_ms += frame_duration
                gif.seek(gif.tell() + 1)
                
        except EOFError:
            pass

    animation.out_point = lottie_frame_count

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    # Lottie Export
    export_lottie(animation, output_path)
    
    # JSON Minify
    minify_lottie_json(output_path)
    
    print("---")
    print(f"Sukses! Berhasil dipadatkan dari timeline aslinya menjadi {lottie_frame_count} frame Lottie.")
    print(f"File Lottie telah di-minify dan tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    gif_to_optimized_vector_lottie(input_file, output_file, target_fps=12, max_colors=16)
