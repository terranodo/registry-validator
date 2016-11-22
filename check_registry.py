# Takes in a uuid from stdin and creates 3 files, uuid.bbox, uuid.yml and uuid.png
# and returns the same uuid and 3 binary values, valid_bbox, valid_config, valid_image.

import sys

for line in sys.stdin:
    uuid = line.rstrip()

    valid_bbox = 0
    valid_config = 0
    valid_image = 0

    output = '%s %s %s %s\n' % (uuid, valid_bbox, valid_config, valid_image)
    sys.stdout.write(output)
