/**
 * iconCategories.js -- hand-kept grouping of the device icons for the
 * sample library overlay. Not generated: sync_icons.py does not touch it.
 * An icon missing from every list still shows, under "Other", so a new
 * icon is never hidden -- add it to a category when convenient.
 */

export const ICON_CATEGORIES = [
    ['Animals', 'bat bee bird bunny butterfly camel cat cat2 caterpillar chicken deer dino dog dog2 dolphin dove dragon duck elephant elephant2 fish frog goat griffin hedgehog humpback lion monarch monkey mouse octopus owl parrot penguin pig polar_bear sheep shark shrimp snake spider swan torogoz trex turtle whale whitebunny worm'],
    ['Food', 'agua_fresca apple baguette banana beans bell_pepper toast broccoli burger candy candy_corn carrot cauliflower cheese cherries chicken_leg chili_pepper churro concha cookie cupcake donut egg elote flour_bag fried_egg garlic grapes hot_chocolate hot_dog icecream kiwi lemon milk mug orange paleta pan_de_muerto pancakes parsnip pie pineapple pizza potato pumpkin pumpkin_pie pupusa radish red_cabbage rice_bowl sandwich soup spaghetti steak strawberry sugar_cubes taco tomato tortillas watermelon'],
    ['People', 'astronaut doctor fairy firefighter fireperson mail_carrier person_arms_out person_armsup person_jumping police running_person spinning_person person_handstand person_kickingball person_sitting hand eyes eye eyes_up lips tongue listen_ear tooth'],
    ['Faces & feelings', 'happy laugh silly surprised sleepy sad mad embarrassed worried_fear heart_eyes ghost monster skull robot'],
    ['Talking', 'speech_bubble speech_bubble_hi speech_bubble_question speech_bubble_question_spanish speech_bubble_exclaim speech_bubble_exclaim_spanish speech_bubbles_conversation'],
    ['Nature & weather', 'sun moon star star_white sparkles cloud rain_cloud storm_cloud lightning rainbow snowflake snowflake2 wind water_drop flame tree leaf grass seed sprout flower flowerpot sunflower marigold mushroom cactus'],
    ['Places', 'house school hospital barn castle igloo cave forest jungle desert fields ocean pond sky sandbox sandcastle slide swings seesaw monkey_bars'],
    ['Vehicles', 'car bus train airplane helicopter rocket ship bicycle tricycle ambulance fire_truck dump_truck cement_mixer shopping_cart'],
    ['Things & toys', 'ball balloon blocks bubbles kite jump_rope teddy_bear book book_closed books pencil materials1 drum guitar maracas trumpet music gem treasure_chest coin trophy medal key padlock mail light_bulb hourglass umbrella fishing_rod cauldron witch_hat'],
    ['Celebrations', 'jack_o_lantern pumpkin2 calavera ofrenda_candle papel_picado pinata xmas_tree'],
    ['Flags', 'usa_flag mex_flag canada_flag brazil_flag guatemala_flag elsalvador_flag cambodia_flag vietnam_flag green_flag white_flag checker_flag'],
    ['Symbols & shapes', 'heart love_heart_pink check ready_green_check x cross question pause_button circle square square_purple triangle target_pink arrow_left_blue arrow_right_orange arrow_down_green red_up_arrow refresh_arrow refresh_arrow_cw refresh_arrow_ccw'],
    ['Game signals', 'splat splat_red splat_yellow splat_green splat_cyan splat_purple splat_magenta splat_white splat_rainbow splat_off wand_lights_on wand_lights_off wand_lighton_sound'],
].map(([title, names]) => ({ title, names: names.split(' ') }));

/** [{title, names}] for the given icon names, in category order, plus "Other". */
export function groupIcons(names) {
    const have = new Set(names);
    const placed = new Set();
    const groups = [];
    for (const { title, names: list } of ICON_CATEGORIES) {
        const hit = list.filter((n) => have.has(n) && !placed.has(n));
        hit.forEach((n) => placed.add(n));
        if (hit.length) groups.push({ title, names: hit });
    }
    const rest = names.filter((n) => !placed.has(n)).sort();
    if (rest.length) groups.push({ title: 'Other', names: rest });
    return groups;
}
