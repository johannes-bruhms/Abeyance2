# gui/piano_roll.py
import tkinter as tk
from core.config import ELEMENTS, CONFIG

ELEMENT_COLORS = {
    'a': '#ff8800',  # orange     — Linear Velocity
    'b': '#0099ff',  # blue       — Vertical Density
    'c': '#ffee00',  # yellow     — Transposed Shapes
    'd': '#cc44ff',  # purple     — Oscillation
    'e': '#ff4488',  # hot pink   — Extreme Registers
}
PENDING_COLOR = '#ff6600'   # amber: inside the current analysis window
HUMAN_BASE    = '#ff3366'   # neon pink: human note, no detection
AI_COLOR      = '#00ffcc'   # cyan: AI-generated note

LABEL_FRAMES  = 50          # ~1500 ms overlay lifetime


class PianoRollCanvas(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg='#0a0a0a', highlightthickness=0, **kwargs)
        self.notes = {}               # note_id (int) → note_data dict
        self._next_note_id = 0
        self.active_human_notes = {}  # pitch → note_id
        self.active_ai_notes    = {}  # pitch → note_id
        self.labels = []
        self.frozen = False
        self.bind('<Configure>', self._on_resize)

    # ----------------------------------------------------------------- layout

    def _on_resize(self, event=None):
        self.delete('grid_line')
        self.delete('legend')
        h = self.winfo_height()
        w = self.winfo_width()
        key_height = h / 88.0
        for i in range(0, 88, 12):
            y = h - (i * key_height)
            self.create_line(0, y, w, y, fill='#1f1f1f', tags='grid_line')
        self.tag_lower('grid_line')
        self._draw_legend(w, h)

    def _draw_legend(self, w, h):
        items = list(ELEMENTS.items())
        x, y = 6, h - 18
        for el_id, name in items:
            color = ELEMENT_COLORS.get(el_id, HUMAN_BASE)
            self.create_rectangle(x, y, x + 10, y + 10,
                                  fill=color, outline=color, tags='legend')
            self.create_text(x + 13, y + 5, text=name, anchor='w',
                             font=('Consolas', 7), fill=color, tags='legend')
            x += 13 + len(name) * 5 + 6

    # ----------------------------------------------------------------- drawing

    def draw_note(self, note, velocity, is_ai=False, frame_id=None):
        if self.frozen:
            return
        h = self.winfo_height() if self.winfo_height() > 10 else 600
        w = self.winfo_width()  if self.winfo_width()  > 10 else 600

        key_height = h / 88.0
        y1 = h - ((note - 21 + 1) * key_height)
        y2 = y1 + key_height
        x1, x2 = w - 10, w - 5

        if is_ai:
            color = AI_COLOR
        elif frame_id is not None:
            color = PENDING_COLOR
        else:
            color = HUMAN_BASE

        if velocity < 64:
            color = _lerp_color(color, '#333333', 0.35)

        rect_id = self.create_rectangle(x1, y1, x2, y2, fill=color, outline='')

        note_id = self._next_note_id
        self._next_note_id += 1

        # rects: list of {'id', 'frac_start', 'frac_end'} — one per color band
        self.notes[note_id] = {
            'rects':     [{'id': rect_id, 'frac_start': 0.0, 'frac_end': 1.0}],
            'x1':        x1,
            'x2':        x2,
            'y1':        y1,
            'y2':        y2,
            'is_active': True,
            'is_ai':     is_ai,
            'frame_id':  frame_id,
        }

        if is_ai:
            if note in self.active_ai_notes:
                self._deactivate(self.active_ai_notes[note])
            self.active_ai_notes[note] = note_id
        else:
            if note in self.active_human_notes:
                self._deactivate(self.active_human_notes[note])
            self.active_human_notes[note] = note_id

    def release_note(self, note, is_ai=False):
        """Stop the right edge from tracking 'now' — the note is released."""
        registry = self.active_ai_notes if is_ai else self.active_human_notes
        note_id  = registry.pop(note, None)
        if note_id is not None:
            self._deactivate(note_id)

    def _deactivate(self, note_id):
        if note_id in self.notes:
            self.notes[note_id]['is_active'] = False

    # --------------------------------------------------------------- detection

    def resolve_frame(self, frame_id, active_elements):
        """
        Repaint all notes that belong to frame_id with confidence-proportional
        horizontal color bands — one band per detected element.
        """
        if not active_elements:
            for data in self.notes.values():
                if data.get('frame_id') == frame_id and not data['is_ai']:
                    self._apply_bands(data, [(HUMAN_BASE, 1.0)])
            return

        sorted_els = sorted(active_elements.items(), key=lambda x: x[1], reverse=True)
        total = sum(c for _, c in sorted_els)
        bands = [
            (ELEMENT_COLORS.get(el, HUMAN_BASE), conf / total)
            for el, conf in sorted_els
        ]

        for data in self.notes.values():
            if data.get('frame_id') == frame_id and not data['is_ai']:
                self._apply_bands(data, bands)

        self._show_label(sorted_els[0][0], active_elements)

    def _apply_bands(self, data, bands):
        """Replace all existing rects with N proportional horizontal color bands."""
        for r in data['rects']:
            self.delete(r['id'])

        y1, y2  = data['y1'], data['y2']
        x1, x2  = data['x1'], data['x2']
        height  = y2 - y1

        new_rects = []
        frac_cur  = 0.0
        for color, weight in bands:
            frac_end = frac_cur + weight
            ry1 = y1 + frac_cur * height
            ry2 = y1 + frac_end * height
            rect_id = self.create_rectangle(x1, ry1, x2, ry2, fill=color, outline='')
            new_rects.append({'id': rect_id, 'frac_start': frac_cur, 'frac_end': frac_end})
            frac_cur = frac_end

        data['rects'] = new_rects

    def _show_label(self, dominant_id, all_active):
        w = self.winfo_width() if self.winfo_width() > 10 else 600
        lines = []
        for el_id, conf in sorted(all_active.items(), key=lambda x: x[1], reverse=True):
            filled = int(conf * 8)
            bar = '[' + '#' * filled + '-' * (8 - filled) + ']'
            lines.append(f'{ELEMENTS[el_id]:<22} {bar} {conf:.0%}')
        el_color = ELEMENT_COLORS.get(dominant_id, '#ffffff')
        label_id = self.create_text(w - 12, 12, text='\n'.join(lines),
                                    anchor='ne', font=('Consolas', 9, 'bold'),
                                    fill=el_color)
        self.labels.append({'id': label_id, 'tick': 0,
                            'total': LABEL_FRAMES, 'color': el_color})

    # ----------------------------------------------------------------- animate

    def update_roll(self):
        if self.frozen:
            return

        w = self.winfo_width() if self.winfo_width() > 10 else 600
        to_delete = []

        scroll_px = CONFIG['roll_scroll_px']
        for note_id, data in self.notes.items():
            data['x1'] -= scroll_px

            if data['is_active']:
                data['x2'] = w - 5
            else:
                data['x2'] -= scroll_px
                if data['x2'] < -20:
                    to_delete.append(note_id)
                    continue

            y1, y2 = data['y1'], data['y2']
            height  = y2 - y1
            for r in data['rects']:
                ry1 = y1 + r['frac_start'] * height
                ry2 = y1 + r['frac_end']   * height
                self.coords(r['id'], data['x1'], ry1, data['x2'], ry2)

        for note_id in to_delete:
            for r in self.notes[note_id]['rects']:
                self.delete(r['id'])
            del self.notes[note_id]

        dead = []
        for ld in self.labels:
            ld['tick'] += 1
            t = ld['tick'] / ld['total']
            if t >= 1.0:
                self.delete(ld['id'])
                dead.append(ld)
            else:
                self.itemconfig(ld['id'], fill=_lerp_color(ld['color'], '#0a0a0a', t))
        for ld in dead:
            self.labels.remove(ld)


# ------------------------------------------------------------------ utilities

def _lerp_color(hex_a, hex_b, t):
    a = hex_a.lstrip('#')
    b = hex_b.lstrip('#')
    r1, g1, b1 = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
    r2, g2, b2 = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    r  = int(r1 + (r2 - r1) * t)
    g  = int(g1 + (g2 - g1) * t)
    b_ = int(b1 + (b2 - b1) * t)
    return f'#{r:02x}{g:02x}{b_:02x}'
