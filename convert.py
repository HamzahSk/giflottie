import os
import sys
import tempfile
import vtracer
from PIL import Image
from lottie import objects
from lottie.importers.svg import import_svg
from lottie.exporters.core import export_lottie

def gif_to_true_vector_lottie(gif_path, output_path, fps=30):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    print("Membaca file GIF...")
    gif = Image.open(gif_path)
    width, height = gif.size
    
    # Inisialisasi kerangka Lottie
    animation = objects.Animation(0, fps)
    animation.width = width
    animation.height = height
    animation.name = "Auto-Traced Vector Lottie"
    
    frame_count = 0
    
    # Menggunakan temporary directory agar tidak nyampah file PNG/SVG di folder repo
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            while True:
                print(f"Proses vektorisasi Frame {frame_count}...")
                
                # 1. Ambil frame transparan dan simpan sebagai PNG sementara
                frame_img = gif.convert("RGBA")
                png_path = os.path.join(temp_dir, f"frame_{frame_count}.png")
                svg_path = os.path.join(temp_dir, f"frame_{frame_count}.svg")
                frame_img.save(png_path, format="PNG")
                
                # 2. Lakukan Auto-Tracing PNG ke SVG menggunakan vtracer
                vtracer.convert_image_to_svg_py(
                    png_path,
                    svg_path,
                    colormode="color",         # Mendeteksi warna asli
                    mode="spline",             # Membuat garis kurva Bezier halus
                    hierarchical="stacked",    # Menumpuk warna agar rapi
                    filter_speckle=4,          # Menghilangkan noise piksel kecil
                    # Parameter penting untuk transparansi:
                    # vtracer otomatis menghiraukan piksel transparan pada RGBA
                )
                
                # 3. Import hasil SVG dan terjemahkan ke objek Lottie
                svg_anim = import_svg(svg_path)
                
                # 4. Buat Layer baru di Lottie utama untuk frame ini
                frame_layer = animation.add_layer(objects.ShapeLayer())
                frame_layer.name = f"Frame {frame_count}"
                
                # Atur durasi tampil frame (Sequencing)
                frame_layer.in_point = frame_count
                frame_layer.out_point = frame_count + 1
                
                # 5. Pindahkan bentuk matematika (Shapes) dari SVG ke Layer Lottie
                for svg_layer in svg_anim.layers:
                    if isinstance(svg_layer, objects.ShapeLayer):
                        for shape in svg_layer.shapes:
                            frame_layer.add_shape(shape)
                
                frame_count += 1
                gif.seek(gif.tell() + 1)
                
        except EOFError:
            pass # Selesai membaca semua frame

    # Update total durasi animasi
    animation.out_point = frame_count

    # Simpan hasil akhir ke file JSON
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    print(f"Menyusun dan menyimpan Lottie JSON (Total {frame_count} frame)...")
    export_lottie(animation, output_path)
    
    print(f"Sukses! True Vector Lottie tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    gif_to_true_vector_lottie(input_file, output_file)
