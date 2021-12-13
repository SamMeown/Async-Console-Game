import argparse
import asyncio
import curses
import os
import time
from itertools import cycle
from random import choice, randint
from typing import Optional
import signal
import sys

from curses_tools import draw_frame
from curses_tools import read_controls
from explosion import explode
from game_scenario import get_garbage_delay_tics, PHRASES
from obstacles import Obstacle, show_obstacles
from physics import update_speed

TIC_TIMEOUT = 0.1
TICS_PER_YEAR = 10
TIMES = [2.0, 0.3, 0.5, 0.3]

STARS_NUM = 100

coroutines = []
obstacles = []
obstacles_in_last_collisions = []

year = 1957
plasma_unblocked = False


def get_rocket_frames():
    rocket_frames = []
    for filename in (f'rocket_frame_{num}.txt' for num in range(1, 3)):
        with open(f'frames/rocket/{filename}', 'r') as frame:
            rocket_frames.append(frame.read())
    return rocket_frames


def get_garbage_frames():
    grabage_frames = []
    garbage_dir = 'frames/garbage'
    for filename in os.listdir(garbage_dir):
        with open(os.path.join(garbage_dir, filename)) as frame:
            grabage_frames.append(frame.read())
    return grabage_frames


def get_game_over_frame():
    frame_dir = 'frames/game_over'
    with open(os.path.join(frame_dir, 'game_over.txt'), 'r') as frame:
        return frame.read()


def get_frame_size(frame):
    rows = frame.split('\n')
    return max(len(row) for row in rows), len(rows)


async def sleep(tics=1):
    for _ in range(tics):
        await asyncio.sleep(0)


def bound_move(row, column, row_speed, column_speed, row_max, column_max):
    if row <= 0:
        row = 0
        row_speed = 0

    if row >= row_max:
        row = row_max
        row_speed = 0

    if column <= 0:
        column = 0
        column_speed = 0

    if column >= column_max:
        column = column_max
        column_speed = 0

    return row, column, row_speed, column_speed


def _read_controls(canvas):
    return read_controls(canvas)


async def animate_spaceship(canvas, row, column, frames):
    frame_width, frame_height = get_frame_size(frames[0])
    row_max, col_max = curses.window.getmaxyx(canvas)
    row_max -= frame_height
    col_max -= frame_width

    row_speed = column_speed = 0

    #  doubling frames
    frames = [frame for frame in frames for _ in range(2)]
    for frame in cycle(frames):
        # rd, cd, space_pressed = read_controls(canvas)
        rd, cd, space_pressed = _read_controls(canvas)
        row_speed, column_speed = update_speed(row_speed, column_speed, rd, cd)

        row = row + row_speed
        column = column + column_speed
        row, column, row_speed, column_speed = bound_move(row, column, row_speed, column_speed, row_max, col_max)

        if collided := get_collided_obstacle(row, column, frame_height, frame_width):
            obstacles_in_last_collisions.append(collided)
            # First show explosion, then show game over.
            # To synchronize obstacle and spaceship explosions, start the latter one tick later.
            await asyncio.sleep(0)
            await explode(canvas, row + frame_height / 2, column + frame_width / 2)
            coroutines.append(show_gameover(canvas))
            return

        draw_frame(canvas, row, column, frame)
        if space_pressed and plasma_unblocked:
            coroutines.append(fire(canvas, row, column + frame_width // 2, rows_speed=-2))
        await asyncio.sleep(0)
        draw_frame(canvas, row, column, frame, negative=True)


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
    rows_number, columns_number = canvas.getmaxyx()

    column = max(column, 0)
    column = min(column, columns_number - 1)
    row = 0

    frame_width, frame_height = get_frame_size(garbage_frame)
    obstacle = Obstacle(row, column, frame_height, frame_width)
    obstacles.append(obstacle)

    while row < rows_number:
        if obstacle in obstacles_in_last_collisions:
            obstacles.remove(obstacle)
            obstacles_in_last_collisions.remove(obstacle)
            coroutines.append(explode(canvas, row + frame_height / 2, column + frame_width / 2))
            return
        draw_frame(canvas, row, column, garbage_frame)
        await asyncio.sleep(0)
        draw_frame(canvas, row, column, garbage_frame, negative=True)
        row += speed
        obstacle.row = row

    obstacles.remove(obstacle)


async def fill_orbit_with_garbage(canvas):
    global coroutines
    _, col_max = curses.window.getmaxyx(canvas)
    while True:
        delay_tics = get_garbage_delay_tics(year)
        assert delay_tics is not None
        await sleep(delay_tics)
        garbage = choice(get_garbage_frames())
        garbage_width, _ = get_frame_size(garbage)
        column = randint(0, col_max - garbage_width)
        coroutines.append(fly_garbage(canvas, column=column,
                                      garbage_frame=garbage))


async def show_gameover(canvas):
    row_max, col_max = curses.window.getmaxyx(canvas)
    frame = get_game_over_frame()
    frame_width, frame_height = get_frame_size(frame)
    row = row_max / 2 - frame_height / 2
    column = col_max / 2 - frame_width / 2

    while True:
        draw_frame(canvas, row, column, frame)
        await asyncio.sleep(0)


async def blink(canvas, row, column, symbol='*', delay=0):
    canvas.addstr(row, column, symbol, curses.A_DIM)
    await sleep(delay)
    while True:
        canvas.addstr(row, column, symbol)
        await sleep(round(TIMES[1] / TIC_TIMEOUT))

        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await sleep(round(TIMES[2] / TIC_TIMEOUT))

        canvas.addstr(row, column, symbol)
        await sleep(round(TIMES[3] / TIC_TIMEOUT))

        canvas.addstr(row, column, symbol, curses.A_DIM)
        await sleep(round(TIMES[0] / TIC_TIMEOUT))


async def fire(canvas, start_row, start_column, rows_speed=-0.3, columns_speed=0):
    """Display animation of gun shot, direction and speed can be specified."""

    row, column = start_row, start_column

    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)

    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'

    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1

    curses.beep()

    while 0 < row < max_row and 0 < column < max_column:
        if collided := get_collided_obstacle(round(row), round(column)):
            obstacles_in_last_collisions.append(collided)
            return
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


def collides_with_obstacle(obj_row, obj_column, obj_size_rows=1, obj_size_columns=1):
    return any(obstacle.has_collision(obj_row, obj_column, obj_size_rows, obj_size_columns) for obstacle in obstacles)


def get_collided_obstacle(obj_row, obj_column, obj_size_rows=1, obj_size_columns=1) -> Optional[Obstacle]:
    for obstacle in obstacles:
        if obstacle.has_collision(obj_row, obj_column, obj_size_rows, obj_size_columns):
            return obstacle


async def run_scenario(canvas, footer_canvas):
    global year
    year = 1957

    while True:
        _show_year(footer_canvas, year)
        if phrase := PHRASES.get(year):
            show_phrase(footer_canvas, phrase, 40)
        if year == 1961:
            coroutines.append(fill_orbit_with_garbage(canvas))
            # to visualize obstacle frames
            # coroutines.append(show_obstacles(canvas, obstacles))
        if year == 2025:
            global plasma_unblocked
            plasma_unblocked = True
            show_phrase(footer_canvas, "Take the plasma gun! Shoot the garbage!", 999999)

        await sleep(TICS_PER_YEAR)

        year += 1


def _show_year(canvas, _year):
    _, col_max = curses.window.getmaxyx(canvas)
    canvas.addstr(0, col_max - 12, f"Year: {_year}")


async def _show_phrase(canvas, phrase, ticks):
    sub_row_max, sub_col_max = curses.window.getmaxyx(canvas)

    col = - len(phrase)
    stop = (sub_col_max - len(phrase)) // 2

    try:
        while col < stop:
            draw_frame(canvas, 0, col, phrase)
            await asyncio.sleep(0)
            draw_frame(canvas, 0, col, phrase, negative=True)
            col += 6

        draw_frame(canvas, 0, col, phrase)
        await sleep(ticks)
        draw_frame(canvas, 0, col, phrase, negative=True)
    except asyncio.CancelledError:
        draw_frame(canvas, 0, col, phrase, negative=True)
        await asyncio.sleep(0)


def show_phrase(canvas, phrase, ticks):
    if last_phrase := getattr(show_phrase, 'last_phrase', None):
        if last_phrase in coroutines:
            last_phrase.throw(asyncio.CancelledError)
    show_phrase.last_phrase = _show_phrase(canvas, phrase, ticks)
    coroutines.append(show_phrase.last_phrase)


def draw(stdscr):
    curses.curs_set(False)

    stdscr_row_max, stdscr_col_max = curses.window.getmaxyx(stdscr)
    stdscr.border()
    stdscr.hline(stdscr_row_max - 3, 1, curses.ACS_HLINE, stdscr_col_max - 1)
    stdscr.addch(stdscr_row_max - 3, 0, curses.ACS_SSSB)
    stdscr.addch(stdscr_row_max - 3, stdscr_col_max - 1, curses.ACS_SBSS)
    stdscr.refresh()

    canvas = curses.newwin(stdscr_row_max - 4, stdscr_col_max - 2, 1, 1)
    canvas.keypad(True)
    canvas.nodelay(True)

    sub = stdscr.derwin(1, stdscr_col_max - 2, stdscr_row_max - 2, 1)

    row_max, col_max = curses.window.getmaxyx(canvas)
    symbols = '+*.:'

    global coroutines
    coroutines = [blink(canvas,
                        row=randint(1, row_max - 2),
                        column=randint(1, col_max - 2),
                        symbol=choice(symbols),
                        delay=randint(0, round(1.0 / TIC_TIMEOUT))) for _ in range(STARS_NUM)]

    coroutines.append(animate_spaceship(canvas,
                                        row_max // 2,
                                        col_max // 2,
                                        get_rocket_frames()))

    coroutines.append(run_scenario(canvas, sub))

    while True:
        for coroutine in coroutines.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines.remove(coroutine)
        if not coroutines:
            break
        canvas.refresh()
        sub.refresh()
        time.sleep(TIC_TIMEOUT)

    time.sleep(5)


def _tear_down():
    pass


def signal_handler(signal, frame):
    _tear_down()
    sys.exit(0)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Funny console game'
    )
    parser.add_argument('-a', '--advanced-control', action='store_true', default=False,
                        help='Use keyboard monitor to provide advanced spaceship control (experimental)')
    return parser


if __name__ == '__main__':

    signal.signal(signal.SIGINT, signal_handler)

    arg_parser = create_parser()
    args = arg_parser.parse_args()
    if args.advanced_control:
        from keyboard_tools import read_controls as read_controls_advanced, stop_controls_reading

        def _read_controls_advanced(canvas):
            return read_controls_advanced()

        _read_controls = _read_controls_advanced
        _tear_down = stop_controls_reading

    curses.update_lines_cols()
    curses.wrapper(draw)
