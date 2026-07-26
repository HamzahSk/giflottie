import os
import sys
import tempfile
import vtracer
from PIL import Image
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def gif_to_micro_vector_lottie(gif_path, output_path, target_fps=12, max_dimension=150):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print(f"Membaca file GIF dan mengoptimalkan ke {target_fps}fps...")
    gif = Image.open(gif_path)
    
    # Hitung rasio ukuran baru (Kecilkan resolusi)
    width, height = gif.size
    ratio = min(max_dimension / width, max_dimension / height)
    new_w, new_h = int(width * ratio), int(height * ratio)
    
    print(f"Kompresi Kanvas: {width}x{height}px -> {new_w}x{new_h}px (Vektor otomatis membesar tanpa pecah)")
    
    # Inisialisasi kerangka Lottie dengan ukuran kanvas yang sudah dikecilkan
    animation = objects.Animation(0, target_fps)
    animation.width = new_w
    animation.height = new_h
    animation.name = "Micro Vector Lottie"
    
    lottie_frame_count = 0
    frame_interval_ms = 1000.0 / target_fps
    current_time_ms = 0
    next_target_time_ms = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            while True:
                frame_duration = gif.info.get('duration', 100)
                
                if current_time_ms >= next_target_time_ms:
                    print(f"Kompresi & Tracing Frame ke-{lottie_frame_count}...")
                    
                    frame_img = gif.convert("RGBA")
                    
                    # 1. KOMPRESI GAMBAR (Resize ke ukuran kecil agar titik vektor berkurang drastis)
                    frame_img = frame_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    
                    png_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.png")
                    svg_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.svg")
                    frame_img.save(png_path, format="PNG")
                    
                    # 2. TUNING VTRACER (Mode agresif untuk mengurangi ukuran file SVG)
                    vtracer.convert_image_to_svg_py(
                        png_path,
                        svg_path,
                        colormode="color",
                        mode="polygon",         # Polygon (garis lurus) jauh lebih ringan dari Spline (kurva)
                        hierarchical="stacked",
                        filter_speckle=10,      # Mengabaikan bercak noise/piksel di bawah 10px
                        color_precision=4       # Menurunkan variasi warna agar bentuk lebih menyatu
                    )
                    
                    # Import SVG dan masukkan ke Layer Lottie
                    svg_anim = import_svg(svg_path)
                    
                    frame_layer = animation.add_layer(objects.ShapeLayer())
                    frame_layer.name = f"Frame {lottie_frame_count}"
                    frame_layer.in_point = lottie_frame_count
                    frame_layer.out_point = lottie_frame_count + 1
                    
                    for svg_layer in svg_anim.layers:
                        if isinstance(svg_layer, objects.ShapeLayer):
                            for shape in svg_layer.shapes:
                                frame_layer.add_shape(shape)
                    
                    next_target_time_ms += frame_interval_ms
                    lottie_frame_count += 1
                
                current_time_ms += frame_duration
                gif.seek(gif.tell() + 1)
                
        except EOFError:
            pass 

    animation.out_point = lottie_frame_count
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    export_lottie(animation, output_path)
    
    print("---")
    print(f"Sukses! Hasil Lottie dipadatkan dengan kompresi tingkat tinggi.")
    print(f"Tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    
    # Menjalankan dengan target 12 fps dan maksimal dimensi 150px
    gif_to_micro_vector_lottie(input_file, output_file, target_fps=12, max_dimension=150)
