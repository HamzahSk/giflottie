import sys
import os
import cv2
import numpy as np
from PIL import Image

# Import library pembuat Lottie
from lottie import objects
from lottie.exporters.core import export_lottie
from lottie.utils.color import Color
from lottie.objects.bezier import Bezier

def extract_contours(image_frame, simplify_tolerance=1.5):
    """Mengekstrak kontur dari transparansi menggunakan OpenCV"""
    np_image = np.array(image_frame)
    
    # Pisahkan Alpha Channel (Transparansi)
    if np_image.shape[2] == 4:
        mask = np_image[:, :, 3]
    else:
        mask = cv2.cvtColor(np_image, cv2.COLOR_RGBA2GRAY)
        
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    shapes = []
    for contour in contours:
        epsilon = simplify_tolerance * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        if len(approx) < 3:
            continue
            
        vertices = []
        for point in approx:
            x, y = point[0]
            vertices.append((float(x), float(y)))
            
        shapes.append(vertices)
    return shapes

def gif_to_accurate_lottie(gif_path, output_path, fps=30):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    gif = Image.open(gif_path)
    width, height = gif.size
    
    print(f"Memproses {gif_path} menjadi Lottie dengan library...")
    
    frames_shapes = []
    try:
        while True:
            frame = gif.convert("RGBA")
            shapes = extract_contours(frame)
            frames_shapes.append(shapes)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    total_frames = len(frames_shapes)
    
    # --- Inisialisasi Objek Animasi Lottie ---
    # Library Lottie akan mengurus struktur dasar JSON secara otomatis
    animation = objects.Animation(total_frames, fps)
    animation.width = width
    animation.height = height
    animation.name = "Accurate Vectorized Lottie"

    # --- Menyusun Frame ke dalam Shape Layers ---
    for i, shapes in enumerate(frames_shapes):
        # Buat layer baru untuk setiap frame
        layer = animation.add_layer(objects.ShapeLayer())
        layer.name = f"Frame {i}"
        
        # Atur kapan frame ini muncul dan menghilang
        layer.in_point = i
        layer.out_point = i + 1
        
        # Masukkan semua bentuk vektor ke dalam layer ini
        for shape_vertices in shapes:
            group = layer.add_shape(objects.Group())
            
            # Buat kurva Bezier (Poligon tertutup)
            bezier = Bezier()
            for x, y in shape_vertices:
                bezier.add_point(objects.NVector(x, y))
            bezier.close()
            
            # Tambahkan Path
            path = group.add_shape(objects.Path())
            path.shape.value = bezier
            
            # Tambahkan Fill Color (Warna isi: Hitam pekat)
            # Kamu bisa mengubah RGB-nya di sini (skala 0-1)
            group.add_shape(objects.Fill(Color(0, 0, 0)))

    # --- Ekspor ke JSON ---
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    export_lottie(animation, output_path)
    print(f"Sukses! Lottie JSON akurat tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    gif_to_accurate_lottie(input_file, output_file)
