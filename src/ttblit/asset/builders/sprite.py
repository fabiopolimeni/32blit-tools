import io
import logging
import pathlib

import click
from PIL import Image

from ...core.palette import Colour, Palette
from ...core.struct import struct_blit_spritesheet
from ..builder import AssetBuilder, AssetTool

sprite_typemap = {
    'image': {
        '.png': True,
        '.gif': True,
    }
}


@AssetBuilder(typemap=sprite_typemap)
def spritesheet(data, subtype, cols, rows, palette=None, transparent=None, strict=False, packed=True):
    if palette is None:
        palette = Palette()
    else:
        palette = Palette(palette)
    if transparent is not None:
        transparent = Colour(transparent)
        p = palette.set_transparent_colour(*transparent)
        if p is not None:
            logging.info(f'Found transparent {transparent} in palette')
        else:
            logging.warning(f'Could not find transparent {transparent} in palette')
    # Since we already have bytes, we need to pass PIL an io.BytesIO object
    image = Image.open(io.BytesIO(data)).convert('RGBA')
    image = palette.quantize_image(image, transparent=transparent, strict=strict)
    image = palette.make_spritesheet(image, columns=cols, rows=rows, count=count)
    return struct_blit_spritesheet.build({
        'type': 'SH',  # None means let the compressor decide
        'data': {
            'width': image.size[0],
            'height': image.size[1],
            'columns': cols,
            'rows': rows,
            'palette': palette.tostruct(),
            'sprites': image.tobytes(),
        },
    })


@AssetTool(spritesheet, 'Convert sprites for 32Blit')
@click.option('--columns', type=int, default=0, help='Number of sprites on the x axis')
@click.option('--rows', type=int, default=0, help='Number of sprites on hte y axis')
@click.option('--palette', type=pathlib.Path, help='Image or palette file of colours to use')
@click.option('--transparent', type=Colour, default=None, help='Transparent colour')
@click.option('--packed', type=click.Choice(['yes', 'no'], case_sensitive=False), default='yes', help='Pack into bits depending on palette colour count')
@click.option('--strict/--no-strict', default=False, help='Reject colours not in the palette')
def sprite_cli(input_file, input_type, packed, **kwargs):
    packed = (packed.lower() == 'yes')
    return spritesheet.from_file(input_file, input_type, packed=packed, **kwargs)
