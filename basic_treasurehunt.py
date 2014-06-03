import libtcodpy as libtcod

#size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 45

#size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 40

#parameters for dungeon generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

LIMIT_FPS = 30


color_dark_wall = libtcod.Color(0, 0, 100)
color_dark_ground = libtcod.Color(50, 50, 150)


class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked

        #by default, if a tile is blocked, it also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight

class Rect:
    #a rectangle on the map, used to characterize a room
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        #returns True is this rectangle intersects with another
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
    #this is a generic object: the player, a monster, item, stair, etc.
    #always represented by a character on the screen
    def __init__(self, x, y, char, color):
        self.x = x
        self.y = y
        self.char = char
        self.color = color

    def move(self, dx, dy):
        #move by the given amount, if destination is not blocked
        if not map[self.x + dx][self.y + dy].blocked:
            self.x += dx
            self.y += dy

    def draw(self):
        #set the color and then draw the character that represents this object at its position
        libtcod.console_set_default_foreground(con, self.color)
        libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        #erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

rooms = []
num_rooms = 0

def make_map():
    global map
    global rooms
    global num_rooms

    #fill map with blocked tiles
    map = [[Tile(True)
            for y in range(MAP_HEIGHT) ]
               for x in range(MAP_WIDTH) ]

    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position without going outside of map boundaries
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        new_room = Rect(x, y, w, h)

        #run throught previous rooms to check for intersection
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            create_room(new_room)

            new_x = libtcod.random_get_int(0, new_room.x1 + 2, new_room.x2 - 1)
            new_y = libtcod.random_get_int(0, new_room.y1 + 1, new_room.y2 - 1)

            if num_rooms == 0: #first room
                (player.x, player.y) = new_room.center()

            else: #all subsequent rooms
                prev_room = rooms[num_rooms - 1]
                prev_x = libtcod.random_get_int(0, prev_room.x1 + 2, prev_room.x2 - 1)
                prev_y = libtcod.random_get_int(0, prev_room.y1 + 2, prev_room.y2 - 1)

                if libtcod.random_get_int(0, 0, 1) == 1:
                    #horizontal, then vertical
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #vertical, then horizontal
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            #append new room to the list
            rooms.append(new_room)
            num_rooms += 1

    final_room = rooms[len(rooms) - 1]
    (final_room_center_x, final_room_center_y) = final_room.center()
    profit = Object(final_room_center_x, final_room_center_y, '$', libtcod.green)
    profit.draw()

def render_all():
    global color_dark_wall
    global color_dark_ground

    #go through all tiles and set their background color
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            wall = map[x][y].block_sight
            if wall:
                libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
            else:
                libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)

    #draw all objects in the list
    for object in objects:
        object.draw()

    #blit the contents of "con" to the root console
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

def handle_keys():
    key = libtcod.console_check_for_keypress()

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return True #exit game


    #movement keys
    if libtcod.console_is_key_pressed(libtcod.KEY_UP):
        player.move(0, -1)

    elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
        player.move(0, 1)

    elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
        player.move(-1, 0)

    elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
        player.move(1, 0)

################################
#      INITIALIZATION AND MAIN LOOP      #
################################


libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, "Rogue-Like, the roguelike game", False)
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
libtcod.sys_set_fps(LIMIT_FPS)

#create object representing the player
player = Object(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, '@', libtcod.white)

#create an NPC
npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, '@', libtcod.yellow)

#list of objects
objects = [npc, player]

#generate map
make_map()

while not libtcod.console_is_window_closed():

    #render the screen
    render_all()

    libtcod.console_flush()

    if (player.x, player.y) == rooms[len(rooms) - 1].center():
        treasure = Object(SCREEN_WIDTH / 2, SCREEN_HEIGHT - 3, '$', libtcod.green)
        treasure.draw()
    
    #erase all objects at their old locations before they move
    for object in objects:
        object.clear()

    #handle keys and exit game if needed
    exit = handle_keys()
    if exit:
        break
