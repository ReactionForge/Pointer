"""Three coherent cursor families; legacy geometry remains in its original renderers."""
import math
from PIL import ImageDraw
from .roles import Canvas, rounded_contour, rotate, INK, OUTLINE

STYLES = ('quill', 'facet', 'outline', 'lance', 'droplet', 'rectilinear')
RECOMMENDED_STYLES = ('sequoia', 'quill', 'facet', 'lance', 'droplet', 'rectilinear')
PROFILES = {'quill': (1.8, .8, 2.0), 'facet': (2.4, .18, 2.8), 'outline': (1.8, .7, 1.8),
            'lance': (1.6, .12, 1.6), 'droplet': (2.0, 2.2, 2.5), 'rectilinear': (2.2, .02, 3.2)}
ARROWS = {
    'quill': [(3, 3), (4, 26), (9, 20), (14, 29), (17, 27), (12, 18), (21, 18)],
    'facet': [(3, 3), (27, 11), (20, 16), (16, 26), (12, 27), (9, 18)],
    'outline': [(3, 3), (25, 12), (18, 16), (12, 27), (9, 24)],
    'lance': [(3, 3), (28, 14), (17, 18), (12, 29)],
    'droplet': [(3, 3), (23, 12), (27, 17), (28, 21), (26, 25), (22, 28), (17, 28), (12, 25)],
    'rectilinear': [(3, 3), (3, 29), (11, 21), (25, 21)],
}


class FamilyCanvas(Canvas):
    def __init__(self, size, style):
        super().__init__(size)
        self.style = style
        self.width, self.trim, self.weight = PROFILES[style]

    def shape(self, points, solid=False):
        points = self.points(rounded_contour(points, self.trim))
        closed = points + [points[0]]
        if self.style == 'outline' and not solid:
            self.painter.line(closed, fill=OUTLINE, width=round(4.2 * self.factor), joint='curve')
            self.painter.line(closed, fill=INK, width=round(1.8 * self.factor), joint='curve')
        else:
            self.painter.polygon(points, fill=INK)
            self.painter.line(closed, fill=OUTLINE, width=round(self.width * self.factor), joint='curve')

    def line(self, points, weight=None):
        weight = weight or self.weight
        self.stroke(points, weight + 2.2, OUTLINE, caps=self.style not in ('facet', 'rectilinear'))
        self.stroke(points, weight, INK, caps=self.style not in ('facet', 'rectilinear'))

    def ring(self, center, radius, frame=0, gap=0, weight=None):
        weight = weight or self.weight
        directions = [(math.cos(math.radians(frame * 15 + angle)),
                       math.sin(math.radians(frame * 15 + angle))) for angle in range(361 - gap)]
        for width, color in ((weight + 2.2, OUTLINE), (weight, INK)):
            points = [((center[0] + distance * x) * self.factor,
                       (center[1] + distance * y) * self.factor)
                      for distance, vectors in ((radius + width / 2, directions),
                                                (radius - width / 2, reversed(directions)))
                      for x, y in vectors]
            self.painter.polygon(points, fill=color)
            if gap and self.style not in ('facet', 'rectilinear'):
                r = width * self.factor / 2
                for x, y in (directions[0], directions[-1]):
                    cx, cy = (center[0] + radius*x)*self.factor, (center[1] + radius*y)*self.factor
                    self.painter.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color)

    def arrow(self):
        self.shape(ARROWS[self.style])
        if self.style == 'outline':
            self.shape([(3, 3), (10, 6), (6, 12)], solid=True)


def render_family(size, role, style, frame=0):
    c = FamilyCanvas(size, style)
    if role in ('arrow', 'help', 'working'):
        c.arrow()
        if role == 'help':
            c.ellipse((18, 18, 30, 30), width=1.6)
            c.stroke([(21, 22), (22, 21), (25, 21), (26, 23), (24, 25)], 1.4, OUTLINE)
            c.ellipse((23.4, 26.5, 24.7, 27.8), fill=OUTLINE, outline=OUTLINE, width=0)
        elif role == 'working':
            c.ring((25, 24), 4.5, frame, gap=90, weight=1.2)
    elif role == 'busy':
        c.ring((16, 16), 10, frame, gap=90)
    elif role == 'hand':
        shoulder = {'quill': 11, 'lance': 9, 'droplet': 14, 'rectilinear': 12}.get(style, 13)
        c.shape([(12, 19), (12, 3), (16, 3), (16, shoulder), (20, shoulder),
                 (20, shoulder+2), (24, shoulder+2), (24, shoulder+4), (28, shoulder+4),
                 (28, 23), (24, 29), (15, 29), (7, 20), (7, 16), (10, 16)])
        if style == 'outline':
            if size < 32:
                # At 24 px the outlined tip becomes an isolated dot. Join its
                # solid center to the shoulder without thickening the family.
                c.stroke([(14, 3), (14, shoulder), (18, shoulder)], 2.8, INK)
            else:
                c.shape([(12, 3), (16, 3), (16, 9), (12, 9)], solid=True)
        for x, y in ((16, shoulder), (20, shoulder+2), (24, shoulder+4)):
            c.stroke([(x, y), (x, 20)], 1.15, OUTLINE)
    elif role == 'ibeam':
        span = {'quill': 5, 'lance': 4, 'droplet': 6, 'rectilinear': 8}.get(style, 7)
        c.line([(16, 4), (16, 28)])
        c.line([(16-span, 4), (16+span, 4)])
        c.line([(16-span, 28), (16+span, 28)])
    elif role in ('ns', 'ew', 'nwse', 'nesw'):
        stem = {'quill': 1.8, 'lance': 1.2, 'droplet': 3.1, 'rectilinear': 2.2}.get(style, 2.7)
        points = [(3, 16), (9, 10), (9, 16-stem), (23, 16-stem), (23, 10),
                  (29, 16), (23, 22), (23, 16+stem), (9, 16+stem), (9, 22)]
        angle = {'ew': 0, 'ns': 90, 'nwse': 45, 'nesw': -45}[role]
        if style == 'outline':
            c.line(rotate([(5, 16), (27, 16)], angle), weight=1.4)
            for head in ([(9, 10), (3, 16), (9, 22)], [(23, 10), (29, 16), (23, 22)]):
                c.line(rotate(head, angle), weight=1.4)
        else:
            c.shape(rotate(points, angle))
    elif role == 'move':
        points = [(16, 3), (10, 9), (14, 9), (14, 14), (9, 14), (9, 10),
                 (3, 16), (9, 22), (9, 18), (14, 18), (14, 23), (10, 23),
                 (16, 29), (22, 23), (18, 23), (18, 18), (23, 18), (23, 22),
                 (29, 16), (23, 10), (23, 14), (18, 14), (18, 9), (22, 9)]
        if style == 'outline':
            c.line([(16, 5), (16, 27)], weight=1.4)
            c.line([(5, 16), (27, 16)], weight=1.4)
            for angle in (0, 90, 180, 270):
                head = [(12, 8), (16, 3), (20, 8)] if size < 32 else [(10, 9), (16, 3), (22, 9)]
                c.line(rotate(head, angle), weight=1.8 if size < 32 else 1.4)
        else:
            c.shape(points)
    elif role == 'crosshair':
        c.line([(16, 4), (16, 28)])
        c.line([(4, 16), (28, 16)])
    elif role == 'no':
        c.ring((16, 16), 11)
        c.line([(8.5, 23.5), (23.5, 8.5)])
    elif role == 'pen':
        if style == 'outline' and size < 32:
            c.shape([(4, 28), (7, 21), (23, 5), (27, 9), (11, 25)], solid=True)
        else:
            c.shape([(4, 28), (6, 21), (23, 4), (27, 8), (10, 25)])
        c.stroke([(20, 7), (24, 11)], 1.3, OUTLINE)
    elif role == 'up':
        if style == 'outline':
            c.line([(16, 5), (16, 28)], weight=1.4)
            c.line([(7, 12), (16, 3), (25, 12)], weight=1.4)
        else:
            c.shape([(16, 3), (7, 12), (13, 12), (13, 28), (19, 28), (19, 12), (25, 12)])
    elif role in ('pin', 'person'):
        c.shape([(11, 11), (11, 27), (16, 23), (20, 23)])
        if role == 'pin':
            c.shape([(22, 3), (28, 3), (30, 8), (25, 15), (20, 8)])
            c.ellipse((23, 5, 27, 9), fill=OUTLINE, outline=OUTLINE, width=0)
        else:
            c.ellipse((22, 2, 28, 8), width=c.width)
            c.shape([(20, 16), (20, 12), (23, 10), (27, 10), (30, 12), (30, 16)])
    else:
        raise ValueError(role)
    return c.finish()
