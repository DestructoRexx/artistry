import re

PRESET_THEMES = {
    "gallery_white": {
        "id": "gallery_white",
        "name": "Gallery White",
        "badge": "Classic",
        "preview": "linear-gradient(135deg, #ffffff 0%, #f4f4f5 100%)",
        "description": "Crisp daylight museum walls with clean black ink.",
        "css": """
            body.studio-body { background-color: #fafafa; color: #18181b; font-family: ui-sans-serif, system-ui, sans-serif; }
            .studio-card { background: #ffffff; border: 1px solid #e4e4e7; }
            .studio-accent { color: #4f46e5; }
            .studio-badge { background: rgba(0, 0, 0, 0.72); color: #ffffff; }
        """
    },
    "pinterest_mode": {
        "id": "pinterest_mode",
        "name": "Pinterest Mode",
        "badge": "Masonry",
        "preview": "linear-gradient(135deg, #ffffff 0%, #ffe4e6 50%, #f4f4f5 100%)",
        "description": "Organic masonry cascade with randomized short & tall frames.",
        "css": """
            body.studio-body { background-color: #ffffff; color: #111111; font-family: ui-sans-serif, system-ui, sans-serif; }
            .studio-card { background: #f8f8f8; border: 1px solid #efefef; }
            .studio-accent { color: #e60023; }
            .studio-badge { background: rgba(17, 17, 17, 0.8); color: #ffffff; border-radius: 9999px; }
        """
    },
    "obsidian_darkroom": {
        "id": "obsidian_darkroom",
        "name": "Obsidian Darkroom",
        "badge": "Dark",
        "preview": "linear-gradient(135deg, #09090b 0%, #18181b 100%)",
        "description": "Matte black exhibition space that makes luminous colors pop.",
        "css": """
            body.studio-body { background-color: #09090b; color: #f4f4f5; font-family: ui-sans-serif, system-ui, sans-serif; }
            .studio-card { background: #121215; border: 1px solid #27272a; }
            .studio-accent { color: #818cf8; }
            .studio-badge { background: rgba(24, 24, 27, 0.85); color: #f4f4f5; border-color: rgba(255,255,255,0.15); }
        """
    },
    "warm_parchment": {
        "id": "warm_parchment",
        "name": "Warm Parchment",
        "badge": "Editorial",
        "preview": "linear-gradient(135deg, #f5f2eb 0%, #e7e0d2 100%)",
        "description": "Fine-art print house aesthetic with classic serif typography.",
        "css": """
            body.studio-body { background-color: #f5f2eb; color: #292524; font-family: Georgia, Cambria, "Times New Roman", serif; }
            .studio-card { background: #faf8f5; border: 1px solid #d6cfc2; }
            .studio-accent { color: #9a3412; }
            .studio-badge { background: rgba(41, 37, 36, 0.82); color: #faf8f5; }
        """
    },
    "cyber_brutalist": {
        "id": "cyber_brutalist",
        "name": "Cyber Brutalist",
        "badge": "Edgy",
        "preview": "linear-gradient(135deg, #111111 0%, #22c55e 100%)",
        "description": "Raw sharp edges, terminal monospace, and high-voltage green.",
        "css": """
            body.studio-body {
                background-color: #0d0d0d; color: #e4e4e7; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                background-image: radial-gradient(#22c55e22 1px, transparent 1px); background-size: 20px 20px;
            }
            .studio-card, .art-frame { background: #141414; border: 1px solid #22c55e; border-radius: 0px !important; }
            .studio-avatar { border-radius: 0px !important; }
            .studio-accent { color: #22c55e; }
            .studio-badge { background: #000000; color: #22c55e; border: 1px solid #22c55e; border-radius: 0px !important; }
        """
    },
    "retro_vaporwave": {
        "id": "retro_vaporwave",
        "name": "Retro Vaporwave",
        "badge": "Animated",
        "preview": "linear-gradient(135deg, #ff71ce 0%, #01cdfe 50%, #b967ff 100%)",
        "description": "Dreamy pastel twilight with drifting horizon aura.",
        "css": """
            @keyframes vaporShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
            body.studio-body {
                background: linear-gradient(-45deg, #1a0b2e, #2d1447, #162447, #2b1038);
                background-size: 400% 400%; animation: vaporShift 14s ease infinite; color: #fdf2f8;
            }
            .studio-card { background: rgba(26, 11, 46, 0.72); backdrop-filter: blur(12px); border: 1px solid rgba(255, 113, 206, 0.35); }
            .studio-accent { color: #ff71ce; }
            .studio-badge { background: rgba(1, 205, 254, 0.25); backdrop-filter: blur(8px); color: #ffffff; border: 1px solid #01cdfe; }
        """
    },
    "sakura_atelier": {
        "id": "sakura_atelier",
        "name": "Sakura Atelier",
        "badge": "Animated",
        "preview": "linear-gradient(135deg, #fff1f2 0%, #fecdd3 100%)",
        "description": "Soft blossom studio with floating petal particles.",
        "css": """
            body.studio-body { background-color: #fff1f2; color: #4c0519; }
            .studio-card { background: rgba(255, 255, 255, 0.85); border: 1px solid #fecdd3; }
            .studio-accent { color: #e11d48; }
            .studio-badge { background: rgba(136, 19, 55, 0.78); color: #fff1f2; }
            .studio-particles::before, .studio-particles::after {
                content: "🌸"; position: fixed; top: -10%; font-size: 18px; opacity: 0.55; pointer-events: none; z-index: 40;
                animation: sakuraFall 12s linear infinite;
            }
            .studio-particles::before { left: 18%; animation-delay: 0s; }
            .studio-particles::after { left: 76%; animation-delay: 6s; }
            @keyframes sakuraFall {
                0% { transform: translateY(0) rotate(0deg); opacity: 0; }
                15% { opacity: 0.65; }
                100% { transform: translateY(110vh) rotate(360deg); opacity: 0; }
            }
        """
    },
    "midnight_neon": {
        "id": "midnight_neon",
        "name": "Midnight Neon",
        "badge": "Animated",
        "preview": "linear-gradient(135deg, #090d16 0%, #4f46e5 100%)",
        "description": "Deep indigo glassmorphism with pulsing ultraviolet frame borders.",
        "css": """
            @keyframes neonPulse { 0%, 100% { box-shadow: 0 0 12px rgba(99, 102, 241, 0.25); } 50% { box-shadow: 0 0 24px rgba(168, 85, 247, 0.5); } }
            body.studio-body { background-color: #070a12; color: #eef2ff; }
            .studio-card { background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(99, 102, 241, 0.4); animation: neonPulse 5s infinite; }
            .studio-accent { color: #a855f7; }
            .studio-badge { background: rgba(79, 70, 229, 0.75); color: #ffffff; border: 1px solid #818cf8; }
        """
    },
    "minimalist_void": {
        "id": "minimalist_void",
        "name": "Minimalist Void",
        "badge": "Ultra Clean",
        "preview": "linear-gradient(135deg, #000000 0%, #0a0a0a 100%)",
        "description": "Zero borders, pure pitch-black negative space, 100% focus on art.",
        "css": """
            body.studio-body { background-color: #000000; color: #d4d4d8; }
            .studio-card, .art-frame { background: #000000; border: none; box-shadow: none; }
            .studio-accent { color: #ffffff; }
            .studio-badge { background: rgba(0, 0, 0, 0.8); color: #a1a1aa; border: none; }
        """
    },
    "golden_louvre": {
        "id": "golden_louvre",
        "name": "Golden Louvre",
        "badge": "Prestige",
        "preview": "linear-gradient(135deg, #1c1917 0%, #ca8a04 100%)",
        "description": "Charcoal velvet walls trimmed in warm museum gold.",
        "css": """
            body.studio-body { background-color: #171412; color: #fefce8; font-family: Georgia, serif; }
            .studio-card { background: #1f1b18; border: 1px solid rgba(202, 138, 4, 0.45); }
            .studio-accent { color: #eab308; }
            .studio-badge { background: rgba(23, 20, 18, 0.88); color: #fde047; border: 1px solid rgba(234, 179, 8, 0.4); }
        """
    },
    "sketchbook_zine": {
        "id": "sketchbook_zine",
        "name": "Sketchbook Zine",
        "badge": "Indie",
        "preview": "linear-gradient(135deg, #fefce8 0%, #fef08a 100%)",
        "description": "Dot-grid sketchbook paper with playful dashed borders.",
        "css": """
            body.studio-body {
                background-color: #fefce8; color: #1c1917; font-family: ui-monospace, SFMono-Regular, monospace;
                background-image: radial-gradient(#a8a29e 1px, transparent 1px); background-size: 16px 16px;
            }
            .studio-card, .art-frame { background: #ffffff; border: 2px dashed #44403c; }
            .art-frame:hover { transform: rotate(-1deg) scale(1.02); }
            .studio-accent { color: #ea580c; }
            .studio-badge { background: #1c1917; color: #fef08a; }
        """
    }
}

FRAME_STYLES = {
    "none": {
        "label": "None (Clean Borderless)",
        "art_css": "",
        "avatar_css": ""
    },
    "louvre_gold": {
        "label": "Ornate Louvre Gold",
        "art_css": """
            .art-frame {
                padding: 10px !important;
                background: linear-gradient(145deg, #f5d061, #b8860b, #f3e5ab, #996515) !important;
                border: 3px solid #78500a !important;
                box-shadow: inset 0 0 8px rgba(0,0,0,0.65), 0 12px 24px rgba(0,0,0,0.35) !important;
                border-radius: 4px !important;
            }
            .art-frame img { border: 2px solid #422b04; }
        """,
        "avatar_css": """
            .studio-avatar {
                padding: 5px !important;
                background: linear-gradient(145deg, #f5d061, #b8860b, #f3e5ab, #996515) !important;
                border: 3px solid #78500a !important;
                box-shadow: 0 8px 20px rgba(0,0,0,0.35) !important;
            }
            .studio-avatar img { border-radius: 9999px; }
        """
    },
    "gallery_mat": {
        "label": "Gallery Matte White (Passe-Partout)",
        "art_css": """
            .art-frame {
                padding: 14px !important;
                background: #fafaf9 !important;
                border: 6px solid #18181b !important;
                box-shadow: inset 0 0 6px rgba(0,0,0,0.18), 0 10px 22px rgba(0,0,0,0.2) !important;
                border-radius: 2px !important;
            }
            .art-frame img { border: 1px solid #d4d4d8; }
        """,
        "avatar_css": """
            .studio-avatar {
                padding: 5px !important;
                background: #fafaf9 !important;
                border: 4px solid #18181b !important;
                box-shadow: 0 8px 18px rgba(0,0,0,0.2) !important;
            }
            .studio-avatar img { border-radius: 9999px; }
        """
    },
    "walnut_wood": {
        "label": "Classic Walnut Wood",
        "art_css": """
            .art-frame {
                padding: 10px !important;
                background: linear-gradient(135deg, #5c3a21 0%, #3e2411 50%, #4a2c16 100%) !important;
                border: 3px solid #2b1709 !important;
                box-shadow: inset 0 0 10px rgba(0,0,0,0.75), 0 12px 24px rgba(0,0,0,0.3) !important;
                border-radius: 3px !important;
            }
            .art-frame img { border: 2px solid #d6cbb8; }
        """,
        "avatar_css": """
            .studio-avatar {
                padding: 5px !important;
                background: linear-gradient(135deg, #5c3a21 0%, #3e2411 100%) !important;
                border: 3px solid #2b1709 !important;
            }
            .studio-avatar img { border-radius: 9999px; }
        """
    },
    "obsidian_box": {
        "label": "Obsidian Museum Box",
        "art_css": """
            .art-frame {
                padding: 8px !important;
                background: #09090b !important;
                border: 4px solid #27272a !important;
                box-shadow: inset 0 0 8px #000000, 0 10px 25px rgba(0,0,0,0.45) !important;
                border-radius: 2px !important;
            }
        """,
        "avatar_css": """
            .studio-avatar {
                padding: 4px !important;
                background: #09090b !important;
                border: 4px solid #27272a !important;
            }
            .studio-avatar img { border-radius: 9999px; }
        """
    },
    "cyber_neon": {
        "label": "Neon Cyber Bezel",
        "art_css": """
            .art-frame {
                padding: 4px !important;
                background: linear-gradient(135deg, #06b6d4, #a855f7, #ec4899) !important;
                box-shadow: 0 0 18px rgba(168, 85, 247, 0.45) !important;
            }
            .art-frame img { border-radius: 8px; }
        """,
        "avatar_css": """
            .studio-avatar {
                padding: 4px !important;
                background: linear-gradient(135deg, #06b6d4, #a855f7, #ec4899) !important;
                box-shadow: 0 0 20px rgba(168, 85, 247, 0.55) !important;
            }
            .studio-avatar img { border-radius: 9999px; }
        """
    }
}

ANIMATION_SNIPPETS = {
    "none": "",
    "float": """
        @keyframes gentleFloat { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-6px); } }
        .art-frame { animation: gentleFloat 6s ease-in-out infinite; }
        .art-frame:nth-child(even) { animation-delay: 3s; }
    """,
    "glow": """
        .art-frame:hover { box-shadow: 0 0 25px rgba(99, 102, 241, 0.45); transform: translateY(-4px); transition: all 0.4s ease; }
    """,
    "shimmer": """
        @keyframes borderShimmer { 0% { border-color: rgba(99,102,241,0.3); } 50% { border-color: rgba(236,72,153,0.7); } 100% { border-color: rgba(99,102,241,0.3); } }
        .studio-card, .art-frame { animation: borderShimmer 4s infinite; }
    """
}

def sanitize_custom_html(raw_html: str) -> str:
    """Strips dangerous JS execution vectors while leaving HTML structure, GIFs, and inline styles intact."""
    if not raw_html:
        return ""
    cleaned = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', raw_html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'<\s*(iframe|object|embed|meta|link|base)[^>]*>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+on[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(href|src)\s*=\s*["\']\s*javascript:[^"\']*["\']', '', cleaned, flags=re.IGNORECASE)
    return cleaned

def sanitize_custom_css(raw_css: str) -> str:
    """Prevents CSS-based script/expression escapes while allowing unrestricted @keyframes and styling."""
    if not raw_css:
        return ""
    cleaned = re.sub(r'<\s*/?\s*style[^>]*>', '', raw_css, flags=re.IGNORECASE)
    cleaned = re.sub(r'expression\s*\(', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'javascript\s*:', '', cleaned, flags=re.IGNORECASE)
    return cleaned