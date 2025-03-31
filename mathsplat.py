from talon import Module, Context, actions, cron, ui
from talon.skia.canvas import Canvas as SkiaCanvas
from talon.canvas import Canvas
from talon.types import Rect
from typing import Tuple, Any
from dataclasses import dataclass
import time, array, math

debugging = True

mod = Module()
mod.list("mathsplat_captures", desc="terms used for dictating math expressions")

ctx = Context()
ctx.matches = "app: firefox"

@dataclass
class Capture:
    term: str
    time: float

@mod.capture(rule="{user.mathsplat_captures}")
def pos_term(m) -> Capture:
    "Create Capture from mathsplat_captures capture and mouse position"
    # return Capture(term=m, x=actions.mouse_x(), y=actions.mouse_y())
    print(m, m[0].start)
    return Capture(term=m, time=m[0].start)

class MousePositions:
    def __init__(self, time_frame:int):
        # create a linear array of mouse positions from the last time_frame seconds
        # E.g., (1 update / 32ms) * (1000ms / s) * 20s = 625 updates
        updates = math.ceil(time_frame * (1000 / 32))
        #index % 3 == 0 is the time, == 1 is the x pos, == 2 is the y pos
        self.positions = array.array('f', [0.0] * (updates * 3))
        self.update_count = updates
        self.index = 0 #index is < update_count

    def add_curr_pos(self):
        "Updates recorded mouse positions with current mouse position and time"
        curr_time = time.perf_counter()
        x_pos = actions.mouse_x()
        y_pos = actions.mouse_y()

        up_index = self.index * 3

        self.positions[up_index] = curr_time
        self.positions[up_index + 1] = x_pos
        self.positions[up_index + 2] = y_pos
        self.index = (self.index + 1) % self.update_count
        #print("add_curr_pos called, index", self.index)

    def get_pos_from_time(self, capture_time: float) -> Tuple[float, float]:
        "Searches recorded mouse positions for the position at capture_time"
        #Currently searches linearly starting from the current index until it finds a recorded position within a threshold from the capture time
        position = None
        i = self.index
        iterations = 0
        while iterations < self.update_count:
            curr_time = self.positions[i * 3]
            if abs(curr_time - capture_time) < 0.1:
                x = self.positions[i * 3 + 1]
                y = self.positions[i * 3 + 2]
                position = (x,y)
                break
            i = (i - 1) % self.update_count
            iterations += 1

        if position == None:
            print("Error, could not find cursor position match for capture time in MousePositions.get_pos_from_time")
        return position

splat_job = None
capture_queue = []
mouse_positions = MousePositions(time_frame=20)
def on_interval() -> None:
        "Record current mouse position, then process a queue item"
        global capture_queue, mouse_positions

        mouse_positions.add_curr_pos()
        if len(capture_queue) > 0:
            capture: Capture = capture_queue.pop()
            actions.user.do_splat(capture)

def on_draw(c: SkiaCanvas):
    "Draws array of recorded mouse positions to canvas as dots"
    global mouse_positions
    c.paint.color = "FF0000"
    c.paint.style = c.paint.Style.FILL
    for update in range(mouse_positions.update_count):
        up_index = update * 3
        x = mouse_positions.positions[up_index + 1]
        y = mouse_positions.positions[up_index + 2]
        c.draw_circle(cx=x, cy=y, rad=3)


#Debugging with a Canvas
if debugging:
    screen: ui.Screen = ui.main_screen()
    canvas = Canvas.from_screen(screen)
    canvas.draggable = False
    canvas.blocks_mouse = False
    canvas.focused = False
    canvas.cursor_visible = True
    # Add a callback to specify how the canvas should be drawn
    canvas.register("draw", on_draw)
    canvas.freeze()
    canvas.hide()

@mod.action_class
class SplatActions:
    def start_splatting() -> None:
        "Starts cron job that processes queue"
        global splat_job, canvas, debugging
        if splat_job is None:
            splat_job = cron.interval("32ms", on_interval)

        #Debugging
        if debugging:
            canvas.show()
    
    def stop_splatting() -> None:
        "Stops cron job that processes queue"
        global splat_job, capture_queue, canvas, debugging
        if splat_job is not None:
            cron.cancel(splat_job)
            splat_job = None
        capture_queue = []

        #Debugging
        if debugging:
            canvas.hide()

    def push_splat(capture: Capture) -> None:
        "Add splat to global queue"
        global capture_queue
        capture_queue.append(capture)

    def do_splat(capture: Capture) -> None:
        "Inserts capture into tldraw canvas at the position it was spoken"
        global mouse_positions
        start_x = actions.mouse_x()
        start_y = actions.mouse_y()
        position = mouse_positions.get_pos_from_time(capture.time)
        if position is None:
            print("Escaping do_splat")
            return
        pos_x, pos_y = position
        print(capture.term, capture.time, pos_x, pos_y)

        #Actions for TLDRAW text insertion
        actions.key("t")
        actions.mouse_move(x=pos_x, y=pos_y)
        actions.mouse_click()
        actions.insert(capture.term)
        actions.mouse_move(x=start_x, y=start_y)
        actions.key("esc")

    
