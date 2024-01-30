import asyncio
from random import randint

async def handle_client(reader, writer):
    # Send a number between 0 and 10 to the client
    number_to_send = str(randint(0, 10))
    writer.write(number_to_send.encode())
    await writer.drain()
    print("Sent: ", number_to_send)

    # Close the connection
    writer.close()
    await writer.wait_closed()

async def run_server(host, port):
    server = await asyncio.start_server(handle_client, host, port)

    addr = server.sockets[0].getsockname()
    print('Serving on ', addr)

    async with server:
        await server.serve_forever()

# Replace 'SERVER_IP' with '0.0.0.0' to bind to all available interfaces or use the specific IP address of the server Raspberry Pi
server_ip = ''
port = 5560

# Run the server
asyncio.run(run_server(server_ip, port)) 