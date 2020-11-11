import json
import os
import sys

from pprint import pformat

import anvil
from jinja2 import Environment, PackageLoader, select_autoescape

__version__ = '201109.1'


item_data = {}

assets_path = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.realpath(__file__))), 'assets')
with open(os.path.join(assets_path, 'items.json')) as f:
    item_data = {x['text_type']: x for x in json.load(f)}


def img_fname(item_name):
    if item_name in item_data:
        return "{type}-{meta}.png".format(**item_data[item_name])


def eprint(s):
    print(s, file=sys.stderr)


eprint('atrafadata v.{}'.format(__version__))


def coord_to_chunk(x, z):
    return x >> 4, z >> 4


def chunk_to_region(x, z):
    return x >> 5, z >> 5


def coord_to_region(x, z):
    return chunk_to_region(*coord_to_chunk(x, z))


def lp(d):
    return d.value.split(':')[1]


def chuck_map(startx, endx, startz, endz):
    rd = dict()
    xd = endx - startx
    zd = endz - startz

    xr = range(xd + 1)
    if not xr:
        xr = [0]

    zr = range(zd + 1)
    if not zr:
        zr = [0]
    for rx in xr:
        for rz in zr:
            x = startx + rx
            z = startz + rz

            c = coord_to_chunk(x, z)
            r = chunk_to_region(*c)
            if r not in rd:
                rd[r] = dict()
            if c not in rd[r]:
                rd[r][c] = list()
            rd[r][c].append((x, z))

    return rd


def dict_range(start, end):
    sx, sz = start
    ex, ez = end
    if sx > ex:
        sx, ex = ex, sx
    if sz > ez:
        sz, ez = ez, sz
    xd = ex - sx
    zd = ez - sz

    xr = range(xd + 1)
    if not xr:
        xr = [0]

    zr = range(zd + 1)
    if not zr:
        zr = [0]
    for x in xr:
        for z in zr:
            yield sx + x, sz + z


def region_fn(start, end):
    for d in dict_range(start, end):
        yield "r.{0}.{1}.mca".format(*d)


def export(server_path, test=False):
    startx = 225
    endx = 310
    startz = -60
    endz = 0

    data_path = os.path.join(server_path, 'world', 'region')

    jenv = Environment(
        loader=PackageLoader('atrafadata'),
        autoescape=select_autoescape(['html']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    cm = chuck_map(startx, endx, startz, endz)
    #eprint(pformat(cm))

    data = dict(
        buy=dict(),
        sell=dict(),
        villagers=list()
    )

    def list_add(list_name, item_name, offer):
        if item_name not in data[list_name]:
            if test and len(data[list_name].keys()) == 3:
                return
            data[list_name][item_name] = list()
        elif test and len(data[list_name][item_name]) == 3:
            return
        data[list_name][item_name].append(offer)

    def to_dict(offer_item):
        name = lp(offer_item['id'])
        return dict(
            name=name.capitalize(),
            count=offer_item['Count'].value,
            img=img_fname(name)
        )

    for rk, rv in cm.items():
        fp = "r.{0}.{1}.mca".format(*rk)
        region_path = os.path.join(data_path, fp)
        if os.path.exists(region_path):
            eprint("Parsing {}".format(region_path))
            r = anvil.Region.from_file(region_path)
            for ck, cv in rv.items():
                c = r.chunk_data(*ck)
                entities = c['Level']['Entities']
                if entities:
                    for e in entities:
                        if e['id'].value == 'minecraft:villager':
                            v = dict(
                                profession=lp(e['VillagerData']['profession']).capitalize(),
                                level=e['VillagerData']['level'].value,
                                xp=e['Xp'].value,
                                pos=[round(x.value) for x in e['Pos']]
                            )
                            v['offers'] = list()
                            for o in e['Offers']['Recipes']:
                                od = {
                                    'buy': to_dict(o['buy']),
                                    'buyB': dict(),
                                    'sell': to_dict(o['sell']),
                                    'villager': v
                                }
                                # Check buyB
                                if o['buyB']['id'].value != 'minecraft:air':
                                    od['buyB'] = to_dict(o['buyB'])

                                list_add('buy', od['buy']['name'], od)
                                if od['buyB']:
                                    list_add('buy', od['buyB']['name'], od)
                                list_add('sell', od['sell']['name'], od)
                                v['offers'].append(od)
                                #print("  {} {} -> {} {}".format(o['buy']['Count'], lp(o['buy']['id']).capitalize(), o['sell']['Count'], lp(o['sell']['id']).capitalize()))
                            data['villagers'].append(v)
    eprint(pformat(data))
    t = jenv.get_template('index.html')
    return t.render(data=data)