import asyncio
import pygame
import socket

# Initialize Pygame
pygame.init()

# Set up the display
screen_width, screen_height = pygame.display.Info().current_w, pygame.display.Info().current_h
screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)

# Define colors
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# Exit button dimensions and position
button_width = 100
button_height = 50
button_position = (screen_width - button_width - 10, 10)  # Top right corner

# Function to draw the exit button
def draw_exit_button():
    exit_button = pygame.Rect(button_position[0], button_position[1], button_width, button_height)
    pygame.draw.rect(screen, RED, exit_button)
    font = pygame.font.Font(None, 36)
    text = font.render('Exit', True, BLACK)
    text_rect = text.get_rect(center=exit_button.center)
    screen.blit(text, text_rect)

# Function to draw the bar chart
def draw_bar(screen, number):
    screen.fill(BLACK)  # Clear the screen
    bar_width = screen_width // 20
    for i in range(10):
        if i < number:
            pygame.draw.rect(screen, GREEN, (i * (bar_width * 2), screen_height // 2, bar_width, screen_height // 2))
    draw_exit_button()  # Draw the exit button
    pygame.display.flip()  # Update the display

# Async function to receive a number from the server
async def receive_number(host, port):
    reader, writer = await asyncio.open_connection(host, port)
    data = await reader.read(100)
    writer.close()
    await writer.wait_closed()
    return int(data.decode())

# Main loop
async def main(host, port):
    running = True
    while running:
        number = await receive_number(host, port)  # Receive number from server
        draw_bar(screen, number)  # Draw the bar chart

        for event in pygame.event.get():  # Check for events
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                if button_position[0] <= mouse_pos[0] <= button_position[0] + button_width and button_position[1] <= mouse_pos[1] <= button_position[1] + button_height:
                    running = False

    pygame.quit()

# Replace 'SERVER_IP_ADDRESS' with the actual IP address of the server Raspberry Pi
server_ip = '10.243.67.147' # Example: '192.168.1.2'
port = 5560

# Run the main function until it is complete
asyncio.run(main(server_ip, port))
