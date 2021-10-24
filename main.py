import asyncio
import curses
import os
import time
from itertools import cycle
from random import choice, randint

from curses_tools import draw_frame, read_controls
from physics import update_speed

TIC_TIMEOUT = 0.1
TIMES = [2.0, 0.3, 0.5, 0.3]

STARS_NUM = 100

coroutines = []


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


async def animate_spaceship(canvas, row, column, frames):
    frame_width, frame_height = get_frame_size(frames[0])
    row_max, col_max = curses.window.getmaxyx(canvas)
    row_max -= frame_height
    col_max -= frame_width

    row_speed = column_speed = 0

    #  doubling frames
    frames = [frame for frame in frames for _ in range(2)]
    for frame in cycle(frames):
        rd, cd, _ = read_controls(canvas)
        row_speed, column_speed = update_speed(row_speed, column_speed, rd, cd)

        row = row + row_speed
        column = column + column_speed
        row, column, row_speed, column_speed = bound_move(row, column, row_speed, column_speed, row_max, col_max)

        draw_frame(canvas, row, column, frame)
        await asyncio.sleep(0)
        draw_frame(canvas, row, column, frame, negative=True)


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
    rows_number, columns_number = canvas.getmaxyx()

    column = max(column, 0)
    column = min(column, columns_number - 1)

    row = 0

    while row < rows_number:
        draw_frame(canvas, row, column, garbage_frame)
        await asyncio.sleep(0)
        draw_frame(canvas, row, column, garbage_frame, negative=True)
        row += speed


async def fill_orbit_with_garbage(canvas):
    global coroutines
    _, col_max = curses.window.getmaxyx(canvas)
    while True:
        await sleep(randint(15, 25))
        garbage = choice(get_garbage_frames())
        garbage_width, _ = get_frame_size(garbage)
        column = randint(0, col_max - garbage_width)
        coroutines.append(fly_garbage(canvas, column=column,
                                      garbage_frame=garbage))


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
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


def draw(stdscr):
    curses.curs_set(False)
    stdscr.border()
    stdscr.refresh()

    stdscr_row_max, stdscr_col_max = curses.window.getmaxyx(stdscr)
    canvas = curses.newwin(stdscr_row_max - 2, stdscr_col_max - 2, 1, 1)
    canvas.keypad(True)
    canvas.nodelay(True)

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

    coroutines.append(fill_orbit_with_garbage(canvas))

    while True:
        for coroutine in coroutines.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines.remove(coroutine)
        if not coroutines:
            break
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)

    time.sleep(5)


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
