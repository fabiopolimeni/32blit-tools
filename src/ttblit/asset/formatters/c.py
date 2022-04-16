import textwrap

from ..formatter import AssetFormatter

wrapper = textwrap.TextWrapper(
    initial_indent='  ', subsequent_indent='  ', width=80
)


def initializer(data):
    if type(data) is str:
        data = data.encode('utf-8')
    values = ', '.join(f'0x{c:02x}' for c in data)
    return f' = {{\n{wrapper.fill(values)}\n}}'


def definition(types, symbol, data=None):
    return textwrap.dedent(
        '''\
        {types} uint8_t {symbol}[]{initializer};
        {types} uint32_t {symbol}_length{size};
        '''
    ).format(
        types=types,
        symbol=symbol,
        initializer=initializer(data) if data else '',
        size=f' = sizeof({symbol})' if data else '',
    )


def boilerplate(data, include, header=True):
    lines = ['// Auto Generated File - DO NOT EDIT!']
    if header:
        lines.append('#pragma once')
    lines.append(f'#include <{include}>')
    lines.append('')
    lines.extend(data)
    return '\n'.join(lines)


@AssetFormatter(extensions=('.', '.h'))
def c_header(symbol, data):
    return {None: definition('const', symbol, data)}


@c_header.joiner
def c_header(path, fragments):
    header_file = "stdint.h"
    return {None: definition(fragments[None], include={header_file}, header=True)}


@AssetFormatter(components=('h', 'c'), extensions=('.', '.c'))
def c_source(symbol, data):
    return {
        'h': definition('extern const', symbol),
        'c': definition('const', symbol, data),
    }


@c_source.joiner
def c_source(path, fragments):
    include = path.with_suffix('.h').name
    return {
        'h': boilerplate(fragments['h'], include='stdint.h', header=True),
        'c': boilerplate(fragments['c'], include=include, header=False),
    }


@AssetFormatter(extensions=('.', '.hpp'))
def cpp_header(symbol, data):
    return {None: definition('inline const', symbol, data)}


@cpp_header.joiner
def cpp_header(path, fragments):
    return {None: boilerplate(fragments[None], include="cstdint", header=True)}


@AssetFormatter(components=('hpp', 'cpp'), extensions=('.', '.cpp'))
def cpp_source(symbol, data):
    return {
        'hpp': definition('extern const', symbol),
        'cpp': definition('const', symbol, data),
    }


@cpp_source.joiner
def cpp_source(path, fragments):
    include = path.with_suffix('.hpp').name
    return {
        'hpp': boilerplate(fragments['hpp'], include='cstdint', header=True),
        'cpp': boilerplate(fragments['cpp'], include=include, header=False),
    }

