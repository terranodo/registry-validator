# Takes in a uuid from stdin and creates 3 files, uuid.bbox, uuid.yml and uuid.png
# and returns the same uuid and 3 binary values, valid_bbox, valid_config, valid_image.
import io
import os
import sys
import shutil
import requests
import yaml
import PIL.Image
from mapproxy.config.config import load_default_config, load_config
from mapproxy.config.loader import ProxyConfiguration
from mapproxy.wsgiapp import MapProxyApp

from six.moves.urllib_parse import unquote as url_unquote


REGISTRY_URL = 'http://hhypermap.wall.piensa.co/registry/hypermap/layer'
yml_folder = 'yml'
xml_folder = 'xml'
png_folder = 'png'


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)


def layer_metadata(uuid, registry_url, folder):
    if not os.path.isdir(folder):
        os.mkdir(folder)

    xml_file = os.path.join(folder, '%s.xml' % uuid)
    touch(xml_file)    

    return 1

MP_CONFIG_URL = 'http://hh.worldmap.harvard.edu/registry/hypermap/layer/%s/map/config'    


def layer_mapproxy(uuid, mapproxy_url, folder):
    if not os.path.isdir(folder):
        os.mkdir(folder)

    yml_file = os.path.join(folder, '%s.yml' % uuid)
    yml_url = MP_CONFIG_URL % uuid

    # If the file is already there, bypass the check.
    # future developers should make sure to write it at the end of this method.
    if os.path.exists(yml_file):
        return 0

    response = requests.get(yml_url)

    if response.status_code != 200:
        return 1

    # If this is a Django error page, then it is not a valid
    # yml file, that's for sure.
    if 'h1 { font-weight:normal; }' in response.content:
        return 1

    yaml_config = {}
    # Let's load it with the yml driver:
    try:
        yaml_conf = yaml.load(response.content)
    # Yes, exceptions should not be silent, but we are explicitly silencing them.
    # The 1 on the return file is enough for us to investigate via other means.
    except:
        raise


    # Copy this at the end of the method, if it is there it is because it is valid.
    with open(yml_file, 'wb') as out_file:
        out_file.write(response.content)

    # If it passed all the other checks, it can be a real one. Let's say it is.
    return 0


def layer_bbox(uuid, folder):
    yml_file = os.path.join(folder, '%s.yml' % uuid)
    with open(yml_file, 'rb') as f:
        yml_config = yaml.load(f)

        if not 'services' in yml_config:
            return 1
        service = yml_config['services']

        if not 'wms' in service:
            return 1

        wms = service['wms']

        if not 'bbox' in wms:
            return 1

        bbox_string = wms['bbox']
        
        coords = bbox_string.split(',')

        if len(coords) != 4:
            return 1

        bbox = [float(coord) for coord in coords]

        if bbox[0] < -180:
            return 1
        if bbox[1] < -90:
            return 1
        if bbox[2] > 180:
            return 1
        if bbox[3] > 90:
            return 1

        return 0


def environ_from_url(path):
    """From webob.request
    TOD: Add License.
    """
    scheme = 'http'
    netloc = 'localhost:80'
    if path and '?' in path:
        path_info, query_string = path.split('?', 1)
        path_info = url_unquote(path_info)
    else:
        path_info = url_unquote(path)
        query_string = ''
    env = {
        'REQUEST_METHOD': 'GET',
        'SCRIPT_NAME': '',
        'PATH_INFO': path_info or '',
        'QUERY_STRING': query_string,
        'SERVER_NAME': netloc.split(':')[0],
        'SERVER_PORT': netloc.split(':')[1],
        'HTTP_HOST': netloc,
        'SERVER_PROTOCOL': 'HTTP/1.0',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': scheme,
        'wsgi.input': io.BytesIO(),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }
    return env


def get_path_info_params(yaml_text):
    sources = yaml_text['sources']['default_source']
    bbox_req = '-180,-90,180,90'

    if 'services' in yaml_text:
        bbox_req = yaml_text['services']['wms']['bbox']

    if 'layers' in yaml_text:
        lay_name = yaml_text['layers'][0]['name']

    return bbox_req, lay_name


def create_mapproxy_image(yaml_file, img_file):

    with open(yaml_file, 'rb') as f:
        yaml_text = yaml.load(f)

    captured = []

    # Inline function that accesses captured. Do not refactor out of this function.
    def start_response(status, headers, exc_info=None):
        captured[:] = [status, headers, exc_info]
        return output.append


    output = []
    bbox_req, lay_name = get_path_info_params(yaml_text)
    
    path_info = ('/service?LAYERS={0}&FORMAT=image%2Fpng&SRS=EPSG%3A4326'
                 '&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&TRANSPARENT=TRUE&SERVICE=WMS&VERSION=1.1.1&'
                 'REQUEST=GetMap&STYLES=&BBOX={1}&WIDTH=200&HEIGHT=150').format(lay_name, bbox_req)

    conf_options = load_default_config()
    # Merge both
    load_config(conf_options, config_dict=yaml_text)
    conf = ProxyConfiguration(conf_options, seed=False, renderd=False)
    
    
    # Create a MapProxy App
    app = MapProxyApp(conf.configured_services(), conf.base_config)
    # Get a response from MapProxyAppy as if it was running standalone.
    environ = environ_from_url(path_info)
    app_iter = None

    try:
        app_iter = app(environ, start_response)
    except:
        return 1

    if app_iter is None:
        return 1

    try:
        with open(img_file, 'wb') as img:
            img.write(app_iter.next())
    except:
        return 1

    content = 'error'
    with open(img_file, 'rb') as img:
        content = img.read()

    if 'error' in content:
        os.remove(img_file)
        return 1

    return 0


def layer_image(uuid, mapproxy_conf, folder):
    if not os.path.isdir(folder):
        os.mkdir(folder)

    png_file = os.path.join(folder, '%s.png' % uuid)

    if os.path.exists(png_file):
        return 0
    
    return create_mapproxy_image(mapproxy_conf, png_file)

def check_image(uuid,folder):
    img=PIL.Image.open(os.path.join(folder, '%s.png' % uuid))
    hist=img.histogram()
    #if it is white
    if hist[0]==sum(hist):
        return 1
    #if it is black
    if hist[255]==sum(hist):
        return 1
    return 0

def check_layer(uuid, registry_url=REGISTRY_URL, yml_folder='yml', xml_folder='xml', png_folder='png'):

    valid_config = layer_mapproxy(uuid, registry_url, yml_folder)
    if valid_config == 1:
        valid_bbox = 1
    else:
        valid_bbox = layer_bbox(uuid, yml_folder)

    if valid_bbox == 1:
        valid_image = 1
    else:
        valid_image = layer_image(uuid, os.path.join(yml_folder, '%s.yml' % uuid), png_folder)

    if valid_image ==1:
        check_color = 1
    else:
        check_color = check_image(uuid,png_folder)


    return valid_bbox, valid_config, valid_image , check_color


if __name__ == "__main__":

    for line in sys.stdin:
        uuid = line.rstrip()

        valid_bbox, valid_config, valid_image, check_color = check_layer(uuid)

        output = '%s %s %s %s %s\n' % (uuid, valid_bbox, valid_config, valid_image, check_color)
        sys.stdout.write(output)
