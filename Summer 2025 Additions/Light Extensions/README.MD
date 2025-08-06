### The LED Matrix is a continuation from 2024 summer, converted to an ESP32 from a pico and now focused on output (removed button function). 

[On Notion](https://fetlab.notion.site/Light-Extensions-242df3d0e052805f8ac2eac283baedd6)

The LED Matrix is a 16x16 and communicates with the splat via the Splat companion. 

The LED Strip future improvements: currently gets "stuck" in patterns (does not receive messages during patterns) and needs interrupts. (It might buffer messages received...). 