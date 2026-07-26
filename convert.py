import os
import sys
import tempfile
import vtracer
from PIL import Image
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def gif_to_optimized_vector_lottie(gif_path, output_path, target_fps=8, max_dim=300):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print(f"Membaca file GIF, set ke {target_fps}fps, dan resize max {max_dim}px...")
    gif = Image.open(gif_path)
    
    # Hitung rasio untuk resize (kompresi resolusi ringan)
    orig_w, orig_h = gif.size
    ratio = min(max_dim / orig_w, max_dim / orig_h) if orig_w > max_dim or orig_h > max_dim else 1
    new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
    
    # Inisialisasi kerangka Lottie dengan target fps dan resolusi baru
    animation = objects.Animation(0, target_fps)
    animation.width = new_w
    animation.height = new_h
    animation.name = "Optimized Vector Lottie"
    
    lottie_frame_count = 0
    
    # Logika Waktu untuk Frame Skipping
    frame_interval_ms = 1000.0 / target_fps
    current_time_ms = 0
    next_target_time_ms = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            while True:
                # Dapatkan durasi frame ini dari metadata GIF (default 100ms jika tidak ada)
                frame_duration = gif.info.get('duration', 100)
                
                # Jika waktu saat ini sudah mencapai atau melewati target waktu berikutnya,
                # kita EKSTRAK frame ini.
                if current_time_ms >= next_target_time_ms:
                    print(f"Memproses Vektor Frame Lottie ke-{lottie_frame_count}...")
                    
                    frame_img = gif.convert("RGBA")
                    
                    # KOMPRESI GAMBAR (Resize sedikit biar vtracer gak kerja terlalu berat)
                    if ratio < 1:
                        frame_img = frame_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        
                    png_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.png")
                    svg_path = os.path.join(temp_dir, f"frame_{lottie_frame_count}.svg")
                    
                    # Simpan PNG dengan optimalisasi
                    frame_img.save(png_path, format="PNG", optimize=True)
                    
                    # Auto-Tracing (PNG ke SVG) - Menggunakan spline agar detail agak natural
                    vtracer.convert_image_to_svg_py(
                        png_path,
                        svg_path,
                        colormode="color",
                        mode="spline",
                        hierarchical="stacked",
                        filter_speckle=4
                    )
                    
                    # Import SVG ke Lottie
                    svg_anim = import_svg(svg_path)
                    
                    # Buat layer frame baru
                    frame_layer = animation.add_layer(objects.ShapeLayer())
                    frame_layer.name = f"Frame {lottie_frame_count}"
                    
                    # Atur kapan frame ini muncul (in) dan hilang (out)
                    frame_layer.in_point = lottie_frame_count
                    frame_layer.out_point = lottie_frame_count + 1
                    
                    # Masukkan data bentuk (shapes)
                    for svg_layer in svg_anim.layers:
                        if isinstance(svg_layer, objects.ShapeLayer):
                            for shape in svg_layer.shapes:
                                frame_layer.add_shape(shape)
                    
                    # Tentukan target waktu untuk frame berikutnya
                    next_target_time_ms += frame_interval_ms
                    lottie_frame_count += 1
                
                # Tambahkan durasi frame saat ini ke total waktu
                current_time_ms += frame_duration
                
                # Pindah ke frame GIF berikutnya
                gif.seek(gif.tell() + 1)
                
        except EOFError:
            pass # Selesai membaca semua frame GIF

    # Set total frame yang dihasilkan
    animation.out_point = lottie_frame_count

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    export_lottie(animation, output_path)
    
    print("---")
    print(f"Sukses! Dipadatkan dari timeline aslinya menjadi {lottie_frame_count} frame Lottie ({new_w}x{new_h}px).")
    print(f"Tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    
    # Target FPS diturunkan jadi 8, maksimal resolusi tracing 300px
    gif_to_optimized_vector_lottie(input_file, output_file, target_fps=8, max_dim=300)
