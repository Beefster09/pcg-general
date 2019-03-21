import math
import itertools
import random
from collections import namedtuple

class Treasure(namedtuple('Treasure', ['name', 'value', 'weight'])):
    def __str__(self):
        return f"{self.name} (${self.value}, {self.weight}kg)"

class Ruins:
    def __init__(self, *adventurers, seed=None):
        self.random = random.Random(seed)
        self.adv_num = itertools.count(1)
        self.treasure_num = itertools.count(1)
        self.rooms = []
        self.adventurers = {
            name: adventurer(name)
            for name, adventurer in (
                (self.generate_name(), adventurer)
                for adventurer in adventurers
            )
        }

    def generate_name(self):
        return f"Adventurer #{next(self.adv_num)}"

    def ndr(self, n, r):
        return sum(self.random.randint(1, r) for _ in range(n))

    def generate_treasure(self, room):
        weight = max(1, self.ndr(2, 6) - 2)
        value = self.ndr(1, 10 * weight) + self.ndr(2, 5 * room + 10)
        if value > room * 6 + 10:
            value += self.random.randint(0, room * weight)
        return Treasure(f"Treasure #{next(self.treasure_num):03}", value, weight)

    def generate_room(self, room):
        n_treasures = self.random.randint(room // 3 + 3, room // 2 + 5)
        return [self.generate_treasure(room) for _ in range(n_treasures)]

    def turn(self):
        def get_action(adv):
            try:
                return self.adventurers[adv].get_action(self.snapshot(adv))
            except Exception:
                return None
        actions = {
            adv: get_action(adv)
            for adv in self.adventurers
        }
        # TODO: resolve stuff


r = Ruins()
for room in range(1, 21):
    print(f"Room #{room}", end='\n  ')
    print(*sorted(r.generate_room(room), key=lambda x: x.value), sep='\n  ')
    print()
