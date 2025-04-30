import asyncio
from simulation_bridge.protocol_adapters.rabbitmq_adapter import RabbitMQAdapter

async def test_rabbitmq_adapter():
    # Configura il RabbitMQAdapter con la configurazione di base
    config = {
        'host': 'localhost',
        'port': 5672,
        'exchange': 'simulation_exchange',
        'exchange_type': 'topic',
        'routing_key': 'simulation.events'
    }

    # Crea un'istanza dell'adattatore
    rabbitmq_adapter = RabbitMQAdapter(config)

    # Connetti al RabbitMQ
    await rabbitmq_adapter.connect()

    # Crea un messaggio di test
    test_message = {"event": "test_event", "value": "Hello RabbitMQ!"}

    # Invia il messaggio all'exchange
    await rabbitmq_adapter.send(test_message)

    # Aspetta la ricezione del messaggio dalla coda
    print("Waiting for the message...")
    message = await rabbitmq_adapter.receive()
    if message:
        print(f"Received message: {message}")
    else:
        print("No message received")

    # Chiudi la connessione
    rabbitmq_adapter.close()

# Esegui il test asincrono
if __name__ == "__main__":
    asyncio.run(test_rabbitmq_adapter())
