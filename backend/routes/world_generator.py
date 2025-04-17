import random

def generate_world(seed=None):
    random.seed(seed)
    world = [[random.choice(['land', 'water']) for _ in range(10)] for _ in range(10)]
    return world