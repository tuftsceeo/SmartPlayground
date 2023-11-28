import asyncio
import pygame
import socket

# Pygame initialization
pygame.init()

screen_width, screen_height = pygame.display.Info().current_w, pygame.display.Info().current_h

# Define colors
BACKGROUND = (0, 109, 119)
GRAY = (237, 246, 249)
GREEN = (131, 197, 190)
EXIT = (226, 149, 120)
BLACK = (0, 0, 0) 

bar_spacing = 1.1

# Exit button dimensions and position
button_width = 50
button_height = 50
button_position = (screen_width - button_width - 10, 10)  # Top right corner

font = pygame.font.Font(None, 12)
font_large = pygame.font.Font(None, 24)

# Function to draw the exit button
def draw_exit_button(screen):
    exit_button = pygame.Rect(button_position[0], button_position[1], button_width, button_height)
    pygame.draw.rect(screen, EXIT, exit_button)    
    text = font.render('EXIT', True, BLACK)
    text_rect = text.get_rect(center=exit_button.center)
    screen.blit(text, text_rect)

# Function to draw the bar chart
def draw_bar(screen, motion_data):
    screen.fill(BACKGROUND)  # Clear the screen
    bar_width = screen_width // (bar_spacing*10)
    bar_height = screen_height // 2
    gap = screen_width // (10) - screen_width // (bar_spacing*10) 
    
    for i, state in enumerate(motion_data):
        color = GREEN if state == 1 else GRAY
        bar_x = int(i * bar_width * bar_spacing)
        pygame.draw.rect(screen, color, (bar_x, bar_height, bar_width, bar_height))

    draw_exit_button(screen)  # Draw the exit button
    text = font_large.render('Motion Segments', True, GRAY)
    text_rect = text.get_rect()
    screen.blit(text, text_rect)
    pygame.display.flip()  # Update the display
    
    
# Function to create the Pygame window and handle drawing
def setup_pygame():
    # Set up the display
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN) # FULLSCREEN
    #screen = pygame.display.set_mode((screen_width, screen_height-20)) #TESTING
    return screen

# Async function to handle the client's network communication
async def handle_client(host, port, screen):
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write('start'.encode())
        await writer.drain()
        while True:
            data = await reader.read(100)
            if not data:
                break

            # Convert bytes to string 
            motionstring = data.decode()
            motion_data = [int(x) for x in motionstring]

            # Draw the motion level bar chart
            draw_bar(screen, motion_data)

            # Pygame event handling
            for event in pygame.event.get():  # Check for events
                if event.type == pygame.QUIT:
                    raise SystemExit('Quit signal received. Exiting.')
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    raise SystemExit('Quit signal received. Exiting.')
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = event.pos
                    if button_position[0] <= mouse_pos[0] <= button_position[0] + button_width and button_position[1] <= mouse_pos[1] <= button_position[1] + button_height:
                        raise SystemExit('Quit signal received. Exiting.')

            
            # for event in pygame.event.get():
            #     if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            #         raise SystemExit('Quit signal received. Exiting.')

    except SystemExit as e:
        print(e)
        # Send exit command to the server
        writer.write('exit'.encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        pygame.quit()

# Main function to start the asyncio event loop
async def main(host, port):
    screen = setup_pygame()
    await handle_client(host, port, screen)

# Replace 'SERVER_IP_ADDRESS' with the actual IP address of the server Raspberry Pi
#server_ip = '10.243.67.147' # Example: '192.168.1.2'
server_ip = '10.0.0.56'
port = 5560

# Run the main function until it is complete
asyncio.run(main(server_ip, port))
