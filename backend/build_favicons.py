import os
import math
from PIL import Image, ImageDraw

def render_icon(target_size=512):
    # Render at 4x supersampling for ultra smooth anti-aliased curves
    scale = 4
    dim = target_size * scale
    img = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background Orange Squircle
    radius = int(dim * 0.28)
    draw.rounded_rectangle([0, 0, dim - 1, dim - 1], radius=radius, fill=(255, 110, 0, 255))

    # Helper coordinate converter from 100x100 grid
    def p(x, y):
        return (x * dim / 100.0, y * dim / 100.0)

    sw = int(dim * 0.048) # Stroke width

    # Draw helper for thick lines with round caps
    def draw_line(p1, p2):
        draw.line([p1, p2], fill=(255, 255, 255, 255), width=sw)
        r = sw / 2.0
        draw.ellipse([p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r], fill=(255, 255, 255, 255))
        draw.ellipse([p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r], fill=(255, 255, 255, 255))

    # Draw vertical axis
    draw_line(p(48, 26), p(48, 74))

    # Draw top circuit branch
    draw_line(p(48, 37), p(57, 37))
    draw_line(p(57, 37), p(57, 32))
    draw_line(p(57, 32), p(63, 32))

    # Draw middle circuit branch
    draw_line(p(48, 52), p(63, 52))

    # Draw bottom circuit branch
    draw_line(p(48, 66), p(57, 66))
    draw_line(p(57, 66), p(57, 71))
    draw_line(p(57, 71), p(63, 71))

    # Terminal node circles
    node_r = (3.6 * dim / 100.0)
    for cx, cy in [(68, 32), (68, 52), (68, 71)]:
        center = p(cx, cy)
        draw.ellipse(
            [center[0] - node_r, center[1] - node_r, center[0] + node_r, center[1] + node_r],
            fill=(255, 255, 255, 255)
        )

    # Bezier curve helper
    def bezier_point(p0, p1, p2, p3, t):
        x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
        return (x, y)

    # Draw Left Brain Hemisphere profile lobes
    lobe_curves = [
        (p(48, 26), p(38, 26), p(31, 32), p(32, 40)),
        (p(32, 40), p(24, 43), p(24, 54), p(31, 59)),
        (p(31, 59), p(30, 67), p(38, 74), p(48, 74)),
    ]

    for c in lobe_curves:
        steps = 50
        pts = [bezier_point(c[0], c[1], c[2], c[3], i / float(steps)) for i in range(steps + 1)]
        for i in range(len(pts) - 1):
            draw_line(pts[i], pts[i+1])

    # Inner cortex loop
    c_inner = (p(48, 64), p(40, 64), p(38, 56), p(43, 51))
    pts_inner = [bezier_point(c_inner[0], c_inner[1], c_inner[2], c_inner[3], i / 40.0) for i in range(41)]
    for i in range(len(pts_inner) - 1):
        draw_line(pts_inner[i], pts_inner[i+1])

    # Final downsample with LANCZOS filter for smooth edges
    final_img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    return final_img

# Output paths
frontend_public = os.path.abspath("../frontend/public")
os.makedirs(frontend_public, exist_ok=True)

# 1. Generate logo.png (512x512)
img_512 = render_icon(512)
img_512.save(os.path.join(frontend_public, "logo.png"), "PNG")
print("Saved logo.png")

# 2. Generate favicon.ico (multi-size 16, 32, 48, 64)
sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
img_512.save(
    os.path.join(frontend_public, "favicon.ico"),
    format="ICO",
    sizes=sizes
)
print("Saved favicon.ico")
