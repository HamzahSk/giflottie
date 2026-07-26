import json
import base64
import sys
import os
from io import BytesIO
from PIL import Image

def gif_to_lottie(gif_path, output_path, fps=30):
    if not os.path.exists(gif_path):
        print(f"Error: File '{gif_path}' tidak ditemukan!")
        sys.exit(1)

    try:
        gif = Image.open(gif_path)
    except Exception as e:
        print(f"Gagal membuka file GIF: {e}")
        sys.exit(1)

    frames = []
    width, height = gif.size
    
    print(f"Mengekstrak frame dari {gif_path} ({width}x{height}px)...")
    
    try:
        while True:
            frame = gif.convert("RGBA")
            buffer = BytesIO()
            frame.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            frames.append(img_str)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    total_frames = len(frames)
    print(f"Total frame diekstrak: {total_frames}")

    lottie_data = {
        "v": "5.5.2",
        "fr": fps,
        "ip": 0,
        "op": total_frames,
        "w": width,
        "h": height,
        "nm": "GIF to Lottie",
        "ddd": 0,
        "assets": [],
        "layers": []
    }

    for i, img_b64 in enumerate(frames):
        asset_id = f"image_{i}"
        
        lottie_data["assets"].append({
            "id": asset_id,
            "w": width,
            "h": height,
            "u": "",
            "p": f"data:image/png;base64,{img_b64}"
        })
        
        lottie_data["layers"].append({
            "ddd": 0,
            "ind": i + 1,
            "ty": 2,
            "nm": f"Frame {i}",
            "refId": asset_id,
            "sr": 1,
            "ks": {
                "o": {"a": 0, "k": 100, "ix": 11},
                "r": {"a": 0, "k": 0, "ix": 10},
                "p": {"a": 0, "k": [width/2, height/2, 0], "ix": 2},
                "a": {"a": 0, "k": [width/2, height/2, 0], "ix": 1},
                "s": {"a": 0, "k": [100, 100, 100], "ix": 6}
            },
            "ao": 0,
            "ip": i,
            "op": i + 1,
            "st": 0,
            "bm": 0
        })

    # Buat direktori output jika belum ada
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(lottie_data, f)
        
    print(f"Selesai! Lottie JSON tersimpan di: {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "inputs/input.gif"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/output.json"
    gif_to_lottie(input_file, output_file)
