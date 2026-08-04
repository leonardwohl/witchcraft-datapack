# --- Player Inventory: Clear unstackable water bottles and give back stackable ones ---
execute as @a store result score @s wc.bottles run clear @s minecraft:potion[max_stack_size=1,potion_contents="minecraft:water"]
execute as @a if score @s wc.bottles matches 1.. run function witchcraft:fix_water_bottles

# --- Dropped Items: Patch unstackable water bottle entities in-place ---
execute as @e[type=item] if items entity @s contents minecraft:potion[potion_contents="minecraft:water",!max_stack_size=64] run data modify entity @s Item.components."minecraft:max_stack_size" set value 64
