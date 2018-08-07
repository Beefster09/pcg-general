#!/usr/bin/env python3.7

import argparse
import importlib
import itertools
import random
import requests
import sys
from traceback import print_exc
from lxml import html


untitled = itertools.count()


MAX_STEALS = 3
PLAYER_NAMES = [
    'Alice', 'Alex', 'Albert',
    'Bob', 'Betty', 'Brian',
    'Carol', 'Charlie', 'Candace',
    'Dave', 'Debra', 'Donna',
    'Elizabeth', 'Elliott', 'Edward',
    'Fred', 'Francis', 'Frank',
    'George', 'Greg', 'Gina',
    'Hank', 'Helen', 'Harold',
    'Isabel', 'Isaac', 'Ian',
    'Justin', 'Jennifer', 'John',
    'Ken', 'Kathy', 'Kyle',
    'Lisa', 'Leonard', 'Link',
    'Matt', 'Mike', 'Melissa',
    'Nancy', 'Nicole', 'Nick',
    'Oliver', 'Ophelia', 'Opal',
    'Peter', 'Priscilla', 'Paul',
    'Quinn',
    'Richard', 'Robin', 'Rachel',
    'Sam', 'Stephanie', 'Steve',
    'Theo', 'Trisha', 'Tony',
    'Ulysses', 'Umbra',
    'Vince', 'Victoria',
    'Winston', 'William', 'Whitney',
    'Xavier',
    'Yvette',
    'Zelda', 'Zachary'
]


verbose = debug = lambda *_, **__: None
info = alert = critical = print


class Disqualification(Exception):
    def __init__(self, bot):
        self.bot = bot


class WhiteElephantBot:
    def __init__(self, name):
        self.name = name

    def steal_targets(self, presents, just_stole):
        return [
            name
            for name, (value, steal_count) in presents.items()
            if steal_count < MAX_STEALS and just_stole != name
        ]


class RandomBot(WhiteElephantBot):
    def take_turn(self, players, presents, just_stole):
        return random.choice([None, *self.steal_targets(presents, just_stole)])


class GreedyBot(WhiteElephantBot):
    def take_turn(self, players, presents, just_stole):
        targets = self.steal_targets(presents, just_stole)
        if targets:
            return max(targets, key=lambda player: presents[player][0])
        else:
            return None


class NiceBot(WhiteElephantBot):
    def take_turn(self, players, presents, just_stole):
        return None


def run_round(competitors):
    n_players = len(competitors)
    presents = {}
    bots = [
        botclass(name)
        for botclass, name
        in zip(competitors, random.sample(PLAYER_NAMES, n_players))
    ]
    random.shuffle(bots)
    names = [bot.name for bot in bots]
    byname = {bot.name: bot for bot in bots}
    verbose("[!!!] A new round begins with this turn order:")
    for bot in bots:
        verbose(f"{bot.name} (Controlled by {type(bot).__name__})")
    verbose("---")
    for front in range(n_players):
        current = bots[front]
        just_stole = None
        while True:
            try:
                action = current.take_turn(
                    names[front+1:],
                    {**presents},
                    just_stole
                )
            except Exception as e:
                raise Disqualification(type(current)) from e
            if (
                action
                and action != just_stole
                and action in presents
                and presents[action][0] < MAX_STEALS
            ):
                value, steal_count = presents.pop(action)
                presents[current.name] = value, steal_count + 1
                verbose(f"{current.name} steals from {action}. (value: {value})")
                just_stole = current.name
                current = byname[action]
            else:
                value = random.random()
                verbose(f"{current.name} opens a present worth {value}.")
                presents[current.name] = value, 0
                break
    verbose("[!!!] The round ends")
    return {
        type(bot).__name__: presents[bot.name][0]
        for bot in bots
    }


def run_game(competitors, win_score=500):
    scores = {botclass.__name__: 0 for botclass in competitors}
    while max(scores.values()) < win_score:
        try:
            for botname, present in run_round(competitors).items():
                scores[botname] += present
        except Disqualification as e:
            competitors.remove(e.bot)
            alert(f"{e.bot.__name__} has been disqualified. Reason: {e.__cause__}")
        verbose()
    info(f"[!!!] {max(scores, key=lambda s: scores[s])} is the winner!")
    return scores


def run_competition(bot_classes, win_score=500, show=print):
    results = run_game(bot_classes, win_score)
    ranking = sorted(results.items(), key=lambda x: -x[1])
    for rank, (bot, score) in enumerate(ranking, 1):
        (show or (lambda x: None))(f"{rank:>2}. {bot:<20} {score:>7.3f}")
    return ranking


def get_answers(url):
    page = html.fromstring(requests.get(url).text)
    for answer in page.xpath("//div[@class='answer']"):
        try:
            headers = answer.xpath(".//h1")
            title = headers[0].text if headers else f"Untiltled-{next(untitled)}"
            user = answer.xpath(".//div[@class='user-details']//a")[-1].text
            code = answer.xpath(".//pre/code")[0].text
        except Exception:
            print_exc()
        else:
            yield code, title, user


def extract_bots(base_url):
    for code, title, user in get_answers(base_url):
        try:
            debug(code)
            bot_code = compile(code, f"{user} - {title}", 'exec')
            modscope = {'WhiteElephantBot': WhiteElephantBot}
            exec(bot_code, modscope)
            for varname, var in modscope.items():
                debug(varname)
                if var is WhiteElephantBot:
                    continue
                if isinstance(var, type) and issubclass(var, WhiteElephantBot):
                    yield var
        except Exception:
            print_exc()


def main():
    parser = argparse.ArgumentParser(
        description='Test driver for the "White Elephant Exchange" king of the'
        ' hill challenge'
    )

    parser.add_argument(
        'local_bots',
        nargs='*',
        help="Qualified names for all the local bots to include"
    )
    parser.add_argument(
        '-u', '--url',
        help="URL to use for extracting bots from answers."
    )
    parser.add_argument(
        '-c', '--clone',
        metavar='N',
        type=int,
        help="Create N additional clones of each bot class."
    )
    parser.add_argument(
        '-w', '--win-score',
        type=float,
        default=500,
        help="Set the score required for a win."
    )
    parser.add_argument(
        '-x', '--exclude',
        action='append',
        default=[],
        help="Exclude certain bots (for being broken)"
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help="Show more messages"
    )
    parser.add_argument(
        '-q', '--quiet',
        action='count',
        default=0,
        help="Show less messages"
    )

    args = parser.parse_args()

    verbosity = args.verbose - args.quiet

    if verbosity >= 1:
        global verbose
        verbose = print
    if verbosity >= 2:
        global debug
        debug = print
    if verbosity <= -1:
        global info
        info = lambda *_, **__: None
    if verbosity <= -2:
        global alert
        alert = lambda *_, **__: None
    if verbosity <= -3:
        global critical
        alert = lambda *_, **__: None

    bot_classes = [RandomBot, GreedyBot, NiceBot]

    for qualname in args.local_bots:
        modulename, classname = qualname.rsplit('.', 1)
        module = importlib.import_module(modulename)
        bot_classes.append(getattr(module, classname))

    if args.url:
        bot_classes += extract_bots(args.url)

    if args.exclude:
        bot_classes = [
            bot for bot in bot_classes if bot.__name__ not in args.exclude
        ]

    if args.clone and args.clone > 0:
        base_bots = [*bot_classes]
        for i in range(args.clone):
            bot_classes += [
                type(f'{bot.__name__}__{i+1}', (bot,), {})
                for bot in base_bots
            ]

    run_competition(bot_classes, args.win_score)

if __name__ == '__main__':
    main()
