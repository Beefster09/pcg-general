import math
import itertools
import random
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from typing import List

class Treasure(namedtuple('Treasure', ['name', 'value', 'weight'])):
    def __str__(self):
        return f"{self.name} (${self.value}, {self.weight}kg)"

RoomState = namedtuple('RoomState', ['room', 'treasures', 'players', 'inventory', 'stamina'])

Move = namedtuple('Move', ['direction'])
Take = namedtuple('Take', ['treasure', 'bid'])
Drop = namedtuple('Drop', ['treasure'])


class Adventurer:
    def __init__(self, name, random):
        self.name = name
        self.random = random
        self.enter_ruins()

    def get_action(self, room_state):
        raise NotImplementedError()

    def enter_ruins(self):
        raise NotImplementedError()


@dataclass
class Player:
    name: str
    bot: Adventurer
    room: int = 1
    stamina: int = 10_000
    treasures: List[Treasure] = field(default_factory=list)

    def get_action(self, state):
        if not self.alive:
            return None

        try:
            raw_action = self.bot.get_action(state)
        except Exception:
            return None

        try:
            if raw_action == 'next':
                return Move(1)
            elif raw_action == 'previous':
                return Move(-1)
            else:
                atype, *args = raw_action
                if atype == 'take':
                    return Take(self.room, *args)
                elif atype == 'drop':
                    return Drop(self.room, *args)
        except TypeError:
            pass
        return None

    @property
    def carry_weight(self):
        return sum(treasure.weight for treasure in self.treasures)

    @property
    def alive(self):
        return self.stamina > 0 or self.room == 0



class Ruins:
    def __init__(self, *adventurers, seed=None):
        self.random = random.Random(seed)
        self.adv_num = itertools.count(1)
        self.treasure_num = itertools.count(1)
        self.players = {
            name: Player(name, adventurer(name, self.new_seed()))
            for name, adventurer in (
                (self.generate_name(), adventurer)
                for adventurer in adventurers
            )
        }
        self.rooms = [self.generate_room(1)]

    def new_seed(self):
        rand = random.Random(self.random.getrandbits(1024))

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
        bids = defaultdict(list)
        drops = defaultdict(list)
        kill_later = []
        for player in self.players.values():
            if not player.alive:
                continue

            action = player.get_action(self.snapshot(player))

            if action is None:
                kill_later.append((player, "was crushed by a boulder"))
                continue

            elif isinstance(action, Move):
                cost = 10 + int(math.ceil(player.carry_weight / 5))
                if player.stamina >= cost:
                    player.room += action.direction
                    player.stamina -= cost
                    self.ensure_room(player.room)
                else:
                    kill_later.append((player, "died of exhaustion"))
                    continue

            elif isinstance(action, Take):
                treasure, bid = action
                try:
                    bid = int(bid)
                    min_bid = self.rooms[player.room][int(treasure)].weight
                except (IndexError, TypeError, ValueError):
                    kill_later.append((player, "fell into a pit of spikes"))
                    continue
                if 0 < bid <= player.stamina:
                    bids[player.room, treasure].append((player.name, bid))
                    player.stamina -= bid
                else:
                    kill_later.append(
                        (player, "tripped on a rock, landed on their knife, and died")
                    )

            elif isinstance(action, Drop):
                if player.stamina >= 1:
                    player.stamina -= 1
                    try:
                        dropped = player.treasures.pop(int(action.treasure))
                    except (IndexError, TypeError, ValueError):
                        kill_later.append(
                            (player, "was bitten by a venomous spider and died moments later")
                        )
                    else:
                        drops[player.room].append(dropped)
                else:
                    kill_later.append((player, "lost the will to live"))

        # TODO: bids

        for player, message in kill_later:
            self.kill(player, message)

        for room, items in drops.items():
            self.rooms[room] += items

    def kill(self, player, message):
        self.gamelog(player, message)
        player.stamina = 0
        self.rooms[player.room] += player.treasures
        player.treasures = []

    def ensure_room(self, room):
        while len(self.rooms) < room:
            self.rooms.append(self.generate_room(len(self.rooms) + 1))

    def snapshot(self, player):
        return RoomState(
            player.room,
            list(self.rooms[player.room]),
            [
                other.name
                for other in self.players.values()
                if other is not player and other.room == player.room
            ],
            list(player.treasures),
            player.stamina
        )


r = Ruins()
for room in range(1, 21):
    print(f"Room #{room}", end='\n  ')
    print(*sorted(r.generate_room(room), key=lambda x: x.value), sep='\n  ')
    print()
