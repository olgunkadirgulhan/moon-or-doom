"""Kadro (Bölüm 3). Renkler 0-1 RGB; ses kimlikleri config.yaml -> voices."""
from . import CONFIG

CAST = {
    'charlie': {
        'name': 'Chart Charlie', 'shirt': (0.20, 0.45, 0.85), 'skin': (0.96, 0.80, 0.66), 'scale': 1.0,
        'accent': (0.45, 0.72, 1.0),
        'bio': 'calm analyst in a blue shirt and glasses, holds a pointer stick, uses exact levels, dry humor.',
    },
    'moon_max': {
        'name': 'Moon Max', 'shirt': (0.18, 0.72, 0.36), 'skin': (0.86, 0.64, 0.48), 'scale': 0.96,
        'accent': (0.35, 0.95, 0.5),
        'bio': 'wildly optimistic young investor in a green hoodie with a rocket badge. Yells "to the moon!", '
               'hypes every green candle, gets crushed by reality.',
    },
    'bear_betty': {
        'name': 'Bear Betty', 'shirt': (0.82, 0.16, 0.18), 'skin': (0.98, 0.84, 0.72), 'scale': 0.97,
        'accent': (1.0, 0.4, 0.4),
        'bio': 'skeptic in a red jacket, thick eyebrows, arms always crossed. Dry, sarcastic, '
               'thinks everything is "going to zero".',
    },
}
for _k, _v in CONFIG['voices'].items():
    CAST[_k].update(_v)

EMOTIONS = ['neutral', 'happy', 'angry', 'shock', 'cry', 'nervous', 'sad', 'smug', 'confused', 'excited', 'suspicious']
# Bölüm 3 pozları -> rig pozları: pointing_chart=pointing, jumping=celebrate(+jump), shocked=standing+shock
POSES = ['standing', 'arms_crossed', 'hips', 'pointing', 'shrug', 'celebrate', 'facepalm', 'thinking', 'crying']
CHART_ACTIONS = ['none', 'show', 'draw_resistance', 'draw_support', 'highlight_scenario_up', 'highlight_scenario_down']
