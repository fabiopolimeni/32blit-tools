import argparse
import logging
import pathlib
from pickletools import uint8
import re
import struct

from PIL import Image


class Colour():
    def __init__(self, colour):
        if type(colour) is Colour:
            self.r, self.g, self.b = colour
        elif len(colour) == 6:
            self.r, self.g, self.b = tuple(bytes.fromhex(colour))
        elif ',' in colour:
            self.r, self.g, self.b = [int(c, 10) for c in colour.split(',')]

    def __getitem__(self, index):
        return [self.r, self.g, self.b][index]

    def __repr__(self):
        return f'Colour{self.r, self.g, self.b}'


class Palette():
    def __init__(self, palette_file=None):
        self.transparent = None
        self.entries = []

        if isinstance(palette_file, Palette):
            self.transparent = palette_file.transparent
            self.entries = palette_file.entries
            return

        if palette_file is not None:
            palette_file = pathlib.Path(palette_file)
            palette_type = palette_file.suffix[1:]

            palette_loader = f'load_{palette_type}'

            fn = getattr(self, palette_loader, None)
            if fn is None:
                self.load_image(palette_file)
            else:
                fn(palette_file, open(palette_file, 'rb').read())

            self.extract_palette()

    def extract_palette(self):
        self.entries = []
        for y in range(self.height):
            for x in range(self.width):
                self.entries.append(self.image.getpixel((x, y)))

    def set_transparent_colour(self, r, g, b):
        if (r, g, b, 0xff) in self.entries:
            self.transparent = self.entries.index((r, g, b, 0xff))
            self.entries[self.transparent] = (r, g, b, 0x00)
            return self.transparent
        return None

    def load_act(self, palette_file, data):
        # Adobe Colour Table .act
        palette = data
        if len(palette) < 772:
            raise ValueError(f'palette {palette_file} is not a valid Adobe .act (length {len(palette)} != 772')

        size, _ = struct.unpack('>HH', palette[-4:])
        self.width = 1
        self.height = size
        self.image = Image.frombytes('RGB', (self.width, self.height), palette).convert('RGBA')

    def load_pal(self, palette_file, data):
        # Pro Motion NG .pal - MS Palette files and raw palette files share .pal suffix
        # Raw files are just 768 bytes
        palette = data
        if len(palette) < 768:
            raise ValueError(f'palette {palette_file} is not a valid Pro Motion NG .pal')
        # There's no length in .pal files, so we just create a 16x16 256 colour palette
        self.width = 16
        self.height = 16
        self.image = Image.frombytes('RGB', (self.width, self.height), palette).convert('RGBA')

    def load_gpl(self, palette_file, data):
        palette = data
        palette = palette.decode('utf-8').strip().replace('\r\n', '\n')
        if not palette.startswith('GIMP Palette'):
            raise ValueError(f'palette {palette_file} is not a valid GIMP .gpl')
        # Split the whole file into palette entries
        palette = palette.split('\n')
        # drop 'GIMP Palette' from the first entry
        palette.pop(0)

        # drop metadata/comments
        while palette[0].startswith(('Name:', 'Columns:', '#')):
            palette.pop(0)

        # calculate our image width/height here because len(palette)
        # equals the number of palette entries
        self.width = 1
        self.height = len(palette)

        # Split out the palette entries into R, G, B and drop the hex colour
        # This convoluted list comprehension does this while also flatenning to a 1d array
        palette = [int(c) for entry in palette for c in re.split(r'\s+', entry.strip())[0:3]]
        self.image = Image.frombytes('RGB', (self.width, self.height), bytes(palette)).convert('RGBA')

    def load_image(self, palette_file):
        palette = Image.open(palette_file)
        self.width, self.height = palette.size
        if self.width * self.height > 256:
            raise argparse.ArgumentError(None, f'palette {palette_file} has too many pixels {self.width}x{self.height}={self.width*self.height} (max 256)')
        logging.info(f'Using palette {palette_file} {self.width}x{self.height}')

        self.image = palette.convert('RGBA')

    def quantize_image(self, image, transparent=None, strict=False):
        if strict and len(self) == 0:
            raise TypeError("Attempting to enforce strict colours with an empty palette, did you really want to do this?")
        w, h = image.size
        output_image = Image.new('P', (w, h))
        for y in range(h):
            for x in range(w):
                r, g, b, a = image.getpixel((x, y))
                if transparent is not None and (r, g, b) == tuple(transparent):
                    a = 0x00
                index = self.get_entry(r, g, b, a, strict=strict)
                output_image.putpixel((x, y), index)

        return output_image

    def make_spritesheet(self, image:Image, columns:uint8, rows:uint8):
        # image width and height
        iw, ih = image.size

        # sprite width and height
        sw = iw / columns
        sh = ih / rows

        # sprite size
        ss = sw * sh

        image_bytes = bytearray()

        for r in range(rows):
            for c in range(columns):
                x = c * sw
                y = r * sh
                w = x + sw
                h = y + sh
                cropped_image = image.crop((x, y, w, h))
                image_bytes.extend(cropped_image.tobytes())

        return image_bytes

    def get_entry(self, r, g, b, a, remap_transparent=True, strict=False):
        if (r, g, b, a) in self.entries:
            index = self.entries.index((r, g, b, a))
            return index
            # Noisy print
            # logging.info(f'Re-mapping ({r}, {g}, {b}, {a}) at ({x}x{y}) to ({index})')
        # Anything with 0 alpha that's not in the palette might as well be the transparent colour
        elif a == 0 and self.transparent is not None:
            return self.transparent
        elif not strict:
            if len(self.entries) < 256:
                self.entries.append((r, g, b, a))
                if a == 0:
                    # Set this as the transparent colour - if we had one we'd have returned it already.
                    self.transparent = len(self.entries) - 1
                return len(self.entries) - 1
            else:
                raise TypeError('Out of palette entries')
        else:
            raise TypeError(f'Colour {r}, {g}, {b}, {a} does not exist in palette!')

    def tostruct(self):
        return [dict(zip('rgba', c)) for c in self.entries]

    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, index):
        return self.entries[index]
