import asyncio
import socket

async def receive_number_coroutine(reader):
    data = await reader.read(100)
    message = data.decode()
    addr = reader._transport.get_extra_info('peername')
    print(f"Received {message} from {addr}")
    return message

async def main(host, port):
    # Connect to the server
    reader, writer = await asyncio.open_connection(host, port)

    try:
        # Receive number asynchronously
        number = await receive_number_coroutine(reader)

        # Check if the data received is a number within the range
        try:
            number = int(number)
            if 0 <= number <= 10:
                print("Received number within range: ", number)
            else:
                print("The number is not in the range 0-10.")
        except ValueError:
            print("Received data is not a valid number.")

    except Exception as e:
        print("An error occurred: ", e)
    
    finally:
        # Close the connection
        writer.close()
        await writer.wait_closed()

# Replace 'SERVER_IP_ADDRESS' with the actual IP address of the server Raspberry Pi
server_ip = '10.243.67.147' # Example: '192.168.1.2'
port = 5560

# Run the main function until it is complete
asyncio.run(main(server_ip, port))