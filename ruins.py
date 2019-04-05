#!/usr/bin/env python3.7

import math
import itertools
import random
import sys
import traceback
import time
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from typing import List

# Logging constants
if sys.stdin.isatty():
    MSG_COLORS = defaultdict(
        lambda: '\x1b[37m', # default value
        major='\x1b[94m',
        minor='\x1b[93m',
        good='\x1b[92m',
        bad='\x1b[91m',
        warning='\x1b[33m',
        error='\x1b[31m',
        info='\x1b[37m',
        debug='\x1b[90m',
    )
    CLEAR_COLOR = '\x1b[0m'
else:
    MSG_COLORS = defaultdict(str)
    CLEAR_COLOR = ''
LOG_END = CLEAR_COLOR + '\n'

class Treasure(namedtuple('Treasure', ['name', 'value', 'weight'])):
    def __str__(self):
        return f"{self.name} (${self.value}, {self.weight}kg)"

class RoomState(
    namedtuple(
        'RoomState',
        ['room', 'treasures', 'players', 'inventory', 'stamina']
    )
):
    def __str__(self):
        builder = [
            f"Room #{self.room}",
            "  Treasures:"
        ]
        builder.extend(
            f"    {treasure}"
            for treasure in self.treasures
        )
        builder.append("  Other Players:")
        builder.extend(
            f"    {player}"
            for player in self.players
        )
        builder.append("  Your Inventory:")
        builder.extend(
            f"    {treasure}"
            for treasure in self.inventory
        )
        builder.append(f"  Stamina: {self.stamina}")
        return '\n'.join(builder)

    @property
    def carry_weight(self):
        return sum(treasure.weight for treasure in self.inventory)

    @property
    def total_value(self):
        return sum(treasure.value for treasure in self.inventory)


Move = namedtuple('Move', ['direction'])
Take = namedtuple('Take', ['treasure', 'bid'])
Drop = namedtuple('Drop', ['treasure'])


class Adventurer:
    def __init__(self, name, random):
        self.name = name
        self.random = random
        self.enter_ruins()

    def get_action(self, state):
        raise NotImplementedError()

    def enter_ruins(self):
        pass


class Drunkard(Adventurer):
    def get_action(self, state):
        move_cost = 10 + int(math.ceil(state.carry_weight / 5))
        if state.stamina // move_cost <= state.room + 1:
            return 'previous'
        options = ['next']
        if state.room > 1:
            options.append('previous')
        if state.treasures:
            options += ['take'] * 5

        action = self.random.choice(options)
        if action == 'take':
            which = self.random.randrange(len(state.treasures))
            treasure = state.treasures[which]
            if treasure.weight + state.carry_weight > 50:  # it doesn't fit
                return 'drop', self.random.randrange(len(state.inventory))
            else:
                return 'take', which, treasure.weight + (self.random.randrange(5) if state.players else 0)
        else:
            return action

@dataclass
class Player:
    name: str
    bot: Adventurer
    room: int = 1
    stamina: int = 1000
    treasures: List[Treasure] = field(default_factory=list)

    def get_action(self, state):
        if not self.active:
            return None

        try:
            raw_action = self.bot.get_action(state)
        except Exception as e:
            print(f"{MSG_COLORS['error']}Exception from {self}: {str(e)}")
            traceback.print_exc()
            return None

        try:
            if raw_action == 'next':
                return Move(1)
            elif raw_action == 'previous':
                return Move(-1)
            else:
                atype, *args = raw_action
                if atype == 'take':
                    return Take(*args)
                elif atype == 'drop':
                    return Drop(*args)
        except TypeError:
            print(f"{MSG_COLORS['error']}Invalid action from {self}: {raw_action}")
            traceback.print_exc()
            pass
        return None

    @property
    def carry_weight(self):
        return sum(treasure.weight for treasure in self.treasures)

    @property
    def total_value(self):
        return sum(treasure.value for treasure in self.treasures)

    @property
    def active(self):
        return self.stamina > 0 and self.room > 0

    @property
    def alive(self):
        return self.stamina > 0 or self.room == 0

    def __str__(self):
        return f"{self.name} ({type(self.bot).__name__})"



class Ruins:
    def __init__(self, *adventurers, seed=None):
        assert adventurers
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
        self.turn_number = 0

    def new_seed(self):
        return random.Random(self.random.getrandbits(1024))

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
        self.turn_number += 1
        self.gamelog("Turn", self.turn_number, "begins!", type='major')
        bids = defaultdict(list)
        drops = defaultdict(list)
        kill_later = []
        actions = [ # Actions must resolve simultaneously
            (player, player.get_action(self.snapshot(player)))
            for player in self.players.values()
            if player.active
        ]
        for player, action in actions:
            self.gamelog(player, action, type='debug')
            if action is None:
                kill_later.append((player, "was crushed by a boulder"))
                continue

            elif isinstance(action, Move):
                cost = 10 + int(math.ceil(player.carry_weight / 5))
                if player.stamina >= cost:
                    player.room += action.direction
                    player.stamina -= cost
                    self.ensure_room(player.room)
                    if player.room > 0:
                        if player.stamina == 0:
                            kill_later.append((
                                player,
                                f"collapsed in the doorway to room #{player.room}"
                                " and died of exhaustion"
                            ))
                        else:
                            self.gamelog(player, f"moved into room #{player.room}")
                    else:
                        self.gamelog(
                            player,
                            f"""exited the ruins with {
                                player.stamina
                            } stamina and {
                                len(player.treasures)
                            } treasures, totaling ${
                                player.total_value
                            } in value.""",
                            type='minor'
                        )
                else:
                    kill_later.append((player, "died of exhaustion"))
                    continue

            elif isinstance(action, Take):
                treasure, bid = action
                try:
                    bid = int(bid)
                    min_bid = self.rooms[player.room - 1][int(treasure)].weight
                except (IndexError, TypeError, ValueError):
                    kill_later.append((player, "fell into a pit of spikes"))
                    continue
                if min_bid <= bid <= player.stamina:
                    bids[player.room, treasure].append((bid, player.name))
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
                        self.gamelog(
                            player,
                            f"Dropped a treasure into room #{player.room}:",
                            dropped
                        )
                else:
                    kill_later.append((player, "lost the will to live"))

        for (room, index), bidlist in bids.items():
            treasure = self.rooms[room - 1][index]
            if len(bidlist) == 1:  # No competition over treasure
                _, player = bidlist[0]
                self.players[player].treasures.append(treasure)
                self.rooms[room - 1][index] = None
                self.gamelog(self.players[player], "took", treasure)
            elif len(bidlist) > 1:  # Multiple players going for same treasure
                bidlist.sort(reverse=True)
                if bidlist[0][0] > bidlist[1][0]:  # No one tied for first
                    _, player = bidlist.pop(0)
                    self.players[player].treasures.append(treasure)
                    self.rooms[room - 1][index] = None
                    self.gamelog(self.players[player], "fought hard and took", treasure)
                # everyone else is a loser
                for _, player in bidlist:
                    self.gamelog(
                        self.players[player],
                        f"attempted to take {treasure.name}, but was met with resistance."
                    )

        for player, message in kill_later:
            self.kill(player, message)

        for room, items in drops.items():
            self.rooms[room - 1] += items

        for room in self.rooms:
            if None in room:
                room[:] = [treasure for treasure in room if treasure]

    def run_game(self):
        self.gamelog("A new game begins!", type='major')

        while any(player.active for player in self.players.values()):
            # if self.turn_number: time.sleep(0.4)
            self.turn()

        self.gamelog("The game has ended!", type='major')

        # TODO: score game

    def kill(self, player, message):
        self.gamelog(player, message, type='bad')
        player.stamina = 0
        self.rooms[player.room - 1] += player.treasures
        player.treasures = []

    def ensure_room(self, room):
        while len(self.rooms) < room:
            self.rooms.append(self.generate_room(len(self.rooms) + 1))

    def gamelog(self, *message, type='info'):
        print(f"{MSG_COLORS[type]}[Turn {self.turn_number:03}]", *message, end=LOG_END)

    def snapshot(self, player):
        return RoomState(
            player.room,
            list(self.rooms[player.room - 1]),
            [
                other.name
                for other in self.players.values()
                if other is not player and other.room == player.room
            ],
            list(player.treasures),
            player.stamina
        )


Ruins(Drunkard, Drunkard, Drunkard, Drunkard, Drunkard).run_game()
