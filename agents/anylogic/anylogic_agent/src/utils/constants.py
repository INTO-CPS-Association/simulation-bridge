"""Common constants used across the ANYLOGIC Agent."""

# Timeouts
ACCEPT_TIMEOUT = 60  # seconds to wait for TCP connection

# Network buffer size
BUFFER_SIZE = 4096

# Default UDP Host and Port
UDP_HOST = "localhost"
UDP_PORT = 9876

# TO be deleted TCP old communication
DEFAULT_OUTPUT_PORT = 9878
DEFAULT_INPUT_PORT = 9877

# Default Output Host
DEFAULT_OUTPUT_HOST = "localhost"

# Memory usage divisor for converting bytes to MB
BYTES_IN_MB = 1024 * 1024

# Maximum filename length
MAX_FILENAME_LENGTH = 120

# Exchange stream names for streaming input (MODE INTERACTIVE)
EXCHANGE_INPUT_STREAM = "ex.input.stream"
