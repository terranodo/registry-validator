# registry-validator
Checks all layers in a spatial registry.

Usage:
    cat uuid.csv | parallel --pipe -L 1000 -j0 --progress python check_registry.py 
