from datetime import datetime
import json
import os

import anvil

__version__ = '201124.2'


item_data = {}
entities_data = {}


_roman = {
    1: 'I',
    2: 'II',
    3: 'III',
    4: 'IV',
    5: 'V'
}

_title = {
    1: {'name': 'Novice', 'next_lvl': 10},
    2: {'name': 'Apprentice', 'next_lvl': 70},
    3: {'name': 'Journeyman', 'next_lvl': 150},
    4: {'name': 'Expert', 'next_lvl': 250},
    5: {'name': 'Master', 'next_lvl': 0},
}


def box(center_x, center_z, side):
    d = int(side/2)
    return center_x - d, center_x + d, center_z - d, center_z + d


def item_img_fname(item_name):
    if item_name in item_data:
        return "{type}-{meta}.png".format(**item_data[item_name])


def entity_img_fname(entity_name):
    if entity_name in entities_data:
        return "{type}.png".format(**item_data[entity_name])


print('atrafadata v.{}'.format(__version__))


def coord_to_chunk(x, z):
    return x >> 4, z >> 4


def chunk_to_region(x, z):
    return x >> 5, z >> 5


def coord_to_region(x, z):
    return chunk_to_region(*coord_to_chunk(x, z))


def lp(d):
    return d.split(':')[1]


def chunk_map(startx, endx, startz, endz):
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
    now = datetime.now()
    startx = 225
    endx = 310
    startz = -60
    endz = 0

    data_path = os.path.join(server_path, 'world', 'region')

    cm = chunk_map(startx, endx, startz, endz)
    #eprint(pformat(cm))

    data = dict(
        buy=list(),
        sell=list(),
        villagers=dict(),
    )

    def list_add(list_name, offer):
        if test and len(data[list_name]) == 5:
            return
        data[list_name].append(offer)

    def to_name(iid):
        return lp(iid).capitalize().replace('_', ' ')

    def to_dict(offer_item):
        raw_name = offer_item['id'].value
        name = to_name(raw_name)

        rd = dict(
            name=name.capitalize(),
            count=offer_item['Count'].value,
            img=lp(raw_name)+'.png'
        )

        if 'tag' in offer_item:
            if 'Enchantments' in offer_item['tag']:
                if offer_item['tag']['Enchantments']:
                    ea = list()
                    for e in offer_item['tag']['Enchantments']:
                        ea.append("{} {}".format(to_name(e['id'].value), _roman[e['lvl'].value]))

                    rd['enchantments'] = ea

        return rd

    profession_count = dict()

    for rk, rv in cm.items():
        fp = "r.{0}.{1}.mca".format(*rk)
        region_path = os.path.join(data_path, fp)
        if os.path.exists(region_path):
            print("Parsing {}".format(region_path))
            r = anvil.Region.from_file(region_path)
            for ck, cv in rv.items():
                c = r.chunk_data(*ck)
                entities = c['Level']['Entities']
                if entities:
                    for e in entities:
                        if e['id'].value == 'minecraft:villager':
                            v = dict(
                                profession=lp(e['VillagerData']['profession'].value).capitalize(),
                                level=e['VillagerData']['level'].value,
                                xp=e['Xp'].value,
                                pos=[round(x.value) for x in e['Pos']],
                                offers=list(),
                                title=_title[e['VillagerData']['level'].value]
                            )
                            p = v['profession']
                            if p not in profession_count:
                                profession_count[p] = 1
                            else:
                                profession_count[p] += 1
                            v['name'] = "{} {}".format(p, profession_count[p])
                            v['offers'] = list()
                            if 'Offers' in e:
                                for o in e['Offers']['Recipes']:
                                    od = {
                                        'buy': to_dict(o['buy']),
                                        'buyB': dict(),
                                        'sell': to_dict(o['sell']),
                                        'villager': v['name'],
                                        'usesLeft': o['maxUses'].value - o['uses'].value
                                    }
                                    # Check buyB
                                    if o['buyB']['id'].value != 'minecraft:air':
                                        od['buyB'] = to_dict(o['buyB'])

                                    if od['sell']['name'] == 'Emerald':
                                        list_add('sell', od)
                                    else:
                                        list_add('buy', od)
                                    v['offers'].append(od)
                                    #print("  {} {} -> {} {}".format(o['buy']['Count'], lp(o['buy']['id']).capitalize(), o['sell']['Count'], lp(o['sell']['id']).capitalize()))
                                v['offers'].sort(key=lambda x: x['buy']['name'])
                            if 'memories' in e['Brain']:
                                m = e['Brain']['memories']
                                if 'minecraft:job_site' in m:
                                    print(m['minecraft:job_site']['value'])
                            data['villagers'][v['name']] = v
    #eprint(pformat(data))
    data['timestamp'] = now.strftime('%Y-%m-%d %H.%M.%S')

    def sell_key(x):
        key = x['buy']['name']
        if x['buyB']:
            key += x['buyB']['name']
        return key

    data['sell'].sort(key=sell_key)
    data['buy'].sort(key=lambda x: x['sell']['name'])
    data['villager_keys'] = sorted(data['villagers'].keys())

    return json.dumps(data)

