import pytest
import yaml
from unittest.mock import MagicMock, patch

from agents.matlab.matlab_agent.src.comm.rabbitmq.message_handler import (
    MessageHandler, MessagePayload, SimulationData
)


class TestMessageHandler:
    """Test suite for the message handler."""

    @pytest.fixture
    def mock_rabbitmq_manager(self):
        """Create a mock for RabbitMQManager."""
        manager = MagicMock()
        manager.send_result = MagicMock()
        return manager

    @pytest.fixture
    def mock_channel(self):
        """Create a mock for the RabbitMQ channel."""
        channel = MagicMock()
        channel.basic_ack = MagicMock()
        channel.basic_nack = MagicMock()
        return channel

    @pytest.fixture
    def basic_deliver(self):
        """Mock for the Basic.Deliver method."""
        mock_deliver = MagicMock()
        mock_deliver.routing_key = "source.test_agent"
        mock_deliver.delivery_tag = 123
        return mock_deliver

    @pytest.fixture
    def complex_deliver(self):
        """Mock for Basic.Deliver with a complex routing key."""
        mock_deliver = MagicMock()
        mock_deliver.routing_key = "source.subtype.test_agent.additional"
        mock_deliver.routing_key = "source.test_agent"
        mock_deliver.delivery_tag = 123
        return mock_deliver

    @pytest.fixture
    def complex_deliver(self):
        """Mock per Basic.Deliver con routing key complessa."""
        mock_deliver = MagicMock()
        mock_deliver.routing_key = "source.subtype.test_agent.additional"
        mock_deliver.delivery_tag = 123
        return mock_deliver

    @pytest.fixture
    def basic_properties(self):
        """Mock per le proprietà del messaggio."""
        mock_properties = MagicMock()
        mock_properties.message_id = "test-message-id"
        return mock_properties

    @pytest.fixture
    def properties_no_message_id(self):
        """Mock per le proprietà senza message_id."""
        mock_properties = MagicMock()
        mock_properties.message_id = None
        return mock_properties

    @pytest.fixture
    def message_handler(self, mock_rabbitmq_manager):
        """Istanzia un MessageHandler con un RabbitMQManager in mock."""
        return MessageHandler(
            agent_id="test_agent",
            rabbitmq_manager=mock_rabbitmq_manager
        )

    @pytest.fixture
    def valid_batch_message(self):
        """Crea un messaggio batch valido."""
        return yaml.dump({
            'simulation': {
                'simulator': 'test_simulator',
                'type': 'batch',
                'file': 'test_file.mat',
                'inputs': {'param1': 10, 'param2': 'test'}
            },
            'destinations': ['dest1', 'dest2'],
            'request_id': 'test-request-id'
        })

    @pytest.fixture
    def valid_streaming_message(self):
        """Crea un messaggio streaming valido."""
        return yaml.dump({
            'simulation': {
                'simulator': 'test_simulator',
                'type': 'streaming',
                'file': 'test_file.mat',
                'inputs': {'param1': 10, 'param2': 'test'}
            },
            'destinations': ['dest1', 'dest2'],
            'request_id': 'test-request-id'
        })

    @pytest.fixture
    def invalid_yaml_message(self):
        """Crea un messaggio con YAML non valido."""
        return "this is not valid yaml: ["

    @pytest.fixture
    def invalid_structure_message(self):
        """Crea un messaggio con YAML valido ma struttura non valida."""
        return yaml.dump({
            'simulation': {
                # Campo 'simulator' richiesto mancante
                'type': 'batch',
                'file': 'test_file.mat',
                'inputs': {'param1': 10}
            },
            'destinations': ['dest1']
        })

    def test_handle_message_batch(
            self, message_handler, mock_channel, basic_deliver,
            basic_properties, valid_batch_message):
        """Testa gestione di un messaggio di tipo 'batch'."""
        # Patcha l'handler della simulazione batch
        with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
            message_handler.handle_message(
                ch=mock_channel,
                method=basic_deliver,
                properties=basic_properties,
                body=valid_batch_message.encode()
            )

            # Verifica che la funzione batch sia chiamata con argomenti
            # corretti
            mock_handle_batch.assert_called_once()
            args = mock_handle_batch.call_args[0]
            assert args[0] == yaml.safe_load(valid_batch_message)
            assert args[1] == "source"
            assert args[2] == message_handler.rabbitmq_manager

            # Verifica che l'acknowledgment sia inviato
            mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)

    def test_handle_message_streaming(
            self, message_handler, mock_channel, basic_deliver,
            basic_properties, valid_streaming_message):
        """Testa gestione di un messaggio di tipo 'streaming'."""
        # Patcha l'handler della simulazione streaming
        with patch("src.handlers.message_handler.handle_streaming_simulation") as mock_handle_streaming:
            message_handler.handle_message(
                ch=mock_channel,
                method=basic_deliver,
                properties=basic_properties,
                body=valid_streaming_message.encode()
            )

            # Verifica che la funzione streaming sia chiamata con argomenti
            # corretti
            mock_handle_streaming.assert_called_once()
            args = mock_handle_streaming.call_args[0]
            assert args[0] == yaml.safe_load(valid_streaming_message)
            assert args[1] == "source"
            assert args[2] == message_handler.rabbitmq_manager

            # Verifica che l'acknowledgment sia inviato prima della gestione
            # streaming
            mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)

    def test_handle_message_invalid_yaml(
            self, message_handler, mock_channel, basic_deliver,
            basic_properties, invalid_yaml_message):
        """Testa gestione di un messaggio con YAML non valido."""
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=invalid_yaml_message.encode()
        )

        # Verifica che l'acknowledgment negativo sia inviato
        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)

        # Verifica che la risposta di errore sia inviata
        message_handler.rabbitmq_manager.send_result.assert_called_once()
        error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
        assert error_response['status'] == 'error'
        assert 'YAML parsing error' in error_response['error']['message']

    def test_handle_message_invalid_structure(
            self, message_handler, mock_channel, basic_deliver,
            basic_properties, invalid_structure_message):
        """Testa gestione di un messaggio con YAML valido ma struttura non valida."""
        message_handler.handle_message(
            ch=mock_channel,
            method=basic_deliver,
            properties=basic_properties,
            body=invalid_structure_message.encode()
        )

        # Verifica che l'acknowledgment negativo sia inviato
        mock_channel.basic_nack.assert_called_once_with(
            delivery_tag=123, requeue=False)

        # Verifica che la risposta di errore sia inviata
        message_handler.rabbitmq_manager.send_result.assert_called_once()
        error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
        assert error_response['status'] == 'error'
        assert 'Message validation failed' in error_response['error']['message']

    def test_handle_message_invalid_simulation_type(
            self,
            message_handler,
            mock_channel,
            basic_deliver,
            basic_properties):
        """Testa gestione di un messaggio con un tipo di simulazione non valido."""
        # Dobbiamo bypassare la validazione Pydantic per testare questo
        # percorso
        body = yaml.dump({
            'simulation': {
                'simulator': 'test_simulator',
                'type': 'invalid_type',  # Tipo non valido
                'file': 'test_file.mat',
                'inputs': {'param1': 10}
            },
            'destinations': ['dest1'],
            'request_id': 'test-id'
        })

        # Patcha il validatore Pydantic per lasciare passare il tipo non valido
        with patch("src.handlers.message_handler.MessagePayload", autospec=True) as mock_payload:
            # Configura il mock per restituire un oggetto valido con tipo non
            # valido
            mock_instance = MagicMock()
            mock_instance.simulation.type = 'invalid_type'
            mock_instance.simulation.file = 'test_file.mat'
            mock_payload.return_value = mock_instance

            message_handler.handle_message(
                ch=mock_channel,
                method=basic_deliver,
                properties=basic_properties,
                body=body.encode()
            )

            # Verifica che l'acknowledgment negativo sia inviato
            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag=123, requeue=False)

            # Verifica che la risposta di errore sia inviata
            message_handler.rabbitmq_manager.send_result.assert_called_once()
            error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
            assert error_response['status'] == 'error'
            assert 'Unknown simulation type' in error_response['error']['message']

    def test_handle_message_batch_error(
            self, message_handler, mock_channel, basic_deliver,
            basic_properties, valid_batch_message):
        """Testa gestione quando l'handler della simulazione batch genera un'eccezione."""
        # Patcha l'handler della simulazione batch per generare un'eccezione
        with patch("src.handlers.message_handler.handle_batch_simulation",
                   side_effect=Exception("Batch processing error")):

            message_handler.handle_message(
                ch=mock_channel,
                method=basic_deliver,
                properties=basic_properties,
                body=valid_batch_message.encode()
            )

            # Verifica che l'acknowledgment negativo sia inviato
            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag=123, requeue=False)

            # Verifica che la risposta di errore sia inviata
            message_handler.rabbitmq_manager.send_result.assert_called_once()
            error_response = message_handler.rabbitmq_manager.send_result.call_args[0][1]
            assert error_response['status'] == 'error'
            assert 'Error processing message' in error_response['error']['message']
            assert 'Batch processing error' in error_response['error'].get(
                'details', '')

    def test_handle_message_error_response_failure(
            self, message_handler, mock_channel, basic_deliver,
            basic_properties, valid_batch_message):
        """Testa gestione quando sia l'elaborazione che l'invio della risposta di errore falliscono."""
        # Patcha handler batch per generare eccezione e rabbitmq_manager per
        # generare eccezione
        with patch("src.handlers.message_handler.handle_batch_simulation",
                   side_effect=Exception("Batch processing error")):

            # Fa fallire anche il metodo send_result
            message_handler.rabbitmq_manager.send_result.side_effect = Exception(
                "Send error")

            message_handler.handle_message(
                ch=mock_channel,
                method=basic_deliver,
                properties=basic_properties,
                body=valid_batch_message.encode()
            )

            # Verifica che l'acknowledgment negativo sia inviato
            mock_channel.basic_nack.assert_called_once_with(
                delivery_tag=123, requeue=False)

            # Verifica che si sia tentato di inviare una risposta di errore
            message_handler.rabbitmq_manager.send_result.assert_called_once()

    def test_pydantic_model_validation(self):
        """Testa la validazione del modello Pydantic."""
        # Dati validi
        valid_data = {
            'simulation': {
                'simulator': 'test_simulator',
                'type': 'batch',
                'file': 'test_file.mat',
                'inputs': {'param1': 10}
            },
            'destinations': ['dest1', 'dest2'],
            'request_id': 'test-id'
        }

        # Non dovrebbe generare un'eccezione
        payload = MessagePayload(**valid_data)
        assert payload.simulation.type == 'batch'
        assert payload.simulation.file == 'test_file.mat'
        assert payload.simulation.inputs.param1 == 10
        assert payload.destinations == ['dest1', 'dest2']
        assert payload.request_id == 'test-id'

        # Testa il validatore per il tipo di simulazione
        with pytest.raises(ValueError) as exc_info:
            SimulationData(
                simulator='test_simulator',
                type='invalid_type',  # Tipo non valido
                file='test_file.mat',
                inputs={'param1': 10}
            )
        assert "Invalid simulation type" in str(exc_info.value)

    def test_handle_message_with_no_message_id(
            self, message_handler, mock_channel, basic_deliver,
            properties_no_message_id, valid_batch_message):
        """Testa gestione di un messaggio senza message_id."""
        with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
            message_handler.handle_message(
                ch=mock_channel,
                method=basic_deliver,
                properties=properties_no_message_id,
                body=valid_batch_message.encode()
            )

            # L'elaborazione dovrebbe funzionare comunque
            mock_handle_batch.assert_called_once()

            # Verifica che l'acknowledgment sia inviato
            mock_channel.basic_ack.assert_called_once_with(delivery_tag=123)

    def test_message_handler_initialization(self, mock_rabbitmq_manager):
        """Testa che MessageHandler si inizializzi correttamente."""
        handler = MessageHandler(
            agent_id="test_agent",
            rabbitmq_manager=mock_rabbitmq_manager
        )

        assert handler.agent_id == "test_agent"
        assert handler.rabbitmq_manager == mock_rabbitmq_manager

    def test_handle_message_with_complex_routing_key(
            self, message_handler, mock_channel, complex_deliver,
            basic_properties, valid_batch_message):
        """Testa gestione di un messaggio con una routing key complessa."""
        with patch("src.handlers.message_handler.handle_batch_simulation") as mock_handle_batch:
            message_handler.handle_message(
                ch=mock_channel,
                method=complex_deliver,
                properties=basic_properties,
                body=valid_batch_message.encode()
            )

            # L'elaborazione dovrebbe ancora estrarre la fonte corretta
            mock_handle_batch.assert_called_once()
            assert mock_handle_batch.call_args[0][1] == "source"
