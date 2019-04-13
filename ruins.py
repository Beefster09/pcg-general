#!/usr/bin/env python3.7

import argparse
import math
import heapq
import importlib
import itertools
import os.path
import pickle
import pkgutil
import random
import sys
import time
import traceback
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from typing import List

import requests
from lxml import html
from tabulate import tabulate

# Logging constants
MSG_COLORS = defaultdict(
    lambda: '\x1b[37m', # default value
    tourney='\x1b[94m',
    major='\x1b[95m',
    minor='\x1b[93m',
    good='\x1b[32m',
    bad='\x1b[91m',
    warning='\x1b[33m',
    error='\x1b[31m',
    info='\x1b[37m',
    debug='\x1b[90m',
    score='\x1b[36m',
    final='\x1b[96m',
    pool='\x1b[96m',
    winner='\x1b[92m',
)
MSG_TYPES = set(MSG_COLORS)
if sys.stdin.isatty():
    CLEAR_COLOR = '\x1b[0m'
    MSG_COLORS['seed'] = '\x1b[94m'
else:
    MSG_COLORS = defaultdict(str)
    CLEAR_COLOR = ''
LOG_END = CLEAR_COLOR + '\n'
LOG_SUPPRESS = set()

def exception(message=None):
    if message:
        print(f"{MSG_COLORS['error']}{message}", file=sys.stdout)
    else:
        print(MSG_COLORS['error'], end='', file=sys.stdout)
    traceback.print_exc()
    print(CLEAR_COLOR, end='', file=sys.stdout)

ALL = type('ALL', (), {'__contains__': lambda s,x: True})()

# Name Pool (for adventurers)

FIRST_NAMES = [
    'Eddard', 'Rob', 'Jon', 'Sansa', 'Theon', 'Arya', 'Brandon', 'Richard',
    'Hodor', 'Jaime', 'Cersei', 'Tyrion', 'Tywin', 'Robert', 'Joffrey',
    'Tommen', 'Dany', 'Samwell', 'Marjorie', 'Stannis', 'Peter', 'Jora',
    'Bilbo', 'Frodo', 'Sam', 'Legolas', 'Gimley', 'Gandalf', 'Ned', 'Albert',
    'Lyn', 'Eliwood', 'Hector', 'Guy', 'Kent', 'Dorcas', 'Fiora', 'Ike',
    'Marth', 'Roy', 'Lucina', 'Corrin', 'Robin', 'Chrom', 'Anna', 'Ramsey',
    'Alexander', 'James', 'John', 'Jacob', 'Deborah', 'Rebecca', 'Willard',
    'Zeus', 'Athena', 'Apollo', 'Diana', 'Juno', 'Hera', 'Icarus', 'Samson',
    'Chell', 'Gordon', 'Samus', 'Link', 'Edward', 'Alphonse', 'Winry', 'Fox',
    'Mario', 'Luigi', 'Ash', 'Brock', 'Misty', 'Winston', 'Torbjorn', 'Angela',
    'Kirby', 'Masahiro', 'Shigeru', 'Lucy', 'Freddie', 'Patrick', 'Aerith',
    'Cloud', 'Tifa', 'Barret', 'Red', 'Blue', 'Gary', 'Chara', 'Usagi',
    'Ajna', 'Morgan', 'Steve', 'Harry', 'Jack', 'Homer', 'Bart', 'Lisa',
    'Elsa', 'Ana', 'Emma', 'Regina', 'Mary', 'Margaret', 'Pit', 'Brad',
    'Sonja', 'Ryu', 'Ken', 'Olivia', 'Major', 'Ron', 'Quinn', 'Elmer',
    # Signing off
    'Justin'
]

LAST_NAMES = [
    'Stark', 'Barathean', 'Lannister', 'Snow', 'Tarley', 'Grayjoy', 'Bolton',
    'Stormborn', 'Targaryen', 'Balish', 'Mormant', 'Baggins', 'Churchill',
    'Freeman', 'Aran', 'Elric', 'Rockbell', 'McCloud', 'Lombardi', 'Smith',
    'Lindholm', 'Ketchum', 'Sakurai', 'Miyamoto', 'Heartfilia', 'Mercury',
    'Oak', 'Elm', 'Birch', 'Tsukino', 'Strife', 'Lockheart', 'Jackson',
    'Potter', 'Sparrow', 'Simpson', 'Flanders', 'Young', 'Einstein', 'Swan',
    'Parker', 'Harris', 'Moore', 'Barnes', 'Finley', 'Pitt', 'Ridley'
]

NAME_SUFFIXES = [
    'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XIII',
    'Jr.', 'Sr.', 'PhD', 'MD', 'DDS'
]

MONIKERS = [
    'the Great', 'the Smuggler', 'the Cat Burglar', 'the Insomniac',
    'the Forgettable', 'the Orphan', 'the Wizard', 'the Lazy',
    'the Untamed', 'the Well-armed', 'the Pirate', 'the Unimportant',
    'the Hero', 'the Unkempt', 'the Distasteful', 'the Dog Whisperer',
    'the Peasant', 'the Impaler', 'of Arendale', 'the Simpleton'
]

# lol Cloud McCloud is possible.

# === Data structures for the game ===

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


# === Adventurers ===

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

# === Player Information ===

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
            exception(f"Exception from {self}: {str(e)}")
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
            exception(f"Invalid action from {self}: {raw_action}")
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
    pause_on_death = []

    def __init__(self, *adventurers, seed=None):
        assert adventurers
        if seed is None:
            seed = random.getrandbits(6969)
        self._seed_obj = [adv.__name__ for adv in adventurers], seed
        self._replay_saved = False
        self.random = random.Random(seed)
        # create a separate random instance for flavor so that deaths and other
        # flavorful events don't interfere with treasure generation
        self.flavor_rand = random.Random(self.random.getrandbits(420))
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

    @classmethod
    def from_replay(cls, replay_file, candidates):
        with open(replay_file, 'rb') as f:
            adv_names, seed = pickle.load(f)
        cand = {
            botclass.__name__: botclass
            for botclass in [*candidates, Drunkard]
        }
        adventurers = [cand[name] for name in adv_names]
        return cls(*adventurers, seed=seed)

    def save_replay(self, replay_file):
        if not self._replay_saved:
            with open(replay_file, 'wb') as f:
                pickle.dump(self._seed_obj, f)
            self._replay_saved = True

    def new_seed(self):
        return random.Random(self.random.getrandbits(744))

    def generate_name(self):
        r = self.flavor_rand.random()
        parts = [self.flavor_rand.choice(FIRST_NAMES)]
        if r < 0.75:
            parts.append(self.flavor_rand.choice(LAST_NAMES))
            if r < 0.15:
                parts.append(self.flavor_rand.choice(NAME_SUFFIXES))
        else:
            parts.append(self.flavor_rand.choice(MONIKERS))
        return ' '.join(parts)

    def ndr(self, n, r):
        return sum(self.random.randint(1, r) for _ in range(n))

    def generate_treasure(self, room):
        weight = max(1, self.ndr(2, 6) - 2)
        value = self.ndr(1, 10 * weight) + self.ndr(2, 5 * room + 10)
        return Treasure(f"Treasure #{next(self.treasure_num):03}", value, weight)

    def generate_room(self, room):
        n_treasures = self.random.randint(room // 3 + 3, room // 2 + 5)
        return [self.generate_treasure(room) for _ in range(n_treasures)]

    def ensure_room(self, room):
        while len(self.rooms) < room:
            self.rooms.append(self.generate_room(len(self.rooms) + 1))

    def trap(self):
        return self.flavor_rand.choice([
            "was sliced in half by a swinging blade trap.",
            "fell into a pit of spikes.",
            "was crushed by a boulder.",
            "was eaten by a wild shriekbat.",
            "was shot by a crossbow trap.",
            "fell into a bottomless pit.",
            "was devoured by a mimic.",
            "was incinerated by a fire trap.",
            "got sucked into a dimensional vortex.",
            "mysteriously vanished.",
            "was flung into a pool of acid.",
            "was stung by a giant bee.",
            "was absorbed by a gelatinous monster.",
            "was bitten by a swarm of venomous snakes.",
            "was decapitated by a sword trap"
        ])

    def kill(self, player, message):
        self.gamelog(player, message, type='bad')
        player.stamina = 0
        if player.treasures:
            self.rooms[player.room - 1] += player.treasures
            self.gamelog(f"{player.name} dropped these items into room {player.room}:", type='debug')
            for treasure in player.treasures:
                self.gamelog(treasure, type='debug')
            player.treasures = []
        if type(player.bot).__name__ in self.pause_on_death:
            if self._replay_saved:
                input('Press enter to continue...')
            else:
                filename = input('Save a replay? (enter a name) ')
                if filename:
                    self.save_replay(filename + '.seed')
                    if input('Exit? ').lower().startswith('y'):
                        sys.exit(1)

    def gamelog(self, *message, type='info', end='', **kwargs):
        if type in LOG_SUPPRESS:
            return
        if self.complete:
            prefix = 'Game End'
        elif self.turn_number == 0:
            prefix = 'Pregame'
        else:
            prefix = f"Turn {self.turn_number:03}"
        print(f"{MSG_COLORS[type]}[{prefix}]", *message, end=(LOG_END+end), **kwargs)

    def gamelog_lines(self, lines, type='info'):
        if type in LOG_SUPPRESS:
            return
        if self.complete:
            prefix = 'Game End'
        elif self.turn_number == 0:
            prefix = 'Pregame'
        else:
            prefix = f"Turn {self.turn_number:03}"
        print(MSG_COLORS[type], end='')
        for line in lines:
            print(f"[{prefix}] {line}")
        print(CLEAR_COLOR, end='')

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
                kill_later.append((player, f"{self.trap()} (Invalid action.)"))
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
                except ValueError:
                    kill_later.append((player, self.trap() + " (Non-integer bid)"))
                    continue

                try:
                    target = self.rooms[player.room - 1][int(treasure)]
                except IndexError:
                    kill_later.append((player, self.trap() + " (Invalid treasure index)"))
                    continue
                except (TypeError, ValueError):
                    kill_later.append(
                        (player, f"{self.trap()} (Non-integer treasure index)")
                    )
                    continue

                min_bid = target.weight
                if bid < min_bid:
                    kill_later.append((
                        player,
                        f"tried to lift {target.name} but {self.trap()} (Bid too low)"
                    ))
                elif bid > player.stamina:
                    kill_later.append((
                        player,
                        f"went all out to take {target.name}, but had a heart attack and"
                        " collapsed. (Bid too high)"
                    ))
                elif target.weight + player.carry_weight > 50:
                    kill_later.append((player, self.trap() + " (Treasure too heavy)"))
                else:
                    bids[player.room, treasure].append((bid, player.name))
                    player.stamina -= bid

            elif isinstance(action, Drop):
                # No need to check stamina here because we already know this player
                # has at least 1 stamina from the player.active check earlier
                player.stamina -= 1
                try:
                    dropped = player.treasures.pop(int(action.treasure))
                except (IndexError, TypeError, ValueError):
                    kill_later.append((
                        player,
                        "was bitten by a venomous spider and died moments later. (Invalid drop)"
                    ))
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
                exception(f"Failure to initialize {player.bot}")
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
        self.gamelog("Score for this game:", type='score')
        self.gamelog_lines(
            tabulate(
                [
                    [
                        player.bot.__class__.__name__,
                        player.name,
                        f'${player.total_value}' if player.alive else 'DEAD',
                        score,
                    ]
                    for player, score in scores
                ],
                headers=['Bot Class', 'Character', 'Money', 'Score'],
                colalign=['left',     'left',      'right', 'right'],
                tablefmt='presto'
            ).splitlines(),
            type='score'
        )

        return scores

def run_tournament(
    bots,
    game_size=10,
    pool_games=20,
    required_lead=50,
    max_final_games=500,
    seed=None
):
    rand = random.Random(seed)
    def tourneylog(*message, type='tourney', end='', **kwargs):
        if type in LOG_SUPPRESS:
            return
        print(f"{MSG_COLORS[type]}[==TOURNAMENT==]", *message, end=(LOG_END+end), **kwargs)

    full_pool = bots[:]
    scores = {
        bot_class.__name__: 0
        for bot_class in full_pool
    }
    bots_by_name = {
        bot_class.__name__: bot_class
        for bot_class in full_pool
    }

    def run_game(bots):
        game = Ruins(*bots, seed=rand.getrandbits(1337))
        for player, score in game.run_game():
            if not isinstance(player.bot, Drunkard):
                scores[type(player.bot).__name__] += score

    if len(full_pool) > game_size:
        tourneylog(
            f"Since there are more than {game_size} bots in the tournament,"
            " a pool will be run to determine which bots will compete in the final series."
        )
        game_counts = {bot.__name__: 0 for bot in full_pool} #TEMP
        carryover = []
        for pool_round in range(pool_games):
            tourneylog("Starting round", pool_round + 1, "of the pool")
            rand.shuffle(full_pool)
            pool = carryover
            carryover = []
            for bot in full_pool:
                while len(pool) >= game_size:
                    for b in pool[:game_size]:
                        game_counts[b.__name__] += 1
                    run_game(pool[:game_size])
                    pool = pool[game_size:]
                if bot in pool:
                    carryover.append(bot)
                else:
                    pool.append(bot)
            carryover += pool
            while len(carryover) >= game_size:
                for b in carryover[:game_size]:
                    game_counts[b.__name__] += 1
                run_game(carryover[:game_size])
                carryover = carryover[game_size:]
        tourneylog("Making sure an equal number of games were played by each bot...", type='debug')
        for botname, count in game_counts.items():
            tourneylog(
                botname, 'played', count, 'games.',
                type=('debug' if count == pool_games else 'warning')
            )

        ranked_bots = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        tourneylog("Results from pool series:", type='pool')

        for line in tabulate(
            [
                (botname, score, format(score / pool_games, '.03f'))
                for botname, score in ranked_bots
            ],
            headers=['Bot Class', 'Score', 'Mean Score'],
            tablefmt='presto'
        ).splitlines():
            tourneylog(line, type='pool')

        finalists = [
            bots_by_name[botname]
            for botname, _ in ranked_bots[:game_size]
        ]
        scores = {
            bot_class.__name__: 0
            for bot_class in finalists
        }

    else:
        finalists = full_pool
        if len(finalists) < game_size:
            tourneylog(
                "Since there aren't enough bots, remaining slots will be filled in with Drunkards",
                type='warning'
            )
            while len(finalists) < game_size:
                finalists.append(Drunkard)

    finalist_game = 0
    while True:
        finalist_game += 1
        tourneylog(f"Starting game {finalist_game} of the final round.")
        run_game(finalists)
        if finalist_game >= max_final_games:
            tourneylog("Maximum number of finalist games run!", type='warning')
            break
        if len(scores) < 2:
            tourneylog("There aren't enough competitors. Exiting.", type='bad')
            return
        first, second = heapq.nlargest(2, scores.values())
        if first - second >= required_lead:
            tourneylog(
                f"The first place bot has achieved a {first - second} point lead over the"
                " second place bot!"
            )
            break

    ranked_bots = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    tourneylog("The tournament has completed successfully!")
    tourneylog("Final scores of the finalists:", type='final')
    for line in tabulate(
            [
                (botname, score, format(score / finalist_game, '.03f'))
                for botname, score in ranked_bots
            ],
            headers=['Bot Class', 'Score', 'Mean Score'],
            tablefmt='presto'
        ).splitlines():
            tourneylog(line, type='final')

    tourneylog(f"The winner of the tournament is {ranked_bots[0][0]}!", type='winner')

# === META - Loading bots ===

def scrape_page(url):
    try:
        page = html.fromstring(requests.get(url).text)
    except Exception:
        exception("Unable to download bots")
        sys.exit(2)
    for answer in page.xpath("//div[@class='answer']"):
        try:
            headers = answer.xpath(".//h1")
            title = headers[0].text_content()
            user = answer.xpath(".//div[@class='user-details']//a")[-1].text
            code = answer.xpath(".//pre/code")[0].text
        except Exception:
            exception("Unable to extract bot from answer")
        else:
            yield code, title, user


def sanitize(name):
    name = '_'.join(name.split())
    for i, ch in enumerate(name):
        if ch != '_' and not ch.isalnum():
            return name[:i]
    else:
        return name

def download_bots(url, bot_dir):
    for code, title, user in scrape_page(url):
        try:
            module_file = f"{sanitize(user).lower()}__{sanitize(title).lower()}.py"
            if not module_file[0].isalpha():
                module_file = 'a__' + module_file
            with open(os.path.join(bot_dir, module_file), 'w') as f:
                f.write(
                    f"'''{title}\nby {user}\n'''\n"
                    "from __main__ import Adventurer\n"
                    "print = lambda *_, **__: None\n\n"
                )
                f.write(code)
        except Exception:
            exception()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-s', '--seed',
        help="Seed to use"
    )
    parser.add_argument(
        '-r', '--replay',
        help="Run from a replay file."
    )

    parser.add_argument(
        '-d',
        '--bot-dir',
        default='ruins_bots'
    )
    parser.add_argument(
        '--url',
        help="Download bot code from StackExchange first"
    )
    parser.add_argument(
        '-1', '--single',
        action='store_true',
        help="Run a single game instead of a tournament."
        " This will not limit the maximum number of adventurers in the ruins"
        " or fill in empty slots with Drunkards."
    )
    parser.add_argument(
        '-p', '--pause-on-death',
        nargs='?',
        metavar='CLASSNAME',
        const=ALL,
        default=[],
        type=lambda s: s.split(':'),
        help="Pause the controller when an adventurer dies. You may also specify a colon-separated list of class names to match against."
    )

    logmodes = parser.add_mutually_exclusive_group()
    logmodes.add_argument(
        '--debug',
        action='store_true',
        help='Show all game log messages.'
    )
    logmodes.add_argument(
        '--silent',
        action='store_true',
        help="Suppress all log messages"
    )
    logmodes.add_argument(
        '-q', '--quiet',
        action='store_true',
        help="Suppress unimportant log messages."
    )
    parser.add_argument(
        '-x', '--suppress',
        nargs='+',
        default=[],
        choices=MSG_TYPES,
        metavar='TYPE',
        help=f"Suppress messages of the given type. (One of: {', '.join(MSG_TYPES)})"
    )
    logmodes.add_argument(
        '-o', '--only',
        nargs='+',
        choices=MSG_TYPES,
        metavar='TYPE',
        help="Only show messages of the given types. (Same options as --suppress)"
    )

    args = parser.parse_args()

    if args.debug and args.suppress:
        parser.error("Cannot pass --suppress and --debug together.")
    if args.only and args.suppress:
        parser.error("Cannot pass --suppress and --only together.")

    if args.silent:
        LOG_SUPPRESS = ALL
    elif args.quiet:
        LOG_SUPPRESS |= {'minor', 'good', 'info'}
        if not args.single:
            LOG_SUPPRESS.update({'score', 'major'})
    elif args.only:
        LOG_SUPPRESS = MSG_TYPES - set(args.only)

    if not args.debug:
        LOG_SUPPRESS.add('debug')

    LOG_SUPPRESS.update(args.suppress)
    if 'error' in LOG_SUPPRESS:
        exception = lambda *_, **__: None

    if args.url:
        os.makedirs(args.bot_dir, exist_ok=True)
        download_bots(args.url, args.bot_dir)

    bot_classes = []
    if os.path.isdir(args.bot_dir):
        for finder, name, ispkg in pkgutil.walk_packages([os.path.abspath(args.bot_dir)]):
            if ispkg:
                continue
            try:
                module = finder.find_module(name).load_module(name)
            except:
                exception("Recovering from error in import")
            else:
                for obj in vars(module).values():
                    if (    obj is not Adventurer
                            and isinstance(obj, type)
                            and issubclass(obj, Adventurer)):
                        bot_classes.append(obj)

    Ruins.pause_on_death = args.pause_on_death

    if args.replay:
        Ruins.from_replay(args.replay, [*bot_classes, Drunkard]).run_game()
    else:
        if args.seed is None:
            args.seed = ''.join(
                random.choice('0123456789ABCDEFGHJKLMNPQRSTVWXY') for _ in range(8)
            )
            if not args.silent:
                print(f"Seed: {MSG_COLORS['seed']}{args.seed}{CLEAR_COLOR}")

        if args.single:
            Ruins(*bot_classes, seed=args.seed).run_game()
        else:
            run_tournament(bot_classes, seed=args.seed)
