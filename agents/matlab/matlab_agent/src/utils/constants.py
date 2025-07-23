"""Common constants used across the MATLAB agent."""

# Timeouts
ACCEPT_TIMEOUT = 60  # seconds to wait for TCP connection

# Network buffer size
BUFFER_SIZE = 4096

# Default TCP ports
DEFAULT_OUTPUT_PORT = 5678
DEFAULT_INPUT_PORT = 5679

# Memory usage divisor for converting bytes to MB
BYTES_IN_MB = 1024 * 1024

# Maximum filename length
MAX_FILENAME_LENGTH = 120

# Exchange stream names for streaming input (MODE INTERACTIVE)
EXCHANGE_INPUT_STREAM = "ex.input.stream"