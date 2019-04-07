#!/usr/bin/env python3.7

import argparse
import math
import itertools
import random
import sys
import time
import traceback
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
LOG_SUPPRESS = set()

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
            if 'error' not in LOG_SUPPRESS:
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
            if 'error' not in LOG_SUPPRESS:
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


Trap = object()  # simple sentinel
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
        self.complete = False

    def new_seed(self):
        return random.Random(self.random.getrandbits(1024))

    def generate_name(self):
        return f"Adventurer #{next(self.adv_num)}"

    def ndr(self, n, r):
        return sum(self.random.randint(1, r) for _ in range(n))

    def generate_treasure(self, room):
        weight = max(1, self.ndr(2, 6) - 2)
        value = self.ndr(1, 10 * weight) + self.ndr(2, 5 * room + 10)
        return Treasure(f"Treasure #{next(self.treasure_num):03}", value, weight)

    def generate_room(self, room):
        n_treasures = self.random.randint(room // 3 + 3, room // 2 + 5)
        return [self.generate_treasure(room) for _ in range(n_treasures)]

    def turn(self):
        self.turn_number += 1
        self.gamelog("Turn", self.turn_number, "begins!", type='minor')
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
                kill_later.append((player, Trap))
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
                    target = self.rooms[player.room - 1][int(treasure)]
                    min_bid = target.weight
                except (IndexError, TypeError, ValueError):
                    kill_later.append((player, Trap))
                    continue
                if min_bid <= bid <= player.stamina and target.weight + player.carry_weight <= 50:
                    bids[player.room, treasure].append((bid, player.name))
                    player.stamina -= bid
                else:
                    kill_later.append((player, Trap))

            elif isinstance(action, Drop):
                # No need to check stamina here because we already know this player
                # has at least 1 stamina from the player.active check earlier
                player.stamina -= 1
                try:
                    dropped = player.treasures.pop(int(action.treasure))
                except (IndexError, TypeError, ValueError):
                    kill_later.append(
                        (player, "was bitten by a venomous spider and died moments later.")
                    )
                else:
                    drops[player.room].append(dropped)
                    self.gamelog(
                        player,
                        f"Dropped a treasure into room #{player.room}:",
                        dropped
                    )

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


        for room, items in drops.items():
            self.rooms[room - 1] += items

        for room in self.rooms:
            if None in room:
                room[:] = [treasure for treasure in room if treasure]

        for player, message in kill_later:
            self.kill(player, message)

    def run_game(self):
        self.gamelog("A new game begins!", type='major')
        self.gamelog("Competitors:")
        for player in self.players.values():
            self.gamelog(f"* {player}")
            try:
                player.bot.enter_ruins()
            except Exception:
                if 'error' not in LOG_SUPPRESS:
                    print(f"{MSG_COLORS['error']}Failure to initialize {player.bot}")
                    traceback.print_exc()
                self.kill(player, "is dead on arrival.")

        while any(player.active for player in self.players.values()):
            # input()
            self.turn()

        self.complete = True
        self.gamelog("The game has ended!", type='major')

        def ranking_key(player):
            player.treasures.sort(key=lambda x: x.value, reverse=True)
            return (
                player.alive,
                player.total_value,
                -player.carry_weight,
                -len(player.treasures),
                *(treasure.value for treasure in player.treasures)
            )

        ranked = sorted(self.players.values(), key=ranking_key, reverse=True)
        n_players = len(ranked)

        scores = [
            (player, n_players - index if player.alive and player.treasures else 0)
            for index, player in enumerate(ranked)
        ]

        self.gamelog(scores[0][0], "won the game", type='good')
        self.gamelog("Score for this game:")
        for player, score in scores:
            self.gamelog(
                f"{score:>4} -- {player} "
                f"[{f'${player.total_value}' if player.alive else 'DEAD'}]"
            )

        return scores

    def kill(self, player, message=Trap):
        if message is Trap:
            message = random.choice([
                # Yes, this is the global random.
                # This is cosmetic and shouldn't interfere with room generation
                "was sliced in half by a blade trap.",
                "fell into a pit of spikes.",
                "was crushed by a boulder.",
                "was eaten by a wild shriekbat.",
                "was shot by a crossbow trap.",
                "fell into a bottomless pit.",
                "was devoured by a mimic.",
                "was incinerated by a fire trap.",
                "got sucked into a dimensional vortex.",
                "mysteriously vanished."
            ])
        self.gamelog(player, message, type='bad')
        player.stamina = 0
        if player.treasures:
            self.rooms[player.room - 1] += player.treasures
            self.gamelog(f"{player.name} dropped these items into room {player.room}:", type='debug')
            for treasure in player.treasures:
                self.gamelog(treasure, type='debug')
            player.treasures = []

    def ensure_room(self, room):
        while len(self.rooms) < room:
            self.rooms.append(self.generate_room(len(self.rooms) + 1))

    def gamelog(self, *message, type='info'):
        if type in LOG_SUPPRESS:
            return
        if self.complete:
            prefix = 'Game End'
        elif self.turn_number == 0:
            prefix = 'Pregame'
        else:
            prefix = f"Turn {self.turn_number:03}"
        print(f"{MSG_COLORS[type]}[{prefix}]", *message, end=LOG_END)

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


# Adventurers for testing (These intentionally lose)
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
            return 'take', 0, state.treasures[0].weight * 2
        else:
            return 'next'


def run_tournament(seed):
    Ruins(
        Drunkard,
        Drunkard,
        Drunkard,
        Drunkard,
        Drunkard,
        Drunkard,
        EmoKid,
        # Chad,
        Coward,
        GreedyBastard,
        seed=seed
    ).run_game()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-d', '--bot-dir', default='ruins_bots')
    parser.add_argument('--url', help="Download bot code from StackExchange first")
    parser.add_argument('-s', '--seed', help="Seed to use")

    parser.add_argument(
        '--debug',
        action='store_true'
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help="Suppress all log messages"
    )
    parser.add_argument(
        '--quiet',
        dest='suppress',
        action='append_const',
        const={'minor', 'good', 'info'},
        help="Suppress unimportant log messages."
    )
    parser.add_argument(
        '-x', '--suppress',
        action='append',
        type=lambda x: {x},
        help="Suppress messages of the given type."
    )

    args = parser.parse_args()

    if args.silent:
        LOG_SUPPRESS = type('ALL', (), {'__contains__': lambda s,x: True})()
    elif not args.debug:
        LOG_SUPPRESS.add('debug')
    if args.suppress:
        for levels in args.suppress:
            LOG_SUPPRESS |= levels

    if args.seed is None:
        args.seed = ''.join(random.choice('0123456789ABCDEFGHJKLMNPQRSTVWXY') for _ in range(8))
        if not args.silent
            print(f"Seed: {MSG_COLORS['major']}{args.seed}{CLEAR_COLOR}")

    run_tournament(args.seed)
