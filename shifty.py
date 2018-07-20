#!/usr/bin/env python3.7

import argparse
import importlib
import random
try:
    import readline
except ImportError:
    pass
from dataclasses import dataclass, field
from typing import List, Union


@dataclass(frozen=True)
class CellView:
    forward: bool
    left: bool
    right: bool
    back: bool
    contents: Union[int, str, None]


@dataclass(frozen=True)
class Vision:
    forward: List[CellView]
    left: CellView
    right: CellView

    def __str__(self):
        vision_dist = len(self.forward)
        grid = [
            *[list('  +++  ') for _ in range((vision_dist - 1) * 2)],
            *[['+'] * 7 for _ in range(3)],
        ]

        def contents(cell):
            if cell.contents:
                if cell.contents == 'cache':
                    return '**'
                else:
                    return format(cell.contents, '>2')[:2]
            else:
                return '  '

        for i, cell in enumerate(self.forward):
            r = (vision_dist - i) * 2 - 2
            grid[r][1] = '  '
            grid[r][5] = '  '
            grid[r + 1][1] = '  '
            grid[r + 1][5] = '  '

            if cell:
                grid[r + 1][3] = contents(cell)

                grid[r][3] = '--' if cell.forward else '  '
                grid[r + 2][3] = '--' if cell.back else '  '
                grid[r + 1][2] = '|' if cell.left else ' '
                grid[r + 1][4] = '|' if cell.right else ' '
            else:
                grid[r + 1][3] = '<>'
                grid[r][3] = '  '
                grid[0][3] = '  '
                grid[0][2] = ' '
                grid[0][4] = ' '
                grid[r + 2][3] = '  '
                grid[r + 1][2] = ' '
                grid[r + 1][4] = ' '
                grid[r][3] = ' '
                grid[r][5] = ' '

        if self.left != '???':
            if self.left:
                grid[-2][1] = contents(self.left)
                grid[-3][1] = '--' if self.left.forward else '  '
                grid[-1][1] = '--' if self.left.back else '  '
                grid[-2][0] = '|' if self.left.left else ' '
            else:
                grid[-2][1] = '<>'
                grid[-1][1] = '  '
                grid[-3][1] = '  '
                grid[-1][0] = ' '
                grid[-2][0] = ' '
                grid[-3][0] = ' '
        else:
            grid[-1][1] = '++'
            grid[-2][1] = '++'
            grid[-3][1] = '++'

        if self.right != '???':
            if self.right:
                grid[-2][5] = contents(self.right)
                grid[-3][5] = '--' if self.right.forward else '  '
                grid[-1][5] = '--' if self.right.back else '  '
                grid[-2][6] = '|' if self.right.right else ' '
            else:
                grid[-2][5] = '<>'
                grid[-1][5] = '  '
                grid[-3][5] = '  '
                grid[-1][6] = ' '
                grid[-2][6] = ' '
                grid[-3][6] = ' '
        else:
            grid[-1][5] = '++'
            grid[-2][5] = '++'
            grid[-3][5] = '++'

        return '\n'.join([''.join(row) for row in grid])


NORTH = 0
EAST = 1
SOUTH = 2
WEST = 3
DIRS = [
    (-1,  0), # North
    ( 0,  1), # East
    ( 1,  0), # South
    ( 0, -1), # West
]
DIRNAMES = ['North', 'East', 'South', 'West']

@dataclass
class Cell:
    walls: List[bool] = field(default_factory=lambda: [True] * 4)
    contents: Union[int, str, None] = None

    def get_view(self, orientation):
        return CellView(
            forward=self.walls[orientation],
            left=self.walls[(orientation + 3) % 4],
            right=self.walls[(orientation + 1) % 4],
            back=self.walls[(orientation + 2) % 4],
            contents=self.contents
        )


class Maze:
    def __init__(self, width, height, *, rand=None):
        if rand is not None:
            try:
                self.random = random.Random(rand)
            except TypeError:
                self.random = rand
        else:
            self.random = random.Random()
        randrange = self.random.randrange
        randint = self.random.randint
        self.cells = [
            [Cell() for _ in range(width)]
            for __ in range(height)
        ]
        self.width = width
        self.height = height
        self.entrance = None

        if width >= 8:
            w2 = width // 2
            w8 = width // 8
            cache_c = randrange(w2 - w8, w2 + w8)
        else:
            cache_c = width // 2
        if height >= 8:
            h2 = height // 2
            h8 = height // 8
            cache_r = randrange(h2 - h8, h2 + h8)
        else:
            cache_r = height // 2
        unvisited = [[True] * width for _ in range(height)]
        unvisited[cache_r][cache_c] = False
        self.cells[cache_r][cache_c].contents = 'cache'

        def solid(r, c):
            if 0 <= r < height and 0 <= c < width:
                return unvisited[r][c]
            else:
                return False

        def get_walls(r, c):
            if solid(r - 1, c):
                yield r, c, r - 1, c, NORTH
            if solid(r + 1, c):
                yield r, c, r + 1, c, SOUTH
            if solid(r, c - 1):
                yield r, c, r, c - 1, WEST
            if solid(r, c + 1):
                yield r, c, r, c + 1, EAST

        walls = [*get_walls(cache_r, cache_c)]
        while walls:
            r1, c1, r2, c2, direction = walls.pop(randrange(len(walls)))
            if solid(r2, c2):
                unvisited[r2][c2] = False
                self.cells[r1][c1].walls[direction] = False
                self.cells[r2][c2].walls[(direction + 2) % 4] = False
                walls += get_walls(r2, c2)

        for _ in range((width * height) // 10):
            while True:
                r = randrange(height)
                c = randrange(width)
                if self.cells[r][c].contents is None:
                    break
            self.cells[r][c].contents = randint(3, 5)

        self.randomize_entrance()

    def __str__(self):
        grid = [
            ['+'] * (self.width * 2 + 1)
            for _ in range(self.height * 2 + 1)
        ]
        for r in range(self.height):
            for c in range(self.width):
                cell = self.cells[r][c]
                grid[r*2+1][c*2+1] = (
                    '  ' if cell.contents is None
                    else format(str(cell.contents)[:2], '>2')
                )
                north, east, south, west = cell.walls
                grid[r*2][c*2+1] = '--' if north else '  '
                grid[r*2+2][c*2+1] = '--' if south else '  '
                grid[r*2+1][c*2] = '|' if west else ' '
                grid[r*2+1][c*2+2] = '|' if east else ' '
        return '\n'.join([''.join(row) for row in grid])

    def randomize_entrance(self):
        if self.entrance:
            r, c, dir = self.entrance
            self.cells[r][c].walls[dir] = True

        def set_entrance(r, c, dir):
            self.entrance = r, c, dir
            self.cells[r][c].walls[dir] = False

        entrance = self.random.randrange(self.width * 2 + self.height * 2)
        if entrance < self.width:
            set_entrance(0, entrance, NORTH)
            return
        else:
            entrance -= self.width

        if entrance < self.height:
            set_entrance(entrance, self.width - 1, EAST)
            return
        else:
            entrance -= self.height

        if entrance < self.width:
            set_entrance(self.height - 1, entrance, SOUTH)
            return
        else:
            entrance -= self.width

        assert entrance < self.height
        set_entrance(entrance, 0, WEST)

    def get_view(self, r, c, dir):
        def cell_view(r, c):
            if 0 <= r < self.height and 0 <= c < self.width:
                return self.cells[r][c].get_view(dir)
            else:
                return None
        fdr, fdc = DIRS[dir]
        rdr, rdc = DIRS[(dir + 1) % 4]
        ldr, ldc = DIRS[(dir + 3) % 4]
        curcell = cell_view(r, c)
        left = '???' if curcell.left else cell_view(r + ldr, c + ldc)
        right = '???' if curcell.right else cell_view(r + rdr, c + rdc)
        forward = [curcell]
        while curcell and not curcell.forward:
            r += fdr
            c += fdc
            curcell = cell_view(r, c)
            forward.append(curcell)
        return Vision(left=left, right=right, forward=forward)


class InvalidAction(Exception):
    pass


def run_challenge(width, height, mouseclass, *, random=None, cache_size=100):
    maze = Maze(width, height, rand=random)
    mouse = mouseclass()
    turn = 0
    for seed in range(cache_size):
        r, c, dir = maze.entrance
        dir = (dir + 2) % 4
        mouse.enter_maze()
        has_seed = False
        while True:
            view = maze.get_view(r, c, dir)
            action = mouse.get_action(view)
            if action == 'right':
                dir = (dir + 1) % 4
            elif action == 'left':
                dir = (dir + 3) % 4
            elif action == 'forward':
                if view.forward[0].forward:
                    raise InvalidAction("Cannot move forward through wall.")
                dr, dc = DIRS[dir]
                if not (0 <= r + dr < maze.height and 0 <= c + dc < maze.width):
                    if has_seed:
                        break
                    else:
                        raise InvalidAction("Cannot exit maze without seed.")
                r += dr
                c += dc
            elif action == 'eat':
                if not isinstance(view.forward[0].contents, int):
                    raise InvalidAction("Nothing to eat")
                maze.cells[r][c].contents -= 1
                if maze.cells[r][c].contents <= 0:
                    maze.cells[r][c].contents = None
            else:
                raise InvalidAction(f"Unrecognized action: {action}")
            turn += 1
            if not has_seed and maze.cells[r][c].contents == 'cache':
                has_seed = True
        maze.randomize_entrance()
    print(f"All seeds collected in {turn} turns")


class InteractiveMouse:
    SHORTCUTS = {
        'f': 'forward',
        'l': 'left',
        'r': 'right',
        'e': 'eat',

        'w': 'forward',
        'a': 'left',
        's': 'eat',
        'd': 'right',
    }
    def __init__(self):
        self.last = 'forward'

    def enter_maze(self):
        print("Entered maze")

    def get_action(self, view):
        print()
        print(view)
        while True:
            action = input('> ')
            if not action:
                action = self.last
            else:
                self.last = action
            if action in self.SHORTCUTS:
                return self.SHORTCUTS[action]
            elif action in ['forward', 'eat', 'right', 'left']:
                return action


def main():
    parser = argparse.ArgumentParser(
        description='The official "Shifty Maze" code challenge test driver'
    )

    parser.add_argument(
        'bot_class',
        nargs='?',
        help="The qualified name of your bot class, including the module name."
    )

    parser.add_argument(
        '-r', '--seed', '--random-seed',
        help="The random seed to use"
    )
    parser.add_argument(
        '-i', '--interactive-demo',
        action='store_true',
        help="Run the interactive demo. Control with w, a, s, d commands or"
        " input your intended action or the first letter of it."
    )
    parser.add_argument(
        '-s', '--size',
        nargs=2,
        type=int,
        default=None,
        help="Change the size of the maze"
    )
    parser.add_argument(
        '-c', '--cache_size', '--seed-count',
        type=int,
        default=None,
        help="The number of sunflower seeds in the maze's cache."
    )
    parser.add_argument(
        '-f', '--final-score',
        action='store_true',
        help="Score the bot on the standard maze"
    )

    args = parser.parse_args()

    if args.final_score:
        args.size = 30, 30
        args.cache_size = 100
        args.random_seed = 'ShiftyMazeCodeChallenge2018'

    if args.interactive_demo:
        bot_class = InteractiveMouse
        if not args.size:
            args.size = 5, 5
        if not args.cache_size:
            args.cache_size = 3
    else:
        if not args.bot_class:
            parser.error("Either a bot class or interactive mode is required!")
        modulename, classname = args.bot_class.rsplit('.', 1)
        module = importlib.import_module(modulename)
        bot_class = getattr(module, classname)

    if not args.size:
        args.size = 30, 30
    if not args.cache_size:
        args.cache_size = 100

    run_challenge(
        *args.size,
        bot_class,
        random=args.seed,
        cache_size=args.cache_size
    )

if __name__ == '__main__':
    main()
