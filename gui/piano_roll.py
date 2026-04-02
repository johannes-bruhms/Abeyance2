# gui/piano_roll.py
import tkinter as tk

class PianoRollCanvas(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg="#0a0a0a", highlightthickness=0, **kwargs)
        self.notes = {}
        
        # Draw some subtle keyboard guide lines
        self.bind("<Configure>", self._draw_grid)

    def _draw_grid(self, event=None):
        self.delete("grid_line")
        h = self.winfo_height()
        w = self.winfo_width()
        key_height = h / 88.0
        
        # Draw horizontal lines for octaves (every 12 keys)
        for i in range(0, 88, 12):
            y = h - (i * key_height)
            self.create_line(0, y, w, y, fill="#1f1f1f", tags="grid_line")

    def draw_note(self, note, velocity, is_ai=False):
        # Map MIDI 21-108 (Standard 88 keys) to dynamic Y axis
        h = self.winfo_height() if self.winfo_height() > 10 else 600
        w = self.winfo_width() if self.winfo_width() > 10 else 600
        
        key_height = h / 88.0
        # MIDI note 21 is A0 (bottom of the piano)
        y = h - ((note - 21) * key_height)
        
        x = w - 10 # Spawn right at the edge of the window
        
        color = "#00ffcc" if is_ai else "#ff3366"  # Cyan for AI, Neon Pink for Human
        # Make height scale slightly with velocity
        size = max(2, (velocity / 127.0) * (key_height * 2))
        
        rect = self.create_rectangle(x, y, x+15, y+size, fill=color, outline=color)
        self.notes[rect] = [x, y]

    def update_roll(self):
        to_delete = []
        for rect, coords in self.notes.items():
            self.move(rect, -4, 0) # Scroll left 4 pixels per frame
            coords[0] -= 4
            if coords[0] < -20: # Offscreen
                to_delete.append(rect)
                
        for rect in to_delete:
            self.delete(rect)
            del self.notes[rect]