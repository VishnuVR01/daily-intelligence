import os
import struct
import zlib

def create_png(width, height, fill_color, icon_color, filename):
    # Prepare RGBA pixel data
    # Background: fill_color (r, g, b, a)
    # Drawer: draw a crisp newspaper/archive icon in the center
    pixels = bytearray()
    
    cx, cy = width // 2, height // 2
    border_r = int(width * 0.42)
    
    # Simple, high-quality icon design: Dark navy circle with white "DI" emblem / newspaper icon
    for y in range(height):
        pixels.append(0)  # Filter byte for line (0 = None)
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist_sq = dx * dx + dy * dy
            
            # Outer rounded square/circle background
            if dist_sq <= border_r * border_r:
                r, g, b, a = fill_color
                # Draw newspaper folds / paper icon in center
                margin_x = int(width * 0.24)
                margin_y = int(height * 0.24)
                if abs(dx) < int(width * 0.24) and abs(dy) < int(height * 0.24):
                    # Inner newspaper page
                    r, g, b, a = 255, 255, 255, 255
                    # Header line
                    if -int(height * 0.18) <= dy <= -int(height * 0.12) and abs(dx) < int(width * 0.18):
                        r, g, b, a = icon_color
                    # Body lines
                    elif -int(height * 0.05) <= dy <= -int(height * 0.01) and abs(dx) < int(width * 0.18):
                        r, g, b, a = icon_color
                    elif int(height * 0.04) <= dy <= int(height * 0.08) and abs(dx) < int(width * 0.18):
                        r, g, b, a = icon_color
                    elif int(height * 0.12) <= dy <= int(height * 0.16) and abs(dx) < int(width * 0.12):
                        r, g, b, a = icon_color
            else:
                r, g, b, a = 0, 0, 0, 0
                
            pixels.extend([r, g, b, a])
            
    compressed = zlib.compress(pixels, 9)
    
    def make_chunk(chunk_type, data):
        length = len(data)
        crc = zlib.crc32(chunk_type + data) & 0xffffffff
        return struct.pack('>I', length) + chunk_type + data + struct.pack('>I', crc)
        
    png_signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_chunk = make_chunk(b'IHDR', ihdr_data)
    idat_chunk = make_chunk(b'IDAT', compressed)
    iend_chunk = make_chunk(b'IEND', b'')
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(png_signature + ihdr_chunk + idat_chunk + iend_chunk)
    print(f"Generated {filename}")

def create_svg(filename):
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <rect width="512" height="512" rx="128" fill="#1e293b"/>
  <rect x="112" y="112" width="288" height="288" rx="24" fill="#ffffff"/>
  <rect x="152" y="152" width="208" height="36" rx="8" fill="#1e293b"/>
  <rect x="152" y="216" width="208" height="20" rx="4" fill="#64748b"/>
  <rect x="152" y="252" width="208" height="20" rx="4" fill="#64748b"/>
  <rect x="152" y="288" width="144" height="20" rx="4" fill="#64748b"/>
  <circle cx="336" cy="316" r="24" fill="#2563eb"/>
</svg>"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    print(f"Generated {filename}")

if __name__ == "__main__":
    navy = (30, 41, 59, 255)      # #1e293b
    accent = (37, 99, 235, 255)   # #2563eb
    create_svg("static/icons/icon.svg")
    create_png(192, 192, navy, accent, "static/icons/icon-192.png")
    create_png(512, 512, navy, accent, "static/icons/icon-512.png")
