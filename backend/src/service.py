"""Deterministic data tools and evidence-only answer formatting."""
import math
import re
from satellite_geometry import parse_dataset_id, cell_index


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_query(body):
    if not isinstance(body, dict):
        raise ValueError('Expected a JSON object')
    if not number(body.get('lat'), -90, 90) or not number(body.get('lng'), -180, 180):
        raise ValueError('Valid latitude and longitude are required')
    if not number(body.get('heading'), 0, 360) or body['heading'] == 360:
        raise ValueError('Heading must be between 0 and 360, excluding 360')
    question = body.get('question')
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
        raise ValueError('Question must contain 1 to 1000 characters')
    query={key: body[key] for key in ('lat', 'lng', 'heading', 'question')}
    if 'datasetId' in body:
        parse_dataset_id(body['datasetId'])
        query['datasetId']=body['datasetId']
    return query


def distance(a, b):
    lat = math.radians((a['lat'] + b['lat']) / 2)
    return 6371000 * math.hypot(math.radians(a['lat']-b['lat']),
                              math.radians(a['lng']-b['lng'])*math.cos(lat))


class DataTools:
    def __init__(self, grid, metadata, lat, lng):
        self.grid, self.metadata = grid, metadata
        self.origin = {'lat': lat, 'lng': lng}
        self.results = {}

    def check(self, lat, lng):
        if not number(lat,-90,90) or not number(lng,-180,180):
            raise ValueError('Invalid tool coordinates')
        if abs(lat-self.origin['lat']) > 0.000001 or abs(lng-self.origin['lng']) > 0.000001:
            raise ValueError('Use the request coordinates; do not substitute a location')

    def covered(self):
        if 'epsg' in self.grid:
            return cell_index(self.grid,**self.origin) is not None
        west,south,east,north = self.grid['bbox']
        return west <= self.origin['lng'] <= east and south <= self.origin['lat'] <= north

    def nearest(self):
        if not self.covered() or not self.grid['cells']:
            return None
        if 'epsg' in self.grid:
            index=cell_index(self.grid,**self.origin)
            return self.grid['cells'][index] if index is not None else None
        return min(self.grid['cells'],key=lambda cell:distance(self.origin,cell))

    def get_layers(self, lat, lng):
        self.check(lat,lng)
        cell = self.nearest()
        result = {'status':'ok' if cell else 'no_data', 'cell':cell,
                  'provenance':self.metadata['provenance']}
        self.results['get_layers'] = result
        return result

    def compare_nearby(self, lat, lng):
        self.check(lat,lng)
        local = self.nearest()
        nearby = [c for c in self.grid['cells'] if local and distance(self.origin,c)<=500]
        temperatures = [c for c in nearby if c['tempC'] is not None]
        paired = [c for c in temperatures if c['ndvi'] is not None]
        # Candidate is the least vegetated of the warmer half of paired cells.
        warmer = sorted(paired,key=lambda c:c['tempC'],reverse=True)[:max(1,len(paired)//2)]
        result = {'status':'ok' if local else 'no_data', 'local':local,
                  'radiusM':500, 'sampleCount':len(nearby),
                  'coolest':min(temperatures,key=lambda c:c['tempC']) if temperatures else None,
                  'candidate':min(warmer,key=lambda c:c['ndvi']) if warmer else None,
                  'method':'Least NDVI among warmer half of cells within 500 m; field survey required.'}
        self.results['compare_nearby'] = result
        return result

    def simulate_planting(self, lat, lng, n_trees):
        self.check(lat,lng)
        if type(n_trees) is not int or not 1 <= n_trees <= 1000:
            raise ValueError('Tree count must be an integer from 1 to 1000')
        result = {'status':'unavailable', 'nTrees':n_trees, 'deltaTempC':None,
                  'reason':'No calibrated planting model yet; tree count alone cannot predict cooling.'}
        self.results['simulate_planting'] = result
        return result


def summarize_query(query, tools):
    """Route only the demo's fixed questions; no model or generated prose."""
    question=' '.join(query['question'].casefold().split())
    intents={
        'what is the temperature here?':'local',
        'what are the temperature and ndvi here?':'local',
        'why is this block hotter?':'compare',
        'how does this cell compare with nearby cells?':'compare',
        'where should we plant trees here?':'plant',
    }
    intent=intents.get(question,'unsupported')
    tree_count=re.fullmatch(r'what if we plant ([0-9]{1,4}) trees\?',question)
    if tree_count and 1 <= int(tree_count[1]) <= 1000:
        intent='simulate'
        tools.simulate_planting(query['lat'],query['lng'],int(tree_count[1]))
    elif intent=='local':
        tools.get_layers(query['lat'],query['lng'])
    elif intent in ('compare','plant'):
        tools.compare_nearby(query['lat'],query['lng'])
    return render_answer(intent,tools)


def render_answer(intent, tools):
    """Only server-owned sentences and measured values reach the user."""
    required = {'local':'get_layers', 'compare':'compare_nearby',
                'plant':'compare_nearby', 'simulate':'simulate_planting'}
    if intent == 'unsupported':
        return {'text':'Choose a supported data summary: local conditions, nearby comparison, or planting survey. Tree scenarios accept 1–1000 trees; cooling estimates are unavailable.',
                'mode':'data_summary', 'citations':[], 'toolsUsed':list(tools.results)}, None
    if intent not in required or required[intent] not in tools.results:
        raise ValueError('Summary is missing the required evidence')
    citations = []

    def describe(cell, tool_name, label):
        if cell is None:
            return f'{label}: no data.'
        parts=[]
        for field,unit in [('tempC','C'),('ndvi','index')]:
            value=cell[field]
            if value is None:
                parts.append(f'{field}: no data')
                continue
            source=next(p for p in tools.metadata['provenance'] if p['field']==field)
            citation={'id':f'S{len(citations)+1}', 'tool':tool_name, 'lat':cell['lat'],
                      'lng':cell['lng'], 'field':field, 'value':value, 'unit':unit,
                      'dataset':source['dataset'], 'sceneId':source['sceneId'],
                      'acquiredAt':source['acquiredAt']}
            citations.append(citation)
            display=f'{value:.1f} °C surface temperature' if field=='tempC' else f'NDVI {value:.2f}'
            parts.append(f'{display} on {source["acquiredAt"][:10]} [{citation["id"]}]')
        return f'{label} ({cell["lat"]:.5f}, {cell["lng"]:.5f}): '+ '; '.join(parts)+'.'

    scenario=None
    if intent=='simulate':
        scenario=tools.results['simulate_planting']
        text=f'For {scenario["nTrees"]} trees, a cooling estimate is unavailable. {scenario["reason"]}'
    elif intent=='local':
        text=describe(tools.results['get_layers']['cell'],'get_layers','Nearest grid cell')
    else:
        result=tools.results['compare_nearby']
        text=describe(result['local'],'compare_nearby','Nearest grid cell')
        if intent=='compare':
            text+=' '+describe(result['coolest'],'compare_nearby','Coolest measured cell within 500 m')
            if result['coolest'] is None:
                text+=' Temperature comparison is unavailable because no usable surface-temperature observations are available.'
            text+=' These observations do not establish why a block is hotter. Surface materials, shade and moisture may matter, but we have no measurements of those factors here.'
        else:
            text+=' '+describe(result['candidate'],'compare_nearby','Candidate area to survey')
            if result['candidate'] is None:
                text+=' There are not enough paired temperature and NDVI observations to identify a planting survey area.'
            else:
                text+=' Selection uses the lowest NDVI among the warmer half of cells within 500 m. Check land ownership, utilities, space and existing trees on site before planting.'
    text+=' Historical satellite snapshot; surface temperature is not air temperature, and NDVI is not tree-canopy percentage.'
    return {'text':text, 'mode':'data_summary', 'citations':citations, 'toolsUsed':list(tools.results)}, scenario
