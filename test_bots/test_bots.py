from __main__ import Adventurer
import math

class EagerThief(Adventurer):
    def get_action(self, state):
        move_cost = 10 + int(math.ceil(state.carry_weight / 5))
        if state.stamina // move_cost <= state.room + 1:
            return 'previous'
        if state.treasures and state.carry_weight + state.treasures[0].weight < 50:
            return 'take', 0, state.treasures[0].weight + self.random.randrange(len(state.players) * 2 + 1)
        else:
            return 'next'

class EmoKid(Adventurer):
    def get_action(self, state):
        return 'drop', 0

class Chad(Adventurer):
    def get_action(self, state):
        return 'next'

class Coward(Adventurer):
    def get_action(self, state):
        return 'previous'

class GreedyBastard(Adventurer):
    def get_action(self, state):
        if state.treasures:
            return 'take', 0, state.treasures[0].weight + 5
        else:
            return 'next'
class MischievousKid(Adventurer):
    def get_action(self, state):
        return ['take', '5', '1']

for i in range(6):
    name = f"EagerClone{i}"
    globals()[name] = type(name, (EagerThief,), {})
