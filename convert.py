import json
import sys
import os
import cv2
import numpy as np
from PIL import Image

def extract_vector_shapes(image_frame, simplify_tolerance=1.5):
    """
    Menggunakan logika matematika (OpenCV) untuk mencari kontur
    dan menyederhanakannya menjadi titik vektor.
    """
    # Pisahkan channel Alpha (Transparansi) untuk dijadikan acuan bentuk
    # Asumsi: Bagian yang solid (alpha > 128) akan dijadikan vektor
    np_image = np.array(image_frame)
    
    # Jika tidak ada alpha channel, buat gambar grayscale biasa
    if np_image.shape[2] == 4:
        mask = np_image[:, :, 3]
    else:
        mask = cv2.cvtColor(np_image, cv2.COLOR_RGBA2GRAY)
        
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

    # Mencari titik koordinat kontur (Topological Structural Analysis)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    shapes = []
    for contour in contours:
        # Menyederhanakan titik menggunakan algoritma Ramer-Douglas-Peucker
        epsilon = simplify_tolerance * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Jika bentuk terlalu kecil, abaikan (noise filtering)
        if len(approx) < 3:
            continue
            
        # Konversi koordinat matriks OpenCV ke format vertex Lottie
        vertices = []
        for point in approx:
            x, y = point[0]
            vertices.append([float(x), float(y)])
            
        shapes.append(vertices)
        
    return shapes

def gif_to_vector_lottie(gif_path, output_path, fps=30):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    gif = Image.open(gif_path)
    width, height = gif.size
    
    print(f"Mengekstrak dan mem-vektorisasi {gif_path}...")
    
    frames_shapes = []
    
    try:
        while True:
            frame = gif.convert("RGBA")
            # Jalankan logika matematika untuk mengekstrak vektor
            shapes = extract_vector_shapes(frame)
            frames_shapes.append(shapes)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    total_frames = len(frames_shapes)
    
    # --- Struktur Dasar Lottie ---
    lottie_data = {
        "v": "5.5.2",
        "fr": fps,
        "ip": 0,
        "op": total_frames,
        "w": width,
        "h": height,
        "nm": "Vectorized Lottie",
        "ddd": 0,
        "assets": [],
        "layers": []
    }

    # --- Membangun Shape Layers ---
    for i, shapes in enumerate(frames_shapes):
        # Struktur untuk menampung semua bentuk vektor dalam satu frame
        shape_group = []
        
        for shape_vertices in shapes:
            # Karena ini poligon sederhana, in dan out tangents diisi 0 (sudut tajam)
            tangents = [[0, 0] for _ in shape_vertices]
            
            path_data = {
                "ty": "sh", # Shape
                "ks": {
                    "a": 0,
                    "k": {
                        "i": tangents,
                        "o": tangents,
                        "v": shape_vertices,
                        "c": True # Closed path
                    },
                    "ix": 2
                },
                "nm": "Path",
                "hd": False
            }
            shape_group.append(path_data)
            
        # Tambahkan fill color (warna isi vektor, misal: hitam solid)
        shape_group.append({
            "ty": "fl",
            "c": {"a": 0, "k": [0, 0, 0, 1], "ix": 4}, # RGBA (0-1 range)
            "o": {"a": 0, "k": 100, "ix": 5},
            "nm": "Fill 1",
            "hd": False
        })

        # Masukkan ke dalam Layer Lottie
        lottie_data["layers"].append({
            "ddd": 0,
            "ind": i + 1,
            "ty": 4, # Tipe 4 adalah Shape Layer (Vektor Murni)
            "nm": f"Vector Frame {i}",
            "sr": 1,
            "ks": {
                "o": {"a": 0, "k": 100, "ix": 11},
                "r": {"a": 0, "k": 0, "ix": 10},
                "p": {"a": 0, "k": [0, 0, 0], "ix": 2},
                "a": {"a": 0, "k": [0, 0, 0], "ix": 1},
                "s": {"a": 0, "k": [100, 100, 100], "ix": 6}
            },
            "ao": 0,
            "shapes": [{
                "ty": "gr",
                "it": shape_group,
                "nm": "Vector Group",
                "hd": False
            }],
            "ip": i,       # Frame masuk
            "op": i + 1,   # Frame keluar
            "st": 0,
            "bm": 0
        })

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(lottie_data, f)
        
    print(f"Sukses! Vector Lottie (Shape Layers) tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/vector_output.json"
    gif_to_vector_lottie(input_file, output_file)
