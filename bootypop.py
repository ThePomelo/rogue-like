import libtcodpy as libtcod
import math
import textwrap
import shelve

#############
# CONSTANTS #
#############

#size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 45

#size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 38

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 10
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 10
MSG_HEIGHT = PANEL_HEIGHT - 2
INVENTORY_WIDTH = 35
CHARACTER_SCREEN_WIDTH = 30
LEVEL_SCREEN_WIDTH = 40

#parameters for dungeon generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

#spell values
HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 100
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#experience and level-ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

FOV_ALGO = 0 #default FOV algorithm
FOV_LIGHT_WALLS = True #light walls or not
TORCH_RADIUS = 10

#number of frames to wait after moving/attacking
PLAYER_SPEED = 3
DEFAULT_SPEED = 12
DEFAULT_ATTACK_SPEED = 30

#available hotkeys
HOTKEY_OPTIONS = [libtcod.KEY_1, libtcod.KEY_2, libtcod.KEY_3, libtcod.KEY_4]

LIMIT_FPS = 60


#########
# TILES #
#########

mage_tile = 256+32+0 #2nd row, 1st sprite
dead_mage_tile = 256+32+1
skeleton_tile = 256+32+2
dead_skeleton_tile = 256+32+3
orc_tile = 256+32+4
dead_orc_tile = 256+32+5
troll_tile = 256+32+6
dead_troll_tile = 256+32+7

green_potion_tile = 256+2
red_potion_tile = 256+3
blue_potion_tile = 256+4

sword_tile = 256+5
dagger_tile = 256+6
scroll_tile = 256+7
staff_tile = 256+9
wand_tile = 256+10
wood_shield_tile = 256+11
metal_shield_tile = 256+12
bow_tile = 256+13
arrow_tile = 256+14
holy_hand_grenade_tile = 256+17

ice_tile = 256+15
fire_tile = 256+16

wall_tile = 256
ground_tile = 256+1
ladder_tile = 256+8

color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(75, 75, 75)
color_light_ground = libtcod.Color(150, 150, 150)


###########
# CLASSES #
###########

class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked

        #all tiles start unexplored
        self.explored = False

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
    def __init__(self, x, y, char, name, color, blocks = False, always_visible = False,
        fighter = None, ai = None, item = None, equipment = None, speed = DEFAULT_SPEED, label = None):

        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible
        self.fighter = fighter
        self.ai = ai
        self.speed = speed
        self.wait = 0
        self.item = item
        self.equipment = equipment
        self.label = label

        if self.fighter: #let the fighter component know who owns it
            self.fighter.owner = self

        if self.ai: #let AI component know who owns it
            self.ai.owner = self

        if self.item: #let the item component know who owns it
            self.item.owner = self
            self.label = name

        if self.equipment: #let the equipment component know who owns it
            self.equipment.owner = self

            #there must be an Item component if the Equipment component is to work properly
            self.item = Item()
            self.item.owner = self

    def move(self, dx, dy):
        #move by the given amount, if destination is not blocked
        if not is_blocked(self.x +dx, self.y + dy):
            self.x += dx
            self.y += dy
            self.wait = self.speed

    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        #normalize it to length 1 (preserving direction), then round it and convert to interger
        #so that movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        #return distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        #return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def send_to_back(self):
        #make this object be drawn first, so all others appear above it if in the same tile
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        #only show if it's visible to the player
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)) :
            #set the color and then draw the character that represents this object at its position
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        #erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

class Fighter:
    #combat-related properties and methods (monster, player, npc)
    def __init__(self, hp, defense, power, xp, death_function = None, attack_speed = DEFAULT_ATTACK_SPEED, god_mode = False):
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        self.death_function = death_function
        self.attack_speed = attack_speed
        self.god_mode = god_mode

    @property
    def power(self): #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus

    @property
    def defense(self):  #return actual defense, by summing up the bonuses from all equipped items
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus
 
    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    def attack(self, target):
        #a simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            #make the target take some damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ', but it has no effect!')

        self.owner.wait = self.attack_speed

    def take_damage(self, damage):
        #apply damage if possible
        if damage > 0 and not self.god_mode:
            self.hp -= damage

            #check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

                if self.owner != player and not player.fighter.god_mode: #yield experience to the player
                    player.fighter.xp +=self.xp

    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def toggle_god_mode(self):
        if self.god_mode:
            self.god_mode = False
        else:
            self.god_mode = True

        if self.god_mode:
            self.base_power += 100
        else:
            self.base_power -= 100

class BasicMonster:
    #AI for a basic monster
    def take_turn(self):
        #a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y) and not player.fighter.god_mode:

            #move towards player is far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)

            #if close enough, attack! (if the player is still alive)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class ConfusedMonster:
    #AI for a temporarily confused monster (reverts to previos AI after a while)
    def __init__(self, old_ai, num_turns = CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns
    
    def take_turn(self):
        if self.num_turns > 0: #still confused
            #move in random direction and decrease the number of turns confused
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1

        else: #restore the previous AI (this one will be deleted because it's not referenced anymore)
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused', libtcod.red)

class Item:
    #an item that can be picked up and used
    def __init__(self, use_function = None):
        self.use_function = use_function

    def pick_up(self):
        #add to a player's inventory and remove from the map
        
        item_quantity = 1
        for obj in inventory:
            if obj.name == self.owner.name:
                item_quantity += 1
        
        if len(inventory) >= 26:
            message('Your inventory is full.  You cannot pick up a ' + self.owner.name + '!', libtcod.green)
        elif self.owner.equipment and item_quantity > 9:
            message('You can\'t hold any more ' + self.owner.name + 's.', libtcod.green)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)

            
            if not self.owner.equipment:
                if not self.owner.label in inventory_dict.keys():
                    inventory_dict[self.owner.label] = 1
                else:
                    inventory_dict[self.owner.label] +=1
            else:
                i = 1
                self.owner.label = self.owner.name + ' ' + str(i)
                while self.owner.label in inventory_dict.keys():
                    i += 1
                    self.owner.label = self.owner.name + ' ' + str(i)
                inventory_dict[self.owner.label] = 'unequipped'

            #special case: automatically equip, if the corresponding equipment slot is unused
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()

    def drop(self):
        #special case: if object has equipment component, dequip before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip()

        #add to the map and remove from the player's inventory. also place at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        if self.owner.equipment or (not self.owner.equipment and inventory_dict[self.owner.label] == 1):
            del inventory_dict[self.owner.label]
        else:
            inventory_dict[self.owner.label] -= 1
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

    def use(self):
        #special case: if object has an Equipment component, the "use" is equip/dequip
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return

        #call the use_function if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) #destroy after use, unless it was cancelled for some reason
                if inventory_dict[self.owner.label] > 1:
                    inventory_dict[self.owner.label] -= 1
                elif inventory_dict[self.owner.label] == 1:
                    del inventory_dict[self.owner.label]
                
class Equipment:
    #an object that can be equipped, yielding bonuses, automatically adds the Item component
    def __init__(self, slot, power_bonus = 0, defense_bonus = 0, max_hp_bonus = 0):
        self.slot = slot
        self.is_equipped = False
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus            

    def toggle_equip(self): #toggle equip/dequip status
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()

    def equip(self):
        #if the slot is already being used, dequip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()

        #equip an object and show a message
        self.is_equipped = True
        inventory_dict[self.owner.label] = self.slot
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

    def dequip(self):
        #dequip object and show a message
        if not self.is_equipped: return
        self.is_equipped = False
        inventory_dict[self.owner.label] = 'unequipped'
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)

class Hotkey:
    def __init__(self, button, object):
        self.button = button
        self.object = object
        self.char = self.object.char
        self.name = self.object.label
        if self.object.equipment:
            self.type = 'equipment'
        else:
            self.type = 'stackable'
        for i in range(len(HOTKEY_OPTIONS)):
            num = i + 1
            if HOTKEY_OPTIONS[i] == self.button:
                self.prompt = '[' + str(num) + '] ' + self.name.capitalize() + '\n'
            
    def compute_state(self):
        if self.type == 'stackable':
            self.state = 0
            for obj in inventory:
                if obj.label == self.name:
                    self.state += 1
        elif self.type == 'equipment':
            for obj in inventory:
                if obj.label == self.name:
                    self.state = obj.equipment.is_equipped
                    
    def configure(self):
        if self.button in HOTKEY_OPTIONS:
            hotkeys.append(self)
            self.compute_state()
    
    def use(self):
        self.compute_state()
        if self.state != 0 or self.type == 'equipment':
            i = 0
            hot_object = False
            while not hot_object:
                if inventory[i].label == self.name:
                    hot_object = inventory[i]
                i += 1
        
            hot_object.item.use()
            
        elif self.state == 0 and self.type == 'stackable':
            message('You no longer have this item.')

    def render_gui(self, x, y, key_display):
        libtcod.console_print_ex(panel, x, y, libtcod.BKGND_NONE, libtcod.LEFT, '[' + key_display + ']')
        libtcod.console_put_char_ex(panel, x + 4, y, self.char, libtcod.white, libtcod.BKGND_NONE)
        self.compute_state()
        if self.type == 'stackable':
            libtcod.console_print_ex(panel, x + 6, y, libtcod.BKGND_NONE, libtcod.LEFT, str(self.state))
        elif self.type == 'equipment' and self.state:
            libtcod.console_print_ex(panel, x + 6, y, libtcod.BKGND_NONE, libtcod.LEFT, 'E')
            
        
    

#############
# FUNCTIONS #
#############

def get_equipped_in_slot(slot): #returns the equipment in a slot, or None if empty
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(obj): #returns a list of equipped items
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return [] #other objects have no equipment

def is_blocked(x, y):
    #first test the map tile
    if map[x][y].blocked:
        return True
    
    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False

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

def make_map():
    global map, objects, stairs

    #list of objects
    objects = [player]

    #fill map with blocked tiles
    map = [[Tile(True)
            for y in range(MAP_HEIGHT) ]
               for x in range(MAP_WIDTH) ]

    rooms = []
    num_rooms = 0

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
            place_objects(new_room)

            (new_x, new_y) = new_room.center()

            if num_rooms == 0: #first room
                player.x = new_x
                player.y = new_y

            else: #all subsequent rooms
                #center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms - 1].center()

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

    #create stairs at the center of the last room
    stairs = Object(new_x, new_y, ladder_tile, 'ladder', libtcod.white, always_visible = True)
    objects.append(stairs)
    stairs.send_to_back() #so it's drawn below monsters

def random_choice_index(chances): #choose one options from a list of chances and return its index
    dice = libtcod.random_get_int(0, 1, sum(chances))

    #go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        #see if die has landed in the distribution for this choice
        if dice <= running_sum:
            return choice
        choice += 1

def random_choice(chances_dict):
    #choose one option from a dictionary of chances, returning its key
    strings = chances_dict.keys()
    chances = chances_dict.values()

    return strings[random_choice_index(chances)]

def from_dungeon_level(table):
    #returns value that corresponds to a level
    #table specifies what value occurs at what level, default is zero
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0

def place_objects(room):

    #maximum number of monsters per room
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])

    #monster probability distribution
    monster_chances = {}
    monster_chances['orc'] = 80
    monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])

    #choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)

    for i in range(num_monsters):
        #choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'orc':
                #create and orc
                fighter_component = Fighter(hp = 20, defense = 0, power = 4, xp = 35, death_function = monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, orc_tile, 'orc', libtcod.white,
                    blocks = True, fighter = fighter_component, ai = ai_component)
            elif choice == 'troll':
                #create a troll
                fighter_component = Fighter(hp = 30, defense = 2, power = 8, xp = 100, death_function = monster_death)
                ai_component = BasicMonster()
                
                monster = Object(x, y, troll_tile, 'troll', libtcod.white,
                    blocks = True, fighter = fighter_component, ai = ai_component)

            objects.append(monster)

    #maximum number of items per room
    max_items = from_dungeon_level([[1, 1], [2, 4]])

    #item probabilty distribution
    item_chances = {}
    item_chances['heal'] = 35
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] = from_dungeon_level([[25, 6]])
    item_chances['confuse'] = from_dungeon_level([[10, 2]])
    item_chances['sword'] = from_dungeon_level([[5, 4]])
    item_chances['shield'] = from_dungeon_level([[15, 8]])

    #choose random number of items
    num_items = libtcod.random_get_int(0, 0, max_items)

    for i in range(num_items):
        #choose random spot for this item
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        #only place if the tile is not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create a healing potion
                item_component = Item(use_function = cast_heal)
                item = Object(x, y, red_potion_tile, 'healing potion', libtcod.white, item = item_component)

            elif choice == 'lightning':
                #create a lightning bolt scroll
                item_component = Item(use_function = cast_lightning)
                item = Object(x, y, scroll_tile, 'scroll of lightning bolt', libtcod.light_yellow, item = item_component)

            elif choice == 'fireball':
                #creat a fireball scroll
                item_component = Item(use_function = cast_fireball)
                item = Object(x, y, scroll_tile, 'scroll of fireball', libtcod.light_orange, item = item_component)
            
            elif choice == 'confuse':
                #create a confuse scroll
                item_component = Item(use_function = cast_confuse)
                item = Object(x, y, scroll_tile, 'scroll of confusion', libtcod.light_blue, item = item_component)

            elif choice == 'sword':
                #create a sword
                equipment_component = Equipment(slot = 'right hand', power_bonus = 3)
                item = Object(x, y, sword_tile, 'sword', libtcod.white, equipment = equipment_component)

            elif choice == 'shield':
                #create a shield
                equipment_component = Equipment(slot = 'left hand', defense_bonus = 1)
                item = Object(x, y, wood_shield_tile, 'sheild', libtcod.white, equipment = equipment_component)
          
            objects.append(item)
            item.send_to_back() #items appear below other objects
            item.always_visible = True #items are visible even out of FOV, if in an explored area

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color, display = 'default_display'):
    #render a bar (HP, XP, etc.). first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)

    #render the background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

    #now render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

    #finally some centered text with the values
    libtcod.console_set_default_foreground(panel, libtcod.white)
    if display == 'default_display':
        libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
            name + ': ' +str(value) + ' / ' + str(maximum))
    else:
        libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
            display)
                             
def get_names_under_mouse():
    global mouse

    #return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)

    #create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.name for obj in objects
             if obj.x == x and obj.y ==y and (libtcod.map_is_in_fov(fov_map, obj.x, obj.y) or (obj.always_visible and map[obj.x][obj.y].explored))]

    names = ', '.join(names) #join names, separated by commas
    return names.capitalize()

def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute
    global game_msgs
    global hotkeys 
    global hot_chars
    global hot_types

    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        #go through all tiles and set their background color according to FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    #if it's not visible right now, the player can only see it if it's explored
                    if map[x][y].explored:
                        if wall:
                            libtcod.console_put_char_ex(con, x, y, wall_tile, libtcod.grey, color_dark_wall)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    #it's visible
                    if wall:
                        libtcod.console_put_char_ex(con, x, y, wall_tile, libtcod.white, color_light_wall)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                    #since it's visible, explore it
                    map[x][y].explored = True
                            
    #draw all objects in the list, except the player
    for object in objects:
        if object != player:
            object.draw()
    player.draw()

    #blit the contents of "con" to the root console
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

    #prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    #show hotkey bindings
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, BAR_WIDTH + 2, 2,libtcod.BKGND_NONE, libtcod.LEFT, 'HOTKEYS')
    
    i = 0
    for k in HOTKEY_OPTIONS:
        for hot in hotkeys:
            if k == hot.button:
                hot.render_gui(BAR_WIDTH + 2, i + 3, str(i + 1))
        i += 1
            
    #print the game messages, one line at a time
    y = 2
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1

    #show the player's stats
    if player.fighter.god_mode:
        render_bar(1, 2, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
            libtcod.dark_red, libtcod.black, 'GOD MODE ACTIVATED')
    else: 
        render_bar(1, 2, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
            libtcod.dark_red, libtcod.black)

    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.god_mode is False:
        render_bar(1, 0, 78, 'XP', player.fighter.xp, level_up_xp, libtcod.green, libtcod.dark_gray, 'LEVEL ' + str(player.level))

    libtcod.console_print_ex(panel, 1, 5, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon Level ' + str(dungeon_level))

    #display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 4, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    #blit contents of panel to root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def message(new_msg, color = libtcod.white):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for a new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        #add the new line as a tuple with the text and the color
        game_msgs.append( (line, color) )

def player_move_or_attack(dx, dy):
    global fov_recompute

    #coordinates the player is trying to move to or attack
    x = player.x + dx
    y = player.y + dy

    #try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x ==x and object.y ==y:
            target = object
            break

    #attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)

    else:
        player.move(dx, dy)
        fov_recompute = True

def menu(header, options, width):
    global key, window
    
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

    #calculate total height for header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height

    #calculate an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)

    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '[' + chr(letter_index) + '] ' + option_text.capitalize()
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    #blit the contents of window to root console
    x = SCREEN_WIDTH / 2 - width / 2
    y = SCREEN_HEIGHT / 2 - height / 2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    libtcod.console_flush()

    while True:
        #check for input in each iteration
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)

        index = key.c - ord('a')
        if key.vk == libtcod.KEY_NONE: continue #if nothing is pressed keep looping

        elif key.vk == libtcod.KEY_ENTER and key.lalt:
            #Alt+Enter: toggle fullscreen
            libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

        elif index >= 0 and index < len(options): return index #if an option is chosen return it's index in the options list

        elif index < 0 or index >= len(options): return None #if any other key is pressed close the menu
        
def OLD_inventory_menu(header): #OBSOLETE, here for nostalgia
    #show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for item in inventory:
            text = item.name
            #show additional info, in case it's equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)

    index = menu(header, options, INVENTORY_WIDTH)

    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def inventory_menu(header):
    #show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for k in inventory_dict.keys():
            text = k
            if isinstance(inventory_dict[k], int) and inventory_dict[k] > 1:
                text = k + ' (' + str(inventory_dict[k]) + ')'
            if isinstance(inventory_dict[k], str) and inventory_dict[k] != 'unequipped':
                i = 0
                while inventory[i].label != k:
                    i += 1
                item = inventory[i]
                text = text + ' (on ' + item.equipment.slot + ')'
                
            options.append(text)

    options = sorted(options)

    index = menu(header, options, INVENTORY_WIDTH)
    
    if index is None or len(inventory) == 0: return None
        
    i = 0
    item_type = options[index]
    chosen_item = inventory[i]
    while inventory[i].label != item_type[:len(inventory[i].label)].lower():
        i += 1
        chosen_item = inventory[i]
    
    return chosen_item.item

def msgbox(text, width = 50):
    menu(text, [], width) #use menu() as a sort of message box
    
def handle_keys():
    global key
    global hotkeys

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #alt+enter toggles fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit' #exit game

    elif key.vk == libtcod.KEY_TAB:
        player.fighter.toggle_god_mode()

    if game_state == 'playing':

        if player.wait > 0: #don't take a turn yet if still waiting
            player.wait -= 1
            return
        
        #movement keys with num pad support
        elif key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP5:
            pass  #do nothing ie wait for the monster to come to you
            
        else:
            key_char = chr(key.c)
            
            #check for hotkey press (press 5 for manual configuration)
            if key.vk in HOTKEY_OPTIONS or key.vk == libtcod.KEY_5:
                if key.vk == libtcod.KEY_5 or len(hotkeys) == 0 or (key.vk not in [h.button for h in hotkeys]):
                    hotkeys = []
                    render_all()
                    i = 1
                    for k in HOTKEY_OPTIONS:
                        item_component = inventory_menu('Configure Hotkeys\nChoose an item for slot ' + str(i) + '.')
                        if item_component is not None:
                            new_hotkey = Hotkey(k, item_component.owner)
                            new_hotkey.configure()
                        libtcod.console_clear(window)
                        render_all()
                        i += 1
                
                elif key.vk in [h.button for h in hotkeys]:
                    for hot in hotkeys:
                        if hot.button == key.vk:
                            hot.use()
            
            #test for other keys
            elif key_char == 'g':
                #pick up an item
                for object in objects: #look for an item in the player's tile
                    if object.x == player.x and object.y ==player.y and object.item:
                        object.item.pick_up()
                        break

            elif key_char == 'i':        
                #show the inventory. if an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()

            elif key_char == 'd':
                #show inventory; if an item is selected drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            elif key_char == 's':
                #go down stairs, if the player is on them
                if (stairs.x == player.x and stairs.y == player.y) or player.fighter.god_mode:
                    next_level()

            elif key_char == 'c':
                #show character stats
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Stats\n\nLevel: ' + str(player.level) + '\nXP: ' + str(player.fighter.xp) +
                    '\nXP to level up: ' + str(level_up_xp) + '\n\nMax HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense),
                    CHARACTER_SCREEN_WIDTH)

            elif key_char == 'h':
                strings = ''
                for element in [h.prompt for h in hotkeys]:
                    strings = strings + element                
                msgbox('Hotkeys\n\n' + strings, 30)
            
            return 'didnt-take-turn'

def check_level_up():
    #see if the player's experience is enough to level-up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #level up and raise some stats
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)

        choice = None
        while choice == None: #keep asking until a choice is made
            choice = menu('\nLEVEL UP! Choose a stat to raise:\n',
                ['Constitution (+20 HP, currently ' + str(player.fighter.max_hp) + ')',
                'Strength (+1 Attack, currently ' + str(player.fighter.power) + ')',
                'Agility (+1 Defense, currrently ' + str(player.fighter.defense) + ')\n'], LEVEL_SCREEN_WIDTH)

        if choice == 0:
            player.fighter.base_max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1

def player_death(player):
    #the game ended!
    global game_state
    message('You died!', libtcod.red)
    game_state = 'dead'

    #for added effect, transform the player into the corpse!
    player.char = dead_mage_tile
    player.color = libtcod.dark_red

def monster_death(monster):
    #transform it into a nasty corpse! it doesn't block, can't be attacked, and doesn't move
    if player.fighter.god_mode:
        message(monster.name.capitalize() + ' is dead!', libtcod.orange)
    else:
        message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' XP.', libtcod.orange)

    if monster.name == 'orc':
        monster.char = dead_orc_tile
    elif monster.name == 'troll':
        monster.char = dead_troll_tile

    monster.color = libtcod.white
    monster.blocks = False
    monster.fighter = False
    monster.ai = None
    monster.name = 'remains of ' + monster.name

    monster.send_to_back()

def target_tile(max_range = None):
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None, None) if right-clicked
    global key, mouse
    while True:
        #render the screen. this erases the inventory and shows the names of objects under the mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        (x, y) = (mouse.cx, mouse.cy)

        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range)):
            return (x, y)

        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None) #cancel if the player right-clicks or presses ESCAPE

def target_monster(max_range = None):
    #returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None: #player cancelled
            return None

        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y ==y and obj.fighter and obj != player:
                return obj

def closest_monster(max_range):
    #find closest enemy, up to a maximum range and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist: #it's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.light_violet)
        return 'cancelled'

    message('Your wounds start to heal!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    #find closest enemy in range and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None: #no enemy found in range
        message('No enemy is within range of your lightning.', libtcod.red)
        return 'cancelled'

    #zap
    message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder for '
        + str(LIGHTNING_DAMAGE) + ' hit points!', libtcod.light_yellow)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_fireball():
    #ask the player for a target tile to throw a fireball at
    message('Left-click a target for the fireball, or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

    for obj in objects: #damage every fighter in range, including the player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

def cast_confuse():
    #ask the player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'

    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster #tell the new component who owns it
    message('The eyes of the ' +monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_blue)

def save_game():
    #open a new empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player) #index of player in objects list
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()

def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level

    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level, inventory_dict, hotkeys, hot_chars, hot_types

    #create object representing the player
    fighter_component = Fighter(hp = 100, defense = 1, power = 2, xp = 0, death_function = player_death)
    player = Object(0, 0, mage_tile, 'player', libtcod.white, blocks = True, fighter = fighter_component, speed = PLAYER_SPEED)

    player.level = 1
    
    #generate map (at this point, not drawn to the screen)
    dungeon_level = 1
    make_map()
    initialize_fov()

    game_state = 'playing'

    inventory = []
    inventory_dict = {}
    
    hotkeys = []
    
    #create the list of game messages and their colors, starts empty
    game_msgs = []

    message('Welcome, stranger! Try your best not to perish.', libtcod.red)

    #intial equipment: a dagger!
    equipment_component = Equipment(slot = 'right hand', power_bonus = 2)
    obj = Object(0, 0, dagger_tile, 'dagger', libtcod.white, equipment = equipment_component)
    objects.append(obj)
    obj.item.pick_up()
    obj.always_visible = True

def next_level():
    global dungeon_level

    #advance to the next level
    if not player.fighter.god_mode:
        message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
        player.fighter.heal(player.fighter.max_hp / 2) #heal the player by 50%

    dungeon_level += 1
    message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
    make_map() #create a fresh new level!
    initialize_fov()

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
    
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    libtcod.console_clear(con) #unexplored areas start black (default background color)
    
def play_game():
    global key, mouse

    player_action = None

    while not libtcod.console_is_window_closed():
        #render the screen
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        libtcod.console_flush()

        #level up if needed
        check_level_up()
    
        #erase all objects at their old locations before they move
        for object in objects:
            object.clear()

        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        #let monsters take their turn
        if game_state == 'playing':
            for object in objects:
                if object.ai:
                    if object.wait > 0: #don't take a turn if still waiting
                        object.wait -= 1
                    else:
                        object.ai.take_turn()

def main_menu():
    img = libtcod.image_load('nic.png')

    while not libtcod.console_is_window_closed():
        #show the background image, at twice the regular console resolution
        libtcod.image_blit_2x(img, 0, 0, 0)

        #show the game's title, and some credits
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 4, libtcod.BKGND_NONE, libtcod.CENTER,
            'ROGUE-LIKE')
        libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 2, libtcod.BKGND_NONE, libtcod.CENTER,
            'A Roguelike Game')

        #show options and wait for player's choice
        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

        if choice == 0: #new game
            new_game()
            play_game()
        elif choice == 1: #load last save
            try:
                load_game()
            except:
                msgbox('\n No saved game to load. \n', 24)
                continue
            play_game()
        elif choice == 2: #quit
            break
        
    
##########################################
#      INITIALIZATION AND MAIN LOOP      #
##########################################

libtcod.console_set_custom_font('tiles.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD, 32, 12)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, "Rogue-Like, the roguelike game", False, libtcod.RENDERER_SDL)
libtcod.sys_set_fps(LIMIT_FPS)
libtcod.console_map_ascii_codes_to_font(256, 32, 0, 5)
libtcod.console_map_ascii_codes_to_font(256+32, 32, 0, 6)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

mouse = libtcod.Mouse()
key = libtcod.Key()

main_menu()
